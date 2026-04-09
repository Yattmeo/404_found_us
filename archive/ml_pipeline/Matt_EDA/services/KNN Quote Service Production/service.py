from __future__ import annotations

from typing import List

import pandas as pd
from sklearn.neighbors import NearestNeighbors

from feature_engineering import (
    build_monthly_features,
    build_pool_by_month,
    lookup_horizon_proc_cost_pct,
    query_vector_from_pool_means,
    query_vector_from_txn_df,
)
from models import NeighborForecast, QuoteComputationResult, QuoteRequest
from models import (
    CompositeMerchantComputationResult,
    CompositeMerchantRequest,
    CompositeWeeklyFeature,
)
from processing_costs import ProcessingCostProvider
from repository import SQLiteMerchantRepository


class ProductionQuoteService:
    def __init__(
        self,
        repository: SQLiteMerchantRepository,
        processing_cost_provider: ProcessingCostProvider,
        k: int = 5,
        context_len_months: int = 1,
        horizon_len_months: int = 3,
    ) -> None:
        self.repository = repository
        self.processing_cost_provider = processing_cost_provider
        self.k = k
        self.context_len_months = context_len_months
        self.horizon_len_months = horizon_len_months

    @property
    def context_len_wk(self) -> int:
        return self.context_len_months * 4

    @property
    def horizon_len_wk(self) -> int:
        return self.horizon_len_months * 4

    def _resolve_end_period(self, req: QuoteRequest, onboarding_df: pd.DataFrame | None) -> pd.Period:
        if req.as_of_date is not None:
            return pd.to_datetime(req.as_of_date).to_period("M")

        if onboarding_df is not None and not onboarding_df.empty:
            if "transaction_date" in onboarding_df.columns:
                dt = pd.to_datetime(onboarding_df["transaction_date"], errors="coerce")
            else:
                dt = pd.to_datetime(onboarding_df.get("date"), errors="coerce")
            dt = dt.dropna()
            if not dt.empty:
                return dt.max().to_period("M")

        raise ValueError("as_of_date is required when onboarding_merchant_txn_df is not provided.")

    def _filter_reference_by_card_types(
        self,
        reference_txn: pd.DataFrame,
        card_types: list[str],
    ) -> pd.DataFrame:
        normalized = [c.strip().lower() for c in card_types if c.strip() and c.lower() != "both"]
        if not normalized:
            return reference_txn

        brand = reference_txn.get("card_brand", pd.Series(dtype=str)).astype(str).str.lower()
        ctype = reference_txn.get("card_type", pd.Series(dtype=str)).astype(str).str.lower()
        mask = brand.isin(normalized) | ctype.isin(normalized)
        return reference_txn[mask].copy()

    def _build_window_pool(
        self,
        monthly_ref: pd.DataFrame,
        feature_cols: List[str],
        start_period: pd.Period,
        end_period: pd.Period,
    ) -> pd.DataFrame:
        periods = pd.period_range(start_period, end_period, freq="M")
        ctx = monthly_ref[monthly_ref["ym_period"].isin(periods)].copy()
        if ctx.empty:
            return pd.DataFrame()

        # Keep merchants with full coverage of all months in the onboarding window.
        eligible_merchants = (
            ctx.groupby("merchant_id")["ym_period"]
            .nunique()
            .loc[lambda s: s == len(periods)]
            .index
        )
        if len(eligible_merchants) == 0:
            return pd.DataFrame()

        pool = (
            ctx[ctx["merchant_id"].isin(eligible_merchants)]
            .groupby("merchant_id")[feature_cols]
            .mean()
            .reset_index()
        )
        return pool

    def _build_window_query_vector(
        self,
        onboarding_df: pd.DataFrame,
        cost_type_ids: List[str],
        feature_cols: List[str],
        start_period: pd.Period,
        end_period: pd.Period,
    ) -> pd.DataFrame:
        tx = onboarding_df.copy()
        if "transaction_date" in tx.columns and "date" not in tx.columns:
            tx = tx.rename(columns={"transaction_date": "date"})

        tx["date"] = pd.to_datetime(tx["date"], errors="coerce")
        tx = tx.dropna(subset=["date"])
        if tx.empty:
            raise ValueError("onboarding_merchant_txn_df has no valid dates.")

        tx["ym_period"] = tx["date"].dt.to_period("M")
        periods = pd.period_range(start_period, end_period, freq="M")
        tx = tx[tx["ym_period"].isin(periods)].copy()
        if tx.empty:
            raise ValueError("No onboarding transactions in matching window.")

        tx["amount"] = pd.to_numeric(tx.get("amount"), errors="coerce")
        tx["cost_type_ID"] = tx.get("cost_type_ID").fillna(-1).astype(int).astype(str)

        counts = (
            tx.groupby(["ym_period", "cost_type_ID"])  # type: ignore[arg-type]
            .size()
            .rename("count")
            .reset_index()
        )

        cost_counts = counts.pivot_table(
            index=["ym_period"],
            columns="cost_type_ID",
            values="count",
            fill_value=0,
        )
        cost_counts = cost_counts.reindex(columns=cost_type_ids, fill_value=0)
        monthly_total = cost_counts.sum(axis=1).rename("total_transactions")
        monthly_pct = cost_counts.div(monthly_total, axis=0).fillna(0.0)
        monthly_pct.columns = [f"pct_ct_{c}" for c in monthly_pct.columns]

        monthly_avg_amount = tx.groupby("ym_period")["amount"].mean().rename("avg_amount")
        monthly_features = pd.concat(
            [monthly_pct, monthly_total, monthly_avg_amount], axis=1
        )

        query_row = monthly_features.mean(axis=0).to_frame().T
        query_row = query_row.reindex(columns=feature_cols, fill_value=0.0).fillna(0.0)
        return query_row.astype(float)

    def _build_composite_weekly_features(
        self,
        reference_txn: pd.DataFrame,
        merchant_ids: List[int],
        cost_type_ids: List[str],
    ) -> pd.DataFrame:
        tx = reference_txn[reference_txn["merchant_id"].isin(merchant_ids)].copy()
        if tx.empty:
            return pd.DataFrame()

        tx["date"] = pd.to_datetime(tx["date"], errors="coerce")
        tx = tx.dropna(subset=["date"])
        tx["amount"] = pd.to_numeric(tx.get("amount"), errors="coerce")
        tx["proc_cost"] = pd.to_numeric(tx.get("proc_cost"), errors="coerce")
        tx = tx.dropna(subset=["amount"])
        if tx.empty:
            return pd.DataFrame()

        # Force a strict 52-week year for downstream modeling compatibility.
        tx["calendar_year"] = tx["date"].dt.year
        tx["week_of_year"] = (((tx["date"].dt.dayofyear - 1) // 7) + 1).clip(upper=52).astype(int)

        weekly_cost_counts = (
            tx.groupby(["merchant_id", "calendar_year", "week_of_year", "cost_type_ID"])
            .size()
            .rename("count")
            .reset_index()
        )
        weekly_cost_counts = weekly_cost_counts.pivot_table(
            index=["merchant_id", "calendar_year", "week_of_year"],
            columns="cost_type_ID",
            values="count",
            fill_value=0,
        )
        weekly_cost_counts = weekly_cost_counts.reindex(columns=cost_type_ids, fill_value=0)
        weekly_total_txn = weekly_cost_counts.sum(axis=1)
        weekly_pct = weekly_cost_counts.div(weekly_total_txn, axis=0).fillna(0.0)
        weekly_pct.columns = [f"pct_ct_{c}" for c in weekly_pct.columns]

        per_merchant_week = (
            tx.groupby(["merchant_id", "calendar_year", "week_of_year"])
            .agg(
                weekly_txn_count=("transaction_id", "count"),
                weekly_total_proc_value=("amount", "sum"),
                weekly_avg_txn_value=("amount", "mean"),
                sum_proc_cost=("proc_cost", "sum"),
                sum_amount=("amount", "sum"),
            )
            .reset_index()
        )
        per_merchant_week = per_merchant_week.join(
            weekly_pct,
            on=["merchant_id", "calendar_year", "week_of_year"],
        )
        per_merchant_week["weekly_avg_txn_cost_pct"] = (
            per_merchant_week["sum_proc_cost"] / per_merchant_week["sum_amount"]
        ).replace([float("inf"), float("-inf")], 0.0).fillna(0.0)

        pct_cols = [f"pct_ct_{c}" for c in cost_type_ids]
        agg_map = {
            "weekly_txn_count": ["mean", "std"],
            "weekly_total_proc_value": ["mean", "std"],
            "weekly_avg_txn_value": ["mean", "std"],
            "weekly_avg_txn_cost_pct": ["mean", "std"],
            "merchant_id": pd.Series.nunique,
        }
        for col in pct_cols:
            agg_map[col] = "mean"

        composite = (
            per_merchant_week.groupby(["calendar_year", "week_of_year"])
            .agg(agg_map)
        )
        composite.columns = [
            "_".join(str(part) for part in col if part).rstrip("_")
            if isinstance(col, tuple)
            else str(col)
            for col in composite.columns.to_flat_index()
        ]
        composite = composite.rename(
            columns={
                "weekly_txn_count_mean": "weekly_txn_count_mean",
                "weekly_txn_count_std": "weekly_txn_count_stdev",
                "weekly_total_proc_value_mean": "weekly_total_proc_value_mean",
                "weekly_total_proc_value_std": "weekly_total_proc_value_stdev",
                "weekly_avg_txn_value_mean": "weekly_avg_txn_value_mean",
                "weekly_avg_txn_value_std": "weekly_avg_txn_value_stdev",
                "weekly_avg_txn_cost_pct_mean": "weekly_avg_txn_cost_pct_mean",
                "weekly_avg_txn_cost_pct_std": "weekly_avg_txn_cost_pct_stdev",
                "merchant_id_nunique": "neighbor_coverage",
            }
        )
        composite = composite.rename(
            columns={f"{col}_mean": col for col in pct_cols if f"{col}_mean" in composite.columns}
        )
        min_year = int(tx["calendar_year"].min())
        max_year = int(tx["calendar_year"].max())
        full_index = pd.MultiIndex.from_product(
            [range(min_year, max_year + 1), range(1, 53)],
            names=["calendar_year", "week_of_year"],
        )
        composite = composite.reindex(full_index).reset_index()
        composite[
            [
                "weekly_txn_count_mean",
                "weekly_txn_count_stdev",
                "weekly_total_proc_value_mean",
                "weekly_total_proc_value_stdev",
                "weekly_avg_txn_value_mean",
                "weekly_avg_txn_value_stdev",
                "weekly_avg_txn_cost_pct_mean",
                "weekly_avg_txn_cost_pct_stdev",
            ]
        ] = composite[
            [
                "weekly_txn_count_mean",
                "weekly_txn_count_stdev",
                "weekly_total_proc_value_mean",
                "weekly_total_proc_value_stdev",
                "weekly_avg_txn_value_mean",
                "weekly_avg_txn_value_stdev",
                "weekly_avg_txn_cost_pct_mean",
                "weekly_avg_txn_cost_pct_stdev",
            ]
        ].fillna(0.0)
        composite[pct_cols] = composite[pct_cols].fillna(0.0)
        composite["neighbor_coverage"] = composite["neighbor_coverage"].fillna(0).astype(int)
        composite = composite.sort_values(["calendar_year", "week_of_year"])
        return composite

    def get_quote(self, req: QuoteRequest) -> QuoteComputationResult:
        reference_txn = self.repository.load_transactions(req.mcc, req.card_types)
        reference_txn = self._filter_reference_by_card_types(reference_txn, req.card_types)
        if reference_txn.empty:
            raise ValueError("No reference transactions available for requested mcc/card_types.")

        cost_type_ids = self.repository.load_cost_type_ids()

        monthly_ref = build_monthly_features(reference_txn, cost_type_ids)
        if monthly_ref.empty:
            raise ValueError("Reference monthly feature table is empty.")

        feature_cols = [c for c in monthly_ref.columns if c.startswith("pct_ct_")] + [
            "total_transactions",
            "avg_amount",
        ]
        no_df_feature_cols = ["total_transactions", "avg_amount"]
        pool_by_month = build_pool_by_month(
            monthly_ref,
            feature_cols,
            self.context_len_months,
            self.horizon_len_months,
        )

        onboarding_df = None
        if req.onboarding_merchant_txn_df is not None:
            onboarding_df = pd.DataFrame(req.onboarding_merchant_txn_df)
            if onboarding_df.empty:
                onboarding_df = None

        end_period = self._resolve_end_period(req, onboarding_df)
        pool = pool_by_month.get(end_period.month)
        if pool is None or pool.empty:
            raise ValueError("No reference pool available for selected end month.")

        if onboarding_df is not None:
            if "proc_cost" not in onboarding_df.columns or onboarding_df["proc_cost"].isna().any():
                onboarding_df = self.processing_cost_provider.enrich(onboarding_df)

            query_vec = query_vector_from_txn_df(
                onboarding_df=onboarding_df,
                cost_type_ids=cost_type_ids,
                feature_cols=feature_cols,
                end_period=end_period,
                avg_monthly_txn_count=req.avg_monthly_txn_count,
                avg_monthly_txn_value=req.avg_monthly_txn_value,
            )
            knn_feature_cols = feature_cols
        else:
            if req.avg_monthly_txn_count is None or req.avg_monthly_txn_value is None:
                raise ValueError(
                    "avg_monthly_txn_count and avg_monthly_txn_value are required when onboarding_merchant_txn_df is missing."
                )
            query_vec = query_vector_from_pool_means(
                feature_cols=no_df_feature_cols,
                pool=pool,
                avg_monthly_txn_count=req.avg_monthly_txn_count,
                avg_monthly_txn_value=req.avg_monthly_txn_value,
            )
            knn_feature_cols = no_df_feature_cols

        effective_k = min(self.k, len(pool))
        X_pool = pool[knn_feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        X_query = query_vec.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        model = NearestNeighbors(n_neighbors=effective_k, metric="euclidean")
        model.fit(X_pool.values)
        _, idx = model.kneighbors(X_query.values)

        neighbors = pool.iloc[idx[0]]
        horizon_forecasts = lookup_horizon_proc_cost_pct(
            monthly_ref, neighbors, self.horizon_len_months
        )

        neighbor_forecasts: List[NeighborForecast] = []
        for (_, row), forecast in zip(neighbors.iterrows(), horizon_forecasts):
            neighbor_forecasts.append(
                NeighborForecast(
                    merchant_id=int(row["merchant_id"]),
                    forecast_proc_cost_pct_3m=forecast,
                )
            )

        return QuoteComputationResult(
            neighbor_forecasts=neighbor_forecasts,
            context_len_wk=self.context_len_wk,
            horizon_len_wk=self.horizon_len_wk,
            k=effective_k,
            end_month=str(end_period),
        )

    def get_composite_merchant(
        self,
        req: CompositeMerchantRequest,
    ) -> CompositeMerchantComputationResult:
        onboarding_df = pd.DataFrame(req.onboarding_merchant_txn_df)
        if onboarding_df.empty:
            raise ValueError("onboarding_merchant_txn_df cannot be empty.")

        if "transaction_date" in onboarding_df.columns and "date" not in onboarding_df.columns:
            onboarding_df = onboarding_df.rename(columns={"transaction_date": "date"})
        onboarding_df["date"] = pd.to_datetime(onboarding_df.get("date"), errors="coerce")
        onboarding_df = onboarding_df.dropna(subset=["date"])
        if onboarding_df.empty:
            raise ValueError("onboarding_merchant_txn_df has no valid dates.")

        start_period = onboarding_df["date"].min().to_period("M")
        end_period = onboarding_df["date"].max().to_period("M")

        reference_txn = self.repository.load_transactions(req.mcc, req.card_types)
        reference_txn = self._filter_reference_by_card_types(reference_txn, req.card_types)
        if reference_txn.empty:
            raise ValueError("No reference transactions available for requested mcc/card_types.")

        cost_type_ids = self.repository.load_cost_type_ids()
        monthly_ref = build_monthly_features(reference_txn, cost_type_ids)
        if monthly_ref.empty:
            raise ValueError("Reference monthly feature table is empty.")

        feature_cols = [c for c in monthly_ref.columns if c.startswith("pct_ct_")] + [
            "total_transactions",
            "avg_amount",
        ]

        # Fallback to most recent year that has the requested month.
        # E.g., if requesting Nov 2026 but only Jan-Sep 2019 exists, fall back to Nov 2018.
        if not monthly_ref.empty and "ym_period" in monthly_ref.columns:
            min_available_period = monthly_ref["ym_period"].min()
            max_available_period = monthly_ref["ym_period"].max()
            
            # Helper: find most recent period matching a target month
            def find_most_recent_with_month(target_period):
                target_month = target_period.month
                matching = monthly_ref[monthly_ref["ym_period"].dt.month == target_month]["ym_period"]
                return matching.max() if not matching.empty else None
            
            # Fallback end_period: try to keep the requested month, fall back to max available if needed
            if end_period > max_available_period:
                fallback = find_most_recent_with_month(end_period)
                end_period = fallback if fallback is not None else max_available_period
            
            # Fallback start_period: try to keep the requested month, fall back to max available if needed
            if start_period > max_available_period:
                fallback = find_most_recent_with_month(start_period)
                start_period = fallback if fallback is not None else max_available_period
            elif start_period < min_available_period:
                start_period = min_available_period

        pool = self._build_window_pool(
            monthly_ref=monthly_ref,
            feature_cols=feature_cols,
            start_period=start_period,
            end_period=end_period,
        )
        if pool.empty:
            raise ValueError("No reference pool available for onboarding window.")

        if "proc_cost" not in onboarding_df.columns or onboarding_df["proc_cost"].isna().any():
            onboarding_df = self.processing_cost_provider.enrich(onboarding_df)

        query_vec = self._build_window_query_vector(
            onboarding_df=onboarding_df,
            cost_type_ids=cost_type_ids,
            feature_cols=feature_cols,
            start_period=start_period,
            end_period=end_period,
        )

        effective_k = min(self.k, len(pool))
        X_pool = pool[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        X_query = query_vec.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        model = NearestNeighbors(n_neighbors=effective_k, metric="euclidean")
        model.fit(X_pool.values)
        _, idx = model.kneighbors(X_query.values)

        neighbors = pool.iloc[idx[0]].copy()
        neighbor_ids = [int(v) for v in neighbors["merchant_id"].tolist()]

        composite = self._build_composite_weekly_features(
            reference_txn,
            neighbor_ids,
            cost_type_ids,
        )
        if composite.empty:
            raise ValueError("No composite weekly features could be generated.")

        weekly_features: List[CompositeWeeklyFeature] = []
        pct_cols = [f"pct_ct_{c}" for c in cost_type_ids]
        for _, row in composite.iterrows():
            weekly_features.append(
                CompositeWeeklyFeature(
                    calendar_year=int(row["calendar_year"]),
                    week_of_year=int(row["week_of_year"]),
                    weekly_txn_count_mean=float(row["weekly_txn_count_mean"]),
                    weekly_txn_count_stdev=float(row["weekly_txn_count_stdev"]),
                    weekly_total_proc_value_mean=float(row["weekly_total_proc_value_mean"]),
                    weekly_total_proc_value_stdev=float(row["weekly_total_proc_value_stdev"]),
                    weekly_avg_txn_value_mean=float(row["weekly_avg_txn_value_mean"]),
                    weekly_avg_txn_value_stdev=float(row["weekly_avg_txn_value_stdev"]),
                    weekly_avg_txn_cost_pct_mean=float(row["weekly_avg_txn_cost_pct_mean"]),
                    weekly_avg_txn_cost_pct_stdev=float(row["weekly_avg_txn_cost_pct_stdev"]),
                    neighbor_coverage=int(row["neighbor_coverage"]),
                    pct_ct_means={col: float(row[col]) for col in pct_cols},
                )
            )

        return CompositeMerchantComputationResult(
            composite_merchant_id=f"composite_mcc_{req.mcc}_{start_period}_{end_period}",
            matched_neighbor_merchant_ids=neighbor_ids,
            k=effective_k,
            matching_start_month=str(start_period),
            matching_end_month=str(end_period),
            weekly_features=weekly_features,
        )
