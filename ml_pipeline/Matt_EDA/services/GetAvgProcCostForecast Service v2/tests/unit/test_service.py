"""
tests/unit/test_service.py

Unit tests for service.py v2 inference helpers.
No disk I/O, no FastAPI server required.
"""

import math
import sys
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

import numpy as np
import pytest
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Make service importable from the project root without installation
# ---------------------------------------------------------------------------
SERVICE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVICE_ROOT))

from config import HORIZON_LEN, MIN_POOL, TARGET_COV
from models import ContextMonth, M9ForecastRequest
from service import (
    ArtifactBundle,
    _ARTIFACT_CACHE,
    _adaptive_q,
    _build_feature_vector,
    _build_risk_vector,
    _compute_conformal_hw,
    get_monthly_cost_forecast,
)


# ---------------------------------------------------------------------------
# Fixtures — helpers
# ---------------------------------------------------------------------------

def _fitted_scaler_v2() -> StandardScaler:
    """Return a StandardScaler fitted on 7-feature data (v2 shape)."""
    rng = np.random.default_rng(42)
    X = rng.normal(loc=0.03, scale=0.01, size=(20, 7))
    sc = StandardScaler()
    sc.fit(X)
    return sc


def _fitted_models_v2(constant: float = 0.03) -> List[HuberRegressor]:
    """Return HORIZON_LEN HuberRegressor models each trivially predicting `constant`."""
    X = np.tile(np.array([0.03, 0.0, 0.0, 0.03, 0.01, 3.0, 0.005]), (10, 1))
    y = np.full(10, constant)
    models: List[HuberRegressor] = []
    for _ in range(HORIZON_LEN):
        m = HuberRegressor(epsilon=1.35, max_iter=500)
        m.fit(X, y)
        models.append(m)
    return models


def _fitted_risk_models() -> List[GradientBoostingRegressor]:
    """Return HORIZON_LEN trivial GBR risk models (9 features)."""
    rng = np.random.default_rng(42)
    X = rng.normal(size=(40, 9))
    models: List[GradientBoostingRegressor] = []
    for _ in range(HORIZON_LEN):
        y = rng.normal(loc=0.0, scale=0.1, size=40)
        m = GradientBoostingRegressor(
            n_estimators=10, max_depth=2, random_state=42,
        )
        m.fit(X, y)
        models.append(m)
    return models


