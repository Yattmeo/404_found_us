from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class KNNRateQuoteResult(BaseModel):
    """Output of the KNN Rate Quote Engine."""
    forecast_proc_cost: List[float] = Field(
        ..., description="Forecasted processing cost for each horizon month"
    )
    context_len: int = Field(..., description="Number of context months used")
    horizon_len: int = Field(..., description="Number of forecast months")
    k: int = Field(..., description="Number of nearest neighbours used")
    end_month: int = Field(..., description="Calendar month index used as the query end point")
    notes: Optional[str] = None
