from __future__ import annotations
from typing import Any
import pandas as pd
from sqlalchemy.orm import Session
from .schemas import ClusterAssignmentResult
from .service import ClusterAssignmentService


def run_cluster_assignment(
    df: pd.DataFrame,
    metrics: dict[str, Any],
    db: Session,
) -> dict:
    result: ClusterAssignmentResult = ClusterAssignmentService.assign(df, metrics, db)
    return result.model_dump()
