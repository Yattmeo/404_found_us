from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CostCalculationResponse(BaseModel):
    totalCost: float
    totalPaymentVolume: float
    effectiveRate: float
    slope: Optional[float] = None
    costVariance: Optional[float] = None          # transaction-level variance
    weeklyCostVariance: Optional[float] = None    # variance of weekly cost sums
