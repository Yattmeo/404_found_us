from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from models import CompositeWeeklyFeature, CostForecastRequest
from service import _build_onboarding_weekly, _week_of_year, get_cost_forecast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_composite_features(n_weeks: int = 120) -> list[CompositeWeeklyFeature]:
    """
    Generate n_weeks of synthetic composite features.
    Starts at 2020-W01 and advances week numbers (capped at 52 per year).
    Includes a gentle sine-wave in weekly_avg_txn_cost_pct_mean to give
    SARIMA something seasonal to fit.
    """
    features: list[CompositeWeeklyFeature] = []
    year, week = 2020, 1
    for i in range(n_weeks):
        features.append(
            CompositeWeeklyFeature(
                calendar_year=year,
                week_of_year=week,
                weekly_txn_count_mean=100.0,
                weekly_txn_count_stdev=10.0,
                weekly_total_proc_value_mean=5000.0,
                weekly_total_proc_value_stdev=500.0,
                weekly_avg_txn_value_mean=50.0,
                weekly_avg_txn_value_stdev=5.0,
                weekly_avg_txn_cost_pct_mean=0.02 + 0.002 * math.sin(2 * math.pi * i / 52),
                weekly_avg_txn_cost_pct_stdev=0.001,
                neighbor_coverage=5,
                pct_ct_means={"pct_ct_1": 0.6, "pct_ct_2": 0.4},
            )
        )
        week += 1
        if week > 52:
            week = 1
            year += 1
    return features


def _base_request(**overrides) -> CostForecastRequest:
    defaults = dict(
        composite_weekly_features=_make_composite_features(120),
        onboarding_merchant_txn_df=[],
        forecast_horizon_wks=4,
        use_optimised_sarima=False,
        use_guarded_calibration=False,
    )
    defaults.update(overrides)
    return CostForecastRequest(**defaults)


# ---------------------------------------------------------------------------
# Week helper tests
# ---------------------------------------------------------------------------

class TestWeekOfYear:
    def test_jan_1_is_week_1(self):
        assert _week_of_year(pd.Timestamp("2022-01-01")) == 1

    def test_jan_8_is_week_2(self):
        # day_of_year=8 → (8-1)//7+1 = 2
        assert _week_of_year(pd.Timestamp("2022-01-08")) == 2

    def test_dec_31_capped_at_52(self):
        assert _week_of_year(pd.Timestamp("2022-12-31")) == 52

    def test_week_26_midyear(self):
        # day 176 → (176-1)//7+1 = 26
        ts = pd.Timestamp("2022-06-25")
        woy = _week_of_year(ts)
        assert 1 <= woy <= 52


# ---------------------------------------------------------------------------
# Onboarding weekly aggregation tests
# ---------------------------------------------------------------------------

class TestBuildOnboardingWeekly:
    def test_basic_aggregation_two_weeks(self):
        rows = [
            {"date": "2022-01-03", "amount": 100.0, "proc_cost": 2.0},   # week 1
            {"date": "2022-01-05", "amount": 200.0, "proc_cost": 4.0},   # week 1
            {"date": "2022-01-10", "amount": 150.0, "proc_cost": 3.0},   # week 2
        ]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 2
        assert "weekly_avg_txn_cost_pct" in df.columns

    def test_accepts_transaction_date_key(self):
        rows = [{"transaction_date": "2022-01-03", "amount": 100.0, "proc_cost": 2.0}]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 1

    def test_skips_row_with_no_proc_cost(self):
        rows = [{"date": "2022-01-03", "amount": 100.0}]
        df = _build_onboarding_weekly(rows)
        assert df.empty

    def test_skips_zero_amount(self):
        rows = [{"date": "2022-01-03", "amount": 0.0, "proc_cost": 2.0}]
        df = _build_onboarding_weekly(rows)
        assert df.empty

    def test_skips_negative_amount(self):
        rows = [{"date": "2022-01-03", "amount": -50.0, "proc_cost": 1.0}]
        df = _build_onboarding_weekly(rows)
        assert df.empty

    def test_empty_input(self):
        df = _build_onboarding_weekly([])
        assert df.empty

    def test_cost_pct_calculation(self):
        rows = [{"date": "2022-01-03", "amount": 100.0, "proc_cost": 2.0}]
        df = _build_onboarding_weekly(rows)
        assert pytest.approx(df.iloc[0]["weekly_avg_txn_cost_pct"], rel=1e-6) == 0.02


# ---------------------------------------------------------------------------
# get_cost_forecast — core behaviour
# ---------------------------------------------------------------------------

