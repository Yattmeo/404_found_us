"""
Cluster Assignment Engine — Service Layer

Goal:
    Assign the current merchant / transaction set to an existing cluster
    using a nearest-neighbour search on the pgvector embeddings stored
    in PostgreSQL by the Cluster Generation Engine.

── WHERE TO EDIT ─────────────────────────────────────────────────────────────
ALL model logic lives in the `assign()` method below.
Nearest-neighbour lookup lives in `_nearest_centroid()`.
Persistence of the assignment lives in `_persist_assignment()`.

Inputs available to you:
  df       — pandas DataFrame (see Rate Optimisation service for column list)
  metrics  — dict: mcc, total_cost, total_payment_volume, effective_rate,
                   slope, cost_variance
  db       — SQLAlchemy Session

PostgreSQL storage:
  Reads  → cluster_centroids        (models.py → ClusterCentroid)
  Writes → merchant_cluster_vectors (models.py → MerchantClusterVector)

pgvector nearest-neighbour query:
  Uses the `<->` operator (L2 distance).  See `_nearest_centroid()`.
  To switch to cosine distance use `<=>` instead.

Suggested implementation steps:
  1. Build feature vector with _build_feature_vector() (same as Gen engine).
  2. Query cluster_centroids ORDER BY centroid <-> :vec LIMIT 1.
  3. Write the result to merchant_cluster_vectors with the embedding.
  4. Return ClusterAssignmentResult.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from models import ClusterCentroid, MerchantClusterVector
from modules.cluster_generation.service import ClusterGenerationService  # reuse feature builder
from .schemas import ClusterAssignmentResult


class ClusterAssignmentService:

    # ── Nearest centroid via pgvector ─────────────────────────────────────────

    @staticmethod
    def _nearest_centroid(
        feature_vec: list[float],
        db: Session,
    ) -> Optional[ClusterCentroid]:
        """
        Find the nearest cluster centroid using pgvector's L2 <-> operator.

        ── WHERE TO EDIT ──────────────────────────────────────────────────────
        • Change <-> to <=> for cosine similarity.
        • Add a WHERE clause to filter by mcc if you want per-MCC clusters.
        ──────────────────────────────────────────────────────────────────────
        PostgreSQL table read: cluster_centroids
        """
        vec_str = "[" + ",".join(str(v) for v in feature_vec) + "]"
        row = (
            db.query(ClusterCentroid)
            .order_by(text(f"centroid <-> '{vec_str}'::vector"))
            .first()
        )
        return row

    # ── Persistence ───────────────────────────────────────────────────────────

    @staticmethod
    def _persist_assignment(
        metrics: dict[str, Any],
        feature_vec: list[float],
        cluster_id: int,
        cluster_label: Optional[str],
        distance: Optional[float],
        db: Session,
    ) -> None:
        """
        Write assignment result to merchant_cluster_vectors.

        ── WHERE TO EDIT ──────────────────────────────────────────────────────
        Add a merchant_id lookup here once the frontend sends merchant_id
        as part of the cost calculation request.
        ──────────────────────────────────────────────────────────────────────
        PostgreSQL table written: merchant_cluster_vectors
        """
        record = MerchantClusterVector(
            mcc                  = metrics["mcc"],
            cluster_id           = cluster_id,
            cluster_label        = cluster_label,
            total_cost           = metrics["total_cost"],
            total_payment_volume = metrics["total_payment_volume"],
            effective_rate       = metrics["effective_rate"],
            slope                = metrics.get("slope"),
            cost_variance        = metrics.get("cost_variance"),
            embedding            = feature_vec,
        )
        db.add(record)
        db.commit()

    # ── Main method ──────────────────────────────────────────────────────────

    @staticmethod
    def assign(
        df: pd.DataFrame,
        metrics: dict[str, Any],
        db: Session,
    ) -> ClusterAssignmentResult:
        """
        ── STUB — REPLACE THIS LOGIC ─────────────────────────────────────────
        Current implementation does a real pgvector nearest-neighbour lookup
        against whatever centroids exist in the DB (written by Cluster
        Generation Engine).  Falls back to cluster 0 if no centroids exist.

        The feature vector building is a stub — edit _build_feature_vector()
        in cluster_generation/service.py to include richer features.
        ──────────────────────────────────────────────────────────────────────
        """
        feature_vec = ClusterGenerationService._build_feature_vector(metrics)

        nearest = ClusterAssignmentService._nearest_centroid(feature_vec, db)

        if nearest:
            cluster_id    = nearest.cluster_id
            cluster_label = nearest.cluster_label
            # ── TODO: compute real distance from pgvector query ───────────────
            distance: Optional[float] = None  # pgvector doesn't return distance
                                               # in ORM queries easily — use raw SQL
                                               # if you need it
        else:
            # No centroids yet — fall back to stub assignment
            cluster_id    = 0
            cluster_label = "Unclassified (no centroids)"
            distance      = None

        ClusterAssignmentService._persist_assignment(
            metrics=metrics,
            feature_vec=feature_vec,
            cluster_id=cluster_id,
            cluster_label=cluster_label,
            distance=distance,
            db=db,
        )

        return ClusterAssignmentResult(
            cluster_id=cluster_id,
            cluster_label=cluster_label,
            distance=distance,
            notes=None if nearest else "STUB fallback — run ClusterGeneration first",
        )
