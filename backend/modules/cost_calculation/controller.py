from __future__ import annotations

from .schemas import CostCalculationResponse
from .service import CostCalculationService


def run_cost_calculation(
    file_bytes: bytes, filename: str, mcc: int
) -> tuple[CostCalculationResponse, bytes]:
    """
    Returns (CostCalculationResponse, enriched_csv_bytes).
    The route layer is responsible for forwarding enriched_csv_bytes
    and the metrics to the ML microservice.
    """
    return CostCalculationService.calculate_from_bytes(file_bytes, filename, mcc)
