from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class TPVPredictionResult(BaseModel):
    """
    Output of the TPV Prediction Engine.

    ── WHERE TO EDIT ──────────────────────────────────────────────────────────
    Add or remove fields here as the model is built out.
    service.py → TPVPredictionService.predict() must return this schema.
    ──────────────────────────────────────────────────────────────────────────
    """
    predicted_tpv:      float
    prediction_horizon: str            # e.g. "next_30_days"
    confidence:         Optional[float] = None
    notes:              Optional[str]   = None
