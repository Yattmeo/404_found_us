"""
KNN Rate Quote Controller.

Exposes run_knn_rate_quote() which routes.py calls.
The KNNRateQuoteService is a lazy singleton — it is instantiated on the first
request so that the PostgreSQL reference data is loaded only once.

── WHERE TO EDIT ─────────────────────────────────────────────────────────────
• Service hyperparameters (k, context_len, horizon_len, year_min/max) →
  change the constructor kwargs in _get_service() below.
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import date

import pandas as pd

from .schemas import (
    CompositeMerchantRequest,
    CompositeMerchantResponse,
    KNNRateQuoteResult,
    QuoteRequest,
    QuoteResponse,
)
from .service import ProductionQuoteService

_service: Optional[ProductionQuoteService] = None


def _get_service() -> ProductionQuoteService:
    global _service
    if _service is None:
        from database import engine  # imported here to avoid circular imports
        _service = ProductionQuoteService(engine=engine)
    return _service


def run_knn_rate_quote(
    df: Optional[pd.DataFrame],
    mcc: int,
    card_type: Optional[str],
    monthly_txn_count: Optional[int],
    avg_amount: Optional[float],
    as_of_date: Optional[date],
) -> dict[str, Any]:
    """
    Call the KNN Rate Quote Engine and return a JSON-serialisable dict.

    Parameters
    ----------
    df                  : enriched transaction DataFrame (optional — may be None)
    mcc                 : Merchant Category Code (used for logging/future filtering)
    card_type           : "visa" | "mastercard" | "both" | None
    monthly_txn_count   : override for total monthly transactions
    avg_amount          : override for average transaction amount
    as_of_date          : end-of-context date; if beyond training range,
                          service maps to same calendar month in latest year
    """
    svc = _get_service()
    ts = pd.Timestamp(as_of_date) if as_of_date is not None else None
    result: KNNRateQuoteResult = svc.quote_legacy(
        df=df,
        mcc=mcc,
        card_type=card_type,
        monthly_txn_count=monthly_txn_count,
        avg_amount=avg_amount,
        as_of_date=ts,
    )
    return result.model_dump()


def run_get_quote(payload: QuoteRequest) -> dict[str, Any]:
    svc = _get_service()
    result = svc.get_quote(payload)
    response = QuoteResponse(
        neighbor_forecasts=result.neighbor_forecasts,
        context_len_wk=result.context_len_wk,
        horizon_len_wk=result.horizon_len_wk,
        k=result.k,
        end_month=result.end_month,
    )
    return response.model_dump()


def run_get_composite_merchant(payload: CompositeMerchantRequest) -> dict[str, Any]:
    svc = _get_service()
    result = svc.get_composite_merchant(payload)
    response = CompositeMerchantResponse(
        composite_merchant_id=result.composite_merchant_id,
        matched_neighbor_merchant_ids=result.matched_neighbor_merchant_ids,
        k=result.k,
        matching_start_month=result.matching_start_month,
        matching_end_month=result.matching_end_month,
        weekly_features=result.weekly_features,
    )
    return response.model_dump()
