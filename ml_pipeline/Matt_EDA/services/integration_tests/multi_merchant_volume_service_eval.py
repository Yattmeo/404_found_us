from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
KNN_DIR = ROOT / "ml_pipeline" / "Matt_EDA" / "services" / "KNN Quote Service Production"
VOLUME_DIR = ROOT / "ml_pipeline" / "Matt_EDA" / "services" / "GetVolumeForecast Service"
OUTPUT_DIR = ROOT / "ml_pipeline" / "Matt_EDA" / "service_eval_outputs" / "multi_volume" / "latest"
DB_PATH = OUTPUT_DIR / "multi_merchant_volume_eval.sqlite"
METRICS_PATH = OUTPUT_DIR / "multi_merchant_volume_eval_metrics.json"
SWEEP_METRICS_PATH = OUTPUT_DIR / "multi_merchant_volume_eval_sweep_metrics.json"
PLOT_PATH = OUTPUT_DIR / "multi_merchant_volume_forecast_panels.png"

PYTHON = ROOT / ".venv" / "bin" / "python"
KNN_PORT = 8090
VOLUME_PORT = 8092

REAL_CSV = KNN_DIR / "processed_transactions_4mcc.csv"
EVAL_MCC = 5411
EVAL_YEAR = 2016
EVAL_CONTEXT_WEEKS = 8
FORECAST_HORIZON_WEEKS = 12
CARD_TYPES = ["debit", "credit", "debit (prepaid)"]

DEFAULT_REFERENCE_MERCHANTS = 300
DEFAULT_TARGET_MERCHANTS = 10
DEFAULT_MIN_TARGET_ROWS_PER_YEAR = 50
DEFAULT_RANDOM_SEED = 7
EPSILON_ACTUAL = 1e-9


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str, timeout: int = 10) -> Dict[str, Any]:
    with urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _wait_for_health(url: str, timeout_s: float = 40.0) -> None:
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


def _weekly_actual_total_proc_value(target_full_df: pd.DataFrame) -> pd.Series:
    df = target_full_df.copy()
    if "date_dt" not in df.columns:
        df["date_dt"] = pd.to_datetime(df["date"])
    df["calendar_year"] = df["date_dt"].dt.year
    df["week_of_year"] = df["date_dt"].apply(_week_of_year)
    weekly = df.groupby(["calendar_year", "week_of_year"]).agg(sum_amount=("amount", "sum"))
    return weekly["sum_amount"]