def _make_context_months(
    n: int = 3,
    avg_cost: float = 0.03,
    std_cost: float = 0.005,
    median_cost: float = 0.029,
    txn_count: int = 100,
    avg_txn_val: float = 50.0,
    std_txn_amt: float = 15.0,
) -> List[ContextMonth]:
    return [
        ContextMonth(
            year=2025,
            month=i + 1,
            avg_proc_cost_pct=avg_cost + 0.001 * i,
            std_proc_cost_pct=std_cost,
            median_proc_cost_pct=median_cost,
            transaction_count=txn_count,
            avg_transaction_value=avg_txn_val,
            std_txn_amount=std_txn_amt,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_bundle() -> ArtifactBundle:
    """A fully populated v2 ArtifactBundle that needs no filesystem access."""
    cal_residuals: Dict[int, List[float]] = {
        1: [0.01 * (i + 1) for i in range(20)],
        2: [0.02 * (i + 1) for i in range(20)],
        3: [0.01 * (i + 1) for i in range(20)],
    }
    knot_x = np.array([0.0, 0.5, 1.0])
    q_vals = np.array([0.15, 0.25, 0.45])
    return ArtifactBundle(
        context_len=3,
        models=_fitted_models_v2(constant=0.03),
        scaler=_fitted_scaler_v2(),
        cal_residuals=cal_residuals,
        global_q90=0.30,
        risk_models=_fitted_risk_models(),
        strat_enabled=True,
        strat_scheme="low-mid-high_50_85",
        strat_knot_x=knot_x,
        strat_q_vals=q_vals,
        config_snapshot={"trained_at": "2026-03-01T00:00:00+00:00"},
        loaded_mtime=1_700_000_000.0,
    )


@pytest.fixture()
def mock_bundle_no_strat() -> ArtifactBundle:
    """An ArtifactBundle with stratification disabled."""
    cal_residuals: Dict[int, List[float]] = {
        1: [0.01 * (i + 1) for i in range(20)],
        2: [0.02 * (i + 1) for i in range(20)],
        3: [0.01 * (i + 1) for i in range(20)],
    }
    return ArtifactBundle(
        context_len=3,
        models=_fitted_models_v2(constant=0.03),
        scaler=_fitted_scaler_v2(),
        cal_residuals=cal_residuals,
        global_q90=0.30,
        risk_models=_fitted_risk_models(),
        strat_enabled=False,
        strat_scheme=None,
        strat_knot_x=None,
        strat_q_vals=None,
        config_snapshot={"trained_at": "2026-03-01T00:00:00+00:00"},
        loaded_mtime=1_700_000_000.0,
    )


@pytest.fixture()
def sample_request() -> M9ForecastRequest:
    """A minimal valid v2 M9ForecastRequest for MCC 5411."""
    return M9ForecastRequest(
        merchant_id="999",
        mcc=5411,
        context_months=_make_context_months(n=3),
        pool_mean_at_context_end=0.027,
        knn_pool_mean_at_context_end=0.028,
        peer_merchant_ids=[1, 2, 3],
        horizon_months=3,
        confidence_interval=0.90,
    )


# ---------------------------------------------------------------------------
# _build_feature_vector (v2 — 7 features)
# ---------------------------------------------------------------------------

class TestBuildFeatureVector:
    def test_output_shape(self):
        ctx = _make_context_months(n=3)
        X = _build_feature_vector(ctx, pool_mean=0.027)
        assert X.shape == (1, 7), "Expected shape (1, 7)"

    def test_feature_values(self):
        ctx = _make_context_months(n=3, avg_cost=0.03, std_cost=0.005, median_cost=0.029)
        X = _build_feature_vector(ctx, pool_mean=0.05)
        vals = [m.avg_proc_cost_pct for m in ctx]
        c_mean = np.mean(vals)
        c_std = np.std(vals)
        momentum = vals[-1] - c_mean
        assert math.isclose(X[0, 0], c_mean, rel_tol=1e-6)
        assert math.isclose(X[0, 1], c_std, rel_tol=1e-6)
        assert math.isclose(X[0, 2], momentum, rel_tol=1e-6)
        assert math.isclose(X[0, 3], 0.05, rel_tol=1e-9)

    def test_constant_context_zero_std(self):
        ctx = [
            ContextMonth(year=2025, month=i, avg_proc_cost_pct=0.03,
                         median_proc_cost_pct=0.03, std_proc_cost_pct=0.0,
                         transaction_count=10, avg_transaction_value=50.0)
            for i in range(1, 4)
        ]
        X = _build_feature_vector(ctx, pool_mean=0.03)
        assert X[0, 1] == pytest.approx(0.0)  # std = 0
        assert X[0, 2] == pytest.approx(0.0)  # momentum = 0


# ---------------------------------------------------------------------------
# _build_risk_vector (v2 — 9 features)
# ---------------------------------------------------------------------------

class TestBuildRiskVector:
    def test_output_shape(self):
        ctx = _make_context_months(n=3)
        R = _build_risk_vector(ctx, pool_mean=0.03, knn_pool_mean=0.031)
        assert R.shape == (1, 9), "Expected shape (1, 9)"

    def test_features_non_negative(self):
        ctx = _make_context_months(n=3)
        R = _build_risk_vector(ctx, pool_mean=0.03, knn_pool_mean=0.031)
        # All risk features should be non-negative given positive inputs
        assert np.all(R >= 0)


# ---------------------------------------------------------------------------
# _adaptive_q
# ---------------------------------------------------------------------------

class TestAdaptiveQ:
    def test_returns_float_for_adequate_pool(self):
        residuals = [0.01 * i for i in range(1, 21)]  # 20 residuals
        q = _adaptive_q(residuals, target=0.90)
        assert q is not None
        assert isinstance(q, float)

    def test_returns_none_for_undersized_pool(self):
        # n=1 → level = ceil(2*0.90)/1 = 2.0 > 1  → None
        q = _adaptive_q([0.05], target=0.90)
        assert q is None

    def test_quantile_is_monotone(self):
        residuals = sorted([0.05 * i for i in range(1, 21)])
        q90 = _adaptive_q(residuals, target=0.90)
        q80 = _adaptive_q(residuals, target=0.80)
        assert q90 >= q80


# ---------------------------------------------------------------------------
# _compute_conformal_hw — tier selection (v2)
# ---------------------------------------------------------------------------

class TestComputeConformalHW:
    def test_local_tier_used_when_peer_pool_adequate(self, mock_bundle):
        ctx = _make_context_months(n=3)
        hw, pool_size, mode, risk_score, strat_scheme = _compute_conformal_hw(
            peer_merchant_ids=[1, 2, 3],
            bundle=mock_bundle,
            context_months=ctx,
            pool_mean=0.03,
            knn_pool_mean=0.031,
            confidence_interval=0.90,
        )
        assert mode == "local"
        assert pool_size == 60
        assert hw > 0

    def test_stratified_when_no_peers_and_strat_enabled(self, mock_bundle):
        ctx = _make_context_months(n=3)
        hw, pool_size, mode, risk_score, strat_scheme = _compute_conformal_hw(
            peer_merchant_ids=[],
            bundle=mock_bundle,
            context_months=ctx,
            pool_mean=0.03,
            knn_pool_mean=0.031,
            confidence_interval=0.90,
        )
        assert mode == "stratified"
        assert strat_scheme is not None
        assert risk_score is not None
        assert hw > 0

    def test_global_fallback_when_strat_disabled_and_no_peers(self, mock_bundle_no_strat):
        ctx = _make_context_months(n=3)
        hw, pool_size, mode, risk_score, _ = _compute_conformal_hw(
            peer_merchant_ids=[],
            bundle=mock_bundle_no_strat,
            context_months=ctx,
            pool_mean=0.03,
            knn_pool_mean=0.031,
            confidence_interval=0.90,
        )
        assert mode == "global_fallback"
        assert math.isclose(hw, mock_bundle_no_strat.global_q90, rel_tol=1e-9)

    def test_global_fallback_when_unknown_peers(self, mock_bundle_no_strat):
        ctx = _make_context_months(n=3)
        hw, pool_size, mode, _, _ = _compute_conformal_hw(
            peer_merchant_ids=[999],
            bundle=mock_bundle_no_strat,
            context_months=ctx,
            pool_mean=0.03,
            knn_pool_mean=0.031,
            confidence_interval=0.90,
        )
        assert mode == "global_fallback"


# ---------------------------------------------------------------------------
# Full round-trip through get_monthly_cost_forecast (v2)
# ---------------------------------------------------------------------------

class TestFullRoundTrip:
    def test_happy_path(self, mock_bundle, sample_request):
        with patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}):
            resp = get_monthly_cost_forecast(sample_request)

        assert len(resp.forecast) == 3
        for fm in resp.forecast:
            assert fm.proc_cost_pct_ci_lower <= fm.proc_cost_pct_mid
            assert fm.proc_cost_pct_mid <= fm.proc_cost_pct_ci_upper

    def test_single_month_context(self, mock_bundle, sample_request):
        """Service should handle ctx_len=1 with the nearest available bundle."""
        short = M9ForecastRequest(
            merchant_id="999",
            mcc=5411,
            context_months=_make_context_months(n=1),
            pool_mean_at_context_end=0.027,
            knn_pool_mean_at_context_end=0.028,
            peer_merchant_ids=[1, 2, 3],
        )
        # Only ctx_len=3 bundle available — should fall back
        with patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}):
            resp = get_monthly_cost_forecast(short)

        assert resp.process_metadata.context_len_used == 1
        assert len(resp.forecast) == 3

    def test_forecast_month_indices(self, mock_bundle, sample_request):
        with patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}):
            resp = get_monthly_cost_forecast(sample_request)

        assert [fm.month_index for fm in resp.forecast] == [1, 2, 3]

    def test_conformal_mode_returned(self, mock_bundle, sample_request):
        with patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}):
            resp = get_monthly_cost_forecast(sample_request)

        assert resp.conformal_metadata.conformal_mode in (
            "local", "stratified", "global_fallback"
        )

    def test_metadata_mcc_variant(self, mock_bundle, sample_request):
        with patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}):
            resp = get_monthly_cost_forecast(sample_request)

        assert resp.process_metadata.mcc == 5411
        assert resp.process_metadata.model_variant == "m9_v2"
