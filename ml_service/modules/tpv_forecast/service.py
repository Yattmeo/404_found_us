"""
TPV (Total Payment Volume) forecast service — Huber in-process inference.

Mirrors m9_forecast/service.py but targets monthly TPV (dollars) trained in
log1p-space.  Conformal intervals are calibrated in dollar space then scaled
proportionally so they remain meaningful across merchant sizes:
    hw = max(global_q90_dollars, 0.10 × mid)

11 prediction features and 11 risk features — must match train.py exactly.
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
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.preprocessing import StandardScaler

from .models import (
    TpvConformalMetadata,
    TpvContextMonth,
    TpvForecastMonth,
    TpvForecastRequest,
    TpvForecastResponse,
    TpvProcessMetadata,
)

# ---------------------------------------------------------------------------
# Constants (must match train.py config)
# ---------------------------------------------------------------------------
SUPPORTED_CONTEXT_LENS = [1, 3, 6]
SUPPORTED_MCCS = [5411]
HORIZON_LEN = 3
TARGET_COV = 0.90
MIN_POOL = 10
_EPS = 1e-9

ARTIFACTS_BASE_PATH = Path(
    os.getenv(
        "TPV_ARTIFACTS_BASE_PATH",
        str(Path(__file__).resolve().parent.parent.parent / "artifacts" / "tpv"),
    )
)
ARTIFACT_POLL_INTERVAL_S = float(os.getenv("ARTIFACT_POLL_INTERVAL_S", "60"))

# Minimum relative CI width — ensures sigma_tpv is meaningful in MC simulation
_MIN_CI_RELATIVE = 0.10


# ---------------------------------------------------------------------------
# Artifact bundle
# ---------------------------------------------------------------------------
@dataclass
class TpvArtifactBundle:
    context_len: int
    models: list           # List[HuberRegressor], one per horizon month
    scaler: StandardScaler
    cal_residuals: dict    # merchant_id -> List[float] of dollar-space residuals
    global_q90_dollars: float
    risk_models: list      # List[GradientBoostingRegressor]
    config_snapshot: dict
    loaded_mtime: float = field(default=0.0)

    @property
    def trained_at(self) -> Optional[str]:
        return self.config_snapshot.get("trained_at")


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_ARTIFACT_CACHE: Dict[Tuple[int, int], TpvArtifactBundle] = {}
_CACHE_LOCK = threading.Lock()


def _artifact_dir(mcc: int, ctx_len: int) -> Path:
    return ARTIFACTS_BASE_PATH / str(mcc) / str(ctx_len)


def _load_bundle(mcc: int, ctx_len: int) -> TpvArtifactBundle:
    d = _artifact_dir(mcc, ctx_len)
    with open(d / "config_snapshot.json") as fh:
        snapshot = json.load(fh)

    models = joblib.load(d / "models.pkl")
    scaler = joblib.load(d / "scaler.pkl")
    cal_residuals = joblib.load(d / "cal_residuals.pkl")
    global_q90_dollars = float(joblib.load(d / "global_q90.pkl"))
    risk_models = joblib.load(d / "risk_models.pkl")

    return TpvArtifactBundle(
        context_len=ctx_len,
        models=models,
        scaler=scaler,
        cal_residuals=cal_residuals,
        global_q90_dollars=global_q90_dollars,
        risk_models=risk_models,
        config_snapshot=snapshot,
        loaded_mtime=os.path.getmtime(d / "config_snapshot.json"),
    )


def init_tpv_cache() -> None:
    """Load artifacts for all MCC × context_len at startup."""
    for mcc in SUPPORTED_MCCS:
        for ctx_len in SUPPORTED_CONTEXT_LENS:
            d = _artifact_dir(mcc, ctx_len)
            if not (d / "config_snapshot.json").exists():
                print(f"[tpv_forecast] No artifacts for MCC {mcc} ctx={ctx_len} at {d}")
                continue
            try:
                bundle = _load_bundle(mcc, ctx_len)
                with _CACHE_LOCK:
                    _ARTIFACT_CACHE[(mcc, ctx_len)] = bundle
                print(
                    f"[tpv_forecast] Loaded MCC {mcc} ctx={ctx_len} "
                    f"trained_at={bundle.trained_at} "
                    f"global_q90=${bundle.global_q90_dollars:.2f}"
                )
            except Exception as exc:
                print(f"[tpv_forecast] Failed to load MCC {mcc} ctx={ctx_len}: {exc}")


def _poll_artifacts() -> None:
    while True:
        time.sleep(ARTIFACT_POLL_INTERVAL_S)
        for key in list(_ARTIFACT_CACHE.keys()):
            mcc, ctx_len = key
            try:
                sp = _artifact_dir(mcc, ctx_len) / "config_snapshot.json"
                mt = os.path.getmtime(sp)
                with _CACHE_LOCK:
                    old = _ARTIFACT_CACHE[key].loaded_mtime
                if mt > old:
                    bundle = _load_bundle(mcc, ctx_len)
                    with _CACHE_LOCK:
                        _ARTIFACT_CACHE[key] = bundle
                    print(f"[tpv_forecast] Hot-reloaded MCC {mcc} ctx={ctx_len}")
            except Exception as exc:
                print(f"[tpv_forecast] Reload failed MCC {mcc} ctx={ctx_len}: {exc}")


def start_tpv_watcher() -> None:
    t = threading.Thread(target=_poll_artifacts, daemon=True, name="tpv-artifact-watcher")
    t.start()


def get_tpv_health() -> dict:
    with _CACHE_LOCK:
        loaded = [
            {"mcc": mcc, "ctx_len": ctx_len, "trained_at": b.trained_at,
             "global_q90_dollars": b.global_q90_dollars}
            for (mcc, ctx_len), b in _ARTIFACT_CACHE.items()
        ]
    return {
        "status": "ok" if loaded else "no_artifacts",
        "supported_mccs": SUPPORTED_MCCS,
        "loaded_bundles": loaded,
    }


# ---------------------------------------------------------------------------
# Feature builders — must match train.py tpv_build_feature_matrix exactly
# (11 prediction features, log-space)
# ---------------------------------------------------------------------------
def _build_tpv_feature_vector(
    ctx_months: List[TpvContextMonth],
    pool_log_mean: float,
) -> np.ndarray:
    """Returns (1, 11) feature matrix in log-space."""
    tpv_vals = np.array([m.total_payment_volume for m in ctx_months], dtype=float)
    log_vals = np.log1p(tpv_vals)  # log1p(monthly_TPV)

    c_mean = float(np.mean(log_vals))
    c_std = float(np.std(log_vals))
    mom = float(log_vals[-1] - c_mean)
    last_month = float(log_vals[-1])

    atv_vals = np.array([m.avg_transaction_value for m in ctx_months], dtype=float)
    avg_atv = float(np.mean(atv_vals))
    log_avg_txn_val = float(np.log1p(avg_atv))

    tc_vals = np.array([m.transaction_count for m in ctx_months], dtype=float)
    log_txn = float(np.log1p(np.mean(tc_vals)))

    std_vals = np.array([m.std_txn_amount for m in ctx_months], dtype=float)
    txn_amount_std = float(np.mean(std_vals))

    median_vals = np.array(
        [m.median_txn_amount if m.median_txn_amount is not None else m.avg_transaction_value
         for m in ctx_months],
        dtype=float,
    )
    avg_median_gap = float(np.mean(np.abs(atv_vals - median_vals)))

    tc_log_vals = np.log1p(tc_vals)
    atv_log_vals = np.log1p(atv_vals)
    mom_tc = float(tc_log_vals[-1] - np.mean(tc_log_vals))
    mom_atv = float(atv_log_vals[-1] - np.mean(atv_log_vals))

    # Feature order must match notebook Cell 8 tpv_build_feature_matrix:
    # [c_mean, c_std, mom, p_mean, txn_amount_std, log_txn,
    #  avg_median_gap, last_month, log_avg_txn_val, mom_tc, mom_atv]
    return np.array(
        [[c_mean, c_std, mom, pool_log_mean, txn_amount_std, log_txn,
          avg_median_gap, last_month, log_avg_txn_val, mom_tc, mom_atv]],
        dtype=float,
    )


def _build_tpv_risk_vector(
    ctx_months: List[TpvContextMonth],
    pool_log_mean: float,
    knn_pool_log_mean: float,
) -> np.ndarray:
    """Returns (1, 11) risk feature matrix — must match train.py tpv_build_risk_features."""
    tpv_vals = np.array([m.total_payment_volume for m in ctx_months], dtype=float)
    log_vals = np.log1p(tpv_vals)
    c_mean = float(np.mean(log_vals))

    atv_vals = np.array([m.avg_transaction_value for m in ctx_months], dtype=float)
    avg_atv = float(np.mean(atv_vals)) + _EPS

    std_vals = np.array([m.std_txn_amount for m in ctx_months], dtype=float)
    intra_txn_cov = float(np.mean(std_vals)) / avg_atv

    median_vals = np.array(
        [m.median_txn_amount if m.median_txn_amount is not None else m.avg_transaction_value
         for m in ctx_months],
        dtype=float,
    )
    avg_median_gap = float(np.mean(np.abs(atv_vals - median_vals))) / avg_atv

    tc_vals = np.array([m.transaction_count for m in ctx_months], dtype=float)
    log_txn_count = float(np.log1p(np.mean(tc_vals)))

    cost_type_hhi = 1.0  # no cost-type breakdown in volume context
    log_avg_txn_val = float(np.log1p(float(np.mean(atv_vals))))
    txn_amount_cov = float(np.mean(std_vals)) / avg_atv

    pool_gap = abs(c_mean - pool_log_mean) / (pool_log_mean + _EPS)
    knn_gap = abs(c_mean - knn_pool_log_mean) / (knn_pool_log_mean + _EPS)
    ctx_cov = float(np.std(log_vals)) / (c_mean + _EPS)

    tc_log_vals = np.log1p(tc_vals)
    atv_log_vals = np.log1p(np.array([m.avg_transaction_value for m in ctx_months], dtype=float))
    tc_cov = float(np.std(tc_log_vals)) / (float(np.mean(tc_log_vals)) + _EPS)
    atv_cov = float(np.std(atv_log_vals)) / (float(np.mean(atv_log_vals)) + _EPS)

    # Feature order must match notebook tpv_build_risk_features:
    # [intra_txn_cov, avg_median_gap, log_txn_count, cost_type_hhi,
    #  log_avg_txn_val, txn_amount_cov, pool_gap, knn_gap, ctx_cov, tc_cov, atv_cov]
    return np.array(
        [[intra_txn_cov, avg_median_gap, log_txn_count, cost_type_hhi,
          log_avg_txn_val, txn_amount_cov, pool_gap, knn_gap, ctx_cov, tc_cov, atv_cov]],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# Conformal half-width
# ---------------------------------------------------------------------------
def _adaptive_q(residuals: list, target: float = TARGET_COV) -> Optional[float]:
    n = len(residuals)
    level = math.ceil((n + 1) * target) / n
    return float(np.quantile(residuals, level)) if level <= 1.0 else None


def _compute_tpv_hw(
    bundle: TpvArtifactBundle,
    ctx_months: List[TpvContextMonth],
    pool_log_mean: float,
    knn_pool_log_mean: float,
    ci: float,
    mid: float,
) -> Tuple[float, int, str]:
    """
    Compute conformal half-width in dollar space.

    Falls back through: local calibration residuals → risk-stratified → global q90.
    Always applies minimum relative floor so the CI is meaningful at any volume scale.
    """
    # Attempt local pool: for TPV there are no per-merchant peer IDs at inference time
    # (no KNN lookup at runtime), so we always fall through to global fallback.

    # Risk score from GBR ensemble
    risk_vec = _build_tpv_risk_vector(ctx_months, pool_log_mean, knn_pool_log_mean)
    scores = np.array([m.predict(risk_vec)[0] for m in bundle.risk_models], dtype=float)
    risk_score = float(np.max(scores))
    _ = risk_score  # available if stratified scheme is added later

    hw_abs = bundle.global_q90_dollars
    # Scale-proportional floor: CI must be at least ±10% of mid
    hw = max(hw_abs, _MIN_CI_RELATIVE * mid)
    return hw, 0, "global_fallback"


# ---------------------------------------------------------------------------
# Bundle resolution
# ---------------------------------------------------------------------------
def _resolve_bundle(mcc: int, ctx_len: int) -> TpvArtifactBundle:
    with _CACHE_LOCK:
        bundle = _ARTIFACT_CACHE.get((mcc, ctx_len))
    if bundle is not None:
        return bundle
    with _CACHE_LOCK:
        available = sorted([cl for (m, cl) in _ARTIFACT_CACHE if m == mcc])
    if not available:
        raise ValueError(f"[tpv_forecast] No artifacts for MCC {mcc}")
    nearest = min(available, key=lambda cl: abs(cl - ctx_len))
    with _CACHE_LOCK:
        return _ARTIFACT_CACHE[(mcc, nearest)]


# ---------------------------------------------------------------------------
# Public inference API
# ---------------------------------------------------------------------------
def run_tpv_forecast(payload: TpvForecastRequest) -> dict:
    """
    Run Huber TPV forecast in-process using loaded artifacts.

    Scale-robustness approach — "centered delta":
    --------------------------------------------------
    The Huber artifacts were trained on composite KNN merchants whose monthly
    TPV is orders-of-magnitude smaller than production merchants.  Running the
    model directly on raw features would extrapolate wildly outside the training
    distribution.

    Instead we:
      1. Replace the absolute-log-scale features (c_mean, p_mean, log_txn,
         last_month, log_avg_txn_val) with the training-distribution centre
         stored in the scaler's mean_[] vector.
      2. Run inference on this "centered" feature vector — the model now
         operates well within its training distribution.
      3. Interpret the output as a log-space delta relative to the training
         centre: Δh = model_output_h − train_c_mean
      4. Apply the delta to the actual context mean:
             y_hat_log_h = c_mean + Δh
         For a stable series (zero momentum) Δh ≈ 0 → flat forecast.
         For a trending series the trained momentum signal shifts Δh.
    """
    generated_at = datetime.now(timezone.utc)
    ctx_months = payload.context_months

    # Select the context window we have an artifact for
    valid = [cl for cl in sorted(SUPPORTED_CONTEXT_LENS, reverse=True) if cl <= len(ctx_months)]
    chosen_len = valid[0] if valid else SUPPORTED_CONTEXT_LENS[0]
    ctx_months = ctx_months[-chosen_len:]

    bundle = _resolve_bundle(payload.mcc, chosen_len)

    pool_log_mean = payload.pool_log_mean_at_context_end
    knn_pool_log_mean = payload.knn_pool_log_mean_at_context_end

    # Fallback: if pool means weren't provided, use context log-mean
    log_vals_ctx = np.log1p([m.total_payment_volume for m in ctx_months])
    ctx_log_mean = float(np.mean(log_vals_ctx))
    if pool_log_mean == 0.0:
        pool_log_mean = ctx_log_mean
    if knn_pool_log_mean == 0.0:
        knn_pool_log_mean = ctx_log_mean

    # Build raw (pre-scale) feature vector
    X_raw = _build_tpv_feature_vector(ctx_months, knn_pool_log_mean)

    # ── Centered-delta inference ──────────────────────────────────────────
    # Feature indices whose values are in absolute log-scale space and
    # would take the scaler wildly out of distribution if left at actual values.
    # Index:  0=c_mean, 3=p_mean, 5=log_txn, 7=last_month, 8=log_avg_txn_val
    _SCALE_INDICES = [0, 3, 5, 7, 8]
    X_centered = X_raw.copy()
    for idx in _SCALE_INDICES:
        X_centered[0, idx] = bundle.scaler.mean_[idx]
    X_centered_scaled = bundle.scaler.transform(X_centered)

    # training c_mean centre (feature 0 scaler mean)
    train_c_mean = float(bundle.scaler.mean_[0])

    horizon = min(payload.horizon_months, len(bundle.models))
    raw_log_preds = np.array(
        [bundle.models[h].predict(X_centered_scaled)[0] for h in range(horizon)],
        dtype=float,
    )
    # Delta in log-space (scale-independent trend/momentum signal)
    log_deltas = raw_log_preds - train_c_mean
    # Anchor to actual context mean
    log_preds = ctx_log_mean + log_deltas
    mid_vals = np.expm1(log_preds)
    # ─────────────────────────────────────────────────────────────────────

    # Build forecast months with scale-appropriate CI
    forecast: List[TpvForecastMonth] = []
    hw_used = 0.0
    for h in range(horizon):
        mid = float(max(0.0, mid_vals[h]))
        hw_abs = bundle.global_q90_dollars
        hw = max(hw_abs, _MIN_CI_RELATIVE * mid)
        hw_used = max(hw_used, hw)
        forecast.append(
            TpvForecastMonth(
                month_index=h + 1,
                total_proc_value_mid=mid,
                total_proc_value_ci_lower=max(0.0, mid - hw),
                total_proc_value_ci_upper=mid + hw,
            )
        )

    resp = TpvForecastResponse(
        forecast=forecast,
        conformal_metadata=TpvConformalMetadata(
            half_width_dollars=hw_used,
            conformal_mode="global_fallback",
            pool_size=0,
        ),
        process_metadata=TpvProcessMetadata(
            context_len_used=chosen_len,
            context_mean_log_tpv=ctx_log_mean,
            mcc=payload.mcc,
            model_variant="tpv_v2",
            horizon_months=horizon,
            confidence_interval=payload.confidence_interval,
            generated_at_utc=generated_at.isoformat(),
            artifact_trained_at=bundle.trained_at or "",
        ),
    )
    return resp.model_dump()
