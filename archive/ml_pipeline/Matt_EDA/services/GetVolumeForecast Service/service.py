from __future__ import annotations

import time
from datetime import datetime, timezone
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from config import (
    CALIBRATION_MAX_ABS_INTERCEPT,
    CALIBRATION_MAX_ABS_INTERCEPT_RELATIVE_TO_CONTEXT_MEAN,
    CALIBRATION_MAX_ABS_SLOPE,
    CALIBRATION_MIN_MATCHED_POINTS,
    CALIBRATION_MIN_PRED_STD,
    EXOGENOUS_FEATURE_COLUMNS,
    FALLBACK_MIN_HISTORY_WEEKS,
    SARIMA_D_FIXED,
    SARIMA_D_SEASONAL_FIXED,
    SARIMA_DEFAULT_P,
    SARIMA_DEFAULT_P_SEASONAL,
    SARIMA_DEFAULT_Q,
    SARIMA_DEFAULT_Q_SEASONAL,
    SARIMA_OPTIMISATION_TIMEOUT_S,
    SARIMA_P_CANDIDATES,
    SARIMA_P_SEASONAL_CANDIDATES,
    SARIMA_Q_CANDIDATES,
    SARIMA_Q_SEASONAL_CANDIDATES,
    SARIMA_SEASONAL_PERIOD,
)
from models import (
    ForecastWeek,
    ProcessMetadata,
    SarimaMetadata,
    VolumeForecastRequest,
    VolumeForecastResponse,
)


