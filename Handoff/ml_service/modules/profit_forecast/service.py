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
from scipy.stats import norm, truncnorm

from .models import (
    ProfitForecastRequest,
    ProfitForecastResponse,
    ProfitMonth,
    ProfitSummary,
    SimulationMetadata,
)


def _sample_cost_pct_soft_guardrail(
    cost_pct_mid: float,
    cost_pct_hw: float,
    confidence_interval: float,
    n_simulations: int,
    rng: np.random.Generator,
    cost_pct_ci_lower: float | None = None,
    cost_pct_ci_upper: float | None = None,
) -> np.ndarray:
    """
    Sample cost% with soft guardrails shaped by calibrated conformal CI.

    Design intent:
    - Keep approximately `confidence_interval` mass inside the calibrated CI.
    - Preserve explicit tails outside the CI (do not hard-clip to bounds).
    - Enforce only physical feasibility: cost_pct >= 0.
    """
    z = norm.ppf((1 + confidence_interval) / 2)
    alpha = 1.0 - confidence_interval
    tail_prob = alpha / 2.0

    lower = cost_pct_ci_lower if cost_pct_ci_lower is not None else cost_pct_mid - cost_pct_hw
    upper = cost_pct_ci_upper if cost_pct_ci_upper is not None else cost_pct_mid + cost_pct_hw

    if lower > upper:
        lower, upper = upper, lower

    lower = float(lower)
    upper = float(upper)

    # Degenerate interval: fallback to Gaussian if we cannot form a proper CI band.
    if upper <= lower:
        sigma_cost = cost_pct_hw / z if z > 0 else max(cost_pct_hw, 1e-9)
        samples = rng.normal(cost_pct_mid, sigma_cost, n_simulations)
        return np.maximum(samples, 0.0)

    # Build a central truncated-normal core and exponential tails beyond CI.
    inner_n = int(round(confidence_interval * n_simulations))
    lower_tail_n = int(round(tail_prob * n_simulations))
    upper_tail_n = n_simulations - inner_n - lower_tail_n

    inner_sigma = max((upper - lower) / (2.0 * z), 1e-9)
    a = (lower - cost_pct_mid) / inner_sigma
    b = (upper - cost_pct_mid) / inner_sigma
    inner = truncnorm.rvs(
        a=a,
        b=b,
        loc=cost_pct_mid,
        scale=inner_sigma,
        size=inner_n,
        random_state=rng,
    )

    # Tail scales tied to CI geometry so widths stay risk-adaptive.
    left_scale = max((cost_pct_mid - lower) / max(z, 1e-9), 1e-9)
    right_scale = max((upper - cost_pct_mid) / max(z, 1e-9), 1e-9)

    lower_tail = lower - rng.exponential(scale=left_scale, size=lower_tail_n)
    upper_tail = upper + rng.exponential(scale=right_scale, size=upper_tail_n)

    samples = np.concatenate([inner, lower_tail, upper_tail])
    rng.shuffle(samples)
    return np.maximum(samples, 0.0)


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
    cost_pct_ci_lower: float | None = None,
    cost_pct_ci_upper: float | None = None,
    fixed_fee_per_tx: float = 0.0,
    avg_ticket: float | None = None,
) -> ProfitMonth:
    z = norm.ppf((1 + confidence_interval) / 2)

    sigma_tpv = tpv_hw / z if z > 0 else tpv_hw

    tpv_samples = rng.normal(tpv_mid, sigma_tpv, n_simulations)
    cost_samples = _sample_cost_pct_soft_guardrail(
        cost_pct_mid=cost_pct_mid,
        cost_pct_hw=cost_pct_hw,
        confidence_interval=confidence_interval,
        n_simulations=n_simulations,
        rng=rng,
        cost_pct_ci_lower=cost_pct_ci_lower,
        cost_pct_ci_upper=cost_pct_ci_upper,
    )

    tpv_samples = np.maximum(tpv_samples, 0.0)
    cost_samples = np.maximum(cost_samples, 0.0)

    revenue_samples = tpv_samples * fee_rate
    # Add deterministic fixed-fee revenue: tx_count = TPV / avg_ticket
    if fixed_fee_per_tx > 0.0 and avg_ticket is not None and avg_ticket > 0.0:
        tx_count_samples = tpv_samples / avg_ticket
        revenue_samples = revenue_samples + tx_count_samples * fixed_fee_per_tx
    cost_dollar_samples = tpv_samples * cost_samples
    profit_samples = revenue_samples - cost_dollar_samples

    # Compute midpoint revenue including fixed fee for deterministic mid values
    mid_tx_count = tpv_mid / avg_ticket if (avg_ticket is not None and avg_ticket > 0.0) else 0.0
    mid_fixed_fee_revenue = mid_tx_count * fixed_fee_per_tx if fixed_fee_per_tx > 0.0 else 0.0
    mid_revenue = tpv_mid * fee_rate + mid_fixed_fee_revenue

    alpha = 1 - confidence_interval
    lo_pct = 100 * (alpha / 2)
    hi_pct = 100 * (1 - alpha / 2)

    return ProfitMonth(
        month_index=0,
        tpv_mid=tpv_mid,
        cost_pct_mid=cost_pct_mid,
        revenue_mid=mid_revenue,
        cost_mid=tpv_mid * cost_pct_mid,
        profit_mid=mid_revenue - tpv_mid * cost_pct_mid,
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
            cost_ci_lower = cost_fm.proc_cost_pct_ci_lower
            cost_ci_upper = cost_fm.proc_cost_pct_ci_upper
            cost_hw = (cost_fm.proc_cost_pct_ci_upper - cost_fm.proc_cost_pct_ci_lower) / 2
        else:
            cost_ci_lower = cost_fm.proc_cost_pct_mid - cost_out.conformal_metadata.half_width
            cost_ci_upper = cost_fm.proc_cost_pct_mid + cost_out.conformal_metadata.half_width
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
            cost_pct_ci_lower=cost_ci_lower,
            cost_pct_ci_upper=cost_ci_upper,
            fixed_fee_per_tx=req.fixed_fee_per_tx,
            avg_ticket=req.avg_ticket,
        )
        pm.month_index = h + 1
        months.append(pm)

    total_revenue = sum(m.revenue_mid for m in months)
    total_cost = sum(m.cost_mid for m in months)
    total_profit = sum(m.profit_mid for m in months)
    p_values = [m.p_profitable for m in months]

    worst_cost_upper = max(
        (
            fm.proc_cost_pct_ci_upper
            if fm.proc_cost_pct_ci_upper is not None
            else fm.proc_cost_pct_mid + cost_out.conformal_metadata.half_width
        )
        for fm in cost_out.forecast[:horizon]
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
        cost_sampling_strategy="ci_shaped_soft_guardrails",
        cost_ci_tail_probability=(1.0 - req.confidence_interval),
        cost_ci_hard_clip=False,
    )

    return ProfitForecastResponse(
        months=months,
        summary=summary,
        metadata=metadata,
    )
