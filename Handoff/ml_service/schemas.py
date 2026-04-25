"""Shared input schema received by every /ml/* endpoint."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class MLProcessRequest(BaseModel):
    """
    Metrics forwarded from the backend CostCalculationService.
    The enriched CSV is received separately as a file upload.
    """
    mcc:                  int
    total_cost:           float
    total_payment_volume: float
    effective_rate:       float
    slope:                Optional[float] = None
    cost_variance:        Optional[float] = None
