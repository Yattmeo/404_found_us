from __future__ import annotations

from typing import Dict, List

import pandas as pd


def normalize_txn_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.copy()
    if "transaction_date" in renamed.columns and "date" not in renamed.columns:
        renamed = renamed.rename(columns={"transaction_date": "date"})
    return renamed


def _coerce_cost_type_series(df: pd.DataFrame) -> pd.Series:
    if "cost_type_ID" in df.columns:
        raw = df["cost_type_ID"]
    elif "cost_type_id" in df.columns:
        raw = df["cost_type_id"]
    else:
        raw = pd.Series([-1] * len(df), index=df.index)

    return pd.to_numeric(raw, errors="coerce").fillna(-1).astype(int).astype(str)


def build_monthly_features(df: pd.DataFrame, cost_type_ids: List[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    tx = normalize_txn_columns(df)
    tx["date"] = pd.to_datetime(tx["date"], errors="coerce")
    tx = tx.dropna(subset=["date", "merchant_id"])
    if tx.empty:
        return pd.DataFrame()

    tx["amount"] = pd.to_numeric(tx["amount"], errors="coerce")
    tx["proc_cost"] = pd.to_numeric(tx.get("proc_cost"), errors="coerce")
    tx["cost_type_ID"] = _coerce_cost_type_series(tx)

    tx["ym"] = tx["date"].dt.to_period("M")

    counts = (
        tx.groupby(["merchant_id", "ym", "cost_type_ID"])
        .size()
        .rename("count")
        .reset_index()
    )

    cost_counts = counts.pivot_table(
        index=["merchant_id", "ym"],
        columns="cost_type_ID",
        values="count",
        fill_value=0,
    )
    cost_counts = cost_counts.reindex(columns=cost_type_ids, fill_value=0)

    total_txn = cost_counts.sum(axis=1).rename("total_transactions")
    cost_pct = cost_counts.div(total_txn, axis=0).fillna(0.0)
    cost_pct.columns = [f"pct_ct_{c}" for c in cost_pct.columns]

    avg_amount = tx.groupby(["merchant_id", "ym"])["amount"].mean().rename("avg_amount")
    sum_amount = tx.groupby(["merchant_id", "ym"])["amount"].sum().rename("sum_amount")
    sum_proc_cost = tx.groupby(["merchant_id", "ym"])["proc_cost"].sum().rename("sum_proc_cost")
    proc_cost_pct = (
        sum_proc_cost / sum_amount
    ).replace([float("inf"), float("-inf")], 0.0).fillna(0.0).rename("proc_cost_pct")

    features = pd.concat([cost_pct, total_txn, avg_amount, proc_cost_pct], axis=1).reset_index()
    features["ym_period"] = pd.PeriodIndex(features["ym"], freq="M")
    return features


def build_pool_by_month(
    monthly_df: pd.DataFrame,
    feature_cols: List[str],
    context_len_months: int,
    horizon_len_months: int,
) -> Dict[int, pd.DataFrame]:
    pool_by_end_month: Dict[int, List[pd.DataFrame]] = {}
    if monthly_df.empty:
        return {}

    all_periods = sorted(monthly_df["ym_period"].unique())
    if not all_periods:
        return {}

    min_period = all_periods[0]
    max_period = all_periods[-1]

    for end_period in all_periods:
        start_context = end_period - (context_len_months - 1)
        end_target = end_period + horizon_len_months
        if start_context < min_period or end_target > max_period:
            continue

        context_periods = pd.period_range(start_context, end_period, freq="M")
        target_periods = pd.period_range(end_period + 1, end_period + horizon_len_months, freq="M")

        ctx = monthly_df[monthly_df["ym_period"].isin(context_periods)]
        tgt = monthly_df[monthly_df["ym_period"].isin(target_periods)]

        if ctx.empty or tgt.empty:
            continue

        ctx_agg = ctx.groupby("merchant_id")[feature_cols].mean()

        merchants_with_full_horizon = (
            tgt.groupby("merchant_id")["ym_period"]
            .nunique()
            .loc[lambda s: s >= horizon_len_months]
            .index
        )

        if ctx_agg.empty or len(merchants_with_full_horizon) == 0:
            continue

        valid_merchants = ctx_agg.index.intersection(merchants_with_full_horizon)
        cases = ctx_agg.loc[valid_merchants].copy().reset_index()
        if cases.empty:
            continue
        cases["end_period"] = str(end_period)
        cases["end_month"] = end_period.month
        pool_by_end_month.setdefault(end_period.month, []).append(cases)

    return {
        month_num: pd.concat(frames, axis=0, ignore_index=True)
        for month_num, frames in pool_by_end_month.items()
    }


def query_vector_from_txn_df(
    onboarding_df: pd.DataFrame,
    cost_type_ids: List[str],
    feature_cols: List[str],
    end_period: pd.Period,
    avg_monthly_txn_count: int | None,
    avg_monthly_txn_value: float | None,
) -> pd.DataFrame:
    tx = normalize_txn_columns(onboarding_df)
    tx["date"] = pd.to_datetime(tx["date"], errors="coerce")
    tx = tx.dropna(subset=["date"])

    in_month = tx[tx["date"].dt.to_period("M") == end_period].copy()
    if in_month.empty:
        raise ValueError("No onboarding transactions found for selected month.")

    in_month["cost_type_ID"] = _coerce_cost_type_series(in_month)
    counts = in_month.groupby("cost_type_ID").size().rename("count").reset_index()
    pivot = counts.pivot_table(index=[], columns="cost_type_ID", values="count", fill_value=0)
    pivot = pivot.reindex(columns=cost_type_ids, fill_value=0)

    total = int(pivot.sum(axis=1).iloc[0]) if avg_monthly_txn_count is None else int(avg_monthly_txn_count)
    if total <= 0:
        raise ValueError("avg_monthly_txn_count must be > 0.")

    avg_value = (
        float(pd.to_numeric(in_month.get("amount"), errors="coerce").mean())
        if avg_monthly_txn_value is None
        else float(avg_monthly_txn_value)
    )

    pct = pivot.div(total, axis=0).fillna(0.0)
    pct.columns = [f"pct_ct_{c}" for c in pct.columns]

    vec = pd.concat(
        [
            pct,
            pd.DataFrame({"total_transactions": [total], "avg_amount": [avg_value]}),
        ],
        axis=1,
    )
    vec = vec.reindex(columns=feature_cols, fill_value=0.0).fillna(0.0)
    return vec.astype(float)


def query_vector_from_pool_means(
    feature_cols: List[str],
    pool: pd.DataFrame,
    avg_monthly_txn_count: int,
    avg_monthly_txn_value: float,
) -> pd.DataFrame:
    means = pool[feature_cols].mean()
    pct_cols = [c for c in feature_cols if c.startswith("pct_ct_")]
    pct = means[pct_cols]
    pct = pct / max(float(pct.sum()), 1e-12)

    row = pd.DataFrame([means.to_dict()])
    for col in pct_cols:
        row[col] = float(pct[col])

    row["total_transactions"] = int(avg_monthly_txn_count)
    row["avg_amount"] = float(avg_monthly_txn_value)
    row = row.reindex(columns=feature_cols, fill_value=0.0).fillna(0.0)
    return row.astype(float)


def lookup_horizon_proc_cost_pct(
    monthly_df: pd.DataFrame,
    matched_cases: pd.DataFrame,
    horizon_len_months: int,
) -> List[List[float]]:
    results: List[List[float]] = []
    for _, row in matched_cases.iterrows():
        merchant_id = row["merchant_id"]
        end_period = pd.Period(str(row["end_period"]), freq="M")
        month_values: List[float] = []
        for i in range(1, horizon_len_months + 1):
            target_period = end_period + i
            match = monthly_df[
                (monthly_df["merchant_id"] == merchant_id)
                & (monthly_df["ym_period"] == target_period)
            ]
            if match.empty or match["proc_cost_pct"].isna().all():
                month_values.append(0.0)
            else:
                month_values.append(float(match["proc_cost_pct"].iloc[0]))
        results.append(month_values)
    return results
