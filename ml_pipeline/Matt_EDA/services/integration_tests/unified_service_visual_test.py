from __future__ import annotations

import json
import math
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
KNN_DIR = ROOT / "ml_pipeline" / "Matt_EDA" / "services" / "KNN Quote Service Production"
FORECAST_DIR = ROOT / "ml_pipeline" / "Matt_EDA" / "services" / "GetCostForecast Service"
OUTPUT_DIR = ROOT / "ml_pipeline" / "Matt_EDA" / "service_eval_outputs" / "unified" / "latest"
DB_PATH = OUTPUT_DIR / "unified_eval.sqlite"

PYTHON = ROOT / ".venv" / "bin" / "python"
KNN_PORT = 8090
FORECAST_PORT = 8091

# ---------------------------------------------------------------------------
# Real-data configuration
# ---------------------------------------------------------------------------
REAL_CSV = KNN_DIR / "processed_transactions_4mcc.csv"
TARGET_MERCHANT_ID = 75781   # MCC-5411; 248 k transactions, full 2010-2019 history
EVAL_MCC = 5411
EVAL_YEAR = 2016             # calibration + forecast evaluation year
EVAL_CONTEXT_WEEKS = 8      # weeks 1-8 → context / calibration window
N_REFERENCE_MERCHANTS = 200  # top merchants by tx count (excluding target)
EVAL_CARD_TYPES = ["debit", "credit", "debit (prepaid)"]  # all real card types in dataset


@dataclass
class EvalResult:
    knn_mae: float
    knn_rmse: float
    forecast_mae: float
    forecast_rmse: float


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, timeout: int = 10) -> Dict[str, Any]:
    with urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _wait_for_health(url: str, timeout_s: float = 30.0) -> None:
    t0 = time.monotonic()
    last_err: str | None = None
    while time.monotonic() - t0 < timeout_s:
        try:
            payload = _get_json(url, timeout=3)
            if payload.get("status") == "ok":
                return
        except URLError as exc:
            last_err = str(exc)
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
        time.sleep(0.4)
    raise RuntimeError(f"Health check timed out for {url}. Last error: {last_err}")


