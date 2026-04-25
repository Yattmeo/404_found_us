from __future__ import annotations

from .schemas import MerchantQuoteRequest, MerchantQuoteResponse
from .service import MerchantQuoteService


def create_merchant_quote(payload: MerchantQuoteRequest) -> MerchantQuoteResponse:
    return MerchantQuoteService.generate_quote(payload)
