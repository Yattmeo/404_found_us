"""
tests/unit/test_service.py

Unit tests for GetTPVForecast v2 service inference helpers.
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

SERVICE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVICE_ROOT))

from config import HORIZON_LEN, MIN_POOL, TARGET_COV
from models import TPVForecastRequest
from service import (
    ArtifactBundle,
    _ARTIFACT_CACHE,
    _MonthSummary,
    _adaptive_q,
    _aggregate_transactions,
    _build_feature_vector,
    _build_risk_vector,
    _compute_conformal_hw,
    _select_context_window,
    get_tpv_forecast,
    set_repository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Approximate feature centres from _make_raw_transactions(n_months=3, txns_per_month=3)
_FEAT_CENTERS = np.array([5.1, 0.07, 0.09, 4.2, 0.08, 1.4, 0.0, 5.2, 4.0, 0.0, 0.09])


def _fitted_scaler() -> StandardScaler:
    rng = np.random.default_rng(42)
    X = rng.normal(loc=_FEAT_CENTERS, scale=1.0, size=(50, 11))
    sc = StandardScaler()
    sc.fit(X)
    return sc


def _fitted_models(
    scaler: StandardScaler, constant: float = 4.5,
) -> List[HuberRegressor]:
    """Train mock models on *scaled* features so predictions stay near `constant`."""
    rng = np.random.default_rng(99)
    X_raw = rng.normal(loc=_FEAT_CENTERS, scale=0.5, size=(50, 11))
    X_scaled = scaler.transform(X_raw)
    y = np.full(50, constant)
    models: List[HuberRegressor] = []
    for _ in range(HORIZON_LEN):
        m = HuberRegressor(epsilon=1.35, max_iter=500)
        m.fit(X_scaled, y)
        models.append(m)
    return models


def _fitted_risk_models() -> List[GradientBoostingRegressor]:
    rng = np.random.default_rng(42)
    X = rng.normal(size=(40, 11))
    models: List[GradientBoostingRegressor] = []
    for _ in range(HORIZON_LEN):
        y = rng.normal(loc=0.0, scale=0.1, size=40)
        m = GradientBoostingRegressor(n_estimators=10, max_depth=2, random_state=42)
        m.fit(X, y)
        models.append(m)
    return models


def _make_month_summaries(
    n: int = 3,
    tpv: float = 150.0,
    txn_count: int = 20,
    avg_txn_val: float = 50.0,
    std_txn_amt: float = 15.0,
    median_txn_amt: float = 45.0,
) -> List[_MonthSummary]:
    return [
        _MonthSummary(
            year=2025,
            month=i + 1,
            total_processing_value=tpv + 10.0 * i,
            transaction_count=txn_count,
            avg_transaction_value=avg_txn_val,
            std_txn_amount=std_txn_amt,
            median_txn_amount=median_txn_amt,
        )
        for i in range(n)
    ]


def _make_raw_transactions(
    n_months: int = 3,
    txns_per_month: int = 3,
    base_amount: float = 50.0,
) -> List[Dict]:
    """Generate raw transaction records spanning n_months.

    Defaults produce ~$150 TPV/month (3 txns × $50) to stay close to the
    mock model's training regime.
    """
    records = []
    for m in range(n_months):
        for d in range(1, txns_per_month + 1):
            records.append({
                "transaction_date": f"2025-{m + 1:02d}-{min(d, 28):02d}",
                "amount": base_amount + m * 5.0 + d * 0.1,
                "cost_type_ID": (d % 3) + 1,
                "card_type": "debit",
            })
    return records


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_bundle() -> ArtifactBundle:
    cal_residuals: Dict[int, List[float]] = {
        1: [10.0 * (i + 1) for i in range(20)],
        2: [20.0 * (i + 1) for i in range(20)],
        3: [10.0 * (i + 1) for i in range(20)],
    }
    knot_x = np.array([0.0, 0.5, 1.0])
    q_vals = np.array([150.0, 250.0, 450.0])
    scaler = _fitted_scaler()
    return ArtifactBundle(
        context_len=3,
        models=_fitted_models(scaler, constant=4.5),
        scaler=scaler,
        cal_residuals=cal_residuals,
        global_q90=300.0,
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
    cal_residuals: Dict[int, List[float]] = {
        1: [10.0 * (i + 1) for i in range(20)],
        2: [20.0 * (i + 1) for i in range(20)],
        3: [10.0 * (i + 1) for i in range(20)],
    }
    scaler = _fitted_scaler()
    return ArtifactBundle(
        context_len=3,
        models=_fitted_models(scaler, constant=4.5),
        scaler=scaler,
        cal_residuals=cal_residuals,
        global_q90=300.0,
        risk_models=_fitted_risk_models(),
        strat_enabled=False,
        strat_scheme=None,
        strat_knot_x=None,
        strat_q_vals=None,
        config_snapshot={"trained_at": "2026-03-01T00:00:00+00:00"},
        loaded_mtime=1_700_000_000.0,
    )


@pytest.fixture()
def sample_request() -> TPVForecastRequest:
    return TPVForecastRequest(
        merchant_id="999",
        mcc=5411,
        onboarding_merchant_txn_df=_make_raw_transactions(n_months=3),
        horizon_months=3,
        confidence_interval=0.90,
    )


# ---------------------------------------------------------------------------
# _aggregate_transactions
# ---------------------------------------------------------------------------

class TestAggregateTransactions:
    def test_basic_aggregation(self):
        records = _make_raw_transactions(n_months=2, txns_per_month=10)
        months = _aggregate_transactions(records)
        assert len(months) == 2
        assert months[0].year == 2025
        assert months[0].month == 1
        assert months[1].month == 2

    def test_tpv_is_sum(self):
        records = [
            {"transaction_date": "2025-01-01", "amount": 100.0},
            {"transaction_date": "2025-01-02", "amount": 200.0},
        ]
        months = _aggregate_transactions(records)
        assert len(months) == 1
        assert months[0].total_processing_value == pytest.approx(300.0)
        assert months[0].transaction_count == 2

    def test_stats_correct(self):
        records = [
            {"transaction_date": "2025-03-01", "amount": 10.0},
            {"transaction_date": "2025-03-15", "amount": 30.0},
        ]
        months = _aggregate_transactions(records)
        m = months[0]
        assert m.avg_transaction_value == pytest.approx(20.0)
        assert m.median_txn_amount == pytest.approx(20.0)
        assert m.std_txn_amount == pytest.approx(10.0)

    def test_cost_type_pcts_populated(self):
        records = [
            {"transaction_date": "2025-01-01", "amount": 10.0, "cost_type_ID": 5},
            {"transaction_date": "2025-01-02", "amount": 20.0, "cost_type_ID": 5},
            {"transaction_date": "2025-01-03", "amount": 30.0, "cost_type_ID": 10},
        ]
        months = _aggregate_transactions(records)
        assert months[0].cost_type_pcts is not None
        assert "cost_type_5_pct" in months[0].cost_type_pcts
        assert months[0].cost_type_pcts["cost_type_5_pct"] == pytest.approx(2.0 / 3.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _aggregate_transactions([])

    def test_no_valid_dates_raises(self):
        with pytest.raises(ValueError):
            _aggregate_transactions([{"transaction_date": "INVALID", "amount": 1.0}])

    def test_sorted_output(self):
        records = [
            {"transaction_date": "2025-03-01", "amount": 10.0},
            {"transaction_date": "2025-01-01", "amount": 20.0},
            {"transaction_date": "2025-02-01", "amount": 30.0},
        ]
        months = _aggregate_transactions(records)
        assert [m.month for m in months] == [1, 2, 3]


# ---------------------------------------------------------------------------
# _select_context_window
# ---------------------------------------------------------------------------

class TestSelectContextWindow:
    def test_selects_6_from_7(self):
        months = _make_month_summaries(n=7)
        ctx = _select_context_window(months)
        assert len(ctx) == 6

    def test_selects_3_from_4(self):
        months = _make_month_summaries(n=4)
        ctx = _select_context_window(months)
        assert len(ctx) == 3

    def test_selects_1_from_2(self):
        months = _make_month_summaries(n=2)
        ctx = _select_context_window(months)
        assert len(ctx) == 1

    def test_single_month(self):
        months = _make_month_summaries(n=1)
        ctx = _select_context_window(months)
        assert len(ctx) == 1

    def test_exact_6(self):
        months = _make_month_summaries(n=6)
        ctx = _select_context_window(months)
        assert len(ctx) == 6

    def test_takes_last_months(self):
        months = _make_month_summaries(n=4)
        ctx = _select_context_window(months)
        assert ctx[-1].month == 4  # last month of 4


# ---------------------------------------------------------------------------
# _build_feature_vector (11 features)
# ---------------------------------------------------------------------------

class TestBuildFeatureVector:
    def test_output_shape(self):
        ctx = _make_month_summaries(n=3)
        X = _build_feature_vector(ctx, pool_mean=4.2)
        assert X.shape == (1, 11)

    def test_feature_values(self):
        ctx = _make_month_summaries(n=3, tpv=150.0)
        X = _build_feature_vector(ctx, pool_mean=5.0)
        log_vals = [np.log1p(m.total_processing_value) for m in ctx]
        c_mean = np.mean(log_vals)
        c_std = np.std(log_vals)
        momentum = log_vals[-1] - c_mean
        assert math.isclose(X[0, 0], c_mean, rel_tol=1e-6)
        assert math.isclose(X[0, 1], c_std, rel_tol=1e-6)
        assert math.isclose(X[0, 2], momentum, rel_tol=1e-6)
        assert math.isclose(X[0, 3], 5.0, rel_tol=1e-9)

    def test_single_month_context(self):
        ctx = _make_month_summaries(n=1)
        X = _build_feature_vector(ctx, pool_mean=4.0)
        assert X.shape == (1, 11)
        assert X[0, 1] == pytest.approx(0.0)
        assert X[0, 2] == pytest.approx(0.0)

    def test_pool_mean_passthrough(self):
        ctx = _make_month_summaries(n=3)
        X = _build_feature_vector(ctx, pool_mean=7.77)
        assert X[0, 3] == pytest.approx(7.77)


# ---------------------------------------------------------------------------
# _build_risk_vector (11 features)
# ---------------------------------------------------------------------------

class TestBuildRiskVector:
    def test_output_shape(self):
        ctx = _make_month_summaries(n=3)
        R = _build_risk_vector(ctx, pool_mean=4.0, knn_pool_mean=4.1)
        assert R.shape == (1, 11)

    def test_features_non_negative(self):
        ctx = _make_month_summaries(n=3)
        R = _build_risk_vector(ctx, pool_mean=4.0, knn_pool_mean=4.1)
        assert np.all(R >= 0)

    def test_cost_type_hhi_default(self):
        ctx = _make_month_summaries(n=3)
        R = _build_risk_vector(ctx, pool_mean=4.0, knn_pool_mean=4.1)
        assert R[0, 3] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _adaptive_q
# ---------------------------------------------------------------------------

class TestAdaptiveQ:
    def test_returns_float_for_adequate_pool(self):
        residuals = [10.0 * i for i in range(1, 21)]
        q = _adaptive_q(residuals, target=0.90)
        assert q is not None
        assert isinstance(q, float)

    def test_returns_none_for_undersized_pool(self):
        q = _adaptive_q([50.0], target=0.90)
        assert q is None

    def test_quantile_monotone(self):
        residuals = sorted([5.0 * i for i in range(1, 21)])
        q90 = _adaptive_q(residuals, target=0.90)
        q80 = _adaptive_q(residuals, target=0.80)
        assert q90 >= q80


# ---------------------------------------------------------------------------
# _compute_conformal_hw — tier selection (dollar-space)
# ---------------------------------------------------------------------------

class TestComputeConformalHW:
    def test_local_tier_used(self, mock_bundle):
        ctx = _make_month_summaries(n=3)
        hw, pool_size, mode, risk_score, strat_scheme = _compute_conformal_hw(
            peer_merchant_ids=[1, 2, 3],
            bundle=mock_bundle,
            context_months=ctx,
            pool_mean=4.0,
            knn_pool_mean=4.1,
            confidence_interval=0.90,
        )
        assert mode == "local"
        assert pool_size == 60
        assert hw > 0

    def test_stratified_when_no_peers(self, mock_bundle):
        ctx = _make_month_summaries(n=3)
        hw, pool_size, mode, risk_score, strat_scheme = _compute_conformal_hw(
            peer_merchant_ids=[],
            bundle=mock_bundle,
            context_months=ctx,
            pool_mean=4.0,
            knn_pool_mean=4.1,
            confidence_interval=0.90,
        )
        assert mode == "stratified"
        assert strat_scheme is not None
        assert risk_score is not None
        assert hw > 0

    def test_global_fallback(self, mock_bundle_no_strat):
        ctx = _make_month_summaries(n=3)
        hw, pool_size, mode, risk_score, _ = _compute_conformal_hw(
            peer_merchant_ids=[],
            bundle=mock_bundle_no_strat,
            context_months=ctx,
            pool_mean=4.0,
            knn_pool_mean=4.1,
            confidence_interval=0.90,
        )
        assert mode == "global_fallback"
        assert math.isclose(hw, mock_bundle_no_strat.global_q90, rel_tol=1e-9)

    def test_global_fallback_unknown_peers(self, mock_bundle_no_strat):
        ctx = _make_month_summaries(n=3)
        hw, pool_size, mode, _, _ = _compute_conformal_hw(
            peer_merchant_ids=[999],
            bundle=mock_bundle_no_strat,
            context_months=ctx,
            pool_mean=4.0,
            knn_pool_mean=4.1,
            confidence_interval=0.90,
        )
        assert mode == "global_fallback"

    def test_hw_is_dollar_denominated(self, mock_bundle_no_strat):
        ctx = _make_month_summaries(n=3)
        hw, *_ = _compute_conformal_hw(
            peer_merchant_ids=[],
            bundle=mock_bundle_no_strat,
            context_months=ctx,
            pool_mean=4.0,
            knn_pool_mean=4.1,
            confidence_interval=0.90,
        )
        assert hw > 1.0


# ---------------------------------------------------------------------------
# Full round-trip (mocking _compute_pool_info + _REPO)
# ---------------------------------------------------------------------------

class TestFullRoundTrip:
    """
    For the full round-trip we mock _compute_pool_info so these tests remain
    pure unit tests (no DB required).
    """

    def _patch_pool_info(self):
        """Return a mock that provides static pool means + peer IDs."""
        return patch(
            "service._compute_pool_info",
            return_value=(4.2, 4.3, [1, 2, 3]),
        )

    def _patch_repo(self):
        return patch("service._REPO", new="fake_repo")

    def test_happy_path(self, mock_bundle, sample_request):
        with (
            patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}),
            self._patch_pool_info(),
            self._patch_repo(),
        ):
            resp = get_tpv_forecast(sample_request)
        assert len(resp.forecast) == 3
        for fm in resp.forecast:
            assert fm.tpv_ci_lower <= fm.tpv_mid
            assert fm.tpv_mid <= fm.tpv_ci_upper
            assert fm.tpv_ci_lower >= 0.0

    def test_single_month_context(self, mock_bundle):
        req = TPVForecastRequest(
            merchant_id="999",
            mcc=5411,
            onboarding_merchant_txn_df=_make_raw_transactions(n_months=1),
        )
        with (
            patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}),
            self._patch_pool_info(),
            self._patch_repo(),
        ):
            resp = get_tpv_forecast(req)
        assert resp.process_metadata.context_len_used == 1
        assert len(resp.forecast) == 3

    def test_month_indices(self, mock_bundle, sample_request):
        with (
            patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}),
            self._patch_pool_info(),
            self._patch_repo(),
        ):
            resp = get_tpv_forecast(sample_request)
        assert [fm.month_index for fm in resp.forecast] == [1, 2, 3]

    def test_conformal_mode_returned(self, mock_bundle, sample_request):
        with (
            patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}),
            self._patch_pool_info(),
            self._patch_repo(),
        ):
            resp = get_tpv_forecast(sample_request)
        assert resp.conformal_metadata.conformal_mode in (
            "local", "stratified", "global_fallback",
        )

    def test_metadata_fields(self, mock_bundle, sample_request):
        with (
            patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}),
            self._patch_pool_info(),
            self._patch_repo(),
        ):
            resp = get_tpv_forecast(sample_request)
        assert resp.process_metadata.mcc == 5411
        assert resp.process_metadata.model_variant == "tpv_v1"

    def test_dollar_intervals_not_log(self, mock_bundle, sample_request):
        with (
            patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}),
            self._patch_pool_info(),
            self._patch_repo(),
        ):
            resp = get_tpv_forecast(sample_request)
        for fm in resp.forecast:
            assert fm.tpv_mid > 1.0, "Forecast should be in dollar space, not log"

    def test_half_width_is_dollar(self, mock_bundle, sample_request):
        with (
            patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}),
            self._patch_pool_info(),
            self._patch_repo(),
        ):
            resp = get_tpv_forecast(sample_request)
        assert resp.conformal_metadata.half_width_dollars > 1.0

    def test_context_mean_dollar(self, mock_bundle, sample_request):
        with (
            patch.dict(_ARTIFACT_CACHE, {(5411, 3): mock_bundle}),
            self._patch_pool_info(),
            self._patch_repo(),
        ):
            resp = get_tpv_forecast(sample_request)
        expected = np.expm1(resp.process_metadata.context_mean_log_tpv)
        assert math.isclose(
            resp.process_metadata.context_mean_dollar, expected, rel_tol=1e-6,
        )
