"""
Cluster Generation Engine — Service Layer

Goal:
    Cluster merchants / transaction patterns using the enriched CSV and cost
    metrics. Store cluster centroids in PostgreSQL (pgvector) so the
    Cluster Assignment Engine can do nearest-neighbour lookups.

── WHERE TO EDIT ─────────────────────────────────────────────────────────────
ALL model logic lives in the `generate()` method below.
Centroid persistence lives in `_store_centroids()`.

Inputs available to you:
  df       — pandas DataFrame (see Rate Optimisation service for column list)
  metrics  — dict: mcc, total_cost, total_payment_volume, effective_rate,
                   slope, cost_variance
  db       — SQLAlchemy Session

Feature vector construction:
  `_build_feature_vector()` turns the metrics dict into a numeric vector.
  This vector is what gets stored in the `embedding` column of
  `merchant_cluster_vectors` and `cluster_centroids` (models.py).
  ── Edit `_build_feature_vector()` to include more features from df.
  ── Also update VECTOR_DIM in ml_service/config.py to match the new length.

PostgreSQL storage:
  Centroids → `cluster_centroids` table  (models.py → ClusterCentroid)
  Merchant vectors → written by Cluster Assignment Engine

Suggested implementation steps:
  1. Build feature vectors across all rows (or per-merchant aggregation).
  2. Run K-Means / DBSCAN / hierarchical clustering.
  3. Persist centroid vectors via `_store_centroids()`.
  4. Return cluster labels and inertia.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from config import MLConfig
from models import ClusterCentroid
from .schemas import ClusterGenerationResult


class ClusterGenerationService:

    # ── Feature engineering ──────────────────────────────────────────────────

    @staticmethod
    def _build_feature_vector(metrics: dict[str, Any]) -> list[float]:
        """
        Convert cost metrics into a fixed-length numeric feature vector.

        ── TODO: EDIT THIS ────────────────────────────────────────────────────
        Add more features here (e.g. per-card-type ratios from df).
        Keep len(vector) == VECTOR_DIM in config.py (currently 8).
        ──────────────────────────────────────────────────────────────────────
        return [
            metrics.get("total_cost",            0.0),
            metrics.get("total_payment_volume",  0.0),
            metrics.get("effective_rate",         0.0),
            metrics.get("slope")      or 0.0,
            metrics.get("cost_variance") or 0.0,
            float(metrics.get("mcc",             0)),
            0.0,   # placeholder — add real feature
            0.0,   # placeholder — add real feature
        ]
        """
        return [
            metrics.get("total_cost",            0.0),
            metrics.get("total_payment_volume",  0.0),
            metrics.get("effective_rate",         0.0),
            metrics.get("slope")       or 0.0,
            metrics.get("cost_variance") or 0.0,
            float(metrics.get("mcc",             0)),
            0.0,
            0.0,
        ]

    # ── Centroid persistence ─────────────────────────────────────────────────

    @staticmethod
    def _store_centroids(
        centroids: np.ndarray,
        labels: dict[int, str],
        db: Session,
    ) -> None:
        """
        Upsert cluster centroids into PostgreSQL using pgvector.

        ── WHERE TO EDIT ──────────────────────────────────────────────────────
        This is called after every re-clustering run. If you change the
        number of clusters or VECTOR_DIM, existing rows are overwritten.
        ──────────────────────────────────────────────────────────────────────
        PostgreSQL table: cluster_centroids  (models.py → ClusterCentroid)
        Columns written: cluster_id, cluster_label, centroid (vector)
        """
        for cluster_id, centroid_vec in enumerate(centroids):
            existing = db.query(ClusterCentroid).filter_by(cluster_id=cluster_id).first()
            if existing:
                existing.centroid      = centroid_vec.tolist()
                existing.cluster_label = labels.get(cluster_id)
            else:
                db.add(ClusterCentroid(
                    cluster_id    = cluster_id,
                    cluster_label = labels.get(cluster_id),
                    centroid      = centroid_vec.tolist(),
                ))
        db.commit()

    # ── Main method ──────────────────────────────────────────────────────────

    @staticmethod
    def generate(
        df: pd.DataFrame,
        metrics: dict[str, Any],
        db: Session,
    ) -> ClusterGenerationResult:
        """
        ── STUB — REPLACE THIS LOGIC ─────────────────────────────────────────
        Current stub: creates a single "stub cluster" centroid from the
        single feature vector produced by this one request.

        Replace with:
          • Accumulate vectors across many merchant requests (or use a
            historical dataset), then run K-Means / DBSCAN.
          • Store real centroids via _store_centroids().
        ──────────────────────────────────────────────────────────────────────
        """
        from datetime import datetime
        from models import ClusterCentroid

        # ── TODO: replace below with real clustering algorithm ───────────────
        n_clusters = 5
        stub_labels: dict[int, str] = {
            0: "High-Volume Grocery",
            1: "Mid-Market Retail",
            2: "Food & Beverage",
            3: "Professional Services",
            4: "E-Commerce",
        }
        feature_vec = ClusterGenerationService._build_feature_vector(metrics)
        # Create identical stub centroids (just for schema completeness)
        stub_centroids = np.array([feature_vec] * n_clusters, dtype=float)
        ClusterGenerationService._store_centroids(stub_centroids, stub_labels, db)
        # ── END TODO ─────────────────────────────────────────────────────────

        return ClusterGenerationResult(
            n_clusters=n_clusters,
            cluster_labels=stub_labels,
            inertia=None,  # TODO: return real inertia from K-Means fit
            notes="STUB — replace with real clustering model",
        )
