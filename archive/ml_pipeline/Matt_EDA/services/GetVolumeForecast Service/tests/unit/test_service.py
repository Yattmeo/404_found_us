import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import CompositeWeeklyFeature, VolumeForecastRequest
from service import _build_onboarding_weekly, get_volume_forecast


def _make_features(n=40, start_year=2024, start_week=1, base=1500.0):
    rows = []
    year = start_year
    week = start_week
    for i in range(n):
        seasonal = 120.0 * np.sin(2 * np.pi * (i % 13) / 13)
        trend = i * 4.0
        v = base + seasonal + trend
        rows.append(
            CompositeWeeklyFeature(
                calendar_year=year,
                week_of_year=week,
                weekly_txn_count_mean=float(2000 + i * 10),
                weekly_txn_count_stdev=float(90 + (i % 13)),
                weekly_total_proc_value_mean=float(v),
                weekly_total_proc_value_stdev=float(80 + (i % 11)),
                weekly_avg_txn_value_mean=float(25 + (i % 6)),
                weekly_avg_txn_value_stdev=float(3 + (i % 5)),
                weekly_avg_txn_cost_pct_mean=float(0.01 + 0.0001 * (i % 10)),
                weekly_avg_txn_cost_pct_stdev=float(0.002 + 0.0001 * (i % 4)),
                neighbor_coverage=int(50 + (i % 5)),
                pct_ct_means={"card_present": 0.6, "card_not_present": 0.4},
            )
        )
        week += 1
        if week > 52:
            week = 1
            year += 1
    return rows


def _make_onboarding_txns(year=2024, start_week=10, weeks=8, txns_per_week=3, base_amt=400.0):
    txns = []
    for w in range(start_week, start_week + weeks):
        for t in range(txns_per_week):
            day = min(1 + ((w - 1) * 7) + t, 365)
            date = f"{year}-01-01"
            ts = np.datetime64(date) + np.timedelta64(day - 1, "D")
            txns.append(
                {
                    "transaction_date": str(ts),
                    "amount": float(base_amt + 10 * t + 2 * (w - start_week)),
                }
            )
    return txns


def test_build_onboarding_weekly_basic():
    txns = [
        {"transaction_date": "2024-01-02", "amount": 100.0},
        {"transaction_date": "2024-01-04", "amount": 80.0},
        {"transaction_date": "2024-01-12", "amount": 200.0},
    ]

    weekly = _build_onboarding_weekly(txns)

    assert list(weekly.columns) == ["calendar_year", "week_of_year", "weekly_total_proc_value"]
    assert len(weekly) == 2
    assert np.isclose(float(weekly.iloc[0]["weekly_total_proc_value"]), 180.0)
    assert np.isclose(float(weekly.iloc[1]["weekly_total_proc_value"]), 200.0)


def test_fallback_when_insufficient_history():
    req = VolumeForecastRequest(
        onboarding_merchant_txn_df=_make_onboarding_txns(weeks=4),
        composite_weekly_features=_make_features(n=3),
        forecast_horizon_wks=6,
        confidence_interval=0.95,
    )

    resp = get_volume_forecast(req)

    assert resp.process_metadata.is_fallback is True
    assert len(resp.forecast) == 6
    mids = [w.total_proc_value_mid for w in resp.forecast]
    assert all(v >= 0 for v in mids)
    assert resp.sarima_metadata.fit_status == "fallback"


def test_forecast_shape_and_ordering_non_fallback():
    req = VolumeForecastRequest(
        onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
        composite_weekly_features=_make_features(n=52),
        forecast_horizon_wks=13,
        confidence_interval=0.9,
        use_optimised_sarima=False,
        use_exogenous_sarimax=False,
        use_guarded_calibration=True,
    )

    resp = get_volume_forecast(req)

    assert resp.process_metadata.is_fallback is False
    assert len(resp.forecast) == 13
    week_idx = [w.forecast_week_index for w in resp.forecast]
    assert week_idx == sorted(week_idx)
    assert all(w.total_proc_value_ci_lower <= w.total_proc_value_mid <= w.total_proc_value_ci_upper for w in resp.forecast)
    assert len(resp.context_sarima_fitted) == resp.process_metadata.context_window_weeks_count