def _week_of_year(ts: pd.Timestamp) -> int:
    return min((ts.day_of_year - 1) // 7 + 1, 52)


def _load_real_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load real merchant transaction data from the processed CSV.

    Returns:
    - reference_txn_df  — top N reference merchants (excl. target) for the SQLite backing store
    - onboarding_quote_df  — target merchant January EVAL_YEAR, used for /getQuote
    - onboarding_weekly_df — target merchant weeks 1-EVAL_CONTEXT_WEEKS of EVAL_YEAR,
                             used for /getCompositeMerchant + /GetCostForecast
    - target_full_df       — target merchant full EVAL_YEAR data, holdout ground truth
    """
    print(f"Loading real transaction data from {REAL_CSV} ...")
    df = pd.read_csv(REAL_CSV)
    df5411 = df[df["mcc"] == EVAL_MCC].copy()
    df5411["date_dt"] = pd.to_datetime(df5411["date"])
    df5411["calendar_year"] = df5411["date_dt"].dt.year
    df5411["week_of_year"] = df5411["date_dt"].apply(_week_of_year)

    # Target merchant: full EVAL_YEAR slice for ground-truth comparison
    target_full_df = df5411[
        (df5411["merchant_id"] == TARGET_MERCHANT_ID)
        & (df5411["calendar_year"] == EVAL_YEAR)
    ].copy()

    # Reference merchants: top N by transaction count, excluding the target
    ref_counts = (
        df5411[df5411["merchant_id"] != TARGET_MERCHANT_ID]
        .groupby("merchant_id")["transaction_id"]
        .count()
        .sort_values(ascending=False)
        .head(N_REFERENCE_MERCHANTS)
    )
    reference_txn_df = df5411[df5411["merchant_id"].isin(ref_counts.index)].copy()
    print(f"  Reference merchants: {ref_counts.index.tolist()}")
    print(f"  Reference rows: {len(reference_txn_df):,}")

    # /getQuote onboarding: January of EVAL_YEAR (predict Feb-Apr)
    quote_month = pd.Period(f"{EVAL_YEAR}-01", freq="M")
    onboarding_quote_df = target_full_df[
        target_full_df["date_dt"].dt.to_period("M") == quote_month
    ].copy()

    # /getCompositeMerchant + /GetCostForecast calibration: weeks 1-EVAL_CONTEXT_WEEKS
    onboarding_weekly_df = target_full_df[
        target_full_df["week_of_year"].between(1, EVAL_CONTEXT_WEEKS)
    ].copy()

    print(f"  Target EVAL_YEAR rows: {len(target_full_df):,}")
    print(f"  Quote onboarding rows (Jan {EVAL_YEAR}): {len(onboarding_quote_df):,}")
    print(f"  Weekly onboarding rows (weeks 1-{EVAL_CONTEXT_WEEKS}): {len(onboarding_weekly_df):,}")
    return reference_txn_df, onboarding_quote_df, onboarding_weekly_df, target_full_df


def _build_sqlite(reference_txn_df: pd.DataFrame) -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    # Extract just the columns the KNN service needs
    _TXN_COLS = ["transaction_id", "date", "amount", "merchant_id", "mcc",
                 "card_brand", "card_type", "cost_type_ID", "proc_cost"]
    txn_insert = reference_txn_df[_TXN_COLS].copy()
    txn_insert["cost_type_ID"] = txn_insert["cost_type_ID"].astype("Int64")

    all_cost_type_ids = sorted(
        txn_insert["cost_type_ID"].dropna().unique().astype(int).tolist()
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE transactions (
                transaction_id INTEGER PRIMARY KEY,
                date TEXT,
                amount REAL,
                merchant_id INTEGER,
                mcc INTEGER,
                card_brand TEXT,
                card_type TEXT,
                cost_type_ID INTEGER,
                proc_cost REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE cost_type_ref (
                cost_type_ID INTEGER PRIMARY KEY
            )
            """
        )
        txn_insert.to_sql("transactions", conn, if_exists="append", index=False)
        pd.DataFrame({"cost_type_ID": all_cost_type_ids}).to_sql(
            "cost_type_ref", conn, if_exists="append", index=False
        )
        conn.commit()
    print(f"  SQLite built: {len(txn_insert):,} rows, {len(all_cost_type_ids)} cost types")


def _monthly_actual_proc_cost_pct(target_full_df: pd.DataFrame) -> pd.Series:
    df = target_full_df.copy()
    df["date_dt"] = pd.to_datetime(df["date"])
    df["month"] = df["date_dt"].dt.to_period("M")
    monthly = (
        df.groupby("month")
        .agg(sum_proc_cost=("proc_cost", "sum"), sum_amount=("amount", "sum"))
        .assign(proc_cost_pct=lambda d: d["sum_proc_cost"] / d["sum_amount"])
    )
    return monthly["proc_cost_pct"]


def _weekly_actual_proc_cost_pct(target_full_df: pd.DataFrame) -> pd.Series:
    df = target_full_df.copy()
    if "date_dt" not in df.columns:
        df["date_dt"] = pd.to_datetime(df["date"])
    df["calendar_year"] = df["date_dt"].dt.year
    df["week_of_year"] = df["date_dt"].apply(_week_of_year)
    weekly = (
        df.groupby(["calendar_year", "week_of_year"])
        .agg(sum_proc_cost=("proc_cost", "sum"), sum_amount=("amount", "sum"))
        .assign(proc_cost_pct=lambda d: d["sum_proc_cost"] / d["sum_amount"])
    )
    return weekly["proc_cost_pct"]