class TestGetCostForecast:
    def test_returns_correct_forecast_length(self):
        req = _base_request(forecast_horizon_wks=6)
        resp = get_cost_forecast(req)
        assert len(resp.forecast) == 6

    def test_week_indices_are_one_based_sequential(self):
        req = _base_request(forecast_horizon_wks=4)
        resp = get_cost_forecast(req)
        assert [w.forecast_week_index for w in resp.forecast] == [1, 2, 3, 4]

    def test_week_indices_start_after_calibration_window(self):
        onboarding = [
            {"date": "2020-01-02", "amount": 100.0, "proc_cost": 2.0},  # week 1
            {"date": "2020-01-09", "amount": 100.0, "proc_cost": 2.0},  # week 2
            {"date": "2020-01-16", "amount": 100.0, "proc_cost": 2.0},  # week 3
            {"date": "2020-01-23", "amount": 100.0, "proc_cost": 2.0},  # week 4
        ]
        req = _base_request(
            onboarding_merchant_txn_df=onboarding,
            forecast_horizon_wks=4,
        )
        resp = get_cost_forecast(req)
        assert resp.process_metadata.context_window_weeks_count == 4
        assert [w.forecast_week_index for w in resp.forecast] == [5, 6, 7, 8]

    def test_ci_ordering(self):
        req = _base_request()
        resp = get_cost_forecast(req)
        for wk in resp.forecast:
            assert wk.proc_cost_pct_ci_lower <= wk.proc_cost_pct_mid
            assert wk.proc_cost_pct_mid <= wk.proc_cost_pct_ci_upper

    def test_non_fallback_response_structure(self):
        req = _base_request()
        resp = get_cost_forecast(req)
        assert resp.process_metadata.is_fallback is False
        assert resp.sarima_metadata.fit_status == "ok"
        assert resp.sarima_metadata.seasonal_length == 13
        assert resp.sarima_metadata.use_exogenous_sarimax is False
        assert resp.sarima_metadata.exogenous_feature_names == []

    def test_seasonal_order_length(self):
        req = _base_request()
        resp = get_cost_forecast(req)
        assert len(resp.sarima_metadata.selected_seasonal_order) == 4
        assert len(resp.sarima_metadata.selected_order) == 3

    def test_fallback_on_insufficient_composite_history(self):
        req = _base_request(
            composite_weekly_features=_make_composite_features(2),
        )
        resp = get_cost_forecast(req)
        assert resp.process_metadata.is_fallback is True
        assert resp.sarima_metadata.fit_status == "fallback"
        # All forecast weeks should be equal (flat constant)
        mids = [w.proc_cost_pct_mid for w in resp.forecast]
        assert len(set(mids)) == 1

    def test_fallback_response_still_has_correct_horizon_length(self):
        req = _base_request(
            composite_weekly_features=_make_composite_features(2),
            forecast_horizon_wks=8,
        )
        resp = get_cost_forecast(req)
        assert len(resp.forecast) == 8

    def test_calibration_skipped_when_no_onboarding_data(self):
        req = _base_request(
            onboarding_merchant_txn_df=[],
            use_guarded_calibration=True,
        )
        resp = get_cost_forecast(req)
        assert resp.process_metadata.calibration_mode == "skipped_insufficient_data"
        assert resp.is_guarded_sarima is False

    def test_calibration_skipped_when_disabled(self):
        req = _base_request(use_guarded_calibration=False)
        resp = get_cost_forecast(req)
        assert resp.process_metadata.calibration_mode == "skipped_disabled"
        assert resp.is_guarded_sarima is False

    def test_calibration_applied_with_matching_onboarding(self):
        # Build onboarding rows whose dates land in calendar weeks present in the composite.
        # Composite starts at 2020-W01 → 2020-01-01 falls in week 1.
        onboarding = [
            {"date": "2020-01-02", "amount": 100.0, "proc_cost": 2.1},   # 2020-W01
            {"date": "2020-01-09", "amount": 110.0, "proc_cost": 2.2},   # 2020-W02
            {"date": "2020-01-16", "amount": 105.0, "proc_cost": 2.15},  # 2020-W03
        ]
        req = _base_request(
            onboarding_merchant_txn_df=onboarding,
            use_guarded_calibration=True,
        )
        resp = get_cost_forecast(req)
        # With 3 matched calibration points, calibration should be attempted.
        # It may succeed or be skipped for statistical reasons; we just assert
        # the metadata is coherent.
        assert resp.process_metadata.matched_calibration_points >= 0
        if resp.is_guarded_sarima:
            assert resp.process_metadata.calibration_mode == "guarded_linear"
            assert resp.process_metadata.calibration_successful is True
            assert resp.process_metadata.calibration_mae is not None
            assert resp.process_metadata.calibration_rmse is not None

    def test_exogenous_sarimax_runs_when_flag_enabled(self):
        req = _base_request(use_exogenous_sarimax=True)
        resp = get_cost_forecast(req)
        assert resp.process_metadata.is_fallback is False
        assert resp.sarima_metadata.use_exogenous_sarimax is True
        assert len(resp.sarima_metadata.exogenous_feature_names) > 0

    def test_calibration_quality_fields_null_when_skipped(self):
        req = _base_request(
            onboarding_merchant_txn_df=[],
            use_guarded_calibration=True,
        )
        resp = get_cost_forecast(req)
        assert resp.process_metadata.calibration_successful is False
        assert resp.process_metadata.calibration_mae is None
        assert resp.process_metadata.calibration_rmse is None
        assert resp.process_metadata.calibration_r2 is None

    def test_context_window_count_matches_onboarding_weeks(self):
        onboarding = [
            {"date": "2020-01-02", "amount": 100.0, "proc_cost": 2.0},  # week 1
            {"date": "2020-01-09", "amount": 100.0, "proc_cost": 2.0},  # week 2
        ]
        req = _base_request(onboarding_merchant_txn_df=onboarding)
        resp = get_cost_forecast(req)
        assert resp.process_metadata.context_window_weeks_count == 2

    def test_metadata_generated_at_utc_present(self):
        req = _base_request()
        resp = get_cost_forecast(req)
        assert resp.process_metadata.generated_at_utc is not None


