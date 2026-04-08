"""
GetTPVForecast — v2 inference service (embedded in ml_service).

Adapted from the standalone GetTPVForecast Service v2.
All imports use relative paths. Graceful degraded mode when artifacts
are not yet trained (returns a simple extrapolation-based fallback).
"""

from __future__ import annotations

import json
import logging
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

from .config import (
    ARTIFACT_POLL_INTERVAL_S,
    ARTIFACTS_BASE_PATH,
    HORIZON_LEN,
    KNN_K,
    LOG_TARGET,
    MIN_POOL,
    SUPPORTED_CONTEXT_LENS,
    SUPPORTED_MCCS,
    TARGET_COV,
    _VOL_EPS,
)
from .models import (
    ConformalMetadata,
    ForecastMonth,
    ProcessMetadata,
    TPVForecastRequest,
    TPVForecastResponse,
)
from .repository import MerchantRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal monthly summary
# ---------------------------------------------------------------------------

@dataclass
class _MonthSummary:
    year: int
    month: int
    total_processing_value: float
    transaction_count: int
    avg_transaction_value: float
    std_txn_amount: float
    median_txn_amount: float
    cost_type_pcts: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Artifact bundle
# ---------------------------------------------------------------------------

@dataclass
class ArtifactBundle:
    context_len: int
    models: List[HuberRegressor]
    scaler: StandardScaler
    cal_residuals: Dict[int, List[float]]
    global_q90: float
    risk_models: List[GradientBoostingRegressor]
    strat_enabled: bool
    strat_scheme: Optional[str]
    strat_knot_x: Optional[np.ndarray]
    strat_q_vals: Optional[np.ndarray]
    config_snapshot: dict
    loaded_mtime: float = field(default=0.0)

    @property
    def trained_at(self) -> Optional[str]:
        return self.config_snapshot.get("trained_at")


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------

def _artifact_dir(mcc: int, ctx_len: int) -> Path:
    return ARTIFACTS_BASE_PATH / str(mcc) / str(ctx_len)


def _load_bundle(mcc: int, ctx_len: int) -> ArtifactBundle:
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
# ---------------------------------------------------------------------------

_ARTIFACT_CACHE: Dict[Tuple[int, int], ArtifactBundle] = {}
_CACHE_LOCK = threading.Lock()
_REPO: Optional[MerchantRepository] = None


def set_repository(repo: MerchantRepository) -> None:
    global _REPO
    _REPO = repo


def _init_cache() -> None:
    for mcc in SUPPORTED_MCCS:
        for ctx_len in SUPPORTED_CONTEXT_LENS:
            d = _artifact_dir(mcc, ctx_len)
            if not (d / "config_snapshot.json").exists():
                logger.warning(
                    "[TPV] No artifacts for MCC %d ctx=%d at %s — skipping",
                    mcc, ctx_len, d,
                )
                continue
            try:
                bundle = _load_bundle(mcc, ctx_len)
                with _CACHE_LOCK:
                    _ARTIFACT_CACHE[(mcc, ctx_len)] = bundle
                logger.info(
                    "[TPV] Loaded artifacts for MCC %d ctx=%d trained_at=%s strat=%s",
                    mcc, ctx_len, bundle.trained_at, bundle.strat_enabled,
                )
            except Exception as exc:
                logger.warning(
                    "[TPV] Failed to load artifacts for MCC %d ctx=%d: %s",
                    mcc, ctx_len, exc,
                )


def _poll_artifacts() -> None:
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
                    logger.info(
                        "[TPV] Hot-reloaded artifacts for MCC %d ctx=%d trained_at=%s",
                        mcc, ctx_len, bundle.trained_at,
                    )
            except Exception as exc:
                logger.warning(
                    "[TPV] Artifact reload failed for MCC %d ctx=%d: %s",
                    mcc, ctx_len, exc,
                )


def start_artifact_watcher() -> None:
    t = threading.Thread(target=_poll_artifacts, daemon=True, name="tpv-artifact-watcher")
    t.start()


def initialize() -> None:
    """Called at ml_service startup. Graceful — does NOT crash if no artifacts."""
    _init_cache()
    if _ARTIFACT_CACHE:
        start_artifact_watcher()
        logger.info("[TPV] Artifact cache loaded with %d bundles", len(_ARTIFACT_CACHE))
    else:
        logger.warning(
            "[TPV] No trained artifacts found — service will run in degraded "
            "mode (simple extrapolation fallback)."
        )


