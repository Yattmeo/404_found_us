from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ClusterAssignmentResult(BaseModel):
    """
    Output of the Cluster Assignment Engine.

    ── WHERE TO EDIT ──────────────────────────────────────────────────────────
    Add or remove fields here as the model is built out.
    service.py → ClusterAssignmentService.assign() must return this schema.
    Assignments are persisted to PostgreSQL (merchant_cluster_vectors table) —
    see models.py and service.py → _persist_assignment().
    ──────────────────────────────────────────────────────────────────────────
    """
    cluster_id:     int
    cluster_label:  Optional[str]   = None
    distance:       Optional[float] = None   # distance to centroid via pgvector <->
    notes:          Optional[str]   = None
