"""
tests/test_soft_guardrail_profitability.py

Verifies the relationship between conformal half-width, fee rate,
and P(profitable) under the soft-guardrail cost sampling strategy.

Key finding: the soft guardrail places ~5% of samples ABOVE the CI
upper bound via an exponential tail.  When the CI upper is close to
or exceeds the fee rate, this tail drags P(profitable) well below the
nominal coverage (e.g. 65% instead of 95%).  This is mathematically
correct — the test documents and locks in that behaviour.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Make the profit_forecast module importable
# ---------------------------------------------------------------------------
ML_SERVICE_ROOT = Path(__file__).resolve().parents[3]  # ml_service/
sys.path.insert(0, str(ML_SERVICE_ROOT))

from modules.profit_forecast.service import (
    _sample_cost_pct_soft_guardrail,
    _simulate_profit_month,
    get_profit_forecast,
)
from modules.profit_forecast.models import (
    ProfitForecastRequest,
    ProfitMonth,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tpv_output(horizon: int = 3, tpv_mid: float = 50_000.0, hw: float = 5_000.0):
    return {
        "forecast": [
            {
                "month_index": i + 1,
                "tpv_mid": tpv_mid,
                "tpv_ci_lower": tpv_mid - hw,
                "tpv_ci_upper": tpv_mid + hw,
            }
            for i in range(horizon)
        ],
        "conformal_metadata": {
            "half_width_dollars": hw,
            "conformal_mode": "test",
        },
        "process_metadata": {"context_len_used": 6},
    }


def _cost_output(
    horizon: int = 3,
    cost_mid: float = 0.038,
    hw: float = 0.05,
):
    return {
        "forecast": [
            {
                "month_index": i + 1,
                "proc_cost_pct_mid": cost_mid,
                "proc_cost_pct_ci_lower": max(cost_mid - hw, 0.0),
                "proc_cost_pct_ci_upper": cost_mid + hw,
            }
            for i in range(horizon)
        ],
        "conformal_metadata": {
            "half_width": hw,
            "conformal_mode": "test",
        },
        "process_metadata": {"context_len_used": 6},
    }


def _make_request(**overrides) -> ProfitForecastRequest:
    defaults = dict(
        tpv_service_output=_tpv_output(),
        cost_service_output=_cost_output(),
        fee_rate=0.05,
        mcc=5411,
        merchant_id="test",
        confidence_interval=0.90,
        n_simulations=50_000,
    )
    defaults.update(overrides)
    return ProfitForecastRequest(**defaults)


# ============================================================================
# Tests for _sample_cost_pct_soft_guardrail tail behaviour
# ============================================================================


class TestSoftGuardrailTailBehaviour:
    """Verify that the soft guardrail produces explicit tails beyond CI."""

    @pytest.fixture()
    def rng(self):
        return np.random.default_rng(42)

    def test_samples_exceed_ci_upper(self, rng):
        """Some samples must lie above CI upper (soft, not hard clip)."""
        ci_upper = 0.038
        samples = _sample_cost_pct_soft_guardrail(
            cost_pct_mid=0.033,
            cost_pct_hw=0.005,
            confidence_interval=0.90,
            n_simulations=100_000,
            rng=rng,
            cost_pct_ci_lower=0.028,
            cost_pct_ci_upper=ci_upper,
        )
        pct_above = float((samples > ci_upper).mean())
        # Expect ~5% of samples above CI upper (alpha/2 = 0.05)
        assert pct_above > 0.03, f"Expected >3% above CI upper, got {pct_above:.1%}"

    def test_samples_below_ci_lower(self, rng):
        """Some samples must lie below CI lower (left tail)."""
        ci_lower = 0.028
        samples = _sample_cost_pct_soft_guardrail(
            cost_pct_mid=0.033,
            cost_pct_hw=0.005,
            confidence_interval=0.90,
            n_simulations=100_000,
            rng=rng,
            cost_pct_ci_lower=ci_lower,
            cost_pct_ci_upper=0.038,
        )
        pct_below = float((samples < ci_lower).mean())
        assert pct_below > 0.03, f"Expected >3% below CI lower, got {pct_below:.1%}"

    def test_approximately_ci_fraction_inside_bounds(self, rng):
        """~90% of samples should land inside [CI_lower, CI_upper]."""
        ci_lower, ci_upper = 0.028, 0.038
        samples = _sample_cost_pct_soft_guardrail(
            cost_pct_mid=0.033,
            cost_pct_hw=0.005,
            confidence_interval=0.90,
            n_simulations=100_000,
            rng=rng,
            cost_pct_ci_lower=ci_lower,
            cost_pct_ci_upper=ci_upper,
        )
        pct_inside = float(((samples >= ci_lower) & (samples <= ci_upper)).mean())
        assert 0.85 < pct_inside < 0.95, (
            f"Expected ~90% inside CI, got {pct_inside:.1%}"
        )

    def test_all_samples_nonnegative(self, rng):
        """cost_pct samples must be ≥ 0 (physically feasible)."""
        samples = _sample_cost_pct_soft_guardrail(
            cost_pct_mid=0.01,
            cost_pct_hw=0.02,
            confidence_interval=0.90,
            n_simulations=100_000,
            rng=rng,
            cost_pct_ci_lower=0.0,
            cost_pct_ci_upper=0.03,
        )
        assert samples.min() >= 0.0


# ============================================================================
# Tests: wide CI suppresses P(profitable) — the user's reported scenario
# ============================================================================


class TestWideCISuppressesProfitability:
    """
    Reproduces the user's observation:

        cost CI 95th pct ≈ 3.8%, fee = 5%
        → expected P(profitable) ≥ 95%
        → actual P(profitable) ≈ 65%

    Root cause: conformal half_width is much wider than the
    cost_mid-to-CI_upper gap, pushing the effective CI upper
    well above 5% and placing heavy exponential tail mass there.
    """

    @pytest.fixture()
    def rng(self):
        return np.random.default_rng(42)

    def test_narrow_hw_gives_high_profitability(self, rng):
        """
        cost_mid=3.3%, CI=[2.8%, 3.8%], fee=5%.
        Narrow CI → P(profitable) should be >95%.
        """
        pm = _simulate_profit_month(
            tpv_mid=50_000.0,
            tpv_hw=5_000.0,
            cost_pct_mid=0.033,
            cost_pct_hw=0.005,
            fee_rate=0.05,
            confidence_interval=0.90,
            n_simulations=100_000,
            rng=rng,
            cost_pct_ci_lower=0.028,
            cost_pct_ci_upper=0.038,
        )
        assert pm.p_profitable > 0.95, (
            f"Narrow CI: expected P(profitable) > 95%, got {pm.p_profitable:.1%}"
        )

    def test_wide_hw_suppresses_profitability(self, rng):
        """
        cost_mid=3.8%, hw=5% → CI=[-1.2%, 8.8%], fee=5%.
        Wide CI + exponential upper tail → P(profitable) ≈ 60-70%.
        This is the user's observed scenario.
        """
        pm = _simulate_profit_month(
            tpv_mid=50_000.0,
            tpv_hw=5_000.0,
            cost_pct_mid=0.038,
            cost_pct_hw=0.05,
            fee_rate=0.05,
            confidence_interval=0.90,
            n_simulations=100_000,
            rng=rng,
            cost_pct_ci_lower=0.0,  # clamped at 0
            cost_pct_ci_upper=0.088,
        )
        # P(profitable) should be well below 95% due to tail sampling
        assert pm.p_profitable < 0.80, (
            f"Wide CI: expected P(profitable) < 80%, got {pm.p_profitable:.1%}"
        )
        # But still majority-profitable since point forecast is below fee
        assert pm.p_profitable > 0.50, (
            f"Wide CI: expected P(profitable) > 50%, got {pm.p_profitable:.1%}"
        )

    def test_profitability_decreases_with_wider_hw(self, rng):
        """
        Increasing the half-width monotonically decreases P(profitable)
        when cost_mid < fee_rate.
        """
        half_widths = [0.005, 0.01, 0.02, 0.03, 0.05]
        p_profs = []
        for hw in half_widths:
            r = np.random.default_rng(42)
            pm = _simulate_profit_month(
                tpv_mid=50_000.0,
                tpv_hw=5_000.0,
                cost_pct_mid=0.038,
                cost_pct_hw=hw,
                fee_rate=0.05,
                confidence_interval=0.90,
                n_simulations=100_000,
                rng=r,
                cost_pct_ci_lower=max(0.038 - hw, 0.0),
                cost_pct_ci_upper=0.038 + hw,
            )
            p_profs.append(pm.p_profitable)

        # Verify monotonically non-increasing
        for i in range(1, len(p_profs)):
            assert p_profs[i] <= p_profs[i - 1] + 0.02, (
                f"P(profitable) should decrease as hw grows: "
                f"hw={half_widths[i]:.3f} gave {p_profs[i]:.3f} vs "
                f"hw={half_widths[i-1]:.3f} gave {p_profs[i-1]:.3f}"
            )

    def test_upper_tail_is_the_dominant_cause(self, rng):
        """
        Verify that the fraction of cost samples exceeding fee_rate
        closely matches 1 − P(profitable), confirming the tail is the
        cause (not TPV uncertainty).
        """
        fee_rate = 0.05
        cost_mid = 0.038
        hw = 0.04

        # Sample cost% directly
        cost_samples = _sample_cost_pct_soft_guardrail(
            cost_pct_mid=cost_mid,
            cost_pct_hw=hw,
            confidence_interval=0.90,
            n_simulations=200_000,
            rng=rng,
            cost_pct_ci_lower=max(cost_mid - hw, 0.0),
            cost_pct_ci_upper=cost_mid + hw,
        )
        pct_cost_exceeds_fee = float((cost_samples > fee_rate).mean())

        # Run the full simulation
        rng2 = np.random.default_rng(42)
        pm = _simulate_profit_month(
            tpv_mid=50_000.0,
            tpv_hw=5_000.0,
            cost_pct_mid=cost_mid,
            cost_pct_hw=hw,
            fee_rate=fee_rate,
            confidence_interval=0.90,
            n_simulations=200_000,
            rng=rng2,
            cost_pct_ci_lower=max(cost_mid - hw, 0.0),
            cost_pct_ci_upper=cost_mid + hw,
        )

        unprofitable_pct = 1.0 - pm.p_profitable

        # The cost-exceeds-fee fraction should approximate the unprofitable fraction
        # (they won't be exact because TPV uncertainty adds some noise)
        assert abs(pct_cost_exceeds_fee - unprofitable_pct) < 0.05, (
            f"cost_exceeds_fee={pct_cost_exceeds_fee:.3f} vs "
            f"unprofitable={unprofitable_pct:.3f} — gap too large"
        )


# ============================================================================
# End-to-end: full get_profit_forecast with the user's scenario
# ============================================================================


class TestEndToEndUserScenario:
    """
    Simulate the user's exact scenario through get_profit_forecast:
    cost_mid ≈ 3.8%, wide conformal hw → P(profitable) ≈ 65%.
    """

    def test_user_scenario_reproduces_65pct(self):
        """fee=5%, cost_mid=3.8%, wide hw → avg_p_profitable well below 95%."""
        req = _make_request(
            tpv_service_output=_tpv_output(horizon=3),
            cost_service_output=_cost_output(
                horizon=3, cost_mid=0.038, hw=0.05,
            ),
            fee_rate=0.05,
            n_simulations=50_000,
        )
        resp = get_profit_forecast(req)

        # Matches the user's observation: ~60-70%, NOT 95%
        assert resp.summary.avg_p_profitable < 0.80
        assert resp.summary.avg_p_profitable > 0.50

    def test_same_scenario_narrow_hw_gives_95pct(self):
        """Same inputs but narrow hw → P(profitable) > 95%."""
        req = _make_request(
            tpv_service_output=_tpv_output(horizon=3),
            cost_service_output=_cost_output(
                horizon=3, cost_mid=0.038, hw=0.005,
            ),
            fee_rate=0.05,
            n_simulations=50_000,
        )
        resp = get_profit_forecast(req)

        assert resp.summary.avg_p_profitable > 0.95, (
            f"Narrow hw: expected >95%, got {resp.summary.avg_p_profitable:.1%}"
        )

    def test_break_even_fee_exceeds_ci_upper_when_hw_wide(self):
        """
        With wide hw, break_even_fee_rate = CI_upper = cost_mid + hw,
        which can be much higher than what the user expects.
        """
        hw = 0.05
        cost_mid = 0.038
        req = _make_request(
            cost_service_output=_cost_output(horizon=3, cost_mid=cost_mid, hw=hw),
        )
        resp = get_profit_forecast(req)

        # break_even = worst-case CI upper = 0.038 + 0.05 = 0.088
        assert resp.summary.break_even_fee_rate == pytest.approx(
            cost_mid + hw, abs=0.001,
        )
        # This is 8.8% — much higher than the 5% fee rate
        assert resp.summary.break_even_fee_rate > 0.05
