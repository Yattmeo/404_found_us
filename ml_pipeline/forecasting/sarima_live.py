from __future__ import annotations

import argparse
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from statsmodels.tsa.statespace.sarimax import SARIMAX  # type: ignore[import-not-found]

auto_arima = None
has_pmdarima = False
try:
    from pmdarima import auto_arima as _auto_arima  # type: ignore[import-not-found]

    auto_arima = _auto_arima
    has_pmdarima = True
except Exception:
    pass


@dataclass
class NeighbourSelection:
    end_month: int
    neighbour_ids: List[int]
    distances: List[float]


@dataclass
class SarimaLiveResult:
    week_labels: List[str]
    tpv_forecast: List[float]
    tcr_forecast: List[float]
    tpc_forecast: List[float]
    neighbour_ids: List[int]
    neighbour_distances: List[float]
    tpv_order: Tuple[int, int, int]
    tpv_seasonal_order: Tuple[int, int, int, int]
    tcr_order: Tuple[int, int, int]
    tcr_seasonal_order: Tuple[int, int, int, int]


class SarimaLiveService:
    def __init__(
        self,
        knn_service_path: Optional[Path] = None,
        knn_base_dir: Optional[Path] = None,
        knn_k: int = 5,
        seasonal_period: int = 52,
    ) -> None:
        self.seasonal_period = seasonal_period
        self.knn = self._build_knn_service(knn_service_path, knn_base_dir, knn_k)

    @staticmethod
    def _default_knn_service_path() -> Path:
        return Path(__file__).resolve().parents[1] / "Matt_EDA" / "KNN Demo Service" / "knn_rate_quote_service.py"

    def _build_knn_service(self, knn_service_path: Optional[Path], knn_base_dir: Optional[Path], knn_k: int) -> Any:
        service_path = knn_service_path or self._default_knn_service_path()
        if not service_path.exists():
            raise FileNotFoundError(f"KNN service file not found: {service_path}")

        spec = importlib.util.spec_from_file_location("knn_live_module", service_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Failed to load KNN service from: {service_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        KNNRateQuoteService = getattr(module, "KNNRateQuoteService")

        return KNNRateQuoteService(base_dir=knn_base_dir, k=knn_k)

    @staticmethod
    def _coerce_prospect_weekly(prospect_weekly: Any) -> pd.DataFrame:
        if isinstance(prospect_weekly, pd.DataFrame):
            df = prospect_weekly.copy()
        elif isinstance(prospect_weekly, list):
            df = pd.DataFrame(prospect_weekly)
        elif isinstance(prospect_weekly, dict):
            df = pd.DataFrame([prospect_weekly])
        else:
            raise TypeError("prospect_weekly must be DataFrame, list[dict], or dict")

        if "week" in df.columns:
            df = df.set_index("week")

        needed = {"TPV", "TCR"}
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"prospect_weekly missing columns: {sorted(missing)}")

        df["TPV"] = pd.to_numeric(df["TPV"], errors="coerce")
        df["TCR"] = pd.to_numeric(df["TCR"], errors="coerce")
        df = df[["TPV", "TCR"]].dropna()

        if len(df) < 4:
            raise ValueError("Need at least 4 prospect weekly rows")

        return df.sort_index()

    def _build_pool_by_month_with_ids(self, monthly_data: pd.DataFrame) -> Dict[int, pd.DataFrame]:
        pool_by_month: Dict[int, List[pd.DataFrame]] = {}

        all_periods = sorted(monthly_data["ym_period"].unique())
        if not all_periods:
            return {}

        min_period = all_periods[0]
        max_period = all_periods[-1]

        for end_period in all_periods:
            start_context = end_period - (self.knn.context_len - 1)
            end_target = end_period + self.knn.horizon_len
            if start_context < min_period or end_target > max_period:
                continue

            context_periods = pd.period_range(start_context, end_period, freq="M")
            target_periods = pd.period_range(end_period + 1, end_period + self.knn.horizon_len, freq="M")

            ctx_df = monthly_data[monthly_data["ym_period"].isin(context_periods)]
            target_df = monthly_data[monthly_data["ym_period"].isin(target_periods)]

            ctx_agg = ctx_df.groupby("merchant_id")[self.knn.feature_cols].mean()
            targets = (
                target_df.pivot_table(index="merchant_id", columns="ym_period", values="target_proc_cost")
                .reindex(columns=target_periods)
                .copy()
            )

            if ctx_agg.empty or targets.empty:
                continue

            targets.columns = [f"t{i}" for i in range(1, self.knn.horizon_len + 1)]
            merchant_cases = ctx_agg.join(targets, how="inner").dropna()
            if merchant_cases.empty:
                continue

            merchant_cases = merchant_cases.reset_index()
            merchant_cases["end_period"] = end_period
            merchant_cases["end_month"] = end_period.month
            pool_by_month.setdefault(end_period.month, []).append(merchant_cases)

        combined: Dict[int, pd.DataFrame] = {}
        for month_num, frames in pool_by_month.items():
            combined[month_num] = pd.concat(frames, axis=0, ignore_index=True)
        return combined

    def _select_live_neighbours(
        self,
        mcc: int,
        card_type: Optional[str],
        df: Optional[pd.DataFrame],
        monthly_txn_count: Optional[int],
        avg_amount: Optional[float],
        as_of_date: Optional[pd.Timestamp],
    ) -> NeighbourSelection:
        _ = mcc
        query_vec, end_month = self.knn._compute_query_features(
            df=df,
            monthly_txn_count=monthly_txn_count,
            avg_amount=avg_amount,
            as_of_date=as_of_date,
            card_type=card_type,
        )

        if card_type and card_type.lower() != "both" and "card_type" in self.knn.all_monthly.columns:
            filtered = self.knn.all_monthly[
                self.knn.all_monthly["card_type"].astype(str).str.lower() == card_type.lower()
            ]
        else:
            filtered = self.knn.all_monthly

        pools = self._build_pool_by_month_with_ids(filtered)
        pool = pools.get(end_month)
        if pool is None or pool.empty:
            raise ValueError(f"No neighbour pool available for month={end_month}")

        X_pool = pool[self.knn.feature_cols].values
        knn = NearestNeighbors(n_neighbors=min(self.knn.k, len(pool)), metric="euclidean")
        knn.fit(X_pool)

        distances, neighbor_idx = knn.kneighbors(query_vec)
        idx = neighbor_idx[0]
        d = distances[0]

        neighbours = pool.iloc[idx]
        ids = neighbours["merchant_id"].astype(int).tolist()
        return NeighbourSelection(end_month=end_month, neighbour_ids=ids, distances=[float(x) for x in d])

    @staticmethod
    def _iso_year_week(series: pd.Series) -> pd.Series:
        iso = series.dt.isocalendar()
        return iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)

    def _load_merchant_weekly(self, merchant_ids: List[int]) -> Dict[int, pd.DataFrame]:
        if not merchant_ids:
            return {}

        placeholders = ",".join(["?"] * len(merchant_ids))
        query = f"""
            SELECT merchant_id, date, amount, proc_cost
            FROM transactions
            WHERE merchant_id IN ({placeholders})
              AND amount > 0
        """

        import sqlite3

        with sqlite3.connect(self.knn.db_path) as conn:
            df = pd.read_sql(query, conn, params=merchant_ids)

        if df.empty:
            return {}

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["proc_cost"] = pd.to_numeric(df["proc_cost"], errors="coerce").fillna(0.0)
        df = df.dropna(subset=["date", "amount"])
        df["year_week"] = self._iso_year_week(df["date"])

        out: Dict[int, pd.DataFrame] = {}
        for mid, grp in df.groupby("merchant_id"):
            weekly = (
                grp.groupby("year_week")
                .agg(TPV=("amount", "sum"), TPC=("proc_cost", "sum"))
                .sort_index()
            )
            weekly["TCR"] = np.where(weekly["TPV"] > 0, weekly["TPC"] / weekly["TPV"] * 100.0, np.nan)
            out[int(str(mid))] = weekly

        return out

    @staticmethod
    def _build_composite(weekly_data: Dict[int, pd.DataFrame], distances_by_id: Dict[int, float]) -> pd.DataFrame:
        all_weeks = sorted({wk for d in weekly_data.values() for wk in d.index})

        raw_w = {mid: 1.0 / (float(distances_by_id[mid]) + 1e-6) for mid in weekly_data.keys()}
        denom = sum(raw_w.values())
        weights = {mid: w / denom for mid, w in raw_w.items()}

        rows: List[Dict[str, float]] = []
        for wk in all_weeks:
            tpv_num = tcr_num = tpv_w = tcr_w = 0.0
            for mid, wd in weekly_data.items():
                if wk not in wd.index:
                    continue
                row = wd.loc[wk]
                w = weights[mid]
                if pd.notna(row["TPV"]):
                    tpv_num += w * float(row["TPV"])
                    tpv_w += w
                if pd.notna(row["TCR"]):
                    tcr_num += w * float(row["TCR"])
                    tcr_w += w
            rows.append(
                {
                    "week": wk,
                    "TPV": tpv_num / tpv_w if tpv_w > 0 else np.nan,
                    "TCR": tcr_num / tcr_w if tcr_w > 0 else np.nan,
                }
            )

        return pd.DataFrame(rows).set_index("week").sort_index()

    def _fallback_order(self, series: pd.Series) -> Tuple[Tuple[int, int, int], Tuple[int, int, int, int]]:
        n = len(series.dropna())
        s = self.seasonal_period if n >= self.seasonal_period * 2 else 4
        return (1, 1, 1), (1, 1, 1, s)

    def _select_order(self, series: pd.Series) -> Tuple[Tuple[int, int, int], Tuple[int, int, int, int]]:
        clean = series.ffill().bfill().dropna()
        if len(clean) < 16 or not has_pmdarima or auto_arima is None:
            return self._fallback_order(clean)

        s = self.seasonal_period if len(clean) >= self.seasonal_period * 2 else 4

        try:
            fitted = auto_arima(
                clean,
                seasonal=True,
                m=s,
                start_p=0,
                start_q=0,
                max_p=2,
                max_q=2,
                start_P=0,
                start_Q=0,
                max_P=1,
                max_Q=1,
                max_d=2,
                max_D=1,
                stepwise=True,
                suppress_warnings=True,
                error_action="ignore",
                trace=False,
                information_criterion="aic",
            )
            return tuple(fitted.order), tuple(fitted.seasonal_order)
        except Exception:
            return self._fallback_order(clean)

    @staticmethod
    def _fit_sarima(series: pd.Series, order: Tuple[int, int, int], sorder: Tuple[int, int, int, int]) -> Any:
        model = SARIMAX(
            series.ffill().bfill().dropna(),
            order=order,
            seasonal_order=sorder,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        try:
            return model.fit(disp=False, method="lbfgs", maxiter=200)
        except Exception:
            return model.fit(disp=False, method="nm", maxiter=500)

    @staticmethod
    def _linear_fit(values: np.ndarray) -> Tuple[float, float]:
        x = np.arange(len(values), dtype=float)
        slope, intercept = np.polyfit(x, values.astype(float), 1)
        return float(slope), float(intercept)

    @classmethod
    def _calibrate(cls, market4: np.ndarray, prospect4: np.ndarray, eps: float = 1e-6) -> Tuple[float, float]:
        m_slope, m_intercept = cls._linear_fit(market4)
        p_slope, p_intercept = cls._linear_fit(prospect4)
        sensitivity = p_slope / m_slope if abs(m_slope) > eps else 1.0
        offset = p_intercept - m_intercept
        return float(sensitivity), float(offset)

    @staticmethod
    def _next_weeks(last_week: str, n: int) -> List[str]:
        try:
            y, w = [int(x) for x in last_week.split("-", 1)]
        except Exception:
            return [f"step_{i+1}" for i in range(n)]

        out: List[str] = []
        for _ in range(n):
            w += 1
            if w > 52:
                w = 1
                y += 1
            out.append(f"{y}-{str(w).zfill(2)}")
        return out

    def forecast_live(
        self,
        prospect_weekly: Any,
        mcc: int,
        card_type: Optional[str] = None,
        df: Optional[pd.DataFrame] = None,
        monthly_txn_count: Optional[int] = None,
        avg_amount: Optional[float] = None,
        as_of_date: Optional[pd.Timestamp] = None,
        n_forecast_weeks: int = 12,
    ) -> SarimaLiveResult:
        prospect_df = self._coerce_prospect_weekly(prospect_weekly)
        prospect_last4 = prospect_df.tail(4)

        selected = self._select_live_neighbours(
            mcc=mcc,
            card_type=card_type,
            df=df,
            monthly_txn_count=monthly_txn_count,
            avg_amount=avg_amount,
            as_of_date=as_of_date,
        )

        dist_map = {mid: d for mid, d in zip(selected.neighbour_ids, selected.distances)}
        weekly_data = self._load_merchant_weekly(selected.neighbour_ids)
        if not weekly_data:
            raise ValueError("No weekly data found for selected neighbours")

        composite = self._build_composite(weekly_data, dist_map).dropna(subset=["TPV", "TCR"])
        if len(composite) < 24:
            raise ValueError("Composite has too little history for stable SARIMA")

        tpv_order, tpv_sorder = self._select_order(composite["TPV"])
        tcr_order, tcr_sorder = self._select_order(composite["TCR"])

        fit_tpv = self._fit_sarima(composite["TPV"], tpv_order, tpv_sorder)
        fit_tcr = self._fit_sarima(composite["TCR"], tcr_order, tcr_sorder)

        raw_tpv = np.clip(np.asarray(fit_tpv.forecast(steps=n_forecast_weeks), dtype=float), 0, None)
        raw_tcr = np.clip(np.asarray(fit_tcr.forecast(steps=n_forecast_weeks), dtype=float), 0, 100)

        market4_tpv = composite["TPV"].tail(4).to_numpy(dtype=float)
        market4_tcr = composite["TCR"].tail(4).to_numpy(dtype=float)
        prospect4_tpv = prospect_last4["TPV"].to_numpy(dtype=float)
        prospect4_tcr = prospect_last4["TCR"].to_numpy(dtype=float)

        sens_tpv, off_tpv = self._calibrate(market4_tpv, prospect4_tpv)
        sens_tcr, off_tcr = self._calibrate(market4_tcr, prospect4_tcr)

        fc_tpv = np.clip(sens_tpv * raw_tpv + off_tpv, 0, None)
        fc_tcr = np.clip(sens_tcr * raw_tcr + off_tcr, 0, 100)
        fc_tpc = fc_tcr / 100.0 * fc_tpv

        weeks = self._next_weeks(str(prospect_last4.index[-1]), n_forecast_weeks)

        return SarimaLiveResult(
            week_labels=weeks,
            tpv_forecast=fc_tpv.tolist(),
            tcr_forecast=fc_tcr.tolist(),
            tpc_forecast=fc_tpc.tolist(),
            neighbour_ids=selected.neighbour_ids,
            neighbour_distances=selected.distances,
            tpv_order=tpv_order,
            tpv_seasonal_order=tpv_sorder,
            tcr_order=tcr_order,
            tcr_seasonal_order=tcr_sorder,
        )


def _load_prospect_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Prospect CSV not found: {path}")
    return pd.read_csv(path)


def _load_knn_txn_csv(path: Optional[Path]) -> Optional[pd.DataFrame]:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"KNN txn CSV not found: {path}")
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live SARIMA forecast using live KNN neighbours")
    parser.add_argument("--prospect-csv", required=True, help="CSV with week,TPV,TCR")
    parser.add_argument("--mcc", type=int, required=True, help="MCC value")
    parser.add_argument("--card-type", default="both", help="Card type for KNN pool: both/credit/debit/prepaid")
    parser.add_argument("--knn-txn-csv", default=None, help="Optional KNN feature input CSV with transaction_date,amount,cost_type_ID")
    parser.add_argument("--monthly-txn-count", type=int, default=None, help="Required if --knn-txn-csv is omitted")
    parser.add_argument("--avg-amount", type=float, default=None, help="Required if --knn-txn-csv is omitted")
    parser.add_argument("--as-of-date", default=None, help="Optional YYYY-MM-DD")
    parser.add_argument("--knn-k", type=int, default=5, help="Number of neighbours")
    parser.add_argument("--n-weeks", type=int, default=12, help="Forecast horizon")
    parser.add_argument("--output-csv", default=None, help="Optional output forecast CSV path")
    args = parser.parse_args()

    prospect_df = _load_prospect_csv(Path(args.prospect_csv))
    knn_df = _load_knn_txn_csv(Path(args.knn_txn_csv) if args.knn_txn_csv else None)
    as_of_date = pd.to_datetime(args.as_of_date) if args.as_of_date else None

    service = SarimaLiveService(knn_k=args.knn_k)
    result = service.forecast_live(
        prospect_weekly=prospect_df,
        mcc=args.mcc,
        card_type=args.card_type,
        df=knn_df,
        monthly_txn_count=args.monthly_txn_count,
        avg_amount=args.avg_amount,
        as_of_date=as_of_date,
        n_forecast_weeks=args.n_weeks,
    )

    out = pd.DataFrame(
        {
            "week": result.week_labels,
            "TPV": result.tpv_forecast,
            "TCR_pct": result.tcr_forecast,
            "TPC": result.tpc_forecast,
        }
    )

    summary = {
        "neighbour_ids": result.neighbour_ids,
        "neighbour_distances": result.neighbour_distances,
        "tpv_order": result.tpv_order,
        "tpv_seasonal_order": result.tpv_seasonal_order,
        "tcr_order": result.tcr_order,
        "tcr_seasonal_order": result.tcr_seasonal_order,
    }

    print(json.dumps(summary, indent=2))
    print("\nForecast:")
    print(out.to_string(index=False))

    if args.output_csv:
        out_path = Path(args.output_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(out_path, index=False)
        print(f"Saved forecast: {out_path}")


if __name__ == "__main__":
    main()
