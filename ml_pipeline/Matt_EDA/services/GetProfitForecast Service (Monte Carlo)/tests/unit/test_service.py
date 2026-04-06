"""
tests/unit/test_service.py

Unit tests for GetProfitForecast Service.
No upstream services required — the caller passes pre-computed outputs.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Make service importable from the project root without installation
# ---------------------------------------------------------------------------
SERVICE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVICE_ROOT))

from models import (
    CostServiceOutput,
    ProfitForecastRequest,
    ProfitMonth,
    TPVServiceOutput,
)
from service import _simulate_profit_month, get_profit_forecast


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _tpv_output(horizon: int = 3) -> dict:
    """Return a dict matching the TPV service JSON response."""
    return {
        "forecast": [
            {"month_index": i + 1, "tpv_mid": 10000.0 + i * 500.0,
             "tpv_ci_lower": 9500.0 + i * 500.0, "tpv_ci_upper": 10500.0 + i * 500.0}
            for i in range(horizon)
        ],
        "conformal_metadata": {
            "half_width_dollars": 500.0,
            "conformal_mode": "adaptive",
            "pool_size": 50,
            "risk_score": 0.3,
        },
        "process_metadata": {
            "context_len_used": 6,
            "context_mean_log_tpv": 9.2,
            "context_mean_dollar": 10000.0,
            "momentum": 0.01,
            "pool_mean_used": 9.1,
            "mcc": 5411,
            "model_variant": "tpv_v1",
            "horizon_months": horizon,
            "confidence_interval": 0.90,
            "generated_at_utc": "2025-01-15T12:00:00Z",
        },
    }


def _cost_output(horizon: int = 3) -> dict:
    """Return a dict matching the Cost service JSON response."""
    return {
        "forecast": [
            {"month_index": i + 1, "proc_cost_pct_mid": 0.020 + i * 0.001,
             "proc_cost_pct_ci_lower": 0.015 + i * 0.001,
             "proc_cost_pct_ci_upper": 0.025 + i * 0.001}
            for i in range(horizon)
        ],
        "conformal_metadata": {
            "half_width": 0.005,
            "conformal_mode": "adaptive",
            "pool_size": 50,
            "risk_score": 0.2,
        },
        "process_metadata": {
            "context_len_used": 6,
            "context_mean": 0.021,
            "context_std": 0.003,
            "momentum": 0.001,
            "pool_mean_used": 0.02,
            "mcc": 5411,
            "model_variant": "m9_v2",
            "horizon_months": horizon,
            "confidence_interval": 0.90,
            "generated_at_utc": "2025-01-15T12:00:00Z",
        },
    }


def _make_request(**overrides) -> ProfitForecastRequest:
    defaults = dict(
        tpv_service_output=_tpv_output(),
        cost_service_output=_cost_output(),
        fee_rate=0.029,
        mcc=5411,
        merchant_id="test-merchant",
        confidence_interval=0.90,
        n_simulations=10_000,
    )
    defaults.update(overrides)
    return ProfitForecastRequest(**defaults)


# ============================================================================
# _simulate_profit_month tests
# ============================================================================


class TestSimulateProfitMonth:
    """Tests for the pure Monte Carlo simulation function."""

    @pytest.fixture()
    def rng(self):
        return np.random.default_rng(42)

    def _run(self, rng, **overrides):
        defaults = dict(
            tpv_mid=10000.0,
            tpv_hw=500.0,
            cost_pct_mid=0.020,
            cost_pct_hw=0.005,
            fee_rate=0.029,
            confidence_interval=0.90,
            n_simulations=50_000,
            rng=rng,
        )
        defaults.update(overrides)
        return _simulate_profit_month(**defaults)

    def test_returns_profit_month(self, rng):
        pm = self._run(rng)
        assert isinstance(pm, ProfitMonth)

    def test_point_estimates_arithmetic(self, rng):
        """revenue = tpv * fee; cost = tpv * cost_pct; profit = revenue - cost."""
        pm = self._run(rng, tpv_mid=10000.0, cost_pct_mid=0.02, fee_rate=0.029)
        assert pm.revenue_mid == pytest.approx(10000.0 * 0.029)
        assert pm.cost_mid == pytest.approx(10000.0 * 0.02)
        assert pm.profit_mid == pytest.approx(10000.0 * (0.029 - 0.02))
        assert pm.margin_mid == pytest.approx(0.029 - 0.02)

    def test_p_profitable_high_when_fee_exceeds_cost(self, rng):
        """When fee >> cost, P(profit > 0) should be close to 1."""
        pm = self._run(rng, fee_rate=0.10, cost_pct_mid=0.02, cost_pct_hw=0.005)
        assert pm.p_profitable > 0.95

    def test_p_profitable_low_when_cost_exceeds_fee(self, rng):
        """When fee << cost, P(profit > 0) should be close to 0."""
        pm = self._run(rng, fee_rate=0.01, cost_pct_mid=0.05, cost_pct_hw=0.005)
        assert pm.p_profitable < 0.05

    def test_p_profitable_near_half_at_breakeven(self, rng):
        """When fee ≈ cost, P(profit > 0) should be near 0.5."""
        pm = self._run(
            rng,
            fee_rate=0.030,
            cost_pct_mid=0.030,
            cost_pct_hw=0.005,
            n_simulations=100_000,
        )
        assert 0.3 < pm.p_profitable < 0.7

    def test_ci_ordering(self, rng):
        """CI lower ≤ median ≤ CI upper."""
        pm = self._run(rng)
        assert pm.profit_ci_lower <= pm.profit_median <= pm.profit_ci_upper

    def test_ci_width_increases_with_uncertainty(self, rng):
        """Wider conformal half-widths → wider profit CI."""
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        pm_narrow = self._run(rng1, tpv_hw=100.0, cost_pct_hw=0.001)
        pm_wide = self._run(rng2, tpv_hw=2000.0, cost_pct_hw=0.02)
        span_narrow = pm_narrow.profit_ci_upper - pm_narrow.profit_ci_lower
        span_wide = pm_wide.profit_ci_upper - pm_wide.profit_ci_lower
        assert span_wide > span_narrow

    def test_std_positive(self, rng):
        pm = self._run(rng)
        assert pm.profit_std > 0

    def test_reproducibility_with_same_seed(self):
        """Same RNG seed → identical results."""
        rng1 = np.random.default_rng(99)
        rng2 = np.random.default_rng(99)
        pm1 = self._run(rng1)
        pm2 = self._run(rng2)
        assert pm1.p_profitable == pm2.p_profitable
        assert pm1.profit_median == pm2.profit_median

    def test_high_n_simulations_stability(self, rng):
        """With 100k sims, p_profitable should be stable across runs."""
        rng1 = np.random.default_rng(10)
        rng2 = np.random.default_rng(20)
        pm1 = self._run(rng1, n_simulations=100_000)
        pm2 = self._run(rng2, n_simulations=100_000)
        assert abs(pm1.p_profitable - pm2.p_profitable) < 0.02

    def test_simulation_mean_present(self, rng):
        """simulation_mean should always be present."""
        pm = self._run(rng)
        assert isinstance(pm.simulation_mean, float)

    def test_simulation_mean_close_to_profit_mid(self, rng):
        """With many sims, simulation_mean ≈ profit_mid."""
        pm = self._run(rng, n_simulations=100_000)
        assert pm.simulation_mean == pytest.approx(pm.profit_mid, rel=0.05)

    def test_p_target_margin_met_none_by_default(self, rng):
        """Without target_margin, p_target_margin_met is None."""
        pm = self._run(rng)
        assert pm.p_target_margin_met is None

    def test_p_target_margin_met_with_easy_target(self, rng):
        """fee=0.10, cost~0.02, target=0.01 → high probability."""
        pm = self._run(rng, fee_rate=0.10, cost_pct_mid=0.02,
                       cost_pct_hw=0.005, target_margin=0.01)
        assert pm.p_target_margin_met is not None
        assert pm.p_target_margin_met > 0.90

    def test_p_target_margin_met_with_hard_target(self, rng):
        """fee=0.029, cost~0.02, target=0.05 → very low probability."""
        pm = self._run(rng, fee_rate=0.029, cost_pct_mid=0.02,
                       cost_pct_hw=0.005, target_margin=0.05)
        assert pm.p_target_margin_met is not None
        assert pm.p_target_margin_met < 0.10


# ============================================================================
# get_profit_forecast tests (no mocks needed — just pass upstream outputs)
# ============================================================================


class TestGetProfitForecast:
    """End-to-end tests for get_profit_forecast."""

    def test_basic_response_structure(self):
        req = _make_request()
        resp = get_profit_forecast(req)
        assert len(resp.months) == 3
        assert resp.summary is not None
        assert resp.metadata is not None

    def test_month_indices_are_1_based(self):
        req = _make_request()
        resp = get_profit_forecast(req)
        indices = [m.month_index for m in resp.months]
        assert indices == [1, 2, 3]

    def test_single_month_horizon(self):
        req = _make_request(
            tpv_service_output=_tpv_output(horizon=1),
            cost_service_output=_cost_output(horizon=1),
        )
        resp = get_profit_forecast(req)
        assert len(resp.months) == 1
        assert resp.months[0].month_index == 1

    def test_summary_totals_consistent(self):
        req = _make_request()
        resp = get_profit_forecast(req)
        assert resp.summary.total_revenue_mid == pytest.approx(
            sum(m.revenue_mid for m in resp.months)
        )
        assert resp.summary.total_cost_mid == pytest.approx(
            sum(m.cost_mid for m in resp.months)
        )
        assert resp.summary.total_profit_mid == pytest.approx(
            sum(m.profit_mid for m in resp.months)
        )

    def test_summary_p_profitable_bounds(self):
        req = _make_request()
        resp = get_profit_forecast(req)
        assert 0.0 <= resp.summary.avg_p_profitable <= 1.0
        assert 0.0 <= resp.summary.min_p_profitable <= 1.0
        assert resp.summary.min_p_profitable <= resp.summary.avg_p_profitable

    def test_break_even_above_max_cost(self):
        """Break-even fee rate should equal the worst-case cost upper bound."""
        cost_out = _cost_output()
        req = _make_request(cost_service_output=cost_out)
        resp = get_profit_forecast(req)

        cost_parsed = CostServiceOutput(**cost_out)
        horizon = len(cost_parsed.forecast)
        worst_upper = max(
            cost_parsed.forecast[h].proc_cost_pct_mid
            + cost_parsed.conformal_metadata.half_width
            for h in range(horizon)
        )
        assert resp.summary.break_even_fee_rate == pytest.approx(worst_upper)

    def test_metadata_fields(self):
        req = _make_request(fee_rate=0.035, mcc=5411)
        resp = get_profit_forecast(req)

        m = resp.metadata
        assert m.fee_rate == 0.035
        assert m.mcc == 5411
        assert m.n_simulations == 10_000
        assert m.confidence_interval == 0.90
        assert m.horizon_months == 3
        assert m.correlation_assumed == "independent"
        assert m.tpv_conformal_mode == "adaptive"
        assert m.cost_conformal_mode == "adaptive"
        assert m.merchant_id == "test-merchant"

    def test_high_fee_gives_high_profitability(self):
        """Fee well above cost → P(profitable) close to 1."""
        req = _make_request(fee_rate=0.10)
        resp = get_profit_forecast(req)
        for m in resp.months:
            assert m.p_profitable > 0.95

    def test_low_fee_gives_low_profitability(self):
        """Fee well below cost → P(profitable) close to 0."""
        cost_high = _cost_output()
        for fm in cost_high["forecast"]:
            fm["proc_cost_pct_mid"] = 0.10
        req = _make_request(fee_rate=0.02, cost_service_output=cost_high)
        resp = get_profit_forecast(req)
        for m in resp.months:
            assert m.p_profitable < 0.05

    def test_ci_ordering_all_months(self):
        req = _make_request()
        resp = get_profit_forecast(req)
        for m in resp.months:
            assert m.profit_ci_lower <= m.profit_median <= m.profit_ci_upper

    def test_profit_mid_equals_revenue_minus_cost(self):
        req = _make_request()
        resp = get_profit_forecast(req)
        for m in resp.months:
            assert m.profit_mid == pytest.approx(m.revenue_mid - m.cost_mid)

    def test_margin_equals_fee_minus_cost_pct(self):
        req = _make_request(fee_rate=0.035)
        resp = get_profit_forecast(req)
        for m in resp.months:
            assert m.margin_mid == pytest.approx(0.035 - m.cost_pct_mid)

    def test_no_merchant_id(self):
        """merchant_id=None should not cause errors."""
        req = _make_request(merchant_id=None)
        resp = get_profit_forecast(req)
        assert resp.metadata.merchant_id is None
        assert len(resp.months) == 3

    def test_extra_fields_in_upstream_output_ignored(self):
        """Extra fields from upstream services should be silently ignored."""
        tpv = _tpv_output()
        tpv["some_unexpected_field"] = "hello"
        tpv["conformal_metadata"]["strat_scheme"] = "quantile"
        req = _make_request(tpv_service_output=tpv)
        resp = get_profit_forecast(req)
        assert len(resp.months) == 3

    def test_mismatched_horizon_raises(self):
        """TPV has 3 months, cost has 1 → ValueError."""
        req = _make_request(
            tpv_service_output=_tpv_output(horizon=3),
            cost_service_output=_cost_output(horizon=1),
        )
        with pytest.raises(ValueError, match="must match"):
            get_profit_forecast(req)

    def test_simulation_mean_in_response(self):
        """Every month must have simulation_mean."""
        req = _make_request()
        resp = get_profit_forecast(req)
        for m in resp.months:
            assert isinstance(m.simulation_mean, float)

    def test_target_margin_none_gives_null_fields(self):
        """No target_margin → all target fields are None."""
        req = _make_request()
        resp = get_profit_forecast(req)
        for m in resp.months:
            assert m.p_target_margin_met is None
        assert resp.summary.suggested_fee_for_target is None
        assert resp.summary.avg_p_target_margin_met is None
        assert resp.summary.min_p_target_margin_met is None
        assert resp.metadata.target_margin is None

    def test_target_margin_populates_all_fields(self):
        """With target_margin, all target fields are populated."""
        req = _make_request(target_margin=0.005)
        resp = get_profit_forecast(req)
        for m in resp.months:
            assert m.p_target_margin_met is not None
            assert 0.0 <= m.p_target_margin_met <= 1.0
        assert resp.summary.suggested_fee_for_target is not None
        assert resp.summary.avg_p_target_margin_met is not None
        assert resp.summary.min_p_target_margin_met is not None
        assert resp.metadata.target_margin == 0.005

    def test_suggested_fee_for_target_value(self):
        """suggested_fee = break_even + target_margin."""
        req = _make_request(target_margin=0.01)
        resp = get_profit_forecast(req)
        assert resp.summary.suggested_fee_for_target == pytest.approx(
            resp.summary.break_even_fee_rate + 0.01
        )

    def test_per_month_ci_bounds_used(self):
        """Per-month CI bounds should override global half_width."""
        # Construct TPV with very different per-month bounds vs global
        tpv = _tpv_output(horizon=1)
        tpv["forecast"][0]["tpv_ci_lower"] = 9000.0
        tpv["forecast"][0]["tpv_ci_upper"] = 11000.0  # hw=1000
        tpv["conformal_metadata"]["half_width_dollars"] = 200.0  # much narrower

        cost = _cost_output(horizon=1)
        cost["forecast"][0]["proc_cost_pct_ci_lower"] = 0.010
        cost["forecast"][0]["proc_cost_pct_ci_upper"] = 0.030  # hw=0.01
        cost["conformal_metadata"]["half_width"] = 0.002  # much narrower

        req_with = _make_request(
            tpv_service_output=tpv, cost_service_output=cost,
            n_simulations=50_000,
        )
        resp_with = get_profit_forecast(req_with)

        # Construct same but without per-month bounds (fall back to narrow global)
        tpv2 = _tpv_output(horizon=1)
        tpv2["forecast"][0].pop("tpv_ci_lower", None)
        tpv2["forecast"][0].pop("tpv_ci_upper", None)
        tpv2["conformal_metadata"]["half_width_dollars"] = 200.0

        cost2 = _cost_output(horizon=1)
        cost2["forecast"][0].pop("proc_cost_pct_ci_lower", None)
        cost2["forecast"][0].pop("proc_cost_pct_ci_upper", None)
        cost2["conformal_metadata"]["half_width"] = 0.002

        req_without = _make_request(
            tpv_service_output=tpv2, cost_service_output=cost2,
            n_simulations=50_000,
        )
        resp_without = get_profit_forecast(req_without)

        # Per-month bounds (hw=1000) produce wider CI than global (hw=200)
        span_with = (resp_with.months[0].profit_ci_upper
                     - resp_with.months[0].profit_ci_lower)
        span_without = (resp_without.months[0].profit_ci_upper
                        - resp_without.months[0].profit_ci_lower)
        assert span_with > span_without


# ============================================================================
# Model validation tests
# ============================================================================


class TestModelValidation:
    """Pydantic model validation edge cases."""

    def test_fee_rate_must_be_positive(self):
        with pytest.raises(Exception):
            _make_request(fee_rate=0.0)

    def test_fee_rate_must_be_below_one(self):
        with pytest.raises(Exception):
            _make_request(fee_rate=1.0)

    def test_n_simulations_lower_bound(self):
        with pytest.raises(Exception):
            _make_request(n_simulations=50)

    def test_missing_tpv_output_rejected(self):
        with pytest.raises(Exception):
            ProfitForecastRequest(
                cost_service_output=_cost_output(),
                fee_rate=0.029,
                mcc=5411,
            )

    def test_missing_cost_output_rejected(self):
        with pytest.raises(Exception):
            ProfitForecastRequest(
                tpv_service_output=_tpv_output(),
                fee_rate=0.029,
                mcc=5411,
            )
