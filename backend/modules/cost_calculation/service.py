from __future__ import annotations

import io
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .schemas import CostCalculationResponse

# ---------------------------------------------------------------------------
# Path resolution
#   In Docker: backend volume is ./backend:/app and cost_structure is mounted
#              at /app/cost_structure via COST_STRUCTURE_DIR env var.
#   Locally:   fall back to <project_root>/cost_structure (3 levels up from
#              backend/modules/cost_calculation/).
# ---------------------------------------------------------------------------
_env_path = os.environ.get("COST_STRUCTURE_DIR", "")
COST_STRUCTURE_DIR: Path = (
    Path(_env_path) if _env_path
    else Path(__file__).parent.parent.parent.parent / "cost_structure"
)

MASTERCARD_FEE_FILE     = COST_STRUCTURE_DIR / "masterCard_Card.JSON"
VISA_FEE_FILE           = COST_STRUCTURE_DIR / "visa_Card.JSON"
MASTERCARD_NETWORK_FILE = COST_STRUCTURE_DIR / "masterCard_Network.JSON"
VISA_NETWORK_FILE       = COST_STRUCTURE_DIR / "visa_Network.JSON"


class CostCalculationService:
    # ------------------------------------------------------------------ loaders

    @staticmethod
    @lru_cache(maxsize=16)
    def _load_json_cached(path_str: str):
        with open(path_str, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_fee_structure(card_brand: str):
        if card_brand == "Mastercard":
            return CostCalculationService._load_json_cached(str(MASTERCARD_FEE_FILE))
        elif card_brand == "Visa":
            return CostCalculationService._load_json_cached(str(VISA_FEE_FILE))
        return None  # Amex / unknown — no fee structure available

    @staticmethod
    def _load_network_fee_structure(card_brand: str):
        if card_brand == "Mastercard":
            return CostCalculationService._load_json_cached(str(MASTERCARD_NETWORK_FILE))
        elif card_brand == "Visa":
            return CostCalculationService._load_json_cached(str(VISA_NETWORK_FILE))
        return None

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _normalize_card_type(card_type: str) -> str:
        return "Prepaid" if card_type == "Debit (Prepaid)" else card_type

    @staticmethod
    def _find_matching_card_fee(card_brand: str, card_type: str, mcc: int, amount: float):
        fee_structure = CostCalculationService._load_fee_structure(card_brand)
        if fee_structure is None:
            return None

        if amount < 5.0:
            product = "Small Ticket Fee Program (All)"
            target_mcc = None
        else:
            product = "Industry Fee Program (All)"
            target_mcc = mcc

        normalized = CostCalculationService._normalize_card_type(card_type)
        for fee in fee_structure:
            if (
                fee["card_type"] == normalized
                and fee["product"] == product
                and fee["mcc"] == target_mcc
            ):
                return fee
        return None

    @staticmethod
    def _find_matching_network_fee(card_brand: str, card_type: str, amount: float):
        network_structure = CostCalculationService._load_network_fee_structure(card_brand)
        if network_structure is None:
            return None

        if card_brand == "Mastercard":
            base_fee = large_fee = inquiry_fee = None
            for fee in network_structure:
                name = fee.get("fee_name", "")
                if "Acquirer Brand Volume" in name:
                    base_fee = fee
                elif "Transactions => 1000 USD" in name:
                    large_fee = fee
                elif "Account Status Inquiry Service Fee" in name:
                    inquiry_fee = fee

            percent_rate = base_fee["percent_rate"] if base_fee else 0.0
            fixed_rate   = inquiry_fee["fixed_rate"] if inquiry_fee else 0.0
            if amount >= 1000.0 and large_fee:
                percent_rate += large_fee["percent_rate"]

            return {
                "percent_rate": percent_rate,
                "fixed_rate": fixed_rate,
                "fee_name": "Mastercard Network Fees",
            }

        elif card_brand == "Visa":
            normalized = CostCalculationService._normalize_card_type(card_type)
            if normalized == "Prepaid":
                normalized = "Debit"  # treat prepaid as debit for network fees

            assessment = processing = None
            for fee in network_structure:
                name = fee.get("fee_name", "")
                if "Acquirer Service Fee" in name and fee.get("card_type") == normalized:
                    assessment = fee
                elif "Acquirer Processing Fee" in name and fee.get("card_type") == normalized:
                    processing = fee

            if assessment and processing:
                return {
                    "percent_rate": assessment["percent_rate"],
                    "fixed_rate": processing["fixed_rate"],
                    "fee_name": "Visa Network Fees",
                }

        return None

    @staticmethod
    def _calc_cost(amount: float, percent_rate: float, fixed_rate: float, max_fee=None) -> float:
        cost = (amount * percent_rate / 100) + fixed_rate
        if max_fee is not None:
            cost = min(cost, max_fee)
        return round(cost, 5)

    # ------------------------------------------------------------------ core

    @staticmethod
    def _process_df(df: pd.DataFrame, mcc: int) -> pd.DataFrame:
        df = df.copy()
        df["mcc"] = mcc
        for col in (
            "product", "percent_rate", "fixed_rate", "max_fee",
            "card_cost", "network_percent_rate", "network_fixed_rate",
            "network_cost", "total_cost",
        ):
            df[col] = None
        df["match_found"] = True

        for idx, row in df.iterrows():
            if row["amount"] <= 0:
                df.at[idx, "card_cost"]    = 0.0
                df.at[idx, "network_cost"] = 0.0
                df.at[idx, "total_cost"]   = 0.0
                df.at[idx, "match_found"]  = False
                continue

            card_fee = CostCalculationService._find_matching_card_fee(
                row["card_brand"], row["card_type"], mcc, row["amount"]
            )
            if card_fee:
                df.at[idx, "product"]      = card_fee["product"]
                df.at[idx, "percent_rate"] = card_fee["percent_rate"]
                df.at[idx, "fixed_rate"]   = card_fee["fixed_rate"]
                df.at[idx, "max_fee"]      = card_fee.get("max_fee")
                df.at[idx, "card_cost"]    = CostCalculationService._calc_cost(
                    row["amount"],
                    card_fee["percent_rate"],
                    card_fee["fixed_rate"],
                    card_fee.get("max_fee"),
                )
            else:
                df.at[idx, "match_found"] = False
                df.at[idx, "card_cost"]   = 0.0

            network_fee = CostCalculationService._find_matching_network_fee(
                row["card_brand"], row["card_type"], row["amount"]
            )
            if network_fee:
                df.at[idx, "network_percent_rate"] = network_fee["percent_rate"]
                df.at[idx, "network_fixed_rate"]   = network_fee["fixed_rate"]
                df.at[idx, "network_cost"]         = CostCalculationService._calc_cost(
                    row["amount"], network_fee["percent_rate"], network_fee["fixed_rate"]
                )
            else:
                df.at[idx, "network_cost"] = 0.0

            df.at[idx, "total_cost"] = df.at[idx, "card_cost"] + df.at[idx, "network_cost"]

        return df

    @staticmethod
    def _compute_metrics(df: pd.DataFrame) -> CostCalculationResponse:
        valid_df = df[(df["amount"] > 0) & (df["match_found"] == True)].copy()

        total_cost   = round(float(valid_df["total_cost"].sum()), 5)
        total_volume = round(float(valid_df["amount"].sum()), 5)
        effective_rate = round(
            (total_cost / total_volume * 100) if total_volume > 0 else 0.0, 5
        )

        slope: Optional[float] = None
        cost_variance: Optional[float] = None

        # Detect date column (transaction_date preferred per current CSV header)
        date_column: Optional[str] = None
        for col in ("transaction_date", "date", "timestamp"):
            if col in valid_df.columns:
                date_column = col
                break

        weekly_cost_variance: Optional[float] = None

        if date_column and len(valid_df) > 1:
            try:
                valid_df[date_column] = pd.to_datetime(valid_df[date_column])

                # Sort by date so the regression reflects chronological order
                valid_df = valid_df.sort_values(date_column).reset_index(drop=True)

                # --- Slope (transaction-level) ---
                # Linear regression on individual transaction total_cost values.
                # X = sequential transaction index (0, 1, 2, ..., n-1)
                # Y = total_cost per transaction
                # slope = change in cost per transaction (chronological order)
                X = np.arange(len(valid_df), dtype=float)
                Y = valid_df["total_cost"].values.astype(float)
                coefficients = np.polyfit(X, Y, 1)
                slope = round(float(coefficients[0]), 5)

                # --- Transaction-level cost variance ---
                # Variance of individual transaction total_cost values
                cost_variance = round(float(valid_df["total_cost"].var()), 5)

                # --- Weekly cost variance ---
                # Group by ISO year-week, sum costs per week, then take variance
                valid_df["year_week"] = valid_df[date_column].dt.strftime("%Y-%W")
                weekly_costs = valid_df.groupby("year_week")["total_cost"].sum()
                if len(weekly_costs) > 1:
                    weekly_cost_variance = round(float(weekly_costs.var()), 5)

            except Exception:
                pass  # insufficient or unparseable date data

        return CostCalculationResponse(
            totalCost=total_cost,
            totalPaymentVolume=total_volume,
            effectiveRate=effective_rate,
            slope=slope,
            costVariance=cost_variance,
            weeklyCostVariance=weekly_cost_variance,
        )

    @staticmethod
    def _print_results(result: CostCalculationResponse, mcc: int) -> None:
        na = "N/A (insufficient data)"
        slope_str          = f"{result.slope:.5f}"              if result.slope              is not None else na
        variance_str       = f"{result.costVariance:.5f}"       if result.costVariance       is not None else na
        wk_variance_str    = f"{result.weeklyCostVariance:.5f}" if result.weeklyCostVariance is not None else na
        lines = [
            "",
            "=" * 60,
            "TRANSACTION COST CALCULATION RESULTS",
            f"MCC: {mcc}",
            "=" * 60,
            f"  Total Cost:                    {result.totalCost:.5f}",
            f"  Total Payment Volume:          {result.totalPaymentVolume:.5f}",
            f"  Effective Rate (%):            {result.effectiveRate:.5f}",
            f"  Slope ($/transaction):         {slope_str}",
            f"  Cost Variance (transaction):   {variance_str}",
            f"  Cost Variance (weekly sums):   {wk_variance_str}",
            "=" * 60,
        ]
        print("\n".join(lines), flush=True)

    # ------------------------------------------------------------------ public

    @staticmethod
    def calculate_from_bytes(
        file_bytes: bytes, filename: str, mcc: int
    ) -> tuple[CostCalculationResponse, bytes]:
        """
        Process a transaction file and return:
          - CostCalculationResponse  (5 metrics, 5 d.p.)
          - enriched_csv_bytes       (original rows + cost columns appended)

        The enriched CSV columns added on top of the originals:
            mcc, product, percent_rate, fixed_rate, max_fee,
            card_cost, network_percent_rate, network_fixed_rate,
            network_cost, total_cost, match_found
        Both are printed to stdout and forwarded to the ML microservice
        by the calling route.
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "csv":
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            raise ValueError(f"Unsupported file type: '{ext}'. Expected csv, xlsx, or xls.")

        enriched_df = CostCalculationService._process_df(df, mcc)
        result      = CostCalculationService._compute_metrics(enriched_df)
        CostCalculationService._print_results(result, mcc)

        # Serialise enriched DataFrame back to CSV bytes for ML forwarding
        buf = io.BytesIO()
        enriched_df.to_csv(buf, index=False)
        enriched_csv_bytes = buf.getvalue()

        return result, enriched_csv_bytes
