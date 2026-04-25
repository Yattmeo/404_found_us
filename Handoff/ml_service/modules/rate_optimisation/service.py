"""
Rate Optimisation Engine — Service Layer

Goal:
    Given the cost metrics and enriched transaction CSV, recommend the
    optimal merchant rate that covers interchange costs plus a target margin.

── WHERE TO EDIT ─────────────────────────────────────────────────────────────
ALL model logic lives in the `optimise()` method below.

Inputs available to you:
  df       — pandas DataFrame, enriched CSV columns:
               transaction_id, transaction_date, merchant_id, amount,
               transaction_type, card_type, card_brand,
               mcc, product, percent_rate, fixed_rate, max_fee,
               card_cost, network_percent_rate, network_fixed_rate,
               network_cost, total_cost, match_found

  metrics  — dict with keys:
               mcc, total_cost, total_payment_volume, effective_rate,
               slope, cost_variance

  db       — SQLAlchemy Session (for reading/writing PostgreSQL)

Suggested implementation steps:
  1. Use effective_rate as the baseline cost rate.
  2. Add your target margin (pull from a config or DB table).
  3. Apply volume-based discounts / risk adjustments using slope/variance.
  4. Return a RateOptimisationResult with recommended_rate, min, max.

To persist results to PostgreSQL, use db.add() / db.commit() with a model
from ml_service/models.py or a new model you define there.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from .schemas import RateOptimisationResult


class RateOptimisationService:

    @staticmethod
    def optimise(
        df: pd.DataFrame,
        metrics: dict[str, Any],
        db: Session,
    ) -> RateOptimisationResult:
        """
        ── STUB — REPLACE THIS LOGIC ─────────────────────────────────────────
        The current implementation is a simple rule-based placeholder.
        Replace it with your trained model / regression / optimisation logic.

        Stub logic:
          recommended_rate = effective_rate + 0.5% margin
          min = effective_rate + 0.2%
          max = effective_rate + 1.5%
        ──────────────────────────────────────────────────────────────────────
        """
        effective_rate: float = metrics.get("effective_rate", 0.0)

        # ── TODO: replace below with real model / algorithm ──────────────────
        margin_target      = 0.5    # percentage points above cost (stub value)
        recommended_rate   = round(effective_rate + margin_target, 5)
        min_viable_rate    = round(effective_rate + 0.2, 5)
        max_viable_rate    = round(effective_rate + 1.5, 5)
        # ── END TODO ─────────────────────────────────────────────────────────

        return RateOptimisationResult(
            recommended_rate=recommended_rate,
            min_viable_rate=min_viable_rate,
            max_viable_rate=max_viable_rate,
            confidence=None,  # TODO: add model confidence score
            notes="STUB — replace with real rate optimisation model",
        )