def _build_sqlite(reference_txn_df: pd.DataFrame, db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()

    cols = [
        "transaction_id",
        "date",
        "amount",
        "merchant_id",
        "mcc",
        "card_brand",
        "card_type",
        "cost_type_ID",
        "proc_cost",
    ]
    insert_df = reference_txn_df[cols].copy()
    insert_df["cost_type_ID"] = insert_df["cost_type_ID"].astype("Int64")
    all_cost_type_ids = sorted(insert_df["cost_type_ID"].dropna().unique().astype(int).tolist())

    with sqlite3.connect(db_path) as conn:
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
        insert_df.to_sql("transactions", conn, if_exists="append", index=False)
        pd.DataFrame({"cost_type_ID": all_cost_type_ids}).to_sql(
            "cost_type_ref", conn, if_exists="append", index=False
        )
        conn.commit()


def _select_merchants(
    df5411: pd.DataFrame,
    n_reference_merchants: int,
    n_target_merchants: int,
    min_target_rows_per_year: int,
    eval_year: int,
    random_seed: int,
) -> tuple[List[int], List[int]]:
    rng = np.random.default_rng(random_seed)
    all_merchants = sorted(df5411["merchant_id"].dropna().astype(int).unique().tolist())
    counts_eval_year = df5411[df5411["year"] == eval_year].groupby("merchant_id")["transaction_id"].count()

    candidates: List[int] = []
    for merchant_id, count in counts_eval_year.items():
        merchant_id_int = int(merchant_id)
        if int(count) < min_target_rows_per_year:
            continue
        mdf = df5411[(df5411["merchant_id"] == merchant_id_int) & (df5411["year"] == eval_year)].copy()
        mdf["date_dt"] = pd.to_datetime(mdf["date"])
        jan_rows = mdf[mdf["date_dt"].dt.to_period("M") == pd.Period(f"{eval_year}-01", freq="M")]
        if jan_rows.empty:
            continue
        candidates.append(merchant_id_int)

    if len(candidates) < n_target_merchants:
        raise RuntimeError(
            f"Not enough eligible target merchants. Required={n_target_merchants}, available={len(candidates)}"
        )

    target_merchants = sorted(rng.choice(np.array(candidates), size=n_target_merchants, replace=False).astype(int).tolist())

    reference_candidates = [m for m in all_merchants if m not in set(target_merchants)]
    if len(reference_candidates) < n_reference_merchants:
        raise RuntimeError(
            f"Not enough reference merchants. Required={n_reference_merchants}, available={len(reference_candidates)}"
        )
    reference_merchants = sorted(
        rng.choice(np.array(reference_candidates), size=n_reference_merchants, replace=False).astype(int).tolist()
    )
    return reference_merchants, target_merchants


def _plot_all_merchants(eval_rows: List[Dict[str, Any]], output_path: Path) -> None:
    if not eval_rows:
        return

    n = len(eval_rows)
    ncols = 2
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(16, 3.8 * nrows), squeeze=False)
    axes_flat = axes.flatten()

    for i, row in enumerate(eval_rows):
        ax = axes_flat[i]
        merchant_id = row["merchant_id"]

        x_context = np.array(row["x_context"], dtype=int)
        x_forecast = np.array(row["x_forecast"], dtype=int)
        context_actual = np.array(row["context_actual"], dtype=float)
        forecast_actual = np.array(row["forecast_actual"], dtype=float)
        context_raw = np.array(row["context_raw"], dtype=float)
        forecast_raw = np.array(row["forecast_raw"], dtype=float)
        forecast_cal = np.array(row["forecast_cal"], dtype=float)
        forecast_low = np.array(row["forecast_low"], dtype=float)
        forecast_up = np.array(row["forecast_up"], dtype=float)
        context_mean = float(row["context_mean"])

        ax.plot(x_context, context_actual, marker="o", linewidth=2.0, color="steelblue", label="Actual (context)")
        ax.plot(x_forecast, forecast_actual, marker="o", linewidth=2.0, color="royalblue", label="Actual (forecast)")

        raw_ctx_mask = ~np.isnan(context_raw)
        if raw_ctx_mask.any():
            ax.plot(
                x_context[raw_ctx_mask],
                context_raw[raw_ctx_mask],
                marker="^",
                linewidth=1.8,
                linestyle=":",
                color="tomato",
                label="SARIMA raw (context fit)",
            )
        ax.plot(x_forecast, forecast_raw, marker="^", linewidth=1.8, linestyle=":", color="tomato", label="SARIMA raw")

        ax.plot(x_forecast, forecast_cal, marker="s", linewidth=2.0, linestyle="--", color="darkorange", label="SARIMA calibrated")
        ax.fill_between(x_forecast, forecast_low, forecast_up, alpha=0.18, color="darkorange", label="Prediction CI")

        ax.axhline(y=context_mean, color="black", linestyle="-.", linewidth=1.2, label="Context mean")
        if len(x_forecast) > 0:
            forecast_start_x = float(np.min(x_forecast)) - 0.5
            ax.axvline(x=forecast_start_x, color="grey", linestyle="--", linewidth=1.1, label="Forecast start")

        ax.set_title(f"Merchant {merchant_id}")
        ax.set_xlabel("Week index (context -> forecast)")
        ax.set_ylabel("weekly_total_proc_value")
        ax.grid(alpha=0.25)
        if i == 0:
            ax.legend(fontsize=8)

    for j in range(n, len(axes_flat)):
        axes_flat[j].axis("off")

    fig.suptitle("Multi-merchant volume evaluation: Context + Forecast (Actual vs Raw vs Calibrated)", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def _evaluate_once(
    df5411: pd.DataFrame,
    eval_year: int,
    context_weeks: int,
    forecast_horizon_weeks: int,
    use_optimised_sarima: bool,
    n_reference_merchants: int,
    n_target_merchants: int,
    min_target_rows_per_year: int,
    random_seed: int,
    db_path: Path,
) -> Dict[str, Any]:
    reference_merchants, target_merchants = _select_merchants(
        df5411,
        n_reference_merchants=n_reference_merchants,
        n_target_merchants=n_target_merchants,
        min_target_rows_per_year=min_target_rows_per_year,
        eval_year=eval_year,
        random_seed=random_seed,
    )
    if not target_merchants:
        raise RuntimeError("No suitable target merchants found for evaluation.")

    reference_txn_df = df5411[df5411["merchant_id"].isin(reference_merchants)].copy()
    _build_sqlite(reference_txn_df, db_path=db_path)

    print(f"Reference merchants ({len(reference_merchants)}): {reference_merchants}")
    print(f"Target merchants ({len(target_merchants)}): {target_merchants}")

    knn_env = {"TRANSACTIONS_AND_COST_TYPE_DB_PATH": str(db_path)}
    knn_env_full = {**dict(os.environ), **knn_env}

    knn_proc = subprocess.Popen(
        [str(PYTHON), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(KNN_PORT)],
        cwd=KNN_DIR,
        env=knn_env_full,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    volume_proc = subprocess.Popen(
        [str(PYTHON), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(VOLUME_PORT)],
        cwd=VOLUME_DIR,
        env=dict(os.environ),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    per_merchant: List[Dict[str, Any]] = []
    plot_rows: List[Dict[str, Any]] = []
    try:
        _wait_for_health(f"http://127.0.0.1:{KNN_PORT}/health")
        _wait_for_health(f"http://127.0.0.1:{VOLUME_PORT}/health")

        for merchant_id in target_merchants:
            target_full_df = df5411[(df5411["merchant_id"] == merchant_id) & (df5411["year"] == eval_year)].copy()
            target_full_df["date_dt"] = pd.to_datetime(target_full_df["date"])
            target_full_df["calendar_year"] = target_full_df["date_dt"].dt.year
            target_full_df["week_of_year"] = target_full_df["date_dt"].apply(_week_of_year)

            onboarding_weekly_df = target_full_df[target_full_df["week_of_year"].between(1, context_weeks)].copy()

            composite_req = {
                "onboarding_merchant_txn_df": onboarding_weekly_df[
                    ["date", "amount", "cost_type_ID", "card_type", "proc_cost"]
                ].rename(columns={"date": "transaction_date"}).to_dict(orient="records"),
                "mcc": EVAL_MCC,
                "card_types": CARD_TYPES,
            }
            composite_resp = _post_json(f"http://127.0.0.1:{KNN_PORT}/getCompositeMerchant", composite_req)

            forecast_req = {
                "composite_weekly_features": composite_resp["weekly_features"],
                "onboarding_merchant_txn_df": onboarding_weekly_df[
                    ["date", "amount", "proc_cost", "cost_type_ID", "card_type"]
                ].rename(columns={"date": "transaction_date"}).to_dict(orient="records"),
                "composite_merchant_id": composite_resp["composite_merchant_id"],
                "mcc": EVAL_MCC,
                "forecast_horizon_wks": forecast_horizon_weeks,
                "confidence_interval": 0.95,
                "use_optimised_sarima": use_optimised_sarima,
                "use_exogenous_sarimax": True,
                "use_guarded_calibration": True,
            }
            volume_forecast_resp = _post_json(f"http://127.0.0.1:{VOLUME_PORT}/GetVolumeForecast", forecast_req)

            forecast_req_raw = dict(forecast_req)
            forecast_req_raw["use_guarded_calibration"] = False
            volume_forecast_raw_resp = _post_json(f"http://127.0.0.1:{VOLUME_PORT}/GetVolumeForecast", forecast_req_raw)

            pred_mid = np.array([w["total_proc_value_mid"] for w in volume_forecast_resp["forecast"]], dtype=float)
            pred_mid_raw = np.array([w["total_proc_value_mid"] for w in volume_forecast_raw_resp["forecast"]], dtype=float)
            pred_low = np.array([w["total_proc_value_ci_lower"] for w in volume_forecast_resp["forecast"]], dtype=float)
            pred_up = np.array([w["total_proc_value_ci_upper"] for w in volume_forecast_resp["forecast"]], dtype=float)
            pred_week_idx = np.array([w["forecast_week_index"] for w in volume_forecast_resp["forecast"]], dtype=int)

            weekly_actual = _weekly_actual_total_proc_value(target_full_df)
            actual_weeks: List[float] = []
            observed_actual_mask: List[bool] = []
            missing_forecast_weeks = 0
            for week_idx in pred_week_idx:
                key = (eval_year, int(week_idx))
                if key in weekly_actual.index:
                    actual_weeks.append(float(weekly_actual.loc[key]))
                    observed_actual_mask.append(True)
                else:
                    actual_weeks.append(EPSILON_ACTUAL)
                    observed_actual_mask.append(False)
                    missing_forecast_weeks += 1
            actual_weeks_arr = np.array(actual_weeks, dtype=float)
            observed_mask_arr = np.array(observed_actual_mask, dtype=bool)

            context_week_idx = np.arange(1, context_weeks + 1, dtype=int)
            context_actual_list: List[float] = []
            for wk in context_week_idx:
                key = (eval_year, int(wk))
                if key in weekly_actual.index:
                    context_actual_list.append(float(weekly_actual.loc[key]))
                else:
                    context_actual_list.append(EPSILON_ACTUAL)
            context_actual_arr = np.array(context_actual_list, dtype=float)

            raw_context = np.array(
                [float("nan") if v is None else float(v) for v in volume_forecast_raw_resp.get("context_sarima_fitted", [])],
                dtype=float,
            )
            if len(raw_context) < context_weeks:
                raw_context = np.concatenate([raw_context, np.full(context_weeks - len(raw_context), float("nan"))])
            else:
                raw_context = raw_context[:context_weeks]

            forecast_mae = float(np.mean(np.abs(pred_mid - actual_weeks_arr)))
            forecast_rmse = float(np.sqrt(np.mean(np.square(pred_mid - actual_weeks_arr))))
            forecast_raw_mae = float(np.mean(np.abs(pred_mid_raw - actual_weeks_arr)))
            forecast_raw_rmse = float(np.sqrt(np.mean(np.square(pred_mid_raw - actual_weeks_arr))))
            if observed_mask_arr.any():
                corrected_forecast_mae = float(
                    np.mean(np.abs(pred_mid[observed_mask_arr] - actual_weeks_arr[observed_mask_arr]))
                )
            else:
                corrected_forecast_mae = None

            rec = {
                "merchant_id": merchant_id,
                "rows_in_eval_year": int(len(target_full_df)),
                "forecast_mae": forecast_mae,
                "forecast_rmse": forecast_rmse,
                "forecast_raw_mae": forecast_raw_mae,
                "forecast_raw_rmse": forecast_raw_rmse,
                "forecast_mae_corrected_observed_only": corrected_forecast_mae,
                "missing_forecast_weeks_filled_with_epsilon": int(missing_forecast_weeks),
                "calibration": volume_forecast_resp.get("process_metadata", {}),
                "sarima": volume_forecast_resp.get("sarima_metadata", {}),
            }
            per_merchant.append(rec)

            context_mean = volume_forecast_resp.get("process_metadata", {}).get("context_window_mean_total_proc_value")
            if context_mean is None:
                context_mean = float(np.mean(context_actual_arr))
            plot_rows.append(
                {
                    "merchant_id": int(merchant_id),
                    "x_context": context_week_idx.tolist(),
                    "x_forecast": pred_week_idx.tolist(),
                    "context_actual": context_actual_arr.tolist(),
                    "forecast_actual": actual_weeks_arr.tolist(),
                    "context_raw": raw_context.tolist(),
                    "forecast_raw": pred_mid_raw.tolist(),
                    "forecast_cal": pred_mid.tolist(),
                    "forecast_low": pred_low.tolist(),
                    "forecast_up": pred_up.tolist(),
                    "context_mean": float(context_mean),
                }
            )
            print(
                f"merchant {merchant_id}: "
                f"Forecast MAE={forecast_mae:.4f}, "
                f"cal_mode={rec['calibration'].get('calibration_mode')}"
            )

        if len(per_merchant) == 0:
            raise RuntimeError("No merchant produced complete metrics after filtering.")

        fc_maes = np.array([m["forecast_mae"] for m in per_merchant], dtype=float)
        fc_rmses = np.array([m["forecast_rmse"] for m in per_merchant], dtype=float)
        fc_raw_maes = np.array([m["forecast_raw_mae"] for m in per_merchant], dtype=float)
        fc_raw_rmses = np.array([m["forecast_raw_rmse"] for m in per_merchant], dtype=float)
        fc_corrected_maes = np.array(
            [m["forecast_mae_corrected_observed_only"] for m in per_merchant if m["forecast_mae_corrected_observed_only"] is not None],
            dtype=float,
        )

        summary = {
            "merchant_count": len(per_merchant),
            "get_volume_forecast": {
                "mae_mean": float(fc_maes.mean()),
                "mae_median": float(np.median(fc_maes)),
                "mae_std": float(fc_maes.std()),
                "rmse_mean": float(fc_rmses.mean()),
                "rmse_median": float(np.median(fc_rmses)),
                "rmse_std": float(fc_rmses.std()),
            },
            "get_volume_forecast_corrected_observed_only": {
                "mae_mean": float(fc_corrected_maes.mean()) if len(fc_corrected_maes) > 0 else None,
                "mae_median": float(np.median(fc_corrected_maes)) if len(fc_corrected_maes) > 0 else None,
                "mae_std": float(fc_corrected_maes.std()) if len(fc_corrected_maes) > 0 else None,
                "merchant_count_with_observed_weeks": int(len(fc_corrected_maes)),
            },
            "get_volume_forecast_raw": {
                "mae_mean": float(fc_raw_maes.mean()),
                "mae_median": float(np.median(fc_raw_maes)),
                "mae_std": float(fc_raw_maes.std()),
                "rmse_mean": float(fc_raw_rmses.mean()),
                "rmse_median": float(np.median(fc_raw_rmses)),
                "rmse_std": float(fc_raw_rmses.std()),
            },
        }

        _plot_all_merchants(plot_rows, PLOT_PATH)

        payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "dataset": {
                "csv": str(REAL_CSV),
                "mcc": EVAL_MCC,
                "eval_year": eval_year,
                "context_weeks": context_weeks,
                "forecast_horizon_weeks": forecast_horizon_weeks,
                "use_optimised_sarima": use_optimised_sarima,
                "reference_merchants": reference_merchants,
                "target_merchants": target_merchants,
                "card_types": CARD_TYPES,
                "n_reference_merchants": n_reference_merchants,
                "n_target_merchants": n_target_merchants,
                "min_target_rows_per_year": min_target_rows_per_year,
                "random_seed": random_seed,
                "epsilon_actual_for_missing_weeks": EPSILON_ACTUAL,
            },
            "summary": summary,
            "per_merchant": per_merchant,
            "artifacts": {
                "plot": str(PLOT_PATH),
            },
        }
        return payload
    finally:
        for proc in (knn_proc, volume_proc):
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-merchant volume service evaluation.")
    parser.add_argument("--reference-merchants", type=int, default=DEFAULT_REFERENCE_MERCHANTS)
    parser.add_argument("--target-merchants", type=int, default=DEFAULT_TARGET_MERCHANTS)
    parser.add_argument("--min-target-rows", type=int, default=DEFAULT_MIN_TARGET_ROWS_PER_YEAR)
    parser.add_argument("--eval-year", type=int, default=EVAL_YEAR)
    parser.add_argument("--context-weeks", type=int, default=EVAL_CONTEXT_WEEKS)
    parser.add_argument("--forecast-weeks", type=int, default=FORECAST_HORIZON_WEEKS)
    parser.add_argument("--random-seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--use-optimised-sarima", action="store_true")
    parser.add_argument(
        "--sweep-reference-merchants",
        type=str,
        default="",
        help="Comma-separated list, e.g. 20,50,100",
    )
    return parser.parse_args()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    args = _parse_args()
    print(f"Loading: {REAL_CSV}")
    df = pd.read_csv(REAL_CSV)
    df5411 = df[df["mcc"] == EVAL_MCC].copy()

    sweep_values: List[int] = []
    if args.sweep_reference_merchants.strip():
        sweep_values = [int(x.strip()) for x in args.sweep_reference_merchants.split(",") if x.strip()]
    if not sweep_values:
        sweep_values = [args.reference_merchants]

    sweep_runs: List[Dict[str, Any]] = []
    for n_ref in sweep_values:
        print("\n============================================================")
        print(f"Running configuration: n_reference_merchants={n_ref}")
        payload = _evaluate_once(
            df5411=df5411,
            eval_year=args.eval_year,
            context_weeks=args.context_weeks,
            forecast_horizon_weeks=args.forecast_weeks,
            use_optimised_sarima=args.use_optimised_sarima,
            n_reference_merchants=n_ref,
            n_target_merchants=args.target_merchants,
            min_target_rows_per_year=args.min_target_rows,
            random_seed=args.random_seed,
            db_path=DB_PATH,
        )
        sweep_runs.append(payload)
        print(json.dumps(payload["summary"], indent=2))

    if len(sweep_runs) == 1:
        with METRICS_PATH.open("w", encoding="utf-8") as f:
            json.dump(sweep_runs[0], f, indent=2)
        print(f"\nSaved: {METRICS_PATH}")
    else:
        sweep_payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "runs": sweep_runs,
        }
        with SWEEP_METRICS_PATH.open("w", encoding="utf-8") as f:
            json.dump(sweep_payload, f, indent=2)
        print(f"\nSaved: {SWEEP_METRICS_PATH}")


if __name__ == "__main__":
    main()