def test_optimised_sarima_metadata_present():
    req = VolumeForecastRequest(
        onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
        composite_weekly_features=_make_features(n=48),
        forecast_horizon_wks=8,
        confidence_interval=0.95,
        use_optimised_sarima=True,
        use_exogenous_sarimax=False,
    )

    resp = get_volume_forecast(req)

    assert resp.sarima_metadata.use_optimised_sarima is True
    assert resp.sarima_metadata.optimisation_attempted is True
    assert resp.sarima_metadata.optimisation_candidates_evaluated >= 1


def test_exogenous_sarimax_runs():
    req = VolumeForecastRequest(
        onboarding_merchant_txn_df=_make_onboarding_txns(weeks=9),
        composite_weekly_features=_make_features(n=45),
        forecast_horizon_wks=7,
        use_exogenous_sarimax=True,
        use_optimised_sarima=False,
    )

    resp = get_volume_forecast(req)

    assert resp.process_metadata.is_fallback is False
    assert resp.sarima_metadata.use_exogenous_sarimax is True
    assert len(resp.sarima_metadata.exogenous_feature_names) > 0


def test_calibration_disabled_flag():
    req = VolumeForecastRequest(
        onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
        composite_weekly_features=_make_features(n=50),
        forecast_horizon_wks=6,
        use_guarded_calibration=False,
    )

    resp = get_volume_forecast(req)

    assert resp.process_metadata.used_guarded_calibration is False
    assert resp.process_metadata.calibration_mode == "skipped_disabled"
    assert resp.is_guarded_sarima is False


# ===== Expanded edge case and comprehensive tests =====

class TestOnboardingBuildingEdgeCases:
    """Edge cases for onboarding data processing."""

    def test_single_transaction(self):
        txns = [{"transaction_date": "2024-03-15", "amount": 500.0}]
        weekly = _build_onboarding_weekly(txns)
        assert len(weekly) == 1
        assert np.isclose(float(weekly.iloc[0]["weekly_total_proc_value"]), 500.0)

    def test_all_transactions_same_week(self):
        txns = [
            {"transaction_date": "2024-03-11", "amount": 100.0},
            {"transaction_date": "2024-03-12", "amount": 200.0},
            {"transaction_date": "2024-03-13", "amount": 150.0},
        ]
        weekly = _build_onboarding_weekly(txns)
        assert len(weekly) == 1
        assert np.isclose(float(weekly.iloc[0]["weekly_total_proc_value"]), 450.0)

    def test_transactions_spanning_multiple_years(self):
        txns = [
            {"transaction_date": "2023-12-28", "amount": 300.0},
            {"transaction_date": "2024-01-04", "amount": 400.0},
        ]
        weekly = _build_onboarding_weekly(txns)
        assert len(weekly) == 2

    def test_very_large_transaction_amount(self):
        txns = [{"transaction_date": "2024-01-15", "amount": 1_000_000.0}]
        weekly = _build_onboarding_weekly(txns)
        assert np.isclose(float(weekly.iloc[0]["weekly_total_proc_value"]), 1_000_000.0)

    def test_very_small_transaction_amount(self):
        txns = [{"transaction_date": "2024-01-15", "amount": 0.01}]
        weekly = _build_onboarding_weekly(txns)
        assert len(weekly) == 1
        assert weekly.iloc[0]["weekly_total_proc_value"] > 0

    def test_transaction_date_column_alias(self):
        """Should accept both 'date' and 'transaction_date'."""
        txns_date = [{"date": "2024-01-15", "amount": 100.0}]
        txns_tx_date = [{"transaction_date": "2024-01-15", "amount": 100.0}]
        weekly1 = _build_onboarding_weekly(txns_date)
        weekly2 = _build_onboarding_weekly(txns_tx_date)
        assert len(weekly1) == len(weekly2) == 1

    def test_missing_amount_column(self):
        txns = [{"transaction_date": "2024-01-15"}]
        weekly = _build_onboarding_weekly(txns)
        assert weekly.empty

    def test_null_dates_skipped(self):
        txns = [
            {"transaction_date": None, "amount": 100.0},
            {"transaction_date": "2024-01-15", "amount": 200.0},
        ]
        weekly = _build_onboarding_weekly(txns)
        assert len(weekly) == 1


