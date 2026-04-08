"""
M9 forecast service — in-process artifact-based inference.

Replaces the former thin proxy that forwarded to a separate m9-forecast-service
container.  Now loads artifact bundles from ml_service/artifacts/m9/{mcc}/{ctx_len}/
and runs inference directly inside ml_service.
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
    ConformalMetadata,
    ContextMonth,
    ForecastMonth,
    M9ForecastRequest,
    M9ForecastResponse,
    ProcessMetadata,
)

# ---------------------------------------------------------------------------
# Constants (must match train.py config)
# ---------------------------------------------------------------------------
SUPPORTED_CONTEXT_LENS = [1, 3, 6]
SUPPORTED_MCCS = [5411]
HORIZON_LEN = 3
TARGET_COV = 0.90
MIN_POOL = 10
KNN_K = 10
_VOL_EPS = 1e-6

ARTIFACTS_BASE_PATH = Path(
    os.getenv("M9_ARTIFACTS_BASE_PATH",
              str(Path(__file__).resolve().parent.parent.parent / "artifacts" / "m9"))
)
ARTIFACT_POLL_INTERVAL_S = float(os.getenv("ARTIFACT_POLL_INTERVAL_S", "60"))


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
# Cache
# ---------------------------------------------------------------------------
_ARTIFACT_CACHE: Dict[Tuple[int, int], ArtifactBundle] = {}
_CACHE_LOCK = threading.Lock()


def _artifact_dir(mcc: int, ctx_len: int) -> Path:
    return ARTIFACTS_BASE_PATH / str(mcc) / str(ctx_len)


def _load_bundle(mcc: int, ctx_len: int) -> ArtifactBundle:
    d = _artifact_dir(mcc, ctx_len)
    snapshot_path = d / "config_snapshot.json"
    with open(snapshot_path) as f:
        snapshot = json.load(f)

    models = joblib.load(d / "models.pkl")
    scaler = joblib.load(d / "scaler.pkl")
    cal_residuals = joblib.load(d / "cal_residuals.pkl")
    global_q90 = joblib.load(d / "global_q90.pkl")
    risk_models = joblib.load(d / "risk_models.pkl")

    strat_enabled = snapshot.get("strat_enabled", False)
    strat_scheme = snapshot.get("strat_scheme")
    strat_knot_x = strat_q_vals = None
    if strat_enabled:
        strat_knot_x = joblib.load(d / "strat_knot_x.pkl")
        strat_q_vals = joblib.load(d / "strat_q_vals.pkl")

    return ArtifactBundle(
        context_len=ctx_len, models=models, scaler=scaler,
        cal_residuals=cal_residuals, global_q90=global_q90,
        risk_models=risk_models, strat_enabled=strat_enabled,
        strat_scheme=strat_scheme, strat_knot_x=strat_knot_x,
        strat_q_vals=strat_q_vals, config_snapshot=snapshot,
        loaded_mtime=os.path.getmtime(d / "config_snapshot.json"),
    )


def init_m9_cache() -> None:
    """Load artifacts for all MCC × context_len at startup."""
    for mcc in SUPPORTED_MCCS:
        for ctx_len in SUPPORTED_CONTEXT_LENS:
            d = _artifact_dir(mcc, ctx_len)
            if not (d / "config_snapshot.json").exists():
                print(f"[m9_forecast] No artifacts for MCC {mcc} ctx={ctx_len} at {d}")
                continue
            bundle = _load_bundle(mcc, ctx_len)
            with _CACHE_LOCK:
                _ARTIFACT_CACHE[(mcc, ctx_len)] = bundle
            print(f"[m9_forecast] Loaded MCC {mcc} ctx={ctx_len} trained_at={bundle.trained_at}")


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
                    print(f"[m9_forecast] Hot-reloaded MCC {mcc} ctx={ctx_len}")
            except Exception as exc:
                print(f"[m9_forecast] Reload failed MCC {mcc} ctx={ctx_len}: {exc}")


def start_m9_watcher() -> None:
    t = threading.Thread(target=_poll_artifacts, daemon=True, name="m9-artifact-watcher")
    t.start()


def get_m9_health() -> dict:
    loaded = []
    for (mcc, ctx_len), b in _ARTIFACT_CACHE.items():
        loaded.append({"mcc": mcc, "ctx_len": ctx_len,
                        "trained_at": b.trained_at, "strat_enabled": b.strat_enabled})
    return {"status": "ok" if loaded else "no_artifacts",
            "supported_mccs": SUPPORTED_MCCS, "loaded_bundles": loaded}


# ---------------------------------------------------------------------------
# Feature builders (must match train.py exactly)
# ---------------------------------------------------------------------------
def _build_feature_vector(ctx_months: List[ContextMonth], pool_mean: float) -> np.ndarray:
    """(1, 7) feature vector."""
    vals = np.array([m.avg_proc_cost_pct for m in ctx_months], dtype=float)
    c_mean = float(np.mean(vals))
    c_std = float(np.std(vals))
    momentum = float(vals[-1] - c_mean)
    intra_std = float(np.mean([m.std_proc_cost_pct for m in ctx_months]))
    log_txn = float(np.log1p(np.mean([m.transaction_count for m in ctx_months])))
    medians = np.array([m.median_proc_cost_pct for m in ctx_months], dtype=float)
    mean_median_gap = float(np.mean(np.abs(vals - medians)))
    return np.array([[c_mean, c_std, momentum, pool_mean,
                      intra_std, log_txn, mean_median_gap]], dtype=float)


def _build_risk_vector(ctx_months: List[ContextMonth],
                       pool_mean: float, knn_pool_mean: float) -> np.ndarray:
    """(1, 9) risk feature vector."""
    vals = np.array([m.avg_proc_cost_pct for m in ctx_months], dtype=float)
    c_mean = float(np.mean(vals))
    _denom = c_mean + _VOL_EPS

    intra_cov = float(np.mean([m.std_proc_cost_pct for m in ctx_months])) / _denom
    medians = np.array([m.median_proc_cost_pct for m in ctx_months], dtype=float)
    mean_median_gap = float(np.mean(np.abs(vals - medians))) / _denom
    log_txn_count = float(np.log1p(np.mean([m.transaction_count for m in ctx_months])))

    ct_vals_list = []
    for m in ctx_months:
        if m.cost_type_pcts:
            ct_vals_list.append(list(m.cost_type_pcts.values()))
    if ct_vals_list:
        avg_ct = np.mean(ct_vals_list, axis=0)
        cost_type_hhi = float(np.sum(avg_ct ** 2))
    else:
        cost_type_hhi = 1.0

    avg_txn_val = float(np.mean([m.avg_transaction_value for m in ctx_months]))
    log_avg_txn_val = float(np.log1p(avg_txn_val))
    txn_amount_cov = float(np.mean([m.std_txn_amount for m in ctx_months])) / (avg_txn_val + _VOL_EPS)

    pool_gap = abs(c_mean - pool_mean) / (pool_mean + _VOL_EPS)
    knn_gap = abs(c_mean - knn_pool_mean) / (knn_pool_mean + _VOL_EPS)
    ctx_cov = float(np.std(vals)) / _denom

    return np.array([[intra_cov, mean_median_gap, log_txn_count,
                      cost_type_hhi, log_avg_txn_val, txn_amount_cov,
                      pool_gap, knn_gap, ctx_cov]], dtype=float)


# ---------------------------------------------------------------------------
# Conformal
# ---------------------------------------------------------------------------
def _adaptive_q(residuals: List[float], target: float = TARGET_COV) -> Optional[float]:
    n = len(residuals)
    level = math.ceil((n + 1) * target) / n
    return float(np.quantile(residuals, level)) if level <= 1.0 else None


def _compute_conformal_hw(
    peer_ids: Optional[List[int]], bundle: ArtifactBundle,
    ctx_months: List[ContextMonth], pool_mean: float, knn_pool_mean: float,
    ci: float,
) -> Tuple[float, int, str, Optional[float], Optional[str]]:
    peer_residuals: List[float] = []
    if peer_ids:
        for pid in peer_ids:
            peer_residuals.extend(bundle.cal_residuals.get(pid, []))
    if len(peer_residuals) >= MIN_POOL:
        q = _adaptive_q(peer_residuals, target=ci)
        if q is not None:
            return float(q), len(peer_residuals), "local", None, None

    risk_vec = _build_risk_vector(ctx_months, pool_mean, knn_pool_mean)
    scores = np.array([m.predict(risk_vec)[0] for m in bundle.risk_models], dtype=float)
    risk_score = float(np.max(scores))

    if bundle.strat_enabled and bundle.strat_knot_x is not None:
        hw = float(np.interp(risk_score, bundle.strat_knot_x, bundle.strat_q_vals,
                             left=bundle.strat_q_vals[0], right=bundle.strat_q_vals[-1]))
        return hw, len(peer_residuals), "stratified", risk_score, bundle.strat_scheme

    return bundle.global_q90, len(peer_residuals), "global_fallback", risk_score, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _resolve_bundle(mcc: int, ctx_len: int) -> ArtifactBundle:
    with _CACHE_LOCK:
        bundle = _ARTIFACT_CACHE.get((mcc, ctx_len))
    if bundle is not None:
        return bundle
    with _CACHE_LOCK:
        available = sorted([cl for (m, cl) in _ARTIFACT_CACHE if m == mcc])
    if not available:
        raise ValueError(f"No artifacts for MCC {mcc}")
    nearest = min(available, key=lambda cl: abs(cl - ctx_len))
    with _CACHE_LOCK:
        return _ARTIFACT_CACHE[(mcc, nearest)]


def run_m9_forecast(payload: M9ForecastRequest) -> dict:
    """Run M9 cost forecast in-process using loaded artifacts."""
    generated_at = datetime.now(timezone.utc)
    ctx_months = payload.context_months
    ctx_len = len(ctx_months)

    # Pick best context length
    valid = [cl for cl in sorted(SUPPORTED_CONTEXT_LENS, reverse=True) if cl <= ctx_len]
    chosen_len = valid[0] if valid else SUPPORTED_CONTEXT_LENS[0]
    ctx_months = ctx_months[-chosen_len:]
    ctx_len = len(ctx_months)

    bundle = _resolve_bundle(payload.mcc, ctx_len)

    pool_mean = payload.pool_mean_at_context_end
    knn_pool_mean = payload.knn_pool_mean_at_context_end

    vals = [m.avg_proc_cost_pct for m in ctx_months]
    c_mean = float(np.mean(vals))
    c_std = float(np.std(vals))
    momentum = float(vals[-1] - c_mean)

    X_raw = _build_feature_vector(ctx_months, knn_pool_mean)
    X_scaled = bundle.scaler.transform(X_raw)

    point_forecasts = np.array(
        [bundle.models[h].predict(X_scaled)[0] for h in range(payload.horizon_months)],
        dtype=float,
    )

    hw, pool_size, mode, risk_score, strat_scheme = _compute_conformal_hw(
        peer_ids=payload.peer_merchant_ids, bundle=bundle,
        ctx_months=ctx_months, pool_mean=pool_mean,
        knn_pool_mean=knn_pool_mean, ci=payload.confidence_interval,
    )

    forecast = [
        ForecastMonth(
            month_index=h + 1,
            proc_cost_pct_mid=float(point_forecasts[h]),
            proc_cost_pct_ci_lower=max(0.0, float(point_forecasts[h]) - hw),
            proc_cost_pct_ci_upper=float(point_forecasts[h]) + hw,
        )
        for h in range(payload.horizon_months)
    ]

    resp = M9ForecastResponse(
        forecast=forecast,
        conformal_metadata=ConformalMetadata(
            half_width=hw, conformal_mode=mode,
            pool_size=pool_size, risk_score=risk_score, strat_scheme=strat_scheme,
        ),
        process_metadata=ProcessMetadata(
            context_len_used=ctx_len, context_mean=c_mean,
            context_std=c_std, momentum=momentum,
            pool_mean_used=knn_pool_mean, mcc=payload.mcc,
            horizon_months=payload.horizon_months,
            confidence_interval=payload.confidence_interval,
            generated_at_utc=generated_at.isoformat(),
            artifact_trained_at=bundle.trained_at or "",
            strat_enabled=bundle.strat_enabled,
        ),
    )
    return resp.model_dump()
