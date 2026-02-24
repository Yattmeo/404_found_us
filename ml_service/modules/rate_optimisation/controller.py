from __future__ import annotations
from typing import Any
import pandas as pd
from sqlalchemy.orm import Session
from .schemas import RateOptimisationResult
from .service import RateOptimisationService


def run_rate_optimisation(
    df: pd.DataFrame,
    metrics: dict[str, Any],
    db: Session,
) -> dict:
    result: RateOptimisationResult = RateOptimisationService.optimise(df, metrics, db)
    return result.model_dump()