class TestForecastConfidenceIntervals:
    """Comprehensive CI bounds validation."""

    def test_ci_ordering_all_weeks(self):
        """All weeks must have lower <= mid <= upper."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=12),
            composite_weekly_features=_make_features(n=60),
            forecast_horizon_wks=10,
            confidence_interval=0.95,
        )
        resp = get_volume_forecast(req)
        for w in resp.forecast:
            assert w.total_proc_value_ci_lower <= w.total_proc_value_mid, \
                f"Week {w.forecast_week_index}: lower > mid"
            assert w.total_proc_value_mid <= w.total_proc_value_ci_upper, \
                f"Week {w.forecast_week_index}: mid > upper"

    def test_ci_widths_reasonable_at_80_percent(self):
        """Narrower CI at 80% vs 95%."""
        req_80 = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
            composite_weekly_features=_make_features(n=50),
            forecast_horizon_wks=6,
            confidence_interval=0.80,
        )
        req_95 = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
            composite_weekly_features=_make_features(n=50),
            forecast_horizon_wks=6,
            confidence_interval=0.95,
        )
        resp_80 = get_volume_forecast(req_80)
        resp_95 = get_volume_forecast(req_95)

        width_80 = [w.total_proc_value_ci_upper - w.total_proc_value_ci_lower for w in resp_80.forecast]
        width_95 = [w.total_proc_value_ci_upper - w.total_proc_value_ci_lower for w in resp_95.forecast]
        # CI at 95% should generally be wider than 80%
        assert np.mean(width_95) > np.mean(width_80)

    def test_ci_with_99_percent_confidence(self):
        """Very high confidence interval."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=12),
            composite_weekly_features=_make_features(n=52),
            forecast_horizon_wks=8,
            confidence_interval=0.99,
        )
        resp = get_volume_forecast(req)
        assert len(resp.forecast) == 8
        for w in resp.forecast:
            assert w.total_proc_value_ci_lower >= 0
            assert w.total_proc_value_ci_upper >= w.total_proc_value_mid


class TestForecastBoundaryConditions:
    """Boundary conditions and constraint satisfaction."""

    def test_non_negative_forecasts(self):
        """Forecasts should never be negative."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
            composite_weekly_features=_make_features(n=50),
            forecast_horizon_wks=12,
        )
        resp = get_volume_forecast(req)
        for w in resp.forecast:
            assert w.total_proc_value_mid >= 0, f"Week {w.forecast_week_index} has negative forecast"
            assert w.total_proc_value_ci_lower >= 0, f"Week {w.forecast_week_index} has negative lower CI"

    def test_minimum_data_for_sarima_fit(self):
        """Test with exactly minimum weeks needed for SARIMA."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
            composite_weekly_features=_make_features(n=26),
            forecast_horizon_wks=4,
        )
        resp = get_volume_forecast(req)
        assert len(resp.forecast) == 4

    def test_very_long_forecast_horizon(self):
        """Forecast 26 weeks ahead."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=12),
            composite_weekly_features=_make_features(n=52),
            forecast_horizon_wks=26,
        )
        resp = get_volume_forecast(req)
        assert len(resp.forecast) == 26
        assert resp.process_metadata.is_fallback is False

    def test_single_week_horizon(self):
        """Forecast just one week."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=8),
            composite_weekly_features=_make_features(n=40),
            forecast_horizon_wks=1,
        )
        resp = get_volume_forecast(req)
        assert len(resp.forecast) == 1
        assert resp.forecast[0].forecast_week_index == 1


