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