def _plot_knn(month_labels: List[str], pred: np.ndarray, actual: np.ndarray) -> None:
    plt.figure(figsize=(10, 5))
    x = np.arange(len(month_labels))
    plt.plot(x, actual, marker="o", linewidth=2.5, label="Actual target proc_cost_pct")
    plt.plot(x, pred, marker="s", linewidth=2.5, linestyle="--", label="KNN predicted (neighbor mean)")
    plt.xticks(x, month_labels)
    plt.title("KNN Quote Service: 3-Month Prediction vs Actual")
    plt.ylabel("proc_cost_pct (ratio)")
    plt.xlabel("Forecast month")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "knn_quote_prediction_vs_actual.png", dpi=140)
    plt.close()


def _plot_get_cost_forecast(
    weeks: np.ndarray,
    pred_calibrated: np.ndarray,
    pred_sarima_raw: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    actual: np.ndarray,
    context_week_indices: np.ndarray,
    context_actuals: np.ndarray,
    context_sarima_fitted: np.ndarray,
) -> None:
    plt.figure(figsize=(14, 5))
    # Context window (left segment)
    plt.plot(
        context_week_indices,
        context_actuals,
        marker="o",
        linewidth=2.0,
        color="steelblue",
        label="Context window (actual)",
    )
    # SARIMA in-sample fit over context window
    valid_mask = ~np.isnan(context_sarima_fitted)
    if valid_mask.any():
        plt.plot(
            context_week_indices[valid_mask],
            context_sarima_fitted[valid_mask],
            marker="^",
            linewidth=1.8,
            linestyle=":",
            color="tomato",
            label="SARIMA in-sample fit (context)",
        )
    # Vertical separator between context and forecast horizon (data-driven).
    separator_x = float(np.min(weeks)) - 0.5
    plt.axvline(x=separator_x, color="grey", linestyle="--", linewidth=1.2, label="Forecast start")
    # Forecast horizon actual
    plt.plot(
        weeks,
        actual,
        marker="o",
        linewidth=2.0,
        color="royalblue",
        label="Actual (forecast horizon)",
    )
    plt.plot(
        weeks,
        pred_sarima_raw,
        marker="^",
        linewidth=2.0,
        linestyle=":",
        color="tomato",
        label="Raw SARIMA/SARIMAX mid (no calibration)",
    )
    plt.plot(
        weeks,
        pred_calibrated,
        marker="s",
        linewidth=2.2,
        linestyle="--",
        color="darkorange",
        label="GetCostForecast calibrated mid",
    )
    plt.fill_between(weeks, lower, upper, alpha=0.2, color="darkorange", label="Prediction CI")
    plt.title("GetCostForecast Service: Context Window + Raw SARIMA vs Calibrated Forecast vs Actual")
    plt.ylabel("proc_cost_pct (ratio)")
    plt.xlabel("Week index  ( ← context window | forecast horizon → )")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "get_cost_forecast_prediction_vs_actual.png", dpi=140)
    plt.close()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Load real merchant data + build SQLite backing store for KNN service.
    reference_txn_df, onboarding_quote_df, onboarding_weekly_df, target_full_df = _load_real_data()
    _build_sqlite(reference_txn_df)

    # 2) Start both APIs.
    knn_env = dict(**{"TRANSACTIONS_AND_COST_TYPE_DB_PATH": str(DB_PATH)})
    knn_env_full = {**dict(**subprocess.os.environ), **knn_env}

    knn_proc = subprocess.Popen(
        [str(PYTHON), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(KNN_PORT)],
        cwd=KNN_DIR,
        env=knn_env_full,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    forecast_proc = subprocess.Popen(
        [str(PYTHON), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(FORECAST_PORT)],
        cwd=FORECAST_DIR,
        env=dict(subprocess.os.environ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_for_health(f"http://127.0.0.1:{KNN_PORT}/health")
        _wait_for_health(f"http://127.0.0.1:{FORECAST_PORT}/health")

        # 3) Evaluate /getQuote
        quote_req = {
            "onboarding_merchant_txn_df": onboarding_quote_df[
                ["date", "amount", "cost_type_ID", "card_type", "proc_cost"]
            ].rename(columns={"date": "transaction_date"}).to_dict(orient="records"),
            "mcc": EVAL_MCC,
            "card_types": EVAL_CARD_TYPES,
            "as_of_date": f"{EVAL_YEAR}-01-31T00:00:00",
        }
        quote_resp = _post_json(f"http://127.0.0.1:{KNN_PORT}/getQuote", quote_req)

        pred_neighbors = np.array([n["forecast_proc_cost_pct_3m"] for n in quote_resp["neighbor_forecasts"]], dtype=float)
        pred_knn = pred_neighbors.mean(axis=0)

        monthly_actual = _monthly_actual_proc_cost_pct(target_full_df)
        forecast_months = [
            pd.Period(f"{EVAL_YEAR}-02", freq="M"),
            pd.Period(f"{EVAL_YEAR}-03", freq="M"),
            pd.Period(f"{EVAL_YEAR}-04", freq="M"),
        ]
        actual_knn = np.array([float(monthly_actual.loc[m]) for m in forecast_months], dtype=float)
        month_labels = [str(m) for m in forecast_months]

        # 4) Build composite from KNN and evaluate /GetCostForecast
        composite_req = {
            "onboarding_merchant_txn_df": onboarding_weekly_df[
                ["date", "amount", "cost_type_ID", "card_type", "proc_cost"]
            ].rename(columns={"date": "transaction_date"}).to_dict(orient="records"),
            "mcc": EVAL_MCC,
            "card_types": EVAL_CARD_TYPES,
        }
        composite_resp = _post_json(f"http://127.0.0.1:{KNN_PORT}/getCompositeMerchant", composite_req)

        forecast_req = {
            "composite_weekly_features": composite_resp["weekly_features"],
            "onboarding_merchant_txn_df": onboarding_weekly_df[
                ["date", "amount", "proc_cost", "cost_type_ID", "card_type"]
            ].rename(columns={"date": "transaction_date"}).to_dict(orient="records"),
            "composite_merchant_id": composite_resp["composite_merchant_id"],
            "mcc": 5411,
            "forecast_horizon_wks": 12,
            "confidence_interval": 0.95,
            "use_optimised_sarima": False,
            "use_exogenous_sarimax": True,
            "use_guarded_calibration": True,
        }
        cost_forecast_resp = _post_json(f"http://127.0.0.1:{FORECAST_PORT}/GetCostForecast", forecast_req)

        # Request a second run with calibration disabled to expose the raw
        # SARIMA/SARIMAX trajectory for side-by-side visual comparison.
        forecast_req_raw = dict(forecast_req)
        forecast_req_raw["use_guarded_calibration"] = False
        cost_forecast_raw_resp = _post_json(
            f"http://127.0.0.1:{FORECAST_PORT}/GetCostForecast", forecast_req_raw
        )

        pred_mid = np.array([w["proc_cost_pct_mid"] for w in cost_forecast_resp["forecast"]], dtype=float)
        pred_mid_raw = np.array(
            [w["proc_cost_pct_mid"] for w in cost_forecast_raw_resp["forecast"]],
            dtype=float,
        )
        pred_low = np.array([w["proc_cost_pct_ci_lower"] for w in cost_forecast_resp["forecast"]], dtype=float)
        pred_up = np.array([w["proc_cost_pct_ci_upper"] for w in cost_forecast_resp["forecast"]], dtype=float)
        pred_week_idx = np.array([w["forecast_week_index"] for w in cost_forecast_resp["forecast"]], dtype=int)

        weekly_actual = _weekly_actual_proc_cost_pct(target_full_df)
        actual_weeks = []
        for week_idx in pred_week_idx:
            actual_weeks.append(float(weekly_actual.loc[(EVAL_YEAR, int(week_idx))]))
        actual_weeks_arr = np.array(actual_weeks, dtype=float)

        # Extract context window actuals for plotting
        context_weeks_count = cost_forecast_resp["process_metadata"]["context_window_weeks_count"]
        context_week_indices = np.arange(1, context_weeks_count + 1, dtype=int)
        context_actuals_list: List[float] = []
        for w in context_week_indices:
            try:
                context_actuals_list.append(float(weekly_actual.loc[(EVAL_YEAR, int(w))]))
            except KeyError:
                context_actuals_list.append(float("nan"))
        context_actuals_arr = np.array(context_actuals_list, dtype=float)

        # Extract SARIMA in-sample fitted values for context window from raw response
        raw_fitted = cost_forecast_raw_resp.get("context_sarima_fitted", [])
        context_sarima_fitted_arr = np.array(
            [float("nan") if v is None else float(v) for v in raw_fitted], dtype=float
        )
        # Pad / trim to match context_week_indices length
        if len(context_sarima_fitted_arr) < context_weeks_count:
            context_sarima_fitted_arr = np.concatenate([
                context_sarima_fitted_arr,
                np.full(context_weeks_count - len(context_sarima_fitted_arr), float("nan")),
            ])
        else:
            context_sarima_fitted_arr = context_sarima_fitted_arr[:context_weeks_count]

        # 5) Metrics + plots
        knn_mae = float(np.mean(np.abs(pred_knn - actual_knn)))
        knn_rmse = float(np.sqrt(np.mean(np.square(pred_knn - actual_knn))))

        forecast_mae = float(np.mean(np.abs(pred_mid - actual_weeks_arr)))
        forecast_rmse = float(np.sqrt(np.mean(np.square(pred_mid - actual_weeks_arr))))

        _plot_knn(month_labels, pred_knn, actual_knn)
        _plot_get_cost_forecast(
            pred_week_idx,
            pred_mid,
            pred_mid_raw,
            pred_low,
            pred_up,
            actual_weeks_arr,
            context_week_indices,
            context_actuals_arr,
            context_sarima_fitted_arr,
        )

        metrics = {
            "knn_quote": {
                "mae": knn_mae,
                "rmse": knn_rmse,
                "forecast_months": month_labels,
                "predicted": pred_knn.tolist(),
                "actual": actual_knn.tolist(),
            },
            "get_cost_forecast": {
                "mae": forecast_mae,
                "rmse": forecast_rmse,
                "week_indices": pred_week_idx.tolist(),
                "predicted_mid": pred_mid.tolist(),
                "predicted_mid_raw_sarima": pred_mid_raw.tolist(),
                "predicted_ci_lower": pred_low.tolist(),
                "predicted_ci_upper": pred_up.tolist(),
                "actual": actual_weeks_arr.tolist(),
                "calibration": cost_forecast_resp.get("process_metadata", {}),
            },
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "artifacts": {
                "knn_plot": str(OUTPUT_DIR / "knn_quote_prediction_vs_actual.png"),
                "forecast_plot": str(OUTPUT_DIR / "get_cost_forecast_prediction_vs_actual.png"),
            },
        }

        with (OUTPUT_DIR / "unified_eval_metrics.json").open("w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        print("Unified evaluation complete.")
        print(f"KNN quote MAE={knn_mae:.6f}, RMSE={knn_rmse:.6f}")
        print(f"GetCostForecast MAE={forecast_mae:.6f}, RMSE={forecast_rmse:.6f}")
        print(f"Saved: {OUTPUT_DIR / 'knn_quote_prediction_vs_actual.png'}")
        print(f"Saved: {OUTPUT_DIR / 'get_cost_forecast_prediction_vs_actual.png'}")
        print(f"Saved: {OUTPUT_DIR / 'unified_eval_metrics.json'}")

    finally:
        for proc in (knn_proc, forecast_proc):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