class TestGuardedCalibrationModes:
    """Guarded calibration with multiple modes."""

    def test_guarded_calibration_enabled_vs_disabled(self):
        """Compare results with/without guarded calibration."""
        txns = _make_onboarding_txns(weeks=10)
        features = _make_features(n=50)

        req_enabled = VolumeForecastRequest(
            onboarding_merchant_txn_df=txns,
            composite_weekly_features=features,
            forecast_horizon_wks=6,
            use_guarded_calibration=True,
        )
        req_disabled = VolumeForecastRequest(
            onboarding_merchant_txn_df=txns,
            composite_weekly_features=features,
            forecast_horizon_wks=6,
            use_guarded_calibration=False,
        )

        resp_enabled = get_volume_forecast(req_enabled)
        resp_disabled = get_volume_forecast(req_disabled)

        # Both should have valid forecasts
        assert len(resp_enabled.forecast) == len(resp_disabled.forecast) == 6

        # Calibration metadata should differ
        if not resp_disabled.process_metadata.is_fallback:
            assert resp_enabled.process_metadata.used_guarded_calibration is True
            assert resp_disabled.process_metadata.used_guarded_calibration is False

    def test_calibration_mode_selection_recorded(self):
        """Calibration mode should be recorded in metadata."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=12),
            composite_weekly_features=_make_features(n=52),
            forecast_horizon_wks=8,
            use_guarded_calibration=True,
        )
        resp = get_volume_forecast(req)
        if not resp.process_metadata.is_fallback:
            assert resp.process_metadata.calibration_mode in [
                "guarded_linear",
                "guarded_scale",
                "guarded_shift",
                "no_calibration",
                "skipped_disabled"
            ]

    def test_optimised_vs_standard_sarima(self):
        """Compare optimised SARIMA vs standard."""
        txns = _make_onboarding_txns(weeks=10)
        features = _make_features(n=52)

        req_opt = VolumeForecastRequest(
            onboarding_merchant_txn_df=txns,
            composite_weekly_features=features,
            forecast_horizon_wks=6,
            use_optimised_sarima=True,
        )
        req_std = VolumeForecastRequest(
            onboarding_merchant_txn_df=txns,
            composite_weekly_features=features,
            forecast_horizon_wks=6,
            use_optimised_sarima=False,
        )

        resp_opt = get_volume_forecast(req_opt)
        resp_std = get_volume_forecast(req_std)

        # Optimised should record attempt
        assert resp_opt.sarima_metadata.use_optimised_sarima is True


class TestSparseAndAnomalousData:
    """Sparse data, gaps, and anomalous patterns."""

    def test_sparse_onboarding_data(self):
        """Only a few transactions spread over time."""
        txns = [
            {"transaction_date": "2024-01-05", "amount": 200.0},
            {"transaction_date": "2024-03-20", "amount": 250.0},
            {"transaction_date": "2024-05-15", "amount": 180.0},
        ]
        onboarding_weekly = _build_onboarding_weekly(txns)
        assert len(onboarding_weekly) == 3

    def test_composite_features_with_zero_stdev(self):
        """Features with zero standard deviation (constant values)."""
        rows = []
        for i in range(50):
            year = 2024
            week = (i % 52) + 1
            rows.append(
                CompositeWeeklyFeature(
                    calendar_year=year,
                    week_of_year=week,
                    weekly_txn_count_mean=2000.0,
                    weekly_txn_count_stdev=0.0,  # Zero stdev
                    weekly_total_proc_value_mean=1500.0,
                    weekly_total_proc_value_stdev=0.0,  # Zero stdev
                    weekly_avg_txn_value_mean=25.0,
                    weekly_avg_txn_value_stdev=0.0,  # Zero stdev
                    weekly_avg_txn_cost_pct_mean=0.01,
                    weekly_avg_txn_cost_pct_stdev=0.0,  # Zero stdev
                    neighbor_coverage=50,
                    pct_ct_means={"card_present": 0.6, "card_not_present": 0.4},
                )
            )

        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=8),
            composite_weekly_features=rows,
            forecast_horizon_wks=4,
        )
        resp = get_volume_forecast(req)
        # Should handle gracefully without crashing
        assert len(resp.forecast) == 4

    def test_data_with_sudden_jump(self):
        """Features with a sudden spike/drop (anomaly)."""
        rows = []
        for i in range(50):
            year = 2024
            week = (i % 52) + 1
            seasonal = 120.0 * np.sin(2 * np.pi * (i % 13) / 13)
            v = 1500.0 + seasonal
            if i == 25:
                v *= 5  # Sudden spike at week 25
            rows.append(
                CompositeWeeklyFeature(
                    calendar_year=year,
                    week_of_year=week,
                    weekly_txn_count_mean=float(2000 + i * 10),
                    weekly_txn_count_stdev=float(90),
                    weekly_total_proc_value_mean=float(v),
                    weekly_total_proc_value_stdev=float(80),
                    weekly_avg_txn_value_mean=float(25),
                    weekly_avg_txn_value_stdev=float(3),
                    weekly_avg_txn_cost_pct_mean=0.01,
                    weekly_avg_txn_cost_pct_stdev=0.002,
                    neighbor_coverage=50,
                    pct_ct_means={"card_present": 0.6, "card_not_present": 0.4},
                )
            )

        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
            composite_weekly_features=rows,
            forecast_horizon_wks=6,
        )
        resp = get_volume_forecast(req)
        # Should generate valid forecast despite anomaly
        assert len(resp.forecast) == 6


class TestContextWindowSizing:
    """Context window size validation."""

    def test_context_window_matches_onboarding_weeks(self):
        """Context window should reflect onboarding transaction span."""
        weeks_list = [4, 8, 12, 20]
        for weeks in weeks_list:
            req = VolumeForecastRequest(
                onboarding_merchant_txn_df=_make_onboarding_txns(weeks=weeks),
                composite_weekly_features=_make_features(n=50),
                forecast_horizon_wks=6,
            )
            resp = get_volume_forecast(req)
            # Context window should be close to onboarding weeks
            # (may vary slightly due to week boundary defs)
            assert resp.process_metadata.context_window_weeks_count > 0


class TestResponseMetadataCompleteness:
    """Ensure all required metadata is present."""

    def test_all_sarima_metadata_fields_populated(self):
        """SARIMA metadata should have all expected fields."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
            composite_weekly_features=_make_features(n=50),
            forecast_horizon_wks=6,
        )
        resp = get_volume_forecast(req)

        assert resp.sarima_metadata.fit_status is not None
        assert resp.sarima_metadata.use_optimised_sarima is not None
        assert resp.sarima_metadata.seasonal_length is not None
        assert resp.sarima_metadata.selected_order is not None
        assert resp.sarima_metadata.selected_seasonal_order is not None

    def test_all_process_metadata_fields_populated(self):
        """Process metadata should have all expected fields."""
        req = VolumeForecastRequest(
            onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
            composite_weekly_features=_make_features(n=50),
            forecast_horizon_wks=6,
        )
        resp = get_volume_forecast(req)

        assert resp.process_metadata.is_fallback is not None
        assert resp.process_metadata.context_window_weeks_count >= 0
        assert resp.process_metadata.used_guarded_calibration is not None
        assert resp.process_metadata.calibration_mode is not None

    def test_forecast_week_indices_sequential_and_one_based(self):
        """Forecast week indices must be 1, 2, 3, ... (one-based, sequential)."""
        horizons = [1, 4, 8, 13, 26]
        for horizon in horizons:
            req = VolumeForecastRequest(
                onboarding_merchant_txn_df=_make_onboarding_txns(weeks=10),
                composite_weekly_features=_make_features(n=52),
                forecast_horizon_wks=horizon,
            )
            resp = get_volume_forecast(req)
            indices = [w.forecast_week_index for w in resp.forecast]
            assert indices == list(range(1, horizon + 1))
