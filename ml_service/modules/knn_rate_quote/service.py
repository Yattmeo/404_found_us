"""
KNN Rate Quote Service — PostgreSQL-backed version.

Adapted from KNN Demo Service / knn_rate_quote_service.py.
All KNN logic is identical; SQLite I/O replaced with SQLAlchemy engine queries.

── HOW IT WORKS ──────────────────────────────────────────────────────────────
1. On first request the service reads transactions + cost_type_ref from
   PostgreSQL tables knn_transactions and knn_cost_type_ref (populated once by
   migrate_sqlite_to_postgres.py).
2. Monthly feature vectors (pct_ct_* + total_transactions + avg_amount) are
   built from the raw rows.
3. A sliding-window pool of (context → target) pairs is built per calendar month.
4. At inference time the query merchant's features are computed, then the k
   nearest historical neighbours are found with sklearn NearestNeighbors
   (Euclidean distance).  The mean of the neighbours' target proc_cost values
   for horizon months t+1…t+H is returned as the forecast.

── WHERE TO EDIT ─────────────────────────────────────────────────────────────
• k, context_len, horizon_len — __init__ defaults
• card_type filtering         — _build_monthly_features
• feature columns             — feature_cols derived from pct_ct_* columns
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sqlalchemy.engine import Engine

from .schemas import KNNRateQuoteResult


class KNNRateQuoteService:
    def __init__(
        self,
        engine: Engine,
        k: int = 50,
        context_len: int = 1,
        horizon_len: int = 3,
        year_min: int = 2017,
        year_max: int = 2019,
    ) -> None:
        self.engine = engine
        self.k = k
        self.context_len = context_len
        self.horizon_len = horizon_len
        self.year_min = year_min
        self.year_max = year_max

        self.cost_type_ids = self._load_cost_type_ids()
        self.all_monthly = self._load_monthly_reference()
        self.feature_cols = [
            c for c in self.all_monthly.columns if c.startswith("pct_ct_")
        ] + ["total_transactions", "avg_amount"]
        self.pool_cache: Dict[Tuple[int, str], pd.DataFrame] = {}
        self.pool_means_cache: Dict[Tuple[int, str], pd.Series] = {}

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_cost_type_ids(self) -> List[str]:
        cost_type_ref = pd.read_sql(
            "SELECT cost_type_id FROM knn_cost_type_ref", self.engine
        )
        return (
            cost_type_ref["cost_type_id"].dropna().astype(int).astype(str).tolist()
        )

    def _load_monthly_reference(self) -> pd.DataFrame:
        all_df = pd.read_sql("SELECT * FROM knn_transactions", self.engine)
        # Normalise column name used everywhere in the algo
        if "cost_type_id" in all_df.columns and "cost_type_ID" not in all_df.columns:
            all_df = all_df.rename(columns={"cost_type_id": "cost_type_ID"})
        monthly = self._build_monthly_features(all_df, card_type=None)
        monthly = monthly[monthly["year"].between(self.year_min, self.year_max)].copy()
        return monthly

    # ── Feature engineering ──────────────────────────────────────────────────

    def _build_monthly_features(
        self, df: pd.DataFrame, card_type: Optional[str] = None
    ) -> pd.DataFrame:
        df = df.copy()

        if card_type and card_type.lower() != "both":
            card_type_normalized = card_type.lower()
            if "card_type" in df.columns:
                df = df[df["card_type"].astype(str).str.lower() == card_type_normalized]
                if df.empty:
                    raise ValueError(f"No transactions found for card_type: {card_type}")

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["proc_cost"] = pd.to_numeric(df["proc_cost"], errors="coerce")
        df["year"] = df["date"].dt.year
        df["month_num"] = df["date"].dt.month
        df["ym"] = df["date"].dt.to_period("M").astype(str)
        df["cost_type_ID"] = df["cost_type_ID"].fillna(-1).astype(int).astype(str)

        counts = (
            df.groupby(["merchant_id", "year", "month_num", "ym", "cost_type_ID"])
            .size()
            .rename("count")
            .reset_index()
        )
        cost_counts = counts.pivot_table(
            index=["merchant_id", "year", "month_num", "ym"],
            columns="cost_type_ID",
            values="count",
            fill_value=0,
        )
        cost_counts = cost_counts.reindex(columns=self.cost_type_ids, fill_value=0)
        total_transactions = cost_counts.sum(axis=1).rename("total_transactions")
        cost_pct = cost_counts.div(total_transactions, axis=0).fillna(0)
        cost_pct.columns = [f"pct_ct_{c}" for c in cost_pct.columns]
        avg_amount = (
            df.groupby(["merchant_id", "year", "month_num", "ym"])["amount"]
            .mean()
            .rename("avg_amount")
        )
        target_proc_cost = (
            df.groupby(["merchant_id", "year", "month_num", "ym"])["proc_cost"]
            .mean()
            .rename("target_proc_cost")
        )
        features = pd.concat(
            [cost_pct, total_transactions, avg_amount, target_proc_cost], axis=1
        ).reset_index()
        features["ym_period"] = pd.PeriodIndex(features["ym"], freq="M")
        features = features.sort_values(["merchant_id", "year", "ym_period"])
        features["month_index"] = (
            features.groupby(["merchant_id", "year"]).cumcount() + 1
        )
        return features

    # ── Pool building ─────────────────────────────────────────────────────────

    def _build_pool_by_month(
        self, monthly_data: pd.DataFrame, card_type: str = "both"
    ) -> Tuple[Dict[int, pd.DataFrame], Dict[int, pd.Series]]:
        pool_by_month: Dict[int, list] = {}
        pool_means_by_month: Dict[int, pd.Series] = {}

        all_periods = sorted(monthly_data["ym_period"].unique())
        if not all_periods:
            return {}, {}

        min_period = all_periods[0]
        max_period = all_periods[-1]

        for end_period in all_periods:
            start_context = end_period - (self.context_len - 1)
            end_target = end_period + self.horizon_len
            if start_context < min_period or end_target > max_period:
                continue

            context_periods = pd.period_range(start_context, end_period, freq="M")
            target_periods = pd.period_range(
                end_period + 1, end_period + self.horizon_len, freq="M"
            )

            ctx_df = monthly_data[monthly_data["ym_period"].isin(context_periods)]
            target_df = monthly_data[monthly_data["ym_period"].isin(target_periods)]
            ctx_agg = ctx_df.groupby("merchant_id")[self.feature_cols].mean()
            targets = (
                target_df.pivot_table(
                    index="merchant_id",
                    columns="ym_period",
                    values="target_proc_cost",
                )
                .reindex(columns=target_periods)
                .copy()
            )

            if ctx_agg.empty or targets.empty:
                continue

            targets.columns = [f"t{i}" for i in range(1, self.horizon_len + 1)]
            merchant_cases = ctx_agg.join(targets, how="inner").dropna()
            if merchant_cases.empty:
                continue

            merchant_cases["end_period"] = end_period
            merchant_cases["end_month"] = end_period.month
            pool_by_month.setdefault(end_period.month, []).append(merchant_cases)

        combined = {}
        for month_num, frames in pool_by_month.items():
            combined[month_num] = pd.concat(frames, axis=0, ignore_index=True)
            pool_means_by_month[month_num] = combined[month_num][self.feature_cols].mean()
        return combined, pool_means_by_month

    def _get_pool(self, month_num: int, card_type: str = "both") -> Optional[pd.DataFrame]:
        cache_key = (month_num, card_type)
        if cache_key in self.pool_cache:
            return self.pool_cache[cache_key]

        if card_type.lower() != "both" and "card_type" in self.all_monthly.columns:
            filtered = self.all_monthly[
                self.all_monthly["card_type"].astype(str).str.lower() == card_type.lower()
            ]
        else:
            filtered = self.all_monthly

        if filtered.empty:
            return None

        pools, _ = self._build_pool_by_month(filtered, card_type)
        pool = pools.get(month_num)
        if pool is not None:
            self.pool_cache[cache_key] = pool
        return pool

    def _get_pool_means(
        self, month_num: int, card_type: str = "both"
    ) -> Optional[pd.Series]:
        cache_key = (month_num, card_type)
        if cache_key in self.pool_means_cache:
            return self.pool_means_cache[cache_key]

        if card_type.lower() != "both" and "card_type" in self.all_monthly.columns:
            filtered = self.all_monthly[
                self.all_monthly["card_type"].astype(str).str.lower() == card_type.lower()
            ]
        else:
            filtered = self.all_monthly

        if filtered.empty:
            return None

        _, pool_means = self._build_pool_by_month(filtered, card_type)
        means = pool_means.get(month_num)
        if means is not None:
            self.pool_means_cache[cache_key] = means
        return means

    # ── Query feature computation ─────────────────────────────────────────────

    def _compute_query_features(
        self,
        df: Optional[pd.DataFrame],
        monthly_txn_count: Optional[int],
        avg_amount: Optional[float],
        as_of_date: Optional[pd.Timestamp],
        card_type: Optional[str] = None,
    ) -> Tuple[np.ndarray, int]:
        if df is None:
            if as_of_date is None:
                raise ValueError("as_of_date is required when df is not provided.")
            if monthly_txn_count is None or avg_amount is None:
                raise ValueError(
                    "monthly_txn_count and avg_amount are required when df is not provided."
                )

            as_of_period = pd.to_datetime(as_of_date).to_period("M")
            max_period = self.all_monthly["ym_period"].max()

            if as_of_period > max_period:
                most_recent_year = max_period.year
                end_period = pd.Period(f"{most_recent_year}-{as_of_period.month:02d}", freq="M")
            else:
                end_period = as_of_period

            pool_means = self._get_pool_means(end_period.month, card_type or "both")
            if pool_means is None:
                raise ValueError("No reference pool available for the requested month.")

            cost_pct = pool_means[[c for c in self.feature_cols if c.startswith("pct_ct_")]]
            cost_pct = cost_pct / max(cost_pct.sum(), 1e-12)
            cost_pct = cost_pct.to_frame().T
            cost_pct.columns = [f"pct_ct_{c.split('pct_ct_')[-1]}" for c in cost_pct.columns]

            feature_row = pd.concat(
                [
                    cost_pct,
                    pd.DataFrame(
                        {"total_transactions": [monthly_txn_count], "avg_amount": [avg_amount]}
                    ),
                ],
                axis=1,
            )
            feature_row = feature_row[self.feature_cols]
            return feature_row.values.astype(float), end_period.month

        required_cols = {"transaction_date", "amount", "cost_type_ID"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing required columns for cost_type features: {sorted(missing)}"
            )

        df = df.copy()
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        df = df.dropna(subset=["transaction_date"])

        if df.empty:
            raise ValueError("Input df has no valid transaction_date values.")

        if as_of_date is None:
            end_period = df["transaction_date"].max().to_period("M")
        else:
            as_of_period = pd.to_datetime(as_of_date).to_period("M")
            max_date = df["transaction_date"].max()
            max_period = max_date.to_period("M")
            if as_of_period > max_period:
                most_recent_year = max_date.year
                end_period = pd.Period(f"{most_recent_year}-{as_of_period.month:02d}", freq="M")
            else:
                end_period = as_of_period

        df_month = df[df["transaction_date"].dt.to_period("M") == end_period]
        if df_month.empty:
            raise ValueError("No transactions found for the selected month.")

        df_month["cost_type_ID"] = (
            df_month["cost_type_ID"].fillna(-1).astype(int).astype(str)
        )
        counts = (
            df_month.groupby(["cost_type_ID"]).size().rename("count").reset_index()
        )
        cost_counts = counts.pivot_table(
            index=[],
            columns="cost_type_ID",
            values="count",
            fill_value=0,
        )
        cost_counts = cost_counts.reindex(columns=self.cost_type_ids, fill_value=0)

        total_txns = monthly_txn_count
        if total_txns is None:
            total_txns = int(cost_counts.sum(axis=1).iloc[0])

        avg_amt = avg_amount
        if avg_amt is None:
            avg_amt = float(pd.to_numeric(df_month["amount"], errors="coerce").mean())
        if pd.isna(avg_amt):
            pool_means = self._get_pool_means(end_period.month, card_type or "both")
            if pool_means is not None and "avg_amount" in pool_means:
                avg_amt = float(pool_means["avg_amount"])
            else:
                avg_amt = 0.0

        cost_pct = cost_counts.div(total_txns, axis=0).fillna(0)
        cost_pct.columns = [f"pct_ct_{c}" for c in cost_pct.columns]
        feature_row = pd.concat(
            [
                cost_pct,
                pd.DataFrame({"total_transactions": [total_txns], "avg_amount": [avg_amt]}),
            ],
            axis=1,
        )
        feature_row = feature_row[self.feature_cols].fillna(0.0)
        return feature_row.values.astype(float), end_period.month

    # ── Public inference method ───────────────────────────────────────────────

    def quote(
        self,
        df: Optional[pd.DataFrame],
        mcc: int,
        card_type: Optional[str] = None,
        monthly_txn_count: Optional[int] = None,
        avg_amount: Optional[float] = None,
        as_of_date: Optional[pd.Timestamp] = None,
    ) -> KNNRateQuoteResult:
        query_vec, end_month = self._compute_query_features(
            df,
            monthly_txn_count,
            avg_amount,
            as_of_date,
            card_type=card_type,
        )

        pool = self._get_pool(end_month, card_type or "both")
        if pool is None or pool.empty:
            raise ValueError("No reference pool available for the requested month.")

        X_pool = pool[self.feature_cols].values
        knn = NearestNeighbors(
            n_neighbors=min(self.k, len(pool)), metric="euclidean"
        )
        knn.fit(X_pool)
        _, neighbor_idx = knn.kneighbors(query_vec)

        neighbors = pool.iloc[neighbor_idx[0]]
        target_cols = [f"t{i}" for i in range(1, self.horizon_len + 1)]
        forecast = neighbors[target_cols].mean(axis=0).values.tolist()

        return KNNRateQuoteResult(
            forecast_proc_cost=forecast,
            context_len=self.context_len,
            horizon_len=self.horizon_len,
            k=self.k,
            end_month=end_month,
        )
