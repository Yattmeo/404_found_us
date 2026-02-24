"""
TPV Prediction Engine — Service Layer

Goal:
    Forecast total payment volume (TPV) for a future period based on
    historical transaction data (enriched CSV) and current cost metrics.

── WHERE TO EDIT ─────────────────────────────────────────────────────────────
ALL model logic lives in the `predict()` method below.

Inputs available to you:
  df       — pandas DataFrame (see Rate Optimisation service for column list)
  metrics  — dict: mcc, total_cost, total_payment_volume, effective_rate,
                   slope, cost_variance
  db       — SQLAlchemy Session

Suggested implementation steps:
  1. Aggregate df by week (or day) to get a time series of volumes.
  2. Use slope (linear regression coefficient) as a simple trend indicator.
  3. Train / load a forecasting model (ARIMA, Prophet, LSTM, etc.).
  4. Return predicted_tpv for the next N days.

Useful columns in df for this engine:
  transaction_date  — use for time-series grouping
  amount            — sum per period = TPV for that period
  total_cost        — correlated with volume

To load a pre-trained model from disk, use joblib.load() or pickle.
Store models in ml_service/models/ (create that directory).
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from .schemas import TPVPredictionResult


class TPVPredictionService:

    @staticmethod
    def predict(
        df: pd.DataFrame,
        metrics: dict[str, Any],
        db: Session,
    ) -> TPVPredictionResult:
        """
        ── STUB — REPLACE THIS LOGIC ─────────────────────────────────────────
        Current stub: project forward using the linear slope from cost metrics.
        If slope is positive, TPV is growing; extrapolate 30 days.

        Replace with ARIMA / Prophet / your ML model.
        ──────────────────────────────────────────────────────────────────────
        """
        tpv:   float = metrics.get("total_payment_volume", 0.0)
        slope: float = metrics.get("slope") or 0.0

        # ── TODO: replace below with real forecasting model ──────────────────
        # Stub: assume weekly slope applies equally to volume
        weeks_ahead      = 4   # predict 30 days ≈ 4 weeks
        predicted_tpv    = round(tpv + slope * weeks_ahead, 5)
        # ── END TODO ─────────────────────────────────────────────────────────

        return TPVPredictionResult(
            predicted_tpv=predicted_tpv,
            prediction_horizon="next_30_days",
            confidence=None,   # TODO: add model confidence / prediction interval
            notes="STUB — replace with real TPV forecasting model",
        )
