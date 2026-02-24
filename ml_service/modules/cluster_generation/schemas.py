from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ClusterGenerationResult(BaseModel):
    """
    Output of the Cluster Generation Engine.

    ── WHERE TO EDIT ──────────────────────────────────────────────────────────
    Add or remove fields here as the model is built out.
    service.py → ClusterGenerationService.generate() must return this schema.
    Centroids are persisted to PostgreSQL (cluster_centroids table) —
    see models.py and service.py → _store_centroids().
    ──────────────────────────────────────────────────────────────────────────
    """
    n_clusters:         int
    cluster_labels:     dict[int, str]   # {cluster_id: label}
    inertia:            Optional[float]  = None
    notes:              Optional[str]    = None
