"""
SQLAlchemy ORM models for the ML microservice.

── HOW VECTORS ARE STORED IN POSTGRESQL ─────────────────────────────────────
pgvector adds a native `vector` column type to Postgres.
Each row in `merchant_cluster_vectors` holds one merchant's feature vector
alongside the cluster it was assigned to.

`cluster_centroids` stores the centroid vector for each cluster — this is
what the Cluster Assignment Engine compares against to assign new merchants.

── WHERE TO EDIT ─────────────────────────────────────────────────────────────
• Change VECTOR_DIM in config.py when you finalise feature dimensions.
• Add extra columns here if your engines require additional metadata.
"""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Float, Integer, String

from config import MLConfig
from database import Base


class MerchantClusterVector(Base):
    """One row per merchant per calculation run."""
    __tablename__ = "merchant_cluster_vectors"

    id            = Column(Integer, primary_key=True, index=True)
    merchant_id   = Column(String, index=True, nullable=True)
    mcc           = Column(Integer, nullable=False)
    cluster_id    = Column(Integer, nullable=True)   # filled by ClusterAssignmentEngine
    cluster_label = Column(String, nullable=True)

    # ── Cost metrics (from CostCalculationService) ───────────────────────────
    total_cost            = Column(Float, nullable=False)
    total_payment_volume  = Column(Float, nullable=False)
    effective_rate        = Column(Float, nullable=False)
    slope                 = Column(Float, nullable=True)
    cost_variance         = Column(Float, nullable=True)

    # ── pgvector embedding ───────────────────────────────────────────────────
    # Edit VECTOR_DIM in config.py and _build_feature_vector() in
    # ml_service/modules/cluster_generation/service.py to change dimensions.
    embedding = Column(Vector(MLConfig.VECTOR_DIM), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class ClusterCentroid(Base):
    """
    One row per cluster.  Updated by the Cluster Generation Engine each time
    clustering is re-run.  Used by the Cluster Assignment Engine for
    nearest-neighbour lookup via pgvector's <-> operator.

    ── WHERE TO EDIT ──────────────────────────────────────────────────────────
    ml_service/modules/cluster_generation/service.py  →  _store_centroids()
    ml_service/modules/cluster_assignment/service.py  →  _nearest_centroid()
    """
    __tablename__ = "cluster_centroids"

    id            = Column(Integer, primary_key=True, index=True)
    cluster_id    = Column(Integer, unique=True, nullable=False)
    cluster_label = Column(String, nullable=True)
    centroid      = Column(Vector(MLConfig.VECTOR_DIM), nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
