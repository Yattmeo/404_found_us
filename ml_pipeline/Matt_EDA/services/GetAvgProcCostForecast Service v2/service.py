"""
GetM9MonthlyCostForecast — v2 inference service.

Loads serialised M9-v2 model artifacts at startup (one set per MCC × context_len)
and serves sub-millisecond predictions.  A background thread hot-reloads artifacts
when train.py writes a newer config_snapshot.json, so a monthly batch retrain is
picked up within ARTIFACT_POLL_INTERVAL_S seconds without a service restart.

Inference path (per request):
  1. Validate MCC; select artifact bundle for the request's context length.
  2. Build 7-feature vector [context_mean, context_std, momentum, pool_mean,
     intra_std, log_txn_count, mean_median_gap].
  3. Scale with the stored StandardScaler.
  4. Predict 3 horizon steps with the stored HuberRegressor models.
  5. Compute conformal half-width:
       (a) local  — adaptive_q on peer calibration residuals (>= MIN_POOL)
       (b) GBR-stratified — continuous width mapping based on risk score
       (c) global — entire calibration set q90
  6. Return M9ForecastResponse with forecast + full metadata.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.preprocessing import StandardScaler

from config import (
    ARTIFACT_POLL_INTERVAL_S,
    ARTIFACTS_BASE_PATH,
    HORIZON_LEN,
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
# v2 model feature construction (7 features)
# ---------------------------------------------------------------------------

def _build_feature_vector(
    context_months: list,
    pool_mean: float,
) -> np.ndarray:
    """
    Build the 7-feature row used by M9 v2:
        [context_mean, context_std, momentum, pool_mean,
         intra_std, log_txn_count, mean_median_gap]

    context_months — list of ContextMonth pydantic objects.
    pool_mean      — kNN peer pool mean at the context window end-date.

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
    context_months: list,
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
    context_months: list,
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

    # ── 1. Resolve artifact bundle for this context length ───────────────────
    ctx_len = len(req.context_months)
    bundle = _resolve_bundle(req.mcc, ctx_len)

    # ── 2. Build v2 model features ──────────────────────────────────────────
    context_months = req.context_months
    vals = [m.avg_proc_cost_pct for m in context_months]
    c_mean = float(np.mean(vals))
    c_std = float(np.std(vals))
    momentum = float(vals[-1] - c_mean)

    X_raw = _build_feature_vector(context_months, req.pool_mean_at_context_end)
    X_scaled = bundle.scaler.transform(X_raw)

    # ── 3. Predict HORIZON_LEN steps ────────────────────────────────────────
    point_forecasts = np.array(
        [bundle.models[h].predict(X_scaled)[0] for h in range(req.horizon_months)],
        dtype=float,
    )

    # ── 4. Conformal half-width ──────────────────────────────────────────────
    hw, pool_size, conformal_mode, risk_score, strat_scheme = _compute_conformal_hw(
        peer_merchant_ids=req.peer_merchant_ids,
        bundle=bundle,
        context_months=context_months,
        pool_mean=req.pool_mean_at_context_end,
        knn_pool_mean=req.knn_pool_mean_at_context_end,
        confidence_interval=req.confidence_interval,
    )

    # ── 5. Assemble forecast months ──────────────────────────────────────────
    forecast = [
        ForecastMonth(
            month_index=h + 1,
            proc_cost_pct_mid=float(point_forecasts[h]),
            proc_cost_pct_ci_lower=max(0.0, float(point_forecasts[h]) - hw),
            proc_cost_pct_ci_upper=float(point_forecasts[h]) + hw,
        )
        for h in range(req.horizon_months)
    ]

    # ── 6. Assemble metadata ─────────────────────────────────────────────────
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
        pool_mean_used=req.pool_mean_at_context_end,
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
