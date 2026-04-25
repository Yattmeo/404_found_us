"""
Embedded processing-cost forecast inference engine for ml_service.

Loads trained HuberRegressor + GBR risk-stratified conformal artifacts
from disk and runs inference directly inside ml_service — no separate
container needed.

Accepts pre-aggregated monthly context (CostForecastRequest.context_months)
and pool means pre-computed by the upstream composite merchant pipeline.
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

from .config import (
    ARTIFACT_POLL_INTERVAL_S,
    HORIZON_LEN,
    PROC_COST_ARTIFACTS_BASE_PATH,
    MIN_POOL,
    SUPPORTED_CONTEXT_LENS,
    SUPPORTED_MCCS,
    TARGET_COV,
    _VOL_EPS,
)
from .models import ContextMonth, CostForecastRequest


# ---------------------------------------------------------------------------
# Internal monthly summary
# ---------------------------------------------------------------------------

@dataclass
class _MonthSummary:
    year: int
    month: int
    avg_proc_cost_pct: float
    std_proc_cost_pct: float
    median_proc_cost_pct: float
    transaction_count: int
    avg_transaction_value: float
    std_txn_amount: float
    cost_type_pcts: Optional[Dict[str, float]] = None


def _context_month_to_summary(cm: ContextMonth) -> _MonthSummary:
    return _MonthSummary(
        year=cm.year,
        month=cm.month,
        avg_proc_cost_pct=cm.avg_proc_cost_pct,
        std_proc_cost_pct=cm.std_proc_cost_pct,
        median_proc_cost_pct=cm.median_proc_cost_pct,
        transaction_count=cm.transaction_count,
        avg_transaction_value=cm.avg_transaction_value,
        std_txn_amount=cm.std_txn_amount,
        cost_type_pcts=cm.cost_type_pcts,
    )


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
# Artifact loading helpers
# ---------------------------------------------------------------------------

def _artifact_dir(mcc: int, ctx_len: int) -> Path:
    return PROC_COST_ARTIFACTS_BASE_PATH / str(mcc) / str(ctx_len)


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


def initialize() -> None:
    """Load artifacts for all SUPPORTED_MCCS × SUPPORTED_CONTEXT_LENS."""
    loaded = 0
    for mcc in SUPPORTED_MCCS:
        for ctx_len in SUPPORTED_CONTEXT_LENS:
            d = _artifact_dir(mcc, ctx_len)
            if not (d / "config_snapshot.json").exists():
                print(
                    f"[ProcCost] No artifacts for MCC {mcc} ctx={ctx_len} at {d} — skipping"
                )
                continue
            try:
                bundle = _load_bundle(mcc, ctx_len)
                with _CACHE_LOCK:
                    _ARTIFACT_CACHE[(mcc, ctx_len)] = bundle
                loaded += 1
                print(
                    f"[ProcCost] Loaded MCC {mcc} ctx={ctx_len}  "
                    f"trained_at={bundle.trained_at}  strat={bundle.strat_enabled}"
                )
            except Exception as exc:
                print(f"[ProcCost] WARNING: failed to load MCC {mcc} ctx={ctx_len}: {exc}")
    if loaded == 0:
        print("[ProcCost] No artifacts loaded — service will use fallback mode.")
    else:
        start_artifact_watcher()


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
                    print(f"[ProcCost] Hot-reloaded MCC {mcc} ctx={ctx_len}")
            except Exception as exc:
                print(f"[ProcCost] WARNING: artifact reload failed: {exc}")


def start_artifact_watcher() -> None:
    t = threading.Thread(target=_poll_artifacts, daemon=True, name="proc-cost-artifact-watcher")
    t.start()


# ---------------------------------------------------------------------------
# Context window selection
# ---------------------------------------------------------------------------

def _select_context_window(months: List[_MonthSummary]) -> List[_MonthSummary]:
    n = len(months)
    valid = [cl for cl in sorted(SUPPORTED_CONTEXT_LENS, reverse=True) if cl <= n]
    if not valid:
        return months
    return months[-valid[0]:]


# ---------------------------------------------------------------------------
# Bundle resolution
# ---------------------------------------------------------------------------

def _resolve_bundle(mcc: int, ctx_len: int) -> ArtifactBundle:
    with _CACHE_LOCK:
        bundle = _ARTIFACT_CACHE.get((mcc, ctx_len))
    if bundle is not None:
        return bundle

    with _CACHE_LOCK:
        available = sorted([cl for (m, cl) in _ARTIFACT_CACHE if m == mcc])
    if not available:
        raise ValueError(
            f"MCC {mcc} has no loaded artifacts. Available MCCs: "
            f"{sorted(set(m for m, _ in _ARTIFACT_CACHE.keys()))}"
        )
    nearest = min(available, key=lambda cl: abs(cl - ctx_len))
    with _CACHE_LOCK:
        return _ARTIFACT_CACHE[(mcc, nearest)]


# ---------------------------------------------------------------------------
# Feature engineering (matches proc_cost training features exactly)
# ---------------------------------------------------------------------------

def _build_feature_vector(
    context_months: List[_MonthSummary], pool_mean: float
) -> np.ndarray:
    vals = np.array([m.avg_proc_cost_pct for m in context_months], dtype=float)
    c_mean = float(np.mean(vals))
    c_std = float(np.std(vals))
    momentum = float(vals[-1] - c_mean)
    intra_std = float(np.mean([m.std_proc_cost_pct for m in context_months]))
    log_txn = float(np.log1p(np.mean([m.transaction_count for m in context_months])))
    medians = np.array([m.median_proc_cost_pct for m in context_months], dtype=float)
    mean_median_gap = float(np.mean(np.abs(vals - medians)))
    return np.array(
        [[c_mean, c_std, momentum, pool_mean, intra_std, log_txn, mean_median_gap]],
        dtype=float,
    )


def _build_risk_vector(
    context_months: List[_MonthSummary], pool_mean: float, knn_pool_mean: float
) -> np.ndarray:
    vals = np.array([m.avg_proc_cost_pct for m in context_months], dtype=float)
    c_mean = float(np.mean(vals))
    _denom = c_mean + _VOL_EPS

    intra_cov = float(np.mean([m.std_proc_cost_pct for m in context_months])) / _denom
    medians = np.array([m.median_proc_cost_pct for m in context_months], dtype=float)
    mean_median_gap = float(np.mean(np.abs(vals - medians))) / _denom
    log_txn_count = float(np.log1p(np.mean([m.transaction_count for m in context_months])))

    ct_vals_list = []
    for m in context_months:
        if m.cost_type_pcts:
            ct_vals_list.append(list(m.cost_type_pcts.values()))
    cost_type_hhi = float(np.sum(np.mean(ct_vals_list, axis=0) ** 2)) if ct_vals_list else 1.0

    avg_txn_val = float(np.mean([m.avg_transaction_value for m in context_months]))
    log_avg_txn_val = float(np.log1p(avg_txn_val))
    txn_amount_cov = float(np.mean([m.std_txn_amount for m in context_months])) / (avg_txn_val + _VOL_EPS)

    pool_gap = abs(c_mean - pool_mean) / (pool_mean + _VOL_EPS)
    knn_gap = abs(c_mean - knn_pool_mean) / (knn_pool_mean + _VOL_EPS)
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
    # Tier 1: local peer pool
    peer_residuals: List[float] = []
    if peer_merchant_ids:
        for pid in peer_merchant_ids:
            peer_residuals.extend(bundle.cal_residuals.get(pid, []))

    if len(peer_residuals) >= MIN_POOL:
        q = _adaptive_q(peer_residuals, target=confidence_interval)
        if q is not None:
            return float(q), len(peer_residuals), "local", None, None

    # Compute risk score for tier 2
    risk_vec = _build_risk_vector(context_months, pool_mean, knn_pool_mean)
    scores = np.array([m.predict(risk_vec)[0] for m in bundle.risk_models], dtype=float)
    risk_score = float(np.max(scores))

    # Tier 2: GBR-stratified continuous width mapping
    if bundle.strat_enabled and bundle.strat_knot_x is not None:
        hw = float(np.interp(
            risk_score,
            bundle.strat_knot_x,
            bundle.strat_q_vals,
            left=bundle.strat_q_vals[0],
            right=bundle.strat_q_vals[-1],
        ))
        return hw, len(peer_residuals), "stratified", risk_score, bundle.strat_scheme

    # Tier 3: global fallback
    return bundle.global_q90, len(peer_residuals), "global_fallback", risk_score, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_proc_cost_monthly_forecast(req: CostForecastRequest) -> dict:
    """
    Run processing-cost inference on pre-aggregated monthly context.

    Returns a dict with keys: forecast, conformal_metadata, process_metadata.
    forecast is a list of monthly items (3 months), NOT weekly.
    """
    generated_at = datetime.now(timezone.utc)

    if not _ARTIFACT_CACHE:
        raise RuntimeError(
            "Processing cost forecast artifacts not loaded. "
            "Either train.py has not been run or PROC_COST_ARTIFACTS_BASE_PATH is misconfigured."
        )

    # Convert ContextMonth → _MonthSummary
    all_months = [_context_month_to_summary(cm) for cm in req.context_months]
    if not all_months:
        raise ValueError("context_months is empty.")

    # Select context window (last 1/3/6 months)
    context_months = _select_context_window(all_months)
    ctx_len = len(context_months)

    # Resolve artifact bundle
    bundle = _resolve_bundle(req.mcc, ctx_len)

    # Pool means provided by caller (pre-computed by composite merchant pipeline)
    knn_pool_mean = req.knn_pool_mean_at_context_end
    flat_pool_mean = req.pool_mean_at_context_end

    # Build feature vector and scale
    X_raw = _build_feature_vector(context_months, knn_pool_mean)
    X_scaled = bundle.scaler.transform(X_raw)

    # Predict HORIZON months
    horizon = min(req.horizon_months, HORIZON_LEN)
    point_forecasts = np.array(
        [bundle.models[h].predict(X_scaled)[0] for h in range(horizon)],
        dtype=float,
    )

    # Conformal half-width
    hw, pool_size, conformal_mode, risk_score, strat_scheme = _compute_conformal_hw(
        peer_merchant_ids=req.peer_merchant_ids,
        bundle=bundle,
        context_months=context_months,
        pool_mean=flat_pool_mean,
        knn_pool_mean=knn_pool_mean,
        confidence_interval=req.confidence_interval,
    )

    vals = [m.avg_proc_cost_pct for m in context_months]
    c_mean = float(np.mean(vals))
    c_std = float(np.std(vals))
    momentum = float(vals[-1] - c_mean)

    return {
        "forecast": [
            {
                "month_index": h + 1,
                "proc_cost_pct_mid": round(float(point_forecasts[h]), 6),
                "proc_cost_pct_ci_lower": round(max(0.0, float(point_forecasts[h]) - hw), 6),
                "proc_cost_pct_ci_upper": round(float(point_forecasts[h]) + hw, 6),
            }
            for h in range(horizon)
        ],
        "conformal_metadata": {
            "half_width": hw,
            "conformal_mode": conformal_mode,
            "pool_size": pool_size,
            "risk_score": risk_score,
            "strat_scheme": strat_scheme,
        },
        "process_metadata": {
            "context_len_used": ctx_len,
            "context_mean": c_mean,
            "context_std": c_std,
            "momentum": momentum,
            "pool_mean_used": knn_pool_mean,
            "mcc": req.mcc,
            "model_variant": "proc_cost_embedded",
            "horizon_months": horizon,
            "confidence_interval": req.confidence_interval,
            "generated_at_utc": generated_at.isoformat(),
            "artifact_trained_at": bundle.trained_at or "unknown",
            "strat_enabled": bundle.strat_enabled,
        },
    }


def get_proc_cost_health() -> dict:
    """Return artifact status (no HTTP call needed)."""
    with _CACHE_LOCK:
        loaded = [
            {
                "mcc": mcc,
                "ctx_len": ctx_len,
                "trained_at": bundle.trained_at,
                "strat_enabled": bundle.strat_enabled,
            }
            for (mcc, ctx_len), bundle in _ARTIFACT_CACHE.items()
        ]
    return {
        "status": "ok" if _ARTIFACT_CACHE else "degraded",
        "supported_mccs": SUPPORTED_MCCS,
        "loaded_bundles": loaded,
    }
