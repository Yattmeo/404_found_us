"""
GetM9MonthlyCostForecast — v2 inference service.

v2 simplifies the API: the caller sends raw transaction records and basic
forecast parameters.  The service handles all feature engineering internally:

  1. Aggregate raw transactions into monthly summaries (computing
     avg_proc_cost_pct = mean(proc_cost / amount) per month).
  2. Query the reference database to compute flat / kNN pool means and
     discover peer merchant IDs.
  3. Build model + risk feature vectors.
  4. Predict & wrap in conformal intervals.

Model pipeline (unchanged):
  - Target: avg_proc_cost_pct
  - Regressor: HuberRegressor with inverse-pool-mean sample weights
  - Conformal: absolute residuals (|actual − pred|)
  - Risk model: GBR on 9 risk features → stratified conformal width mapping
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from config import (
    ARTIFACT_POLL_INTERVAL_S,
    ARTIFACTS_BASE_PATH,
    HORIZON_LEN,
    KNN_K,
    MIN_POOL,
    SUPPORTED_CONTEXT_LENS,
    SUPPORTED_MCCS,
    TARGET_COV,
    _VOL_EPS,
)
from models import (
    ConformalMetadata,
    ForecastMonth,
    M9ForecastRequest,
    M9ForecastResponse,
    ProcessMetadata,
)
from repository import MerchantRepository


# ---------------------------------------------------------------------------
# Internal monthly summary (replaces the old ContextMonth pydantic model)
# ---------------------------------------------------------------------------

@dataclass
class _MonthSummary:
    """Aggregated monthly stats produced from raw transactions."""

    year: int
    month: int
    avg_proc_cost_pct: float
    std_proc_cost_pct: float
    median_proc_cost_pct: float
    transaction_count: int
    avg_transaction_value: float
    std_txn_amount: float
    cost_type_pcts: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Artifact bundle (one per MCC × context_len)
# ---------------------------------------------------------------------------

@dataclass
class ArtifactBundle:
    """All trained artifacts for one MCC at one context length, loaded from disk."""

    context_len: int
    models: List[HuberRegressor]            # length == HORIZON_LEN
    scaler: StandardScaler
    cal_residuals: Dict[int, List[float]]   # merchant_id → list of max-over-horizon abs residuals
    global_q90: float
    risk_models: List[GradientBoostingRegressor]  # length == HORIZON_LEN
    strat_enabled: bool
    strat_scheme: Optional[str]
    strat_knot_x: Optional[np.ndarray]      # risk-score knots for interp
    strat_q_vals: Optional[np.ndarray]       # corresponding q values for interp
    config_snapshot: dict
    loaded_mtime: float = field(default=0.0)

    @property
    def trained_at(self) -> Optional[str]:
        return self.config_snapshot.get("trained_at")


# ---------------------------------------------------------------------------
# Artifact loading helpers
# ---------------------------------------------------------------------------

def _artifact_dir(mcc: int, ctx_len: int) -> Path:
    return ARTIFACTS_BASE_PATH / str(mcc) / str(ctx_len)


def _load_bundle(mcc: int, ctx_len: int) -> ArtifactBundle:
    """Load all artifact files for one (mcc, ctx_len) from disk."""
    d = _artifact_dir(mcc, ctx_len)
    snapshot_path = d / "config_snapshot.json"

    with open(snapshot_path) as f:
        snapshot = json.load(f)

    models: List[HuberRegressor] = joblib.load(d / "models.pkl")
    scaler: StandardScaler = joblib.load(d / "scaler.pkl")
    cal_residuals: Dict[int, List[float]] = joblib.load(d / "cal_residuals.pkl")
    global_q90: float = joblib.load(d / "global_q90.pkl")
    risk_models: List[GradientBoostingRegressor] = joblib.load(d / "risk_models.pkl")

    strat_enabled = snapshot.get("strat_enabled", False)
    strat_scheme = snapshot.get("strat_scheme")
    strat_knot_x = None
    strat_q_vals = None
    if strat_enabled:
        strat_knot_x = joblib.load(d / "strat_knot_x.pkl")
        strat_q_vals = joblib.load(d / "strat_q_vals.pkl")

    mtime = os.path.getmtime(snapshot_path)
    return ArtifactBundle(
        context_len=ctx_len,
        models=models,
        scaler=scaler,
        cal_residuals=cal_residuals,
        global_q90=global_q90,
        risk_models=risk_models,
        strat_enabled=strat_enabled,
        strat_scheme=strat_scheme,
        strat_knot_x=strat_knot_x,
        strat_q_vals=strat_q_vals,
        config_snapshot=snapshot,
        loaded_mtime=mtime,
    )


# ---------------------------------------------------------------------------
# Artifact cache with hot-reload
# Key: (mcc, ctx_len)
# ---------------------------------------------------------------------------

_ARTIFACT_CACHE: Dict[Tuple[int, int], ArtifactBundle] = {}
_CACHE_LOCK = threading.Lock()

# Module-level repository handle — set by app.py at startup.
_REPO: Optional[MerchantRepository] = None


def set_repository(repo: MerchantRepository) -> None:
    """Called once at startup to inject the DB connection."""
    global _REPO
    _REPO = repo


def _init_cache() -> None:
    """Load artifacts for all SUPPORTED_MCCS × SUPPORTED_CONTEXT_LENS."""
    for mcc in SUPPORTED_MCCS:
        for ctx_len in SUPPORTED_CONTEXT_LENS:
            d = _artifact_dir(mcc, ctx_len)
            if not (d / "config_snapshot.json").exists():
                print(
                    f"[GetM9] WARNING: no artifacts for MCC {mcc} ctx={ctx_len} "
                    f"at {d} — skipping"
                )
                continue
            bundle = _load_bundle(mcc, ctx_len)
            with _CACHE_LOCK:
                _ARTIFACT_CACHE[(mcc, ctx_len)] = bundle
            print(
                f"[GetM9] Loaded artifacts for MCC {mcc} ctx={ctx_len}  "
                f"trained_at={bundle.trained_at}  strat={bundle.strat_enabled}"
            )


def _poll_artifacts() -> None:
    """Background thread: check for updated artifacts every ARTIFACT_POLL_INTERVAL_S."""
    while True:
        time.sleep(ARTIFACT_POLL_INTERVAL_S)
        for (mcc, ctx_len) in list(_ARTIFACT_CACHE.keys()):
            try:
                snapshot_path = _artifact_dir(mcc, ctx_len) / "config_snapshot.json"
                current_mtime = os.path.getmtime(snapshot_path)
                with _CACHE_LOCK:
                    old_mtime = _ARTIFACT_CACHE[(mcc, ctx_len)].loaded_mtime
                if current_mtime > old_mtime:
                    bundle = _load_bundle(mcc, ctx_len)
                    with _CACHE_LOCK:
                        _ARTIFACT_CACHE[(mcc, ctx_len)] = bundle
                    print(
                        f"[GetM9] Hot-reloaded artifacts for MCC {mcc} ctx={ctx_len}  "
                        f"trained_at={bundle.trained_at}"
                    )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[GetM9] WARNING: artifact reload failed for "
                    f"MCC {mcc} ctx={ctx_len}: {exc}"
                )


def start_artifact_watcher() -> None:
    """Start the hot-reload background thread (daemon so it does not block shutdown)."""
    t = threading.Thread(target=_poll_artifacts, daemon=True, name="artifact-watcher")
    t.start()


# ---------------------------------------------------------------------------
# Raw transaction → monthly summary aggregation
# ---------------------------------------------------------------------------

def _aggregate_transactions(
    records: List[Dict[str, Any]],
) -> List[_MonthSummary]:
    """
    Convert raw transaction records into sorted monthly summaries.

    Each record should have at least ``transaction_date``, ``amount``,
    and ``proc_cost``.  Optional: ``cost_type_ID``.

    The target variable ``avg_proc_cost_pct`` is computed as
    mean(proc_cost / amount) across transactions in each month.
    """
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("onboarding_merchant_txn_df is empty.")

    # Normalise date column
    if "transaction_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"transaction_date": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        raise ValueError("No valid dates in onboarding_merchant_txn_df.")

    df["amount"] = pd.to_numeric(df.get("amount"), errors="coerce").fillna(0.0)
    df["proc_cost"] = pd.to_numeric(df.get("proc_cost"), errors="coerce").fillna(0.0)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    # Per-transaction proc_cost_pct (guard against zero-amount)
    safe_amount = df["amount"].replace(0.0, np.nan)
    df["proc_cost_pct"] = (df["proc_cost"] / safe_amount).fillna(0.0)

    summaries: List[_MonthSummary] = []
    for (yr, mo), grp in df.groupby(["year", "month"]):
        pcts = grp["proc_cost_pct"].values.astype(float)
        amounts = grp["amount"].values.astype(float)
        txn_count = len(grp)

        avg_pct = float(pcts.mean()) if txn_count > 0 else 0.0
        std_pct = float(pcts.std(ddof=0)) if txn_count > 1 else 0.0
        med_pct = float(np.median(pcts)) if txn_count > 0 else 0.0

        avg_val = float(amounts.mean()) if txn_count > 0 else 0.0
        std_val = float(amounts.std(ddof=0)) if txn_count > 1 else 0.0

        # Cost-type percentages (for risk feature HHI)
        cost_type_pcts: Optional[Dict[str, float]] = None
        if "cost_type_ID" in grp.columns:
            ct = grp["cost_type_ID"].fillna(-1).astype(int).astype(str)
            counts = ct.value_counts(normalize=True)
            cost_type_pcts = {
                f"cost_type_{k}_pct": float(v) for k, v in counts.items()
            }

        summaries.append(_MonthSummary(
            year=int(yr),
            month=int(mo),
            avg_proc_cost_pct=avg_pct,
            std_proc_cost_pct=std_pct,
            median_proc_cost_pct=med_pct,
            transaction_count=txn_count,
            avg_transaction_value=avg_val,
            std_txn_amount=std_val,
            cost_type_pcts=cost_type_pcts,
        ))

    summaries.sort(key=lambda s: (s.year, s.month))
    return summaries


# ---------------------------------------------------------------------------
# Pool-mean & kNN peer computation from reference DB
# ---------------------------------------------------------------------------

def _compute_pool_info(
    repo: MerchantRepository,
    mcc: int,
    card_types: List[str],
    context_months: List[_MonthSummary],
) -> Tuple[float, float, List[int]]:
    """
    Query the reference database and return:
      - flat_pool_mean  (avg_proc_cost_pct space)
      - knn_pool_mean   (avg_proc_cost_pct space, cosine on cost-type fingerprint)
      - peer_merchant_ids  (list of kNN neighbor merchant IDs)
    """
    ref_txn = repo.load_transactions(mcc, card_types)
    if ref_txn.empty:
        raise ValueError(
            f"No reference transactions in the database for MCC {mcc}."
        )

    # Normalise column names
    if "transaction_date" in ref_txn.columns and "date" not in ref_txn.columns:
        ref_txn = ref_txn.rename(columns={"transaction_date": "date"})
    ref_txn["date"] = pd.to_datetime(ref_txn["date"], errors="coerce")
    ref_txn = ref_txn.dropna(subset=["date"])
    ref_txn["amount"] = pd.to_numeric(ref_txn.get("amount"), errors="coerce").fillna(0.0)
    ref_txn["proc_cost"] = pd.to_numeric(ref_txn.get("proc_cost"), errors="coerce").fillna(0.0)
    ref_txn["year"] = ref_txn["date"].dt.year
    ref_txn["month"] = ref_txn["date"].dt.month

    # End of context window
    last = context_months[-1]
    end_yr, end_mo = last.year, last.month

    # Restrict reference to data up to context end
    snap = ref_txn[
        (ref_txn["year"] < end_yr)
        | ((ref_txn["year"] == end_yr) & (ref_txn["month"] <= end_mo))
    ]
    if snap.empty:
        return 0.0, 0.0, []

    # Per-transaction proc_cost_pct
    safe_amount = snap["amount"].replace(0.0, np.nan)
    snap = snap.copy()
    snap["proc_cost_pct"] = (snap["proc_cost"] / safe_amount).fillna(0.0)

    # Monthly avg_proc_cost_pct per merchant
    merchant_monthly = (
        snap.groupby(["merchant_id", "year", "month"])["proc_cost_pct"]
        .mean()
        .reset_index()
        .rename(columns={"proc_cost_pct": "avg_proc_cost_pct"})
    )

    # Flat pool mean (all merchants, all months up to context end)
    merchant_avg = merchant_monthly.groupby("merchant_id")["avg_proc_cost_pct"].mean()
    flat_pool_mean = float(merchant_avg.mean())

    # ---- kNN pool mean via cost-type fingerprint ----
    cost_type_ids = repo.load_cost_type_ids()
    if not cost_type_ids:
        return flat_pool_mean, flat_pool_mean, []

    # Build cost-type fingerprint per merchant from reference
    snap_ct = snap.copy()
    snap_ct["cost_type_ID"] = (
        snap_ct.get("cost_type_ID").fillna(-1).astype(int).astype(str)
    )
    ref_ct_counts = (
        snap_ct.groupby(["merchant_id", "cost_type_ID"])
        .size()
        .rename("count")
        .reset_index()
        .pivot_table(
            index="merchant_id",
            columns="cost_type_ID",
            values="count",
            fill_value=0,
        )
    )
    ref_ct_counts = ref_ct_counts.reindex(columns=cost_type_ids, fill_value=0)
    ref_totals = ref_ct_counts.sum(axis=1)
    ref_pct = ref_ct_counts.div(ref_totals, axis=0).fillna(0.0)

    # Build onboarding fingerprint from context months
    onb_ct: Dict[str, float] = defaultdict(float)
    total_ct_count = 0
    for m in context_months:
        if m.cost_type_pcts:
            for key, val in m.cost_type_pcts.items():
                ct_id = key.replace("cost_type_", "").replace("_pct", "")
                onb_ct[ct_id] += val * m.transaction_count
                total_ct_count += val * m.transaction_count

    if total_ct_count > 0:
        for k in onb_ct:
            onb_ct[k] /= total_ct_count

    onb_vec = pd.DataFrame(
        [{ct: onb_ct.get(ct, 0.0) for ct in cost_type_ids}]
    ).fillna(0.0)

    # avg_proc_cost_pct mean per merchant (for pool-mean lookup)
    common_mids = ref_pct.index.intersection(merchant_avg.index)
    if len(common_mids) < KNN_K + 1:
        return flat_pool_mean, flat_pool_mean, []

    ref_pct_aligned = ref_pct.loc[common_mids]
    merchant_avg_aligned = merchant_avg.loc[common_mids]

    nn = NearestNeighbors(
        n_neighbors=min(KNN_K + 1, len(common_mids)),
        metric="cosine",
    )
    nn.fit(ref_pct_aligned.values)
    _, raw_idx = nn.kneighbors(
        onb_vec.reindex(columns=ref_pct_aligned.columns, fill_value=0.0).values
    )

    mid_index = ref_pct_aligned.index.tolist()
    top_ids = [mid_index[i] for i in raw_idx[0]][:KNN_K]

    knn_pool_mean = float(merchant_avg_aligned.loc[top_ids].mean()) if top_ids else flat_pool_mean
    peer_ids = [int(mid) for mid in top_ids]

    return flat_pool_mean, knn_pool_mean, peer_ids


# ---------------------------------------------------------------------------
# Context window selection
# ---------------------------------------------------------------------------

def _select_context_window(
    months: List[_MonthSummary],
) -> List[_MonthSummary]:
    """
    Pick the last N months where N is the largest supported context length
    that does not exceed the number of available months.
    """
    n = len(months)
    valid = [cl for cl in sorted(SUPPORTED_CONTEXT_LENS, reverse=True) if cl <= n]
    if not valid:
        return months
    chosen_len = valid[0]
    return months[-chosen_len:]


# ---------------------------------------------------------------------------
# v2 model feature construction (7 features)
# ---------------------------------------------------------------------------

def _build_feature_vector(
    context_months: List[_MonthSummary],
    pool_mean: float,
) -> np.ndarray:
    """
    Build the 7-feature row used by M9 v2:
        [context_mean, context_std, momentum, pool_mean,
         intra_std, log_txn_count, mean_median_gap]

    Returns shape (1, 7) for direct use with scaler.transform.
    """
    vals = np.array([m.avg_proc_cost_pct for m in context_months], dtype=float)
    c_mean = float(np.mean(vals))
    c_std = float(np.std(vals))
    momentum = float(vals[-1] - c_mean)

    # v2 transaction-level features
    intra_std = float(np.mean([m.std_proc_cost_pct for m in context_months]))
    log_txn = float(np.log1p(np.mean([m.transaction_count for m in context_months])))
    medians = np.array([m.median_proc_cost_pct for m in context_months], dtype=float)
    mean_median_gap = float(np.mean(np.abs(vals - medians)))

    return np.array(
        [[c_mean, c_std, momentum, pool_mean, intra_std, log_txn, mean_median_gap]],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# v2 risk feature construction (9 features)
# ---------------------------------------------------------------------------

def _build_risk_vector(
    context_months: List[_MonthSummary],
    pool_mean: float,
    knn_pool_mean: float,
) -> np.ndarray:
    """
    Build the 9-feature risk vector used by v2 GBR models:
        [intra_cov, mean_median_gap, log_txn_count, cost_type_hhi,
         log_avg_txn_val, txn_amount_cov, pool_mean_gap_ratio,
         ctx_to_knn_gap_ratio, ctx_cov]

    Returns shape (1, 9).
    """
    vals = np.array([m.avg_proc_cost_pct for m in context_months], dtype=float)
    c_mean = float(np.mean(vals))
    _denom = c_mean + _VOL_EPS

    # Category A: intra-month transaction-level
    intra_cov = float(np.mean([m.std_proc_cost_pct for m in context_months])) / _denom
    medians = np.array([m.median_proc_cost_pct for m in context_months], dtype=float)
    mean_median_gap = float(np.mean(np.abs(vals - medians))) / _denom
    log_txn_count = float(np.log1p(np.mean([m.transaction_count for m in context_months])))

    # Cost type HHI
    ct_vals_list = []
    for m in context_months:
        if m.cost_type_pcts:
            ct_vals_list.append(list(m.cost_type_pcts.values()))
    if ct_vals_list:
        avg_ct = np.mean(ct_vals_list, axis=0)
        cost_type_hhi = float(np.sum(avg_ct ** 2))
    else:
        cost_type_hhi = 1.0

    avg_txn_val = float(np.mean([m.avg_transaction_value for m in context_months]))
    log_avg_txn_val = float(np.log1p(avg_txn_val))
    txn_amount_cov = float(
        np.mean([m.std_txn_amount for m in context_months])
    ) / (avg_txn_val + _VOL_EPS)

    # Category B: peer-relative
    pool_gap = abs(c_mean - pool_mean) / (pool_mean + _VOL_EPS)
    knn_gap = abs(c_mean - knn_pool_mean) / (knn_pool_mean + _VOL_EPS)

    # Category C: graceful degrade
    ctx_cov = float(np.std(vals)) / _denom

    return np.array(
        [[intra_cov, mean_median_gap, log_txn_count, cost_type_hhi,
          log_avg_txn_val, txn_amount_cov, pool_gap, knn_gap, ctx_cov]],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# Conformal quantile helpers
# ---------------------------------------------------------------------------

def _adaptive_q(residuals: List[float], target: float = TARGET_COV) -> Optional[float]:
    """
    Finite-sample conformal quantile at level ceil((n+1)*target)/n.
    Returns None when the level exceeds 1.0 (pool too small to guarantee coverage).
    """
    n = len(residuals)
    level = math.ceil((n + 1) * target) / n
    return float(np.quantile(residuals, level)) if level <= 1.0 else None


def _compute_conformal_hw(
    peer_merchant_ids: Optional[List[int]],
    bundle: ArtifactBundle,
    context_months: List[_MonthSummary],
    pool_mean: float,
    knn_pool_mean: float,
    confidence_interval: float,
) -> Tuple[float, int, str, Optional[float], Optional[str]]:
    """
    Determine the conformal half-width using the three-tier fallback chain:

      1. Local  — adaptive_q on calibration residuals of peer merchants (>= MIN_POOL)
      2. GBR-stratified — continuous width mapping from risk score (if strat_enabled)
      3. Global fallback — q90 of the entire calibration set

    Returns (hw, pool_size, conformal_mode, risk_score, strat_scheme).
    """
    # ── Tier 1: local peer pool ──────────────────────────────────────────────
    peer_residuals: List[float] = []
    if peer_merchant_ids:
        for pid in peer_merchant_ids:
            peer_residuals.extend(bundle.cal_residuals.get(pid, []))

    if len(peer_residuals) >= MIN_POOL:
        q = _adaptive_q(peer_residuals, target=confidence_interval)
        if q is not None:
            return float(q), len(peer_residuals), "local", None, None

    # ── Compute risk score (needed for tier 2) ───────────────────────────────
    risk_vec = _build_risk_vector(context_months, pool_mean, knn_pool_mean)
    scores = np.array(
        [m.predict(risk_vec)[0] for m in bundle.risk_models], dtype=float
    )
    risk_score = float(np.max(scores))

    # ── Tier 2: GBR-stratified continuous width mapping ──────────────────────
    if bundle.strat_enabled and bundle.strat_knot_x is not None:
        hw = float(np.interp(
            risk_score,
            bundle.strat_knot_x,
            bundle.strat_q_vals,
            left=bundle.strat_q_vals[0],
            right=bundle.strat_q_vals[-1],
        ))
        return hw, len(peer_residuals), "stratified", risk_score, bundle.strat_scheme

    # ── Tier 3: global fallback ──────────────────────────────────────────────
    return (
        bundle.global_q90,
        len(peer_residuals),
        "global_fallback",
        risk_score,
        None,
    )


# ---------------------------------------------------------------------------
# Bundle resolution
# ---------------------------------------------------------------------------

def _resolve_bundle(
    mcc: int, ctx_len: int
) -> ArtifactBundle:
    """Find the best matching bundle for the given context length."""
    with _CACHE_LOCK:
        bundle = _ARTIFACT_CACHE.get((mcc, ctx_len))
    if bundle is not None:
        return bundle

    # Fall back to nearest supported context length
    with _CACHE_LOCK:
        available = sorted(
            [cl for (m, cl) in _ARTIFACT_CACHE if m == mcc],
        )
    if not available:
        raise ValueError(
            f"MCC {mcc} has no loaded artifacts. "
            f"Supported MCCs: {sorted(set(m for m, _ in _ARTIFACT_CACHE.keys()))}"
        )
    nearest = min(available, key=lambda cl: abs(cl - ctx_len))
    with _CACHE_LOCK:
        return _ARTIFACT_CACHE[(mcc, nearest)]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_monthly_cost_forecast(req: M9ForecastRequest) -> M9ForecastResponse:
    generated_at = datetime.now(timezone.utc)

    # 1. Aggregate raw transactions into monthly summaries
    all_months = _aggregate_transactions(req.onboarding_merchant_txn_df)
    if not all_months:
        raise ValueError("No valid monthly data could be derived from the transactions.")

    # 2. Select context window (last 1/3/6 months)
    context_months = _select_context_window(all_months)
    ctx_len = len(context_months)

    # 3. Resolve artifact bundle
    bundle = _resolve_bundle(req.mcc, ctx_len)

    # 4. Compute pool means + peer IDs from reference DB
    if _REPO is None:
        raise RuntimeError(
            "Reference database not configured. "
            "Set DB_CONNECTION_STRING or TRANSACTIONS_AND_COST_TYPE_DB_PATH."
        )
    flat_pool_mean, knn_pool_mean, peer_ids = _compute_pool_info(
        repo=_REPO,
        mcc=req.mcc,
        card_types=req.card_types,
        context_months=context_months,
    )

    # 5. Build v2 model features
    vals = [m.avg_proc_cost_pct for m in context_months]
    c_mean = float(np.mean(vals))
    c_std = float(np.std(vals))
    momentum = float(vals[-1] - c_mean)

    X_raw = _build_feature_vector(context_months, knn_pool_mean)
    X_scaled = bundle.scaler.transform(X_raw)

    # 6. Predict HORIZON_LEN steps
    point_forecasts = np.array(
        [bundle.models[h].predict(X_scaled)[0] for h in range(req.horizon_months)],
        dtype=float,
    )

    # 7. Conformal half-width
    hw, pool_size, conformal_mode, risk_score, strat_scheme = _compute_conformal_hw(
        peer_merchant_ids=peer_ids,
        bundle=bundle,
        context_months=context_months,
        pool_mean=flat_pool_mean,
        knn_pool_mean=knn_pool_mean,
        confidence_interval=req.confidence_interval,
    )

    # 8. Assemble forecast months
    forecast = [
        ForecastMonth(
            month_index=h + 1,
            proc_cost_pct_mid=float(point_forecasts[h]),
            proc_cost_pct_ci_lower=max(0.0, float(point_forecasts[h]) - hw),
            proc_cost_pct_ci_upper=float(point_forecasts[h]) + hw,
        )
        for h in range(req.horizon_months)
    ]

    # 9. Assemble metadata
    conformal_meta = ConformalMetadata(
        half_width=hw,
        conformal_mode=conformal_mode,
        pool_size=pool_size,
        risk_score=risk_score,
        strat_scheme=strat_scheme,
    )

    process_meta = ProcessMetadata(
        context_len_used=ctx_len,
        context_mean=c_mean,
        context_std=c_std,
        momentum=momentum,
        pool_mean_used=knn_pool_mean,
        mcc=req.mcc,
        horizon_months=req.horizon_months,
        confidence_interval=req.confidence_interval,
        generated_at_utc=generated_at,
        artifact_trained_at=bundle.trained_at,
        strat_enabled=bundle.strat_enabled,
    )

    return M9ForecastResponse(
        forecast=forecast,
        conformal_metadata=conformal_meta,
        process_metadata=process_meta,
    )
