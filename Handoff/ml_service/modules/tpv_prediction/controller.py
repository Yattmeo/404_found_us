from __future__ import annotations
from typing import Any
import pandas as pd
from sqlalchemy.orm import Session
from .schemas import TPVPredictionResult
from .service import TPVPredictionService


def run_tpv_prediction(
    df: pd.DataFrame,
    metrics: dict[str, Any],
    db: Session,
) -> dict:
    result: TPVPredictionResult = TPVPredictionService.predict(df, metrics, db)
    return result.model_dump()