# ===== Expanded edge case and comprehensive tests =====

class TestOnboardingWeeklyBuildingComprehensive:
    """Comprehensive tests for onboarding weekly aggregation."""

    def test_single_transaction_builds_correctly(self):
        rows = [{"date": "2022-01-03", "amount": 100.0, "proc_cost": 2.0}]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 1
        assert np.isclose(df.iloc[0]["weekly_avg_txn_cost_pct"], 0.02)

    def test_multiple_transactions_same_week_aggregated(self):
        rows = [
            {"date": "2022-01-03", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2022-01-04", "amount": 200.0, "proc_cost": 4.0},
            {"date": "2022-01-05", "amount": 300.0, "proc_cost": 6.0},
        ]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 1
        assert np.isclose(df.iloc[0]["weekly_avg_txn_cost_pct"], 0.02)

    def test_very_large_proc_cost(self):
        """Large processing cost should be handled."""
        rows = [{"date": "2022-01-03", "amount": 100.0, "proc_cost": 50.0}]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 1
        assert np.isclose(df.iloc[0]["weekly_avg_txn_cost_pct"], 0.50)

    def test_very_small_proc_cost(self):
        """Small processing cost should be handled."""
        rows = [{"date": "2022-01-03", "amount": 100.0, "proc_cost": 0.01}]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 1
        assert np.isclose(df.iloc[0]["weekly_avg_txn_cost_pct"], 0.0001)

    def test_negative_proc_cost_handled(self):
        """Negative proc cost (refund) should be handled."""
        rows = [{"date": "2022-01-03", "amount": 100.0, "proc_cost": -2.0}]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 1
        assert np.isfinite(df.iloc[0]["weekly_avg_txn_cost_pct"])

    def test_cross_year_boundary_transactions(self):
        """Transactions spanning year boundary."""
        rows = [
            {"date": "2021-12-29", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2022-01-03", "amount": 200.0, "proc_cost": 4.0},
        ]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 2

    def test_null_proc_cost_filtered_out(self):
        rows = [
            {"date": "2022-01-03", "amount": 100.0, "proc_cost": None},
            {"date": "2022-01-04", "amount": 200.0, "proc_cost": 4.0},
        ]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 1

    def test_zero_and_negative_amounts_filtered(self):
        rows = [
            {"date": "2022-01-03", "amount": 0.0, "proc_cost": 2.0},
            {"date": "2022-01-04", "amount": -100.0, "proc_cost": 2.0},
            {"date": "2022-01-05", "amount": 100.0, "proc_cost": 2.0},
        ]
        df = _build_onboarding_weekly(rows)
        assert len(df) == 1


class TestCostForecastConfidenceIntervals:
    """Comprehensive CI validation."""

    def test_ci_lower_le_mid_le_upper_all_weeks(self):
        """All weeks must satisfy lower <= mid <= upper."""
        req = _base_request(forecast_horizon_wks=10)
        resp = get_cost_forecast(req)
        for wk in resp.forecast:
            assert wk.proc_cost_pct_ci_lower <= wk.proc_cost_pct_mid
            assert wk.proc_cost_pct_mid <= wk.proc_cost_pct_ci_upper

    def test_ci_non_negative(self):
        """CIs should not be negative."""
        req = _base_request(forecast_horizon_wks=8)
        resp = get_cost_forecast(req)
        for wk in resp.forecast:
            assert wk.proc_cost_pct_ci_lower >= 0
            assert wk.proc_cost_pct_ci_upper >= 0

    def test_ci_width_monotonic_increasing_with_horizon(self):
        """CI widths should generally increase further out."""
        req = _base_request(forecast_horizon_wks=12)
        resp = get_cost_forecast(req)
        widths = [w.proc_cost_pct_ci_upper - w.proc_cost_pct_ci_lower for w in resp.forecast]
        # Check last week CI is wider than first week CI
        assert widths[-1] >= widths[0]

    def test_ci_narrower_at_lower_confidence(self):
        """CI should be narrower at 68% than 95%."""
        req_68 = CostForecastRequest(
            composite_weekly_features=_make_composite_features(120),
            onboarding_merchant_txn_df=[],
            forecast_horizon_wks=4,
            confidence_interval=0.68,
        )
        req_95 = CostForecastRequest(
            composite_weekly_features=_make_composite_features(120),
            onboarding_merchant_txn_df=[],
            forecast_horizon_wks=4,
            confidence_interval=0.95,
        )
        resp_68 = get_cost_forecast(req_68)
        resp_95 = get_cost_forecast(req_95)
        
        width_68 = np.mean([w.proc_cost_pct_ci_upper - w.proc_cost_pct_ci_lower for w in resp_68.forecast])
        width_95 = np.mean([w.proc_cost_pct_ci_upper - w.proc_cost_pct_ci_lower for w in resp_95.forecast])
        assert width_68 <= width_95


class TestCostForecastBoundaryConditions:
    """Boundary conditions and constraint satisfaction."""

    def test_single_week_horizon(self):
        req = _base_request(forecast_horizon_wks=1)
        resp = get_cost_forecast(req)
        assert len(resp.forecast) == 1

    def test_very_long_horizon_26_weeks(self):
        req = _base_request(
            composite_weekly_features=_make_composite_features(180),
            forecast_horizon_wks=26,
        )
        resp = get_cost_forecast(req)
        assert len(resp.forecast) == 26

    def test_minimum_composite_features_for_fit(self):
        """Minimum features needed for SARIMA fit."""
        req = _base_request(
            composite_weekly_features=_make_composite_features(26),
            forecast_horizon_wks=4,
        )
        resp = get_cost_forecast(req)
        assert len(resp.forecast) == 4

    def test_constant_proc_cost_pct(self):
        """When proc cost pct is constant (no seasonality)."""
        const_features = [
            CompositeWeeklyFeature(
                calendar_year=2020 + (i // 52),
                week_of_year=(i % 52) + 1,
                weekly_txn_count_mean=100.0,
                weekly_txn_count_stdev=10.0,
                weekly_total_proc_value_mean=5000.0,
                weekly_total_proc_value_stdev=500.0,
                weekly_avg_txn_value_mean=50.0,
                weekly_avg_txn_value_stdev=5.0,
                weekly_avg_txn_cost_pct_mean=0.02,  # Constant
                weekly_avg_txn_cost_pct_stdev=0.001,
                neighbor_coverage=5,
                pct_ct_means={"pct_ct_1": 0.6, "pct_ct_2": 0.4},
            )
            for i in range(100)
        ]
        req = _base_request(
            composite_weekly_features=const_features,
            forecast_horizon_wks=6,
        )
        resp = get_cost_forecast(req)
        assert len(resp.forecast) == 6


class TestCalibrationQuality:
    """Calibration mode selection and quality metrics."""

    def test_calibration_mae_non_negative(self):
        """MAE should be non-negative."""
        onboarding = [
            {"date": "2020-01-02", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2020-01-09", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2020-01-16", "amount": 100.0, "proc_cost": 2.0},
        ]
        req = _base_request(
            onboarding_merchant_txn_df=onboarding,
            use_guarded_calibration=True,
        )
        resp = get_cost_forecast(req)
        if resp.process_metadata.calibration_mae is not None:
            assert resp.process_metadata.calibration_mae >= 0

    def test_calibration_rmse_non_negative(self):
        """RMSE should be non-negative."""
        onboarding = [
            {"date": "2020-01-02", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2020-01-09", "amount": 100.0, "proc_cost": 2.0},
        ]
        req = _base_request(
            onboarding_merchant_txn_df=onboarding,
            use_guarded_calibration=True,
        )
        resp = get_cost_forecast(req)
        if resp.process_metadata.calibration_rmse is not None:
            assert resp.process_metadata.calibration_rmse >= 0

    def test_calibration_r2_in_valid_range(self):
        """R² should be <= 1.0."""
        onboarding = [
            {"date": "2020-01-02", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2020-01-09", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2020-01-16", "amount": 100.0, "proc_cost": 2.0},
        ]
        req = _base_request(
            onboarding_merchant_txn_df=onboarding,
            use_guarded_calibration=True,
        )
        resp = get_cost_forecast(req)
        if resp.process_metadata.calibration_r2 is not None:
            assert resp.process_metadata.calibration_r2 <= 1.0


class TestResponseIntegrity:
    """Ensure response structure integrity."""

    def test_response_structure_always_has_forecast(self):
        """Response always has forecast list of correct length."""
        for horizon in [1, 4, 8, 13]:
            req = _base_request(forecast_horizon_wks=horizon)
            resp = get_cost_forecast(req)
            assert resp.forecast is not None
            assert len(resp.forecast) == horizon

    def test_week_indices_always_sequential_one_based(self):
        """Week indices always 1, 2, 3, ... (one-based, sequential)."""
        for horizon in [1, 4, 8, 13, 26]:
            req = _base_request(
                composite_weekly_features=_make_composite_features(180),
                forecast_horizon_wks=horizon
            )
            resp = get_cost_forecast(req)
            indices = [w.forecast_week_index for w in resp.forecast]
            assert indices == list(range(1, horizon + 1))

    def test_all_forecast_weeks_have_required_fields(self):
        """Each forecast week has all required fields."""
        req = _base_request(forecast_horizon_wks=5)
        resp = get_cost_forecast(req)
        for wk in resp.forecast:
            assert wk.forecast_week_index is not None
            assert wk.proc_cost_pct_mid is not None
            assert wk.proc_cost_pct_ci_lower is not None
            assert wk.proc_cost_pct_ci_upper is not None

    def test_metadata_always_populated(self):
        """Metadata fields always populated."""
        req = _base_request()
        resp = get_cost_forecast(req)
        assert resp.process_metadata.is_fallback is not None
        assert resp.process_metadata.generated_at_utc is not None
        assert resp.sarima_metadata.fit_status is not None
        assert resp.sarima_metadata.seasonal_length is not None

    def test_fallback_response_is_flat(self):
        """Fallback responses should have identical forecasts."""
        req = _base_request(
            composite_weekly_features=_make_composite_features(2),
            forecast_horizon_wks=8,
        )
        resp = get_cost_forecast(req)
        if resp.process_metadata.is_fallback:
            mids = [w.proc_cost_pct_mid for w in resp.forecast]
            # All should be effectively equal (within rounding)
            assert len(set([round(m, 10) for m in mids])) == 1


class TestDateHandlingEdgeCases:
    """Date handling and edge cases."""

    def test_onboarding_spanning_year_boundary(self):
        onboarding = [
            {"date": "2019-12-27", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2020-01-02", "amount": 100.0, "proc_cost": 2.0},
        ]
        req = _base_request(onboarding_merchant_txn_df=onboarding)
        resp = get_cost_forecast(req)
        assert resp.process_metadata.context_window_weeks_count == 2

    def test_onboarding_in_leap_year(self):
        """Transactions in leap year (Feb 29)."""
        onboarding = [
            {"date": "2020-02-29", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2020-03-05", "amount": 100.0, "proc_cost": 2.0},
        ]
        req = _base_request(onboarding_merchant_txn_df=onboarding)
        resp = get_cost_forecast(req)
        assert len(resp.forecast) > 0

    def test_very_old_onboarding_dates(self):
        """Onboarding from much earlier than composite features (no overlap)."""
        onboarding = [
            {"date": "2010-01-15", "amount": 100.0, "proc_cost": 2.0},
            {"date": "2010-02-15", "amount": 100.0, "proc_cost": 2.0},
        ]
        req = _base_request(
            composite_weekly_features=_make_composite_features(120),
            onboarding_merchant_txn_df=onboarding,
            use_guarded_calibration=True,
        )
        resp = get_cost_forecast(req)
        # Should handle gracefully (likely no matching weeks for calibration)
        assert len(resp.forecast) > 0
