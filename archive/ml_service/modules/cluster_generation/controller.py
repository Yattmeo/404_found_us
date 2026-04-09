from __future__ import annotations
from typing import Any
import pandas as pd
from sqlalchemy.orm import Session
from .schemas import ClusterGenerationResult
from .service import ClusterGenerationService


def run_cluster_generation(
    df: pd.DataFrame,
    metrics: dict[str, Any],
    db: Session,
) -> dict:
    result: ClusterGenerationResult = ClusterGenerationService.generate(df, metrics, db)
    return result.model_dump()
