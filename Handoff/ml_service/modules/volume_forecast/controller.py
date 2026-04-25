from __future__ import annotations

from .models import VolumeForecastRequest
from .service import get_volume_forecast


def run_volume_forecast(payload: VolumeForecastRequest) -> dict:
    return get_volume_forecast(payload).model_dump()