def _week_of_year(date: pd.Timestamp) -> int:
    return min((date.day_of_year - 1) // 7 + 1, 52)


def _build_onboarding_weekly(txn_rows: List[Dict[str, Any]]) -> pd.DataFrame:
    records = []
    for row in txn_rows:
        raw_date = row.get("transaction_date") or row.get("date")
        if raw_date is None:
            continue
        try:
            date = pd.to_datetime(raw_date)
        except Exception:
            continue

        amount = row.get("amount")
        if amount is None:
            continue
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue

        records.append(
            {
                "calendar_year": int(date.year),
                "week_of_year": int(_week_of_year(date)),
                "amount": amount,
            }
        )

    if not records:
        return pd.DataFrame(columns=["calendar_year", "week_of_year", "weekly_total_proc_value"])

    df = pd.DataFrame(records)
    return (
        df.groupby(["calendar_year", "week_of_year"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "weekly_total_proc_value"})
    )


def _fit_sarima(
    series: np.ndarray,
    order: Tuple[int, int, int],
    seasonal_order: Tuple[int, int, int, int],
    exog: Optional[np.ndarray] = None,
) -> Tuple[Any, str]:
    try:
        model = SARIMAX(
            series,
            exog=exog,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        result = model.fit(disp=False)
        return result, "ok"
    except Exception as exc:  # noqa: BLE001
        return None, f"failed: {exc}"


def _grid_search_sarima(
    series: np.ndarray,
    timeout_s: float,
    exog: Optional[np.ndarray] = None,
) -> Tuple[Any, dict]:
    candidates = list(
        product(
            SARIMA_P_CANDIDATES,
            [SARIMA_D_FIXED],
            SARIMA_Q_CANDIDATES,
            SARIMA_P_SEASONAL_CANDIDATES,
            [SARIMA_D_SEASONAL_FIXED],
            SARIMA_Q_SEASONAL_CANDIDATES,
        )
    )

    best_result = None
    best_aic = np.inf
    best_order: Tuple[int, int, int] = (SARIMA_DEFAULT_P, SARIMA_D_FIXED, SARIMA_DEFAULT_Q)
    best_seasonal_order: Tuple[int, int, int, int] = (
        SARIMA_DEFAULT_P_SEASONAL,
        SARIMA_D_SEASONAL_FIXED,
        SARIMA_DEFAULT_Q_SEASONAL,
        SARIMA_SEASONAL_PERIOD,
    )
    evaluated = 0
    t0 = time.monotonic()

    for p, d, q, P, D, Q in candidates:
        if time.monotonic() - t0 > timeout_s:
            break
        result, _ = _fit_sarima(series, (p, d, q), (P, D, Q, SARIMA_SEASONAL_PERIOD), exog=exog)
        evaluated += 1
        if result is not None and result.aic < best_aic:
            best_aic = result.aic
            best_result = result
            best_order = (p, d, q)
            best_seasonal_order = (P, D, Q, SARIMA_SEASONAL_PERIOD)

    elapsed_ms = (time.monotonic() - t0) * 1000
    return best_result, {
        "order": best_order,
        "seasonal_order": best_seasonal_order,
        "aic": float(best_aic) if best_result is not None else None,
        "evaluated": evaluated,
        "elapsed_ms": elapsed_ms,
    }


def _build_exog_history(sorted_features: List[Any]) -> np.ndarray:
    exog_hist = np.array(
        [[float(getattr(row, col, 0.0)) for col in EXOGENOUS_FEATURE_COLUMNS] for row in sorted_features],
        dtype=float,
    )
    return np.nan_to_num(exog_hist, nan=0.0, posinf=0.0, neginf=0.0)


def _build_fallback_response(
    req: VolumeForecastRequest,
    context_window_weeks: int,
    onboarding_mean: Optional[float],
    fallback_reason: str,
    generated_at: datetime,
) -> VolumeForecastResponse:
    fallback_value = onboarding_mean if onboarding_mean is not None else 0.0

    sarima_meta = SarimaMetadata(
        seasonal_length=SARIMA_SEASONAL_PERIOD,
        use_optimised_sarima=req.use_optimised_sarima,
        use_exogenous_sarimax=req.use_exogenous_sarimax,
        exogenous_feature_names=list(EXOGENOUS_FEATURE_COLUMNS) if req.use_exogenous_sarimax else [],
        selected_order=[0, 0, 0],
        selected_seasonal_order=[0, 0, 0, SARIMA_SEASONAL_PERIOD],
        aic=None,
        fit_status="fallback",
        optimisation_attempted=False,
        optimisation_time_ms=None,
        optimisation_candidates_evaluated=0,
    )

    proc_meta = ProcessMetadata(
        context_window_weeks_count=context_window_weeks,
        matched_calibration_points=0,
        calibration_mode="not_applicable",
        is_fallback=True,
        fallback_reason=fallback_reason,
        fallback_mean_total_proc_value=fallback_value,
        context_window_mean_total_proc_value=onboarding_mean,
        generated_at_utc=generated_at,
        forecast_horizon_wks=req.forecast_horizon_wks,
        confidence_interval=req.confidence_interval,
        used_guarded_calibration=req.use_guarded_calibration,
        calibration_successful=False,
        calibration_mae=None,
        calibration_rmse=None,
        calibration_r2=None,
    )

    forecast_weeks = [
        ForecastWeek(
            forecast_week_index=context_window_weeks + i + 1,
            total_proc_value_mid=fallback_value,
            total_proc_value_ci_lower=fallback_value,
            total_proc_value_ci_upper=fallback_value,
        )
        for i in range(req.forecast_horizon_wks)
    ]

    return VolumeForecastResponse(
        process_metadata=proc_meta,
        sarima_metadata=sarima_meta,
        is_guarded_sarima=False,
        forecast=forecast_weeks,
        context_sarima_fitted=[],
    )


def get_volume_forecast(req: VolumeForecastRequest) -> VolumeForecastResponse:
    generated_at = datetime.now(timezone.utc)

    sorted_features = sorted(req.composite_weekly_features, key=lambda r: (r.calendar_year, r.week_of_year))
    composite_series = np.array([r.weekly_total_proc_value_mean for r in sorted_features], dtype=float)

    exog_hist: Optional[np.ndarray] = None
    exogenous_feature_names: List[str] = []
    if req.use_exogenous_sarimax:
        exog_hist = _build_exog_history(sorted_features)
        exogenous_feature_names = list(EXOGENOUS_FEATURE_COLUMNS)

    week_key_index: Dict[Tuple[int, int], int] = {
        (r.calendar_year, r.week_of_year): i for i, r in enumerate(sorted_features)
    }

    onboarding_weekly = _build_onboarding_weekly(req.onboarding_merchant_txn_df)
    if not onboarding_weekly.empty:
        onboarding_weekly = onboarding_weekly.sort_values(["calendar_year", "week_of_year"]).reset_index(drop=True)

    context_window_weeks = len(onboarding_weekly)
    onboarding_mean: Optional[float] = (
        float(onboarding_weekly["weekly_total_proc_value"].mean()) if not onboarding_weekly.empty else None
    )

    if len(composite_series) < FALLBACK_MIN_HISTORY_WEEKS:
        return _build_fallback_response(
            req=req,
            context_window_weeks=context_window_weeks,
            onboarding_mean=onboarding_mean,
            fallback_reason=(
                f"Composite history has {len(composite_series)} weeks; minimum required is {FALLBACK_MIN_HISTORY_WEEKS}."
            ),
            generated_at=generated_at,
        )

    onboarding_positions: List[int] = []
    if not onboarding_weekly.empty:
        for _, row in onboarding_weekly.iterrows():
            key = (int(row["calendar_year"]), int(row["week_of_year"]))
            if key in week_key_index:
                onboarding_positions.append(week_key_index[key])

    if onboarding_positions and min(onboarding_positions) > 0:
        train_end_pos = min(onboarding_positions) - 1
        onboarding_end_pos = max(onboarding_positions)
    else:
        train_end_pos = len(composite_series) - 1
        onboarding_end_pos = train_end_pos

    train_series = composite_series[: train_end_pos + 1]
    train_exog_hist: Optional[np.ndarray] = None
    if exog_hist is not None:
        train_exog_hist = exog_hist[: train_end_pos + 1, :]

    steps_to_onboarding_end = max(0, onboarding_end_pos - train_end_pos)
    total_generated_steps = steps_to_onboarding_end + req.forecast_horizon_wks

    exog_future_generated: Optional[np.ndarray] = None
    if train_exog_hist is not None:
        last_row = train_exog_hist[-1, :] if len(train_exog_hist) > 0 else np.zeros(len(EXOGENOUS_FEATURE_COLUMNS))
        exog_future_generated = np.repeat(last_row[np.newaxis, :], total_generated_steps, axis=0)

    default_order: Tuple[int, int, int] = (SARIMA_DEFAULT_P, SARIMA_D_FIXED, SARIMA_DEFAULT_Q)
    default_seasonal: Tuple[int, int, int, int] = (
        SARIMA_DEFAULT_P_SEASONAL,
        SARIMA_D_SEASONAL_FIXED,
        SARIMA_DEFAULT_Q_SEASONAL,
        SARIMA_SEASONAL_PERIOD,
    )

    opt_meta: dict = {
        "order": default_order,
        "seasonal_order": default_seasonal,
        "aic": None,
        "evaluated": 0,
        "elapsed_ms": 0.0,
    }

    if req.use_optimised_sarima:
        sarima_result, opt_meta = _grid_search_sarima(
            train_series,
            SARIMA_OPTIMISATION_TIMEOUT_S,
            exog=train_exog_hist,
        )
        order: Tuple[int, int, int] = opt_meta["order"]
        seasonal_order: Tuple[int, int, int, int] = opt_meta["seasonal_order"]
        fit_status = "ok" if sarima_result is not None else "failed"
    else:
        order = default_order
        seasonal_order = default_seasonal
        sarima_result, fit_status = _fit_sarima(train_series, order, seasonal_order, exog=train_exog_hist)

    if sarima_result is None:
        return _build_fallback_response(
            req=req,
            context_window_weeks=context_window_weeks,
            onboarding_mean=onboarding_mean,
            fallback_reason=f"SARIMA fit failed: {fit_status}",
            generated_at=generated_at,
        )

    alpha = 1.0 - req.confidence_interval
    if exog_future_generated is not None:
        forecast_obj = sarima_result.get_forecast(steps=total_generated_steps, exog=exog_future_generated)
    else:
        forecast_obj = sarima_result.get_forecast(steps=total_generated_steps)

    generated_mean = np.asarray(forecast_obj.predicted_mean).copy()
    ci_arr = np.asarray(forecast_obj.conf_int(alpha=alpha))
    generated_lower = ci_arr[:, 0].copy()
    generated_upper = ci_arr[:, 1].copy()

    final_start_step = steps_to_onboarding_end
    final_end_step = final_start_step + req.forecast_horizon_wks
    forecast_mean = generated_mean[final_start_step:final_end_step].copy()
    forecast_lower = generated_lower[final_start_step:final_end_step].copy()
    forecast_upper = generated_upper[final_start_step:final_end_step].copy()

    calib_pred: List[float] = []
    calib_actual: List[float] = []
    context_generated_by_pos: List[Optional[float]] = [None] * context_window_weeks

    if not onboarding_weekly.empty:
        for row_idx, (_, row) in enumerate(onboarding_weekly.iterrows()):
            key = (int(row["calendar_year"]), int(row["week_of_year"]))
            if key not in week_key_index:
                continue
            pos = week_key_index[key]
            gen_step = pos - (train_end_pos + 1)
            if gen_step < 0 or gen_step >= len(generated_mean):
                continue
            pred_val = generated_mean[gen_step]
            if np.isnan(pred_val):
                continue
            context_generated_by_pos[row_idx] = float(pred_val)
            calib_pred.append(float(pred_val))
            calib_actual.append(float(row["weekly_total_proc_value"]))

    matched_calibration_points = len(calib_pred)

    calibration_mode = "skipped_disabled"
    is_guarded_sarima = False
    calibration_successful = False
    calibration_mae: Optional[float] = None
    calibration_rmse: Optional[float] = None
    calibration_r2: Optional[float] = None

    if req.use_guarded_calibration:
        if matched_calibration_points < CALIBRATION_MIN_MATCHED_POINTS:
            calibration_mode = "skipped_insufficient_data"
        else:
            pred_arr = np.array(calib_pred)
            actual_arr = np.array(calib_actual)
            pred_std = float(pred_arr.std())
            context_mean_abs = float(abs(actual_arr.mean())) if len(actual_arr) > 0 else 0.0
            intercept_cap = max(
                CALIBRATION_MAX_ABS_INTERCEPT,
                CALIBRATION_MAX_ABS_INTERCEPT_RELATIVE_TO_CONTEXT_MEAN * context_mean_abs,
            )

            raw_residuals = actual_arr - pred_arr
            raw_rmse = float(np.sqrt(np.mean(np.square(raw_residuals))))

            candidate_results: List[Dict[str, Any]] = []

            # Candidate 1: full guarded linear calibrator (enabled only if predictions vary enough).
            if pred_std >= CALIBRATION_MIN_PRED_STD:
                X = np.column_stack([pred_arr, np.ones(len(pred_arr))])
                try:
                    coeffs, _, _, _ = np.linalg.lstsq(X, actual_arr, rcond=None)
                    slope = float(np.clip(coeffs[0], -CALIBRATION_MAX_ABS_SLOPE, CALIBRATION_MAX_ABS_SLOPE))
                    intercept = float(np.clip(coeffs[1], -intercept_cap, intercept_cap))
                    calibrated_arr = slope * pred_arr + intercept
                    residuals = actual_arr - calibrated_arr
                    calibrated_rmse = float(np.sqrt(np.mean(np.square(residuals))))
                    candidate_results.append(
                        {
                            "mode": "guarded_linear",
                            "calibrated_arr": calibrated_arr,
                            "residuals": residuals,
                            "rmse": calibrated_rmse,
                            "slope": slope,
                            "intercept": intercept,
                        }
                    )
                except np.linalg.LinAlgError:
                    pass

            # Candidate 2: multiplicative scale-only calibrator.
            pred_mean = float(pred_arr.mean()) if len(pred_arr) > 0 else 0.0
            if (
                pred_std >= CALIBRATION_MIN_PRED_STD
                and abs(pred_mean) > 1e-12
                and matched_calibration_points < 6
            ):
                scale = float(np.clip(float(actual_arr.mean()) / pred_mean, 0.0, CALIBRATION_MAX_ABS_SLOPE))
                calibrated_arr = scale * pred_arr
                residuals = actual_arr - calibrated_arr
                calibrated_rmse = float(np.sqrt(np.mean(np.square(residuals))))
                candidate_results.append(
                    {
                        "mode": "guarded_scale",
                        "calibrated_arr": calibrated_arr,
                        "residuals": residuals,
                        "rmse": calibrated_rmse,
                        "slope": scale,
                        "intercept": 0.0,
                    }
                )

            # Candidate 3: additive shift-only calibrator.
            # Restrict this to short/noisy windows to avoid over-correcting stable merchants.
            allow_shift = (
                matched_calibration_points < 6
                or pred_std < CALIBRATION_MIN_PRED_STD
            )
            if allow_shift:
                shift = float(np.clip(float(np.mean(actual_arr - pred_arr)), -intercept_cap, intercept_cap))
                calibrated_arr = pred_arr + shift
                residuals = actual_arr - calibrated_arr
                calibrated_rmse = float(np.sqrt(np.mean(np.square(residuals))))
                candidate_results.append(
                    {
                        "mode": "guarded_shift",
                        "calibrated_arr": calibrated_arr,
                        "residuals": residuals,
                        "rmse": calibrated_rmse,
                        "slope": 1.0,
                        "intercept": shift,
                    }
                )

            best_mode: Optional[str] = None
            best_slope = 1.0
            best_intercept = 0.0
            best_rmse = raw_rmse
            best_residuals: Optional[np.ndarray] = None
            if candidate_results:
                valid_candidates = candidate_results
                if matched_calibration_points >= 6:
                    # For longer context windows, avoid over-aggressive level warping.
                    valid_candidates = [
                        c for c in candidate_results
                        if abs(float(c["slope"]) - 1.0) <= 0.35
                    ]
                    if not valid_candidates:
                        valid_candidates = candidate_results

                best_candidate = min(valid_candidates, key=lambda c: float(c["rmse"]))
                best_mode = str(best_candidate["mode"])
                best_slope = float(best_candidate["slope"])
                best_intercept = float(best_candidate["intercept"])
                best_residuals = best_candidate["residuals"]
                best_rmse = float(best_candidate["rmse"])

            if best_mode is None or best_rmse >= raw_rmse:
                calibration_mode = "skipped_flat_predictions" if pred_std < CALIBRATION_MIN_PRED_STD else "skipped_no_improvement"
            else:
                original_mean = forecast_mean.copy()
                if best_mode == "guarded_linear":
                    forecast_mean = best_slope * forecast_mean + best_intercept
                elif best_mode == "guarded_scale":
                    forecast_mean = best_slope * forecast_mean
                else:
                    forecast_mean = forecast_mean + best_intercept

                offset = forecast_mean - original_mean
                forecast_lower = forecast_lower + offset
                forecast_upper = forecast_upper + offset

                calibration_mode = best_mode
                is_guarded_sarima = True
                calibration_successful = True

                if best_residuals is not None:
                    calibration_mae = float(np.mean(np.abs(best_residuals)))
                    calibration_rmse = best_rmse
                    ss_res = float(np.sum(np.square(best_residuals)))
                    ss_tot = float(np.sum(np.square(actual_arr - actual_arr.mean())))
                    calibration_r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else None

    # Non-negative target guard
    forecast_mean = np.maximum(forecast_mean, 0.0)
    forecast_lower = np.maximum(forecast_lower, 0.0)
    forecast_upper = np.maximum(forecast_upper, 0.0)

    aic_value: Optional[float] = (
        opt_meta["aic"] if req.use_optimised_sarima else (float(sarima_result.aic) if sarima_result is not None else None)
    )

    sarima_meta = SarimaMetadata(
        seasonal_length=SARIMA_SEASONAL_PERIOD,
        use_optimised_sarima=req.use_optimised_sarima,
        use_exogenous_sarimax=req.use_exogenous_sarimax,
        exogenous_feature_names=exogenous_feature_names,
        selected_order=list(order),
        selected_seasonal_order=list(seasonal_order),
        aic=aic_value,
        fit_status=fit_status,
        optimisation_attempted=req.use_optimised_sarima,
        optimisation_time_ms=opt_meta["elapsed_ms"] if req.use_optimised_sarima else None,
        optimisation_candidates_evaluated=opt_meta["evaluated"] if req.use_optimised_sarima else 0,
    )

    proc_meta = ProcessMetadata(
        context_window_weeks_count=context_window_weeks,
        matched_calibration_points=matched_calibration_points,
        calibration_mode=calibration_mode,
        is_fallback=False,
        fallback_reason=None,
        fallback_mean_total_proc_value=None,
        context_window_mean_total_proc_value=onboarding_mean,
        generated_at_utc=generated_at,
        forecast_horizon_wks=req.forecast_horizon_wks,
        confidence_interval=req.confidence_interval,
        used_guarded_calibration=req.use_guarded_calibration,
        calibration_successful=calibration_successful,
        calibration_mae=calibration_mae,
        calibration_rmse=calibration_rmse,
        calibration_r2=calibration_r2,
    )

    if onboarding_weekly.empty:
        output_start_week_index = context_window_weeks + 1
    else:
        output_start_week_index = int(onboarding_weekly["week_of_year"].min()) + context_window_weeks

    forecast_weeks: List[ForecastWeek] = []
    for i in range(req.forecast_horizon_wks):
        mid = float(forecast_mean[i])
        lo = float(forecast_lower[i])
        hi = float(forecast_upper[i])
        if lo > mid:
            lo = mid
        if hi < mid:
            hi = mid
        forecast_weeks.append(
            ForecastWeek(
                forecast_week_index=output_start_week_index + i,
                total_proc_value_mid=mid,
                total_proc_value_ci_lower=lo,
                total_proc_value_ci_upper=hi,
            )
        )

    return VolumeForecastResponse(
        process_metadata=proc_meta,
        sarima_metadata=sarima_meta,
        is_guarded_sarima=is_guarded_sarima,
        forecast=forecast_weeks,
        context_sarima_fitted=context_generated_by_pos,
    )
