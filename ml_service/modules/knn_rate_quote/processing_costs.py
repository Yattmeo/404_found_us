from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Protocol
from urllib.request import Request, urlopen

import pandas as pd


class ProcessingCostProvider(Protocol):
    def enrich(self, txn_df: pd.DataFrame) -> pd.DataFrame:
        ...


@dataclass
class HeuristicProcessingCostProvider:
    base_rate: float = 0.018
    fixed_fee: float = 0.05

    def enrich(self, txn_df: pd.DataFrame) -> pd.DataFrame:
        df = txn_df.copy()
        amount = pd.to_numeric(df.get("amount"), errors="coerce").fillna(0.0)
        df["proc_cost"] = (amount * self.base_rate + self.fixed_fee).astype(float)
        return df


@dataclass
class ExternalProcessingCostProvider:
    endpoint: str
    timeout_seconds: int = 10
    fallback_provider: ProcessingCostProvider = field(default_factory=HeuristicProcessingCostProvider)

    def enrich(self, txn_df: pd.DataFrame) -> pd.DataFrame:
        records = txn_df.to_dict(orient="records")
        req = Request(
            self.endpoint,
            data=json.dumps({"transactions": records}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            enriched = pd.DataFrame(body.get("transactions", []))
            if enriched.empty or "proc_cost" not in enriched.columns:
                return self.fallback_provider.enrich(txn_df)
            return enriched
        except Exception:
            return self.fallback_provider.enrich(txn_df)


def default_processing_cost_provider() -> ProcessingCostProvider:
    endpoint = os.getenv("PROC_COST_SERVICE_URL", "").strip()
    if endpoint:
        return ExternalProcessingCostProvider(endpoint=endpoint)
    return HeuristicProcessingCostProvider()
