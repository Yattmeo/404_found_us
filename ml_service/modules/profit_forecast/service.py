"""
Monte Carlo profit forecast service — in-process module.

Adapted from ml_pipeline/Matt_EDA/services/GetProfitForecast Service (Monte Carlo)/service.py.
Runs independent Monte Carlo simulation using pre-computed cost and volume forecasts.

Independence assumption: ρ(log_tpv, avg_proc_cost_pct) ≈ 0.14 < 0.15,
validated empirically on MCC 5411.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
from scipy.stats import norm as scipy_norm

from .models import (
    ProfitForecastRequest,
    ProfitForecastResponse,
    ProfitMonth,
    ProfitSummary,
    ProfitabilityCurvePoint,
)

logger = logging.getLogger(__name__)

DEFAULT_RATE_GRID = [1.50, 1.75, 2.00, 2.25, 2.35, 2.50, 2.75, 3.00, 3.25, 3.50]

# Maximum coefficient of variation for cost sampling.  The M9 conformal
# half-widths are calibrated on the full training population and can be
# orders of magnitude larger than a specific merchant's cost midpoint.
# Capping sigma_cost to MAX_COST_CV * cost_mid keeps uncertainty
# proportional and prevents the probability curve from plateauing.
MAX_COST_CV = 0.50

# Maximum coefficient of variation for volume sampling.  The SARIMA CI
# lower bound is always 0, giving huge half-widths relative to the
# median for low-volume merchants.  Capping at 1× the midpoint keeps the
# volume noise meaningful without dominating the profit calculation.
MAX_VOLUME_CV = 1.0


def _simulate_month(
    tpv_mid: float,
    tpv_hw: float,
    cost_pct_mid: float,
    cost_pct_hw: float,
    fee_rate: float,
    confidence_interval: float,
    n_simulations: int,
    rng: np.random.Generator,
) -> ProfitMonth:
    z = scipy_norm.ppf((1 + confidence_interval) / 2)
    sigma_tpv = tpv_hw / z if z > 0 else tpv_hw
    sigma_cost = cost_pct_hw / z if z > 0 else cost_pct_hw
    # Cap sigmas so they stay proportional to their midpoints
    if tpv_mid > 0:
        sigma_tpv = min(sigma_tpv, MAX_VOLUME_CV * tpv_mid)
    if cost_pct_mid > 0:
        sigma_cost = min(sigma_cost, MAX_COST_CV * cost_pct_mid)

    tpv_samples = np.maximum(rng.normal(tpv_mid, max(sigma_tpv, 1e-9), n_simulations), 0.0)
    cost_samples = np.maximum(rng.normal(cost_pct_mid, max(sigma_cost, 1e-9), n_simulations), 0.0)

    profit_samples = tpv_samples * (fee_rate - cost_samples)

    alpha = 1 - confidence_interval
    lo_pct = 100 * (alpha / 2)
    hi_pct = 100 * (1 - alpha / 2)

    return ProfitMonth(
        month_index=0,
        tpv_mid=tpv_mid,
        cost_pct_mid=cost_pct_mid,
        revenue_mid=tpv_mid * fee_rate,
        cost_mid=tpv_mid * cost_pct_mid,
        profit_mid=tpv_mid * (fee_rate - cost_pct_mid),
        margin_mid=fee_rate - cost_pct_mid,
        p_profitable=float((profit_samples >= 0).mean()),
        profit_ci_lower=float(np.percentile(profit_samples, lo_pct)),
        profit_ci_upper=float(np.percentile(profit_samples, hi_pct)),
        profit_median=float(np.median(profit_samples)),
        profit_std=float(np.std(profit_samples)),
    )


def _aggregate_weekly_volume_to_monthly(
    weekly_forecast: list[dict],
) -> list[dict]:
    """Group weekly volume forecast into monthly buckets (4 weeks per month)."""
    monthly = []
    for m_idx in range(0, len(weekly_forecast), 4):
        chunk = weekly_forecast[m_idx: m_idx + 4]
        if not chunk:
            continue
        # Sum weekly volumes into monthly totals
        mid = sum(w.get("total_proc_value_mid", 0.0) for w in chunk)
        lo = sum(w.get("total_proc_value_ci_lower", 0.0) for w in chunk)
        hi = sum(w.get("total_proc_value_ci_upper", 0.0) for w in chunk)
        monthly.append({"tpv_mid": mid, "tpv_ci_lower": lo, "tpv_ci_upper": hi})
    return monthly


def run_profit_forecast(req: ProfitForecastRequest) -> ProfitForecastResponse:
    cost_forecast = req.cost_service_output.forecast
    vol_weekly = [w.model_dump() for w in req.volume_service_output.forecast]
    vol_monthly = _aggregate_weekly_volume_to_monthly(vol_weekly)

    horizon = min(len(cost_forecast), len(vol_monthly))
    if horizon == 0:
        raise ValueError("No overlapping forecast months between cost and volume services.")

    # ── Unit normalisation ────────────────────────────────────────────────
    # The M9 model (and KNN pipeline) stores avg_proc_cost_pct as
    # "cents per dollar" (e.g. 1.24 ≈ 1.24 %) because the raw training
    # data has proc_cost in cents and amount in dollars.
    # fee_rate is always a decimal fraction (0.04 = 4 %).
    # When the cost values are clearly in "percent" units (> 0.5) convert
    # them to decimal so the MC comparison is valid.
    cost_mids = [cfm.proc_cost_pct_mid for cfm in cost_forecast]
    if cost_mids and max(cost_mids) > 0.5:
        scale = 0.01
        for cfm in cost_forecast:
            cfm.proc_cost_pct_mid *= scale
            if cfm.proc_cost_pct_ci_lower is not None:
                cfm.proc_cost_pct_ci_lower *= scale
            if cfm.proc_cost_pct_ci_upper is not None:
                cfm.proc_cost_pct_ci_upper *= scale

    # Determine cost conformal half-width fallback
    cost_meta_hw = 0.005
    if req.cost_service_output.conformal_metadata:
        hw = req.cost_service_output.conformal_metadata.half_width
        # Apply same scale if the half_width is in percent units
        cost_meta_hw = hw * 0.01 if hw > 0.5 else hw

    rng = np.random.default_rng(42)
    months: List[ProfitMonth] = []

    for h in range(horizon):
        cfm = cost_forecast[h]
        vm = vol_monthly[h]

        # Per-month CI when available, else global half-width
        if cfm.proc_cost_pct_ci_lower is not None and cfm.proc_cost_pct_ci_upper is not None:
            cost_hw = (cfm.proc_cost_pct_ci_upper - cfm.proc_cost_pct_ci_lower) / 2
        else:
            cost_hw = cost_meta_hw

        tpv_mid = vm["tpv_mid"]
        if vm.get("tpv_ci_lower") is not None and vm.get("tpv_ci_upper") is not None:
            tpv_hw = (vm["tpv_ci_upper"] - vm["tpv_ci_lower"]) / 2
        else:
            tpv_hw = tpv_mid * 0.1  # 10% fallback

        pm = _simulate_month(
            tpv_mid=tpv_mid,
            tpv_hw=max(tpv_hw, 1e-9),
            cost_pct_mid=cfm.proc_cost_pct_mid,
            cost_pct_hw=max(cost_hw, 1e-9),
            fee_rate=req.fee_rate,
            confidence_interval=req.confidence_interval,
            n_simulations=req.n_simulations,
            rng=rng,
        )
        pm.month_index = h + 1
        months.append(pm)

    # ── Summary ───────────────────────────────────────────────────────────
    total_revenue = sum(m.revenue_mid for m in months)
    total_cost = sum(m.cost_mid for m in months)
    total_profit = sum(m.profit_mid for m in months)
    p_values = [m.p_profitable for m in months]

    # Break-even: the worst-case cost upper bound
    worst_cost_upper = max(
        cfm.proc_cost_pct_mid + cost_meta_hw for cfm in cost_forecast[:horizon]
    )

    # ── Profitability curve via Monte Carlo per rate ──────────────────────
    recommended_pct = round(req.fee_rate * 100.0, 2)

    # Average midpoint cost in percentage points — used both for grid construction
    # and to enforce P=0 for rates that are certainly below cost.
    avg_cost_pct = float(np.mean([cfm.proc_cost_pct_mid for cfm in cost_forecast[:horizon]])) * 100.0

    if req.rate_grid_pct:
        # Caller supplied an explicit grid — use it, ensuring recommended is included.
        rate_grid = sorted(set([float(r) for r in req.rate_grid_pct] + [recommended_pct]))
    else:
        # Build a dynamic grid that:
        #  • starts ~0.25 pp below the mean cost (so 0% probability is always visible)
        #  • ends at the recommended rate
        #  • has ~10–12 evenly-spaced steps
        grid_start = max(0.10, round(avg_cost_pct - 0.25, 2))
        grid_end = max(recommended_pct, avg_cost_pct + 0.50)
        step = max(0.05, round((grid_end - grid_start) / 10, 2))
        dynamic_points: list[float] = []
        r = grid_start
        while r <= grid_end + 1e-9:
            dynamic_points.append(round(r, 2))
            r += step
        if recommended_pct not in dynamic_points:
            dynamic_points.append(recommended_pct)
        rate_grid = sorted(set(dynamic_points))

    profitability_curve: List[ProfitabilityCurvePoint] = []
    for rate_pct in rate_grid:
        rate_decimal = rate_pct / 100.0
        # Quick MC: reuse same seed for consistency across rates
        rate_rng = np.random.default_rng(42)
        total_profit_samples = np.zeros(req.n_simulations)

        total_mid_volume = 0.0
        mid_total_rate = 0.0

        for h in range(horizon):
            cfm = cost_forecast[h]
            vm = vol_monthly[h]

            if cfm.proc_cost_pct_ci_lower is not None and cfm.proc_cost_pct_ci_upper is not None:
                cost_hw = (cfm.proc_cost_pct_ci_upper - cfm.proc_cost_pct_ci_lower) / 2
            else:
                cost_hw = cost_meta_hw

            tpv_mid = vm["tpv_mid"]
            if vm.get("tpv_ci_lower") is not None and vm.get("tpv_ci_upper") is not None:
                tpv_hw = (vm["tpv_ci_upper"] - vm["tpv_ci_lower"]) / 2
            else:
                tpv_hw = tpv_mid * 0.1

            z = scipy_norm.ppf((1 + req.confidence_interval) / 2)
            sigma_tpv = max(tpv_hw, 1e-9) / z if z > 0 else max(tpv_hw, 1e-9)
            sigma_cost = max(cost_hw, 1e-9) / z if z > 0 else max(cost_hw, 1e-9)
            # Cap sigmas so they stay proportional to their midpoints
            if tpv_mid > 0:
                sigma_tpv = min(sigma_tpv, MAX_VOLUME_CV * tpv_mid)
            if cfm.proc_cost_pct_mid > 0:
                sigma_cost = min(sigma_cost, MAX_COST_CV * cfm.proc_cost_pct_mid)

            tpv_s = np.maximum(rate_rng.normal(tpv_mid, sigma_tpv, req.n_simulations), 0.0)
            cost_s = np.maximum(rate_rng.normal(cfm.proc_cost_pct_mid, sigma_cost, req.n_simulations), 0.0)

            total_profit_samples += tpv_s * (rate_decimal - cost_s)
            mid_total_rate += vm["tpv_mid"] * (rate_decimal - cfm.proc_cost_pct_mid)
            total_mid_volume += max(0.0, vm["tpv_mid"])

        probability_pct = float((total_profit_samples >= 0).mean()) * 100.0

        # If the fee rate is below the average mid cost, the midpoint outcome is
        # a certain loss.  Zero out the probability so the curve cleanly crosses
        # the x-axis at the break-even rate rather than showing a stochastic tail.
        if rate_pct < avg_cost_pct:
            probability_pct = 0.0

        profitability_pct = (mid_total_rate / total_mid_volume * 100.0) if total_mid_volume > 0 else 0.0

        profitability_curve.append(ProfitabilityCurvePoint(
            rate_pct=round(rate_pct, 2),
            probability_pct=round(max(0.0, min(100.0, probability_pct)), 2),
            profitability_pct=round(profitability_pct, 2),
        ))

    # Enforce monotonically non-decreasing probability.
    # Higher fee rates always yield higher expected profit, so any inversion
    # in the curve is a pure Monte Carlo sampling artifact (variance between
    # adjacent grid points).  Clamp each point to be at least its predecessor.
    _prev_prob = 0.0
    for _pt in profitability_curve:
        if _pt.probability_pct < _prev_prob:
            _pt.probability_pct = round(_prev_prob, 2)
        else:
            _prev_prob = _pt.probability_pct

    # Estimated profit range from the recommended fee_rate simulation
    profit_ci_lowers = [m.profit_ci_lower for m in months]
    profit_ci_uppers = [m.profit_ci_upper for m in months]

    summary = ProfitSummary(
        total_profit_mid=total_profit,
        total_revenue_mid=total_revenue,
        total_cost_mid=total_cost,
        avg_p_profitable=float(np.mean(p_values)),
        min_p_profitable=float(np.min(p_values)),
        break_even_fee_rate=worst_cost_upper,
        estimated_profit_min=sum(profit_ci_lowers),
        estimated_profit_max=sum(profit_ci_uppers),
        profitability_curve=profitability_curve,
    )

    return ProfitForecastResponse(months=months, summary=summary)
