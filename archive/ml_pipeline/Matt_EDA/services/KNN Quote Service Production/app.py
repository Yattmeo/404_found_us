from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException

from models import (
    CompositeMerchantRequest,
    CompositeMerchantResponse,
    QuoteRequest,
    QuoteResponse,
)
from processing_costs import default_processing_cost_provider
from repository import MerchantRepository, SQLAlchemyMerchantRepository, SQLiteMerchantRepository
from service import ProductionQuoteService


def _build_repository() -> MerchantRepository:
    # Prefer a full SQLAlchemy connection string (external / managed databases).
    conn_str = os.getenv("DB_CONNECTION_STRING", "").strip()
    if conn_str:
        return SQLAlchemyMerchantRepository(connection_string=conn_str)

    # Fall back to a local SQLite file.
    sqlite_path = os.getenv("TRANSACTIONS_AND_COST_TYPE_DB_PATH", "").strip()
    if sqlite_path:
        return SQLiteMerchantRepository(db_path=Path(sqlite_path))

    raise RuntimeError(
        "No database configured. Set DB_CONNECTION_STRING (SQLAlchemy URL) "
        "for an external database, or TRANSACTIONS_AND_COST_TYPE_DB_PATH for a local SQLite file."
    )


# Module-level handles. Tests may inject their own `service` via monkeypatch
# before startup; the lifespan skips construction in that case.
repository: Optional[MerchantRepository] = None
service: Optional[ProductionQuoteService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global repository, service
    if service is None:
        repository = _build_repository()
        service = ProductionQuoteService(
            repository=repository,
            processing_cost_provider=default_processing_cost_provider(),
            k=5,
            context_len_months=1,
            horizon_len_months=3,
        )
    yield


app = FastAPI(title="Merchant Quote API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/getQuote", response_model=QuoteResponse)
def get_quote(req: QuoteRequest) -> QuoteResponse:
    try:
        result = service.get_quote(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return QuoteResponse(
        neighbor_forecasts=result.neighbor_forecasts,
        context_len_wk=result.context_len_wk,
        horizon_len_wk=result.horizon_len_wk,
        k=result.k,
        end_month=result.end_month,
    )


@app.post("/getCompositeMerchant", response_model=CompositeMerchantResponse)
def get_composite_merchant(req: CompositeMerchantRequest) -> CompositeMerchantResponse:
    try:
        result = service.get_composite_merchant(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CompositeMerchantResponse(
        composite_merchant_id=result.composite_merchant_id,
        matched_neighbor_merchant_ids=result.matched_neighbor_merchant_ids,
        k=result.k,
        matching_start_month=result.matching_start_month,
        matching_end_month=result.matching_end_month,
        weekly_features=result.weekly_features,
    )
