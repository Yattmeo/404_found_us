from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class RateOptimisationResult(BaseModel):
    """
    Output of the Rate Optimisation Engine.

    ── WHERE TO EDIT ──────────────────────────────────────────────────────────
    Add or remove fields here as the model is built out.
    service.py → RateOptimisationService.optimise() must return this schema.
    ──────────────────────────────────────────────────────────────────────────
    """
    recommended_rate:   float
    min_viable_rate:    float
    max_viable_rate:    float
    confidence:         Optional[float] = None
    notes:              Optional[str]   = None
