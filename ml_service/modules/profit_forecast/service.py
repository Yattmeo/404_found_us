"""
service.py — Monte Carlo profit simulation.

Accepts pre-computed outputs from the TPV and AvgProcCost forecast services,
then runs an independent Monte Carlo simulation to derive the profit
distribution.

Independence assumption: rho(log_tpv, avg_proc_cost_pct) ~ 0.14 < 0.15,
validated empirically on MCC 5411.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import numpy as np

from .models import (
    ProfitForecastRequest,
    ProfitForecastResponse,
    ProfitMonth,
    ProfitSummary,
    SimulationMetadata,
)


def _simulate_profit_month(
    tpv_mid: float,
    tpv_hw: float,
    cost_pct_mid: float,
    cost_pct_hw: float,
    fee_rate: float,
    confidence_interval: float,
    n_simulations: int,
    rng: np.random.Generator,
    target_margin: float | None = None,
) -> ProfitMonth:
    from scipy.stats import norm

    z = norm.ppf((1 + confidence_interval) / 2)

    sigma_tpv = tpv_hw / z if z > 0 else tpv_hw
    sigma_cost = cost_pct_hw / z if z > 0 else cost_pct_hw

    tpv_samples = rng.normal(tpv_mid, sigma_tpv, n_simulations)
    cost_samples = rng.normal(cost_pct_mid, sigma_cost, n_simulations)

    tpv_samples = np.maximum(tpv_samples, 0.0)
    cost_samples = np.maximum(cost_samples, 0.0)

    revenue_samples = tpv_samples * fee_rate
    cost_dollar_samples = tpv_samples * cost_samples
    profit_samples = revenue_samples - cost_dollar_samples

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
        p_profitable=float((profit_samples > 0).mean()),
        profit_ci_lower=float(np.percentile(profit_samples, lo_pct)),
        profit_ci_upper=float(np.percentile(profit_samples, hi_pct)),
        profit_median=float(np.median(profit_samples)),
        profit_std=float(np.std(profit_samples)),
        simulation_mean=float(np.mean(profit_samples)),
        p_target_margin_met=(
            float((fee_rate - cost_samples >= target_margin).mean())
            if target_margin is not None
            else None
        ),
    )


def get_profit_forecast(req: ProfitForecastRequest) -> ProfitForecastResponse:
    generated_at = datetime.now(timezone.utc)

    tpv_out = req.tpv_service_output
    cost_out = req.cost_service_output

    tpv_mids = [fm.tpv_mid for fm in tpv_out.forecast]
    cost_pct_mids = [fm.proc_cost_pct_mid for fm in cost_out.forecast]
    horizon = len(tpv_mids)

    if len(cost_pct_mids) < horizon:
        raise ValueError(
            f"TPV forecast has {horizon} months but cost forecast has "
            f"{len(cost_pct_mids)}. They must match."
        )

    rng = np.random.default_rng(42)
    months: List[ProfitMonth] = []

    for h in range(horizon):
        tpv_fm = tpv_out.forecast[h]
        cost_fm = cost_out.forecast[h]

        if tpv_fm.tpv_ci_lower is not None and tpv_fm.tpv_ci_upper is not None:
            tpv_hw = (tpv_fm.tpv_ci_upper - tpv_fm.tpv_ci_lower) / 2
        else:
            tpv_hw = tpv_out.conformal_metadata.half_width_dollars

        if cost_fm.proc_cost_pct_ci_lower is not None and cost_fm.proc_cost_pct_ci_upper is not None:
            cost_hw = (cost_fm.proc_cost_pct_ci_upper - cost_fm.proc_cost_pct_ci_lower) / 2
        else:
            cost_hw = cost_out.conformal_metadata.half_width

        pm = _simulate_profit_month(
            tpv_mid=tpv_mids[h],
            tpv_hw=tpv_hw,
            cost_pct_mid=cost_pct_mids[h],
            cost_pct_hw=cost_hw,
            fee_rate=req.fee_rate,
            confidence_interval=req.confidence_interval,
            n_simulations=req.n_simulations,
            rng=rng,
            target_margin=req.target_margin,
        )
        pm.month_index = h + 1
        months.append(pm)

    total_revenue = sum(m.revenue_mid for m in months)
    total_cost = sum(m.cost_mid for m in months)
    total_profit = sum(m.profit_mid for m in months)
    p_values = [m.p_profitable for m in months]

    worst_cost_upper = max(
        cost_pct_mids[h] + cost_out.conformal_metadata.half_width
        for h in range(horizon)
    )

    summary = ProfitSummary(
        total_profit_mid=total_profit,
        total_revenue_mid=total_revenue,
        total_cost_mid=total_cost,
        avg_p_profitable=float(np.mean(p_values)),
        min_p_profitable=float(np.min(p_values)),
        break_even_fee_rate=worst_cost_upper,
        suggested_fee_for_target=(
            worst_cost_upper + req.target_margin
            if req.target_margin is not None
            else None
        ),
        avg_p_target_margin_met=(
            float(np.mean([m.p_target_margin_met for m in months]))
            if req.target_margin is not None
            else None
        ),
        min_p_target_margin_met=(
            float(np.min([m.p_target_margin_met for m in months]))
            if req.target_margin is not None
            else None
        ),
    )

    metadata = SimulationMetadata(
        fee_rate=req.fee_rate,
        n_simulations=req.n_simulations,
        confidence_interval=req.confidence_interval,
        mcc=req.mcc,
        merchant_id=req.merchant_id,
        horizon_months=horizon,
        tpv_conformal_mode=tpv_out.conformal_metadata.conformal_mode,
        cost_conformal_mode=cost_out.conformal_metadata.conformal_mode,
        tpv_context_len_used=tpv_out.process_metadata.context_len_used,
        cost_context_len_used=cost_out.process_metadata.context_len_used,
        generated_at_utc=generated_at,
        target_margin=req.target_margin,
        correlation_assumed="independent",
    )

    return ProfitForecastResponse(
        months=months,
        summary=summary,
        metadata=metadata,
    )
