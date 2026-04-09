"""
prepare_monthly_training_data.py

Aggregates raw transaction-level CSV into a monthly merchant-level CSV
suitable for training:
  - GetAvgProcCostForecast Service v2  (train.py --mcc <N> --data-path ...)
  - GetTPVForecast Service v2          (train.py --mcc <N> --data-path ...)

Input columns expected (data/processed_transactions_4mcc.csv):
  transaction_id, merchant_id, date, amount, mcc, card_brand,
  card_type, cost_type_ID, proc_cost, year, week

Output per MCC  (e.g. data/5411_monthly_v2.csv):
  merchant_id, year, month,
  avg_proc_cost_pct, std_proc_cost_pct, median_proc_cost_pct, iqr_proc_cost_pct,
  total_processing_value, transaction_count, avg_transaction_value,
  std_txn_amount, median_txn_amount, n_unique_cost_types,
  cost_type_1_pct ... cost_type_61_pct

Usage:
  python prepare_monthly_training_data.py
  python prepare_monthly_training_data.py --input data/processed_transactions_4mcc.csv --output-dir data
  python prepare_monthly_training_data.py --mcc 5411
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = ROOT / "data" / "processed_transactions_4mcc.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data"
COST_TYPE_IDS = list(range(1, 62))   # cost_type_ID values 1–61


# ---------------------------------------------------------------------------
# Core aggregation
# ---------------------------------------------------------------------------

def _aggregate_to_monthly(txn_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate transaction-level rows to monthly merchant-level rows.
    txn_df must already be filtered to a single MCC.
    """
    df = txn_df.copy()

    # Normalise date column (4mcc uses 'date', others use 'transaction_date')
    date_col = "transaction_date" if "transaction_date" in df.columns else "date"
    df["_date"] = pd.to_datetime(df[date_col])
    df["year"] = df["_date"].dt.year
    df["month"] = df["_date"].dt.month

    # Per-transaction processing cost percentage (guard against zero amount)
    df["_pct"] = np.where(df["amount"] > 0, df["proc_cost"] / df["amount"], np.nan)

    # Cast cost_type_ID to nullable int for grouping
    df["_ct"] = pd.to_numeric(df["cost_type_ID"], errors="coerce").astype("Int64")

    rows = []
    for (mid, yr, mo), g in df.groupby(["merchant_id", "year", "month"]):
        pct = g["_pct"].dropna()
        amt = g["amount"]
        ct = g["_ct"].dropna()

        row: dict = {
            "merchant_id": mid,
            "year": int(yr),
            "month": int(mo),
            # M9 target + v2 cost-pct features
            "avg_proc_cost_pct": float(pct.mean()) if len(pct) > 0 else np.nan,
            "std_proc_cost_pct": float(pct.std(ddof=1)) if len(pct) > 1 else 0.0,
            "median_proc_cost_pct": float(pct.median()) if len(pct) > 0 else np.nan,
            "iqr_proc_cost_pct": (
                float(np.percentile(pct, 75) - np.percentile(pct, 25))
                if len(pct) >= 2 else 0.0
            ),
            # TPV target + v2 amount features (shared with M9)
            "total_processing_value": float(amt.sum()),
            "transaction_count": int(len(g)),
            "avg_transaction_value": float(amt.mean()),
            "std_txn_amount": float(amt.std(ddof=1)) if len(amt) > 1 else 0.0,
            "median_txn_amount": float(amt.median()),
            # M9 v2 feature
            "n_unique_cost_types": int(ct.nunique()),
        }

        # cost_type_N_pct: fraction of transactions (by row count) per cost_type_ID
        ct_fracs = ct.value_counts(normalize=True)
        for cid in COST_TYPE_IDS:
            row[f"cost_type_{cid}_pct"] = float(ct_fracs.get(cid, 0.0))

        rows.append(row)

    monthly = pd.DataFrame(rows)

    # Drop months where avg_proc_cost_pct is NaN (no valid pct observations)
    monthly = monthly.dropna(subset=["avg_proc_cost_pct"]).reset_index(drop=True)

    return monthly


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate raw transactions to monthly training CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help=f"Path to raw transactions CSV (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory to write output CSVs (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--mcc",
        type=int,
        default=None,
        help="Process only this MCC code (default: all MCCs found in the file)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading {input_path} ...")
    txn_df = pd.read_csv(input_path)
    print(f"  {len(txn_df):,} rows | MCCs present: {sorted(txn_df['mcc'].unique())}")

    mcc_list = [args.mcc] if args.mcc else sorted(txn_df["mcc"].unique())

    for mcc in mcc_list:
        sub = txn_df[txn_df["mcc"] == mcc].copy()
        n_merchants = sub["merchant_id"].nunique()
        print(f"\n[MCC {mcc}] {len(sub):,} transactions | {n_merchants:,} merchants")

        monthly = _aggregate_to_monthly(sub)

        n_m_out = monthly["merchant_id"].nunique()
        yr_min = monthly["year"].min()
        yr_max = monthly["year"].max()
        print(
            f"  → {len(monthly):,} monthly rows | {n_m_out:,} merchants | "
            f"years {yr_min}–{yr_max}"
        )

        out_path = output_dir / f"{mcc}_monthly_v2.csv"
        monthly.to_csv(out_path, index=False)
        print(f"  Saved: {out_path}")

    print("\nDone. Next steps:")
    for mcc in mcc_list:
        svc_m9 = "ml_pipeline/Matt_EDA/services/GetAvgProcCostForecast Service v2"
        svc_tpv = "ml_pipeline/Matt_EDA/services/GetTPVForecast Service v2"
        data_path = f"../../data/{mcc}_monthly_v2.csv"
        print(f"\n  # MCC {mcc} — M9 cost forecast:")
        print(f"  cd \"{svc_m9}\"")
        print(f"  python train.py --mcc {mcc} --data-path \"{data_path}\"")
        print(f"\n  # MCC {mcc} — TPV forecast:")
        print(f"  cd \"{svc_tpv}\"")
        print(f"  python train.py --mcc {mcc} --data-path \"{data_path}\"")


if __name__ == "__main__":
    main()