# ---------------------------------------------------------------------------
# Raw transaction → monthly summary aggregation
# ---------------------------------------------------------------------------

def _aggregate_transactions(records: List[Dict[str, Any]]) -> List[_MonthSummary]:
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("onboarding_merchant_txn_df is empty.")

    if "transaction_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"transaction_date": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        raise ValueError("No valid dates in onboarding_merchant_txn_df.")

    df["amount"] = pd.to_numeric(df.get("amount"), errors="coerce").fillna(0.0)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    summaries: List[_MonthSummary] = []
    for (yr, mo), grp in df.groupby(["year", "month"]):
        amounts = grp["amount"].values.astype(float)
        tpv = float(amounts.sum())
        txn_count = len(amounts)
        avg_val = float(amounts.mean()) if txn_count > 0 else 0.0
        std_val = float(amounts.std(ddof=0)) if txn_count > 1 else 0.0
        med_val = float(np.median(amounts)) if txn_count > 0 else 0.0

        cost_type_pcts: Optional[Dict[str, float]] = None
        if "cost_type_ID" in grp.columns:
            ct = grp["cost_type_ID"].fillna(-1).astype(int).astype(str)
            counts = ct.value_counts(normalize=True)
            cost_type_pcts = {
                f"cost_type_{k}_pct": float(v) for k, v in counts.items()
            }

        summaries.append(_MonthSummary(
            year=int(yr), month=int(mo),
            total_processing_value=tpv, transaction_count=txn_count,
            avg_transaction_value=avg_val, std_txn_amount=std_val,
            median_txn_amount=med_val, cost_type_pcts=cost_type_pcts,
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
    ref_txn = repo.load_transactions(mcc, card_types)
    if ref_txn.empty:
        raise ValueError(f"No reference transactions in the database for MCC {mcc}.")

    if "transaction_date" in ref_txn.columns and "date" not in ref_txn.columns:
        ref_txn = ref_txn.rename(columns={"transaction_date": "date"})
    ref_txn["date"] = pd.to_datetime(ref_txn["date"], errors="coerce")
    ref_txn = ref_txn.dropna(subset=["date"])
    ref_txn["amount"] = pd.to_numeric(ref_txn.get("amount"), errors="coerce").fillna(0.0)
    ref_txn["year"] = ref_txn["date"].dt.year
    ref_txn["month"] = ref_txn["date"].dt.month

    last = context_months[-1]
    end_yr, end_mo = last.year, last.month

    snap = ref_txn[
        (ref_txn["year"] < end_yr)
        | ((ref_txn["year"] == end_yr) & (ref_txn["month"] <= end_mo))
    ]
    if snap.empty:
        return 0.0, 0.0, []

    merchant_monthly = (
        snap.groupby(["merchant_id", "year", "month"])["amount"]
        .sum().reset_index()
        .rename(columns={"amount": "total_processing_value"})
    )
    merchant_monthly["log_tpv"] = np.log1p(merchant_monthly["total_processing_value"])
    flat_pool_mean = float(merchant_monthly["log_tpv"].mean())

    cost_type_ids = repo.load_cost_type_ids()
    if not cost_type_ids:
        return flat_pool_mean, flat_pool_mean, []

    snap_ct = snap.copy()
    snap_ct["cost_type_ID"] = (
        snap_ct.get("cost_type_ID").fillna(-1).astype(int).astype(str)
    )
    ref_ct_counts = (
        snap_ct.groupby(["merchant_id", "cost_type_ID"])
        .size().rename("count").reset_index()
        .pivot_table(index="merchant_id", columns="cost_type_ID",
                     values="count", fill_value=0)
    )
    ref_ct_counts = ref_ct_counts.reindex(columns=cost_type_ids, fill_value=0)
    ref_totals = ref_ct_counts.sum(axis=1)
    ref_pct = ref_ct_counts.div(ref_totals, axis=0).fillna(0.0)

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

    merchant_log_tpv = merchant_monthly.groupby("merchant_id")["log_tpv"].mean()
    common_mids = ref_pct.index.intersection(merchant_log_tpv.index)
    if len(common_mids) < KNN_K + 1:
        return flat_pool_mean, flat_pool_mean, []

    ref_pct_aligned = ref_pct.loc[common_mids]
    merchant_log_tpv_aligned = merchant_log_tpv.loc[common_mids]

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

    knn_pool_mean = float(merchant_log_tpv_aligned.loc[top_ids].mean()) if top_ids else flat_pool_mean
    peer_ids = [int(mid) for mid in top_ids]
    return flat_pool_mean, knn_pool_mean, peer_ids


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------

def _build_feature_vector(
    context_months: List[_MonthSummary],
    pool_mean: float,
) -> np.ndarray:
    log_vals = np.array(
        [np.log1p(m.total_processing_value) for m in context_months], dtype=float,
    )
    c_mean = float(np.mean(log_vals))
    c_std = float(np.std(log_vals))
    momentum = float(log_vals[-1] - c_mean)

    txn_amount_std = float(np.mean([m.std_txn_amount for m in context_months]))
    log_txn = float(np.log1p(np.mean([m.transaction_count for m in context_months])))
    avg_median_gap = float(np.mean(
        [abs(m.avg_transaction_value - m.median_txn_amount) for m in context_months]
    ))

    last_month = float(log_vals[-1])
    log_avg_txn_val = float(np.log1p(
        np.mean([m.avg_transaction_value for m in context_months])
    ))

    tc_vals = np.array(
        [np.log1p(m.transaction_count) for m in context_months], dtype=float,
    )
    atv_vals = np.array(
        [np.log1p(m.avg_transaction_value) for m in context_months], dtype=float,
    )
    mom_tc = float(tc_vals[-1] - np.mean(tc_vals))
    mom_atv = float(atv_vals[-1] - np.mean(atv_vals))

    return np.array(
        [[c_mean, c_std, momentum, pool_mean,
          txn_amount_std, log_txn, avg_median_gap,
          last_month, log_avg_txn_val, mom_tc, mom_atv]],
        dtype=float,
    )


def _build_risk_vector(
    context_months: List[_MonthSummary],
    pool_mean: float,
    knn_pool_mean: float,
) -> np.ndarray:
    log_vals = np.array(
        [np.log1p(m.total_processing_value) for m in context_months], dtype=float,
    )
    c_mean = float(np.mean(log_vals))
    _denom = c_mean + _VOL_EPS

    avg_txn_val = float(np.mean([m.avg_transaction_value for m in context_months]))
    intra_txn_cov = float(np.mean([m.std_txn_amount for m in context_months])) / (avg_txn_val + _VOL_EPS)
    avg_median_gap = float(np.mean(
        [abs(m.avg_transaction_value - m.median_txn_amount) for m in context_months]
    )) / (avg_txn_val + _VOL_EPS)
    log_txn_count = float(np.log1p(np.mean([m.transaction_count for m in context_months])))

    ct_vals_list = []
    for m in context_months:
        if m.cost_type_pcts:
            ct_vals_list.append(list(m.cost_type_pcts.values()))
    if ct_vals_list:
        avg_ct = np.mean(ct_vals_list, axis=0)
        cost_type_hhi = float(np.sum(avg_ct ** 2))
    else:
        cost_type_hhi = 1.0

    log_avg_txn_val = float(np.log1p(avg_txn_val))
    txn_amount_cov = float(
        np.mean([m.std_txn_amount for m in context_months])
    ) / (avg_txn_val + _VOL_EPS)

    pool_gap = abs(c_mean - pool_mean) / (pool_mean + _VOL_EPS)
    knn_gap = abs(c_mean - knn_pool_mean) / (knn_pool_mean + _VOL_EPS)
    ctx_cov = float(np.std(log_vals)) / _denom

    tc_vals = np.array(
        [np.log1p(m.transaction_count) for m in context_months], dtype=float,
    )
    atv_vals = np.array(
        [np.log1p(m.avg_transaction_value) for m in context_months], dtype=float,
    )
    tc_mean = float(np.mean(tc_vals))
    atv_mean = float(np.mean(atv_vals))
    tc_cov = float(np.std(tc_vals)) / (tc_mean + _VOL_EPS)
    atv_cov = float(np.std(atv_vals)) / (atv_mean + _VOL_EPS)

    return np.array(
        [[intra_txn_cov, avg_median_gap, log_txn_count,
          cost_type_hhi, log_avg_txn_val, txn_amount_cov,
          pool_gap, knn_gap, ctx_cov,
          tc_cov, atv_cov]],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# Conformal quantile helpers
# ---------------------------------------------------------------------------

def _adaptive_q(residuals: List[float], target: float = TARGET_COV) -> Optional[float]:
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
    peer_residuals: List[float] = []
    if peer_merchant_ids:
        for pid in peer_merchant_ids:
            peer_residuals.extend(bundle.cal_residuals.get(pid, []))

    if len(peer_residuals) >= MIN_POOL:
        q = _adaptive_q(peer_residuals, target=confidence_interval)
        if q is not None:
            return float(q), len(peer_residuals), "local", None, None

    risk_vec = _build_risk_vector(context_months, pool_mean, knn_pool_mean)
    scores = np.array(
        [m.predict(risk_vec)[0] for m in bundle.risk_models], dtype=float,
    )
    risk_score = float(np.max(scores))

    if bundle.strat_enabled and bundle.strat_knot_x is not None:
        hw = float(np.interp(
            risk_score,
            bundle.strat_knot_x,
            bundle.strat_q_vals,
            left=bundle.strat_q_vals[0],
            right=bundle.strat_q_vals[-1],
        ))
        return hw, len(peer_residuals), "stratified", risk_score, bundle.strat_scheme

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

def _resolve_bundle(mcc: int, ctx_len: int) -> Optional[ArtifactBundle]:
    """Returns None if no artifacts are available (degraded mode)."""
    with _CACHE_LOCK:
        bundle = _ARTIFACT_CACHE.get((mcc, ctx_len))
    if bundle is not None:
        return bundle

    with _CACHE_LOCK:
        available = sorted([cl for (m, cl) in _ARTIFACT_CACHE if m == mcc])
    if not available:
        return None
    nearest = min(available, key=lambda cl: abs(cl - ctx_len))
    with _CACHE_LOCK:
        return _ARTIFACT_CACHE[(mcc, nearest)]


# ---------------------------------------------------------------------------
# Context window selection
# ---------------------------------------------------------------------------

def _select_context_window(months: List[_MonthSummary]) -> List[_MonthSummary]:
    n = len(months)
    valid = [cl for cl in sorted(SUPPORTED_CONTEXT_LENS, reverse=True) if cl <= n]
    if not valid:
        return months
    chosen_len = valid[0]
    return months[-chosen_len:]


# ---------------------------------------------------------------------------
# Degraded-mode fallback (simple extrapolation when no trained artifacts)
# ---------------------------------------------------------------------------

def _fallback_forecast(
    context_months: List[_MonthSummary],
    req: TPVForecastRequest,
) -> TPVForecastResponse:
    """
    Simple extrapolation-based fallback when no trained artifacts exist.
    Uses context mean + momentum for point forecast and ±20% CI band.
    """
    generated_at = datetime.now(timezone.utc)
    log_vals = np.array(
        [np.log1p(m.total_processing_value) for m in context_months], dtype=float,
    )
    c_mean = float(np.mean(log_vals))
    momentum = float(log_vals[-1] - c_mean) if len(log_vals) > 1 else 0.0
    c_mean_dollar = float(np.expm1(c_mean))

    # Simple: last observed TPV + small momentum-based drift
    last_tpv = context_months[-1].total_processing_value
    forecast = []
    for h in range(req.horizon_months):
        drift = momentum * (h + 1) * 0.3
        pred_log = log_vals[-1] + drift
        pred_dollar = float(np.expm1(pred_log))
        hw = max(pred_dollar * 0.20, 1.0)  # 20% uncertainty band
        forecast.append(ForecastMonth(
            month_index=h + 1,
            tpv_mid=pred_dollar,
            tpv_ci_lower=max(0.0, pred_dollar - hw),
            tpv_ci_upper=pred_dollar + hw,
        ))

    return TPVForecastResponse(
        forecast=forecast,
        conformal_metadata=ConformalMetadata(
            half_width_dollars=forecast[0].tpv_ci_upper - forecast[0].tpv_mid,
            conformal_mode="extrapolation_fallback",
            pool_size=0,
        ),
        process_metadata=ProcessMetadata(
            context_len_used=len(context_months),
            context_mean_log_tpv=c_mean,
            context_mean_dollar=c_mean_dollar,
            momentum=momentum,
            pool_mean_used=c_mean,
            mcc=req.mcc,
            model_variant="tpv_fallback_extrapolation",
            horizon_months=req.horizon_months,
            confidence_interval=req.confidence_interval,
            generated_at_utc=generated_at,
        ),
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_tpv_forecast(req: TPVForecastRequest) -> TPVForecastResponse:
    generated_at = datetime.now(timezone.utc)

    # 1. Aggregate raw transactions into monthly summaries
    all_months = _aggregate_transactions(req.onboarding_merchant_txn_df)
    if not all_months:
        raise ValueError("No valid monthly data could be derived from the transactions.")

    # 2. Select context window
    context_months = _select_context_window(all_months)
    ctx_len = len(context_months)

    # 3. Resolve artifact bundle — returns None in degraded mode
    bundle = _resolve_bundle(req.mcc, ctx_len)
    if bundle is None:
        logger.warning(
            "[TPV] No artifacts for MCC %d — using extrapolation fallback",
            req.mcc,
        )
        return _fallback_forecast(context_months, req)

    # 4. Compute pool means + peer IDs from reference DB
    if _REPO is None:
        logger.warning("[TPV] No repository configured — using extrapolation fallback")
        return _fallback_forecast(context_months, req)

    try:
        flat_pool_mean, knn_pool_mean, peer_ids = _compute_pool_info(
            repo=_REPO, mcc=req.mcc, card_types=req.card_types,
            context_months=context_months,
        )
    except Exception as exc:
        logger.warning(
            "[TPV] Pool info lookup failed (DB schema mismatch?) — "
            "using extrapolation fallback: %s", exc,
        )
        return _fallback_forecast(context_months, req)

    # 5. Build features (log-space)
    log_vals = [np.log1p(m.total_processing_value) for m in context_months]
    c_mean = float(np.mean(log_vals))
    momentum = float(log_vals[-1] - c_mean)
    c_mean_dollar = float(np.expm1(c_mean))

    X_raw = _build_feature_vector(context_months, knn_pool_mean)
    X_scaled = bundle.scaler.transform(X_raw)

    # 6. Predict HORIZON_LEN steps in log-space
    log_preds = np.array(
        [bundle.models[h].predict(X_scaled)[0] for h in range(req.horizon_months)],
        dtype=float,
    )

    # 7. Back-transform to dollars
    dollar_preds = np.expm1(log_preds)

    # 8. Dollar-space conformal half-width
    hw, pool_size, conformal_mode, risk_score, strat_scheme = _compute_conformal_hw(
        peer_merchant_ids=peer_ids,
        bundle=bundle,
        context_months=context_months,
        pool_mean=flat_pool_mean,
        knn_pool_mean=knn_pool_mean,
        confidence_interval=req.confidence_interval,
    )

    # 9. Assemble forecast
    forecast = [
        ForecastMonth(
            month_index=h + 1,
            tpv_mid=float(dollar_preds[h]),
            tpv_ci_lower=max(0.0, float(dollar_preds[h]) - hw),
            tpv_ci_upper=float(dollar_preds[h]) + hw,
        )
        for h in range(req.horizon_months)
    ]

    conformal_meta = ConformalMetadata(
        half_width_dollars=hw,
        conformal_mode=conformal_mode,
        pool_size=pool_size,
        risk_score=risk_score,
        strat_scheme=strat_scheme,
    )

    process_meta = ProcessMetadata(
        context_len_used=ctx_len,
        context_mean_log_tpv=c_mean,
        context_mean_dollar=c_mean_dollar,
        momentum=momentum,
        pool_mean_used=knn_pool_mean,
        mcc=req.mcc,
        horizon_months=req.horizon_months,
        confidence_interval=req.confidence_interval,
        generated_at_utc=generated_at,
        artifact_trained_at=bundle.trained_at,
        strat_enabled=bundle.strat_enabled,
    )

    return TPVForecastResponse(
        forecast=forecast,
        conformal_metadata=conformal_meta,
        process_metadata=process_meta,
    )
