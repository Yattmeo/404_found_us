from __future__ import annotations

import argparse
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class ProspectForecastResult:
    week_labels: List[str]
    tpv_forecast: List[float]
    tcr_forecast: List[float]
    tpc_forecast: List[float]
    sensitivity_tpv: float
    offset_tpv: float
    sensitivity_tcr: float
    offset_tcr: float


class SARIMADeploymentService:
    """Live inference service using pre-trained SARIMA artifact pkl files."""

    def __init__(
        self,
        artifact_dir: Path,
        artifact_prefix: str = "sarima_composite",
    ) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.artifact_prefix = artifact_prefix

        self.tpv_model_path = self.artifact_dir / f"{artifact_prefix}_tpv_model.pkl"
        self.tcr_model_path = self.artifact_dir / f"{artifact_prefix}_tcr_model.pkl"
        self.metadata_path = self.artifact_dir / f"{artifact_prefix}_metadata.pkl"

        self._tpv_model: Any = None
        self._tcr_model: Any = None
        self._metadata: Optional[Dict[str, Any]] = None

        self._validate_paths()

    def _validate_paths(self) -> None:
        missing = [
            p for p in [self.tpv_model_path, self.tcr_model_path, self.metadata_path] if not p.exists()
        ]
        if missing:
            missing_text = ", ".join(str(p) for p in missing)
            raise FileNotFoundError(f"Missing artifact file(s): {missing_text}")

    def _load_artifacts(self, force_reload: bool = False) -> None:
        if self._tpv_model is not None and self._tcr_model is not None and self._metadata is not None and not force_reload:
            return

        with self.tpv_model_path.open("rb") as f:
            self._tpv_model = pickle.load(f)

        with self.tcr_model_path.open("rb") as f:
            self._tcr_model = pickle.load(f)

        with self.metadata_path.open("rb") as f:
            loaded_meta = pickle.load(f)

        if not isinstance(loaded_meta, dict):
            raise ValueError("Metadata pkl is not a dictionary")
        self._metadata = loaded_meta

    @staticmethod
    def _coerce_prospect_weekly(prospect_weekly: Any) -> pd.DataFrame:
        """Accept DataFrame/list[dict]/dict and return sorted DataFrame with TPV,TCR columns."""
        if isinstance(prospect_weekly, pd.DataFrame):
            df = prospect_weekly.copy()
        elif isinstance(prospect_weekly, list):
            df = pd.DataFrame(prospect_weekly)
        elif isinstance(prospect_weekly, dict):
            df = pd.DataFrame([prospect_weekly])
        else:
            raise TypeError("prospect_weekly must be DataFrame, list[dict], or dict")

        # Allow either index weeks or explicit week column.
        if "week" in df.columns:
            df = df.set_index("week")

        required_cols = {"TPV", "TCR"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required prospect columns: {sorted(missing)}")

        df["TPV"] = pd.to_numeric(df["TPV"], errors="coerce")
        df["TCR"] = pd.to_numeric(df["TCR"], errors="coerce")
        df = df[["TPV", "TCR"]].dropna().copy()

        if len(df) < 4:
            raise ValueError("Need at least 4 prospect rows with valid TPV and TCR")

        # Keep input order if index is not sortable as strings; otherwise sort lexicographically.
        try:
            df = df.sort_index()
        except Exception:
            pass

        return df

    @staticmethod
    def _linear_fit(values: np.ndarray) -> Tuple[float, float]:
        x = np.arange(len(values), dtype=float)
        y = values.astype(float)
        if len(y) < 2:
            return 0.0, float(y[0]) if len(y) == 1 else 0.0
        slope, intercept = np.polyfit(x, y, 1)
        return float(slope), float(intercept)

    @classmethod
    def _calibrate(cls, market_last4: np.ndarray, prospect_4: np.ndarray, slope_eps: float = 1e-6) -> Tuple[float, float]:
        m_slope, m_intercept = cls._linear_fit(market_last4)
        p_slope, p_intercept = cls._linear_fit(prospect_4)
        sensitivity = p_slope / m_slope if abs(m_slope) > slope_eps else 1.0
        delta_offset = p_intercept - m_intercept
        return float(sensitivity), float(delta_offset)

    @staticmethod
    def _safe_float_array(values: Any, min_value: Optional[float] = None, max_value: Optional[float] = None) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        if min_value is not None or max_value is not None:
            low = min_value if min_value is not None else -np.inf
            high = max_value if max_value is not None else np.inf
            arr = np.clip(arr, low, high)
        return arr

    @staticmethod
    def _next_iso_weeks(last_week: str, n: int) -> List[str]:
        """Generate next n ISO week labels after YYYY-WW."""
        try:
            year_text, week_text = last_week.split("-", 1)
            year = int(year_text)
            week = int(week_text)
        except Exception:
            return [f"step_{i+1}" for i in range(n)]

        labels: List[str] = []
        for _ in range(n):
            week += 1
            if week > 52:
                week = 1
                year += 1
            labels.append(f"{year}-{str(week).zfill(2)}")
        return labels

    def _market_last4_from_metadata(self) -> Tuple[np.ndarray, np.ndarray]:
        if self._metadata is None:
            raise RuntimeError("Artifacts not loaded")

        composite_last = self._metadata.get("composite_last_weeks")
        if not isinstance(composite_last, dict) or len(composite_last) < 4:
            raise ValueError("Metadata missing composite_last_weeks with at least 4 rows")

        # Keys are week labels; sort for deterministic last-4 extraction.
        rows = []
        for wk in sorted(composite_last.keys()):
            row = composite_last[wk]
            if isinstance(row, dict):
                rows.append((wk, row.get("TPV"), row.get("TCR")))

        if len(rows) < 4:
            raise ValueError("Not enough composite rows in metadata for calibration")

        last4 = rows[-4:]
        market_tpv = np.asarray([float(r[1]) for r in last4], dtype=float)
        market_tcr = np.asarray([float(r[2]) for r in last4], dtype=float)
        return market_tpv, market_tcr

    def forecast_prospect(
        self,
        prospect_weekly: Any,
        n_forecast_weeks: int = 12,
        reload_artifacts: bool = True,
    ) -> ProspectForecastResult:
        """Run live forecast using current pkl artifacts and incoming prospect data."""
        self._load_artifacts(force_reload=reload_artifacts)

        if self._tpv_model is None or self._tcr_model is None:
            raise RuntimeError("Model artifacts were not loaded")

        prospect_df = self._coerce_prospect_weekly(prospect_weekly)
        prospect_last4 = prospect_df.tail(4)

        market_tpv_4, market_tcr_4 = self._market_last4_from_metadata()
        prospect_tpv_4 = prospect_last4["TPV"].to_numpy(dtype=float)
        prospect_tcr_4 = prospect_last4["TCR"].to_numpy(dtype=float)

        sensitivity_tpv, offset_tpv = self._calibrate(market_tpv_4, prospect_tpv_4)
        sensitivity_tcr, offset_tcr = self._calibrate(market_tcr_4, prospect_tcr_4)

        raw_tpv = self._safe_float_array(self._tpv_model.forecast(steps=n_forecast_weeks), min_value=0.0)
        raw_tcr = self._safe_float_array(self._tcr_model.forecast(steps=n_forecast_weeks), min_value=0.0, max_value=100.0)

        adj_tpv = self._safe_float_array(sensitivity_tpv * raw_tpv + offset_tpv, min_value=0.0)
        adj_tcr = self._safe_float_array(sensitivity_tcr * raw_tcr + offset_tcr, min_value=0.0, max_value=100.0)

        tpc = (adj_tcr / 100.0) * adj_tpv

        last_week = str(prospect_last4.index[-1])
        week_labels = self._next_iso_weeks(last_week=last_week, n=n_forecast_weeks)

        return ProspectForecastResult(
            week_labels=week_labels,
            tpv_forecast=adj_tpv.tolist(),
            tcr_forecast=adj_tcr.tolist(),
            tpc_forecast=tpc.tolist(),
            sensitivity_tpv=sensitivity_tpv,
            offset_tpv=offset_tpv,
            sensitivity_tcr=sensitivity_tcr,
            offset_tcr=offset_tcr,
        )


def _load_prospect_input(prospect_json: Optional[str], prospect_csv: Optional[Path]) -> pd.DataFrame:
    if prospect_json:
        parsed = json.loads(prospect_json)
        return SARIMADeploymentService._coerce_prospect_weekly(parsed)

    if prospect_csv is not None:
        if not prospect_csv.exists():
            raise FileNotFoundError(f"Prospect CSV not found: {prospect_csv}")
        df = pd.read_csv(prospect_csv)
        return SARIMADeploymentService._coerce_prospect_weekly(df)

    raise ValueError("Provide either --prospect-json or --prospect-csv")


def _result_to_frame(result: ProspectForecastResult) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week": result.week_labels,
            "TPV": result.tpv_forecast,
            "TCR_pct": result.tcr_forecast,
            "TPC": result.tpc_forecast,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Live deployment service for SARIMA prospect forecasting")
    parser.add_argument(
        "--artifact-dir",
        default="ml_pipeline/forecasting/artifacts",
        help="Directory containing sarima artifact pkls",
    )
    parser.add_argument(
        "--artifact-prefix",
        default="sarima_composite",
        help="Artifact file prefix",
    )
    parser.add_argument(
        "--prospect-json",
        default=None,
        help='Prospect input as JSON string. Example: [{"week":"2019-01","TPV":1000,"TCR":2.1}, ...]',
    )
    parser.add_argument(
        "--prospect-csv",
        default=None,
        help="Path to CSV with week,TPV,TCR columns",
    )
    parser.add_argument("--n-weeks", type=int, default=12, help="Forecast horizon")
    parser.add_argument("--output-csv", default=None, help="Optional path to save forecast CSV")
    args = parser.parse_args()

    prospect_csv = Path(args.prospect_csv) if args.prospect_csv else None
    prospect_df = _load_prospect_input(args.prospect_json, prospect_csv)

    service = SARIMADeploymentService(
        artifact_dir=Path(args.artifact_dir),
        artifact_prefix=args.artifact_prefix,
    )
    result = service.forecast_prospect(
        prospect_weekly=prospect_df,
        n_forecast_weeks=args.n_weeks,
        reload_artifacts=True,
    )

    out_df = _result_to_frame(result)
    print("Forecast result:")
    print(out_df.to_string(index=False))
    print(
        "\nCalibration: "
        f"TPV sens={result.sensitivity_tpv:.4f}, offset={result.offset_tpv:.4f}; "
        f"TCR sens={result.sensitivity_tcr:.4f}, offset={result.offset_tcr:.4f}"
    )

    if args.output_csv:
        out_path = Path(args.output_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(out_path, index=False)
        print(f"Saved forecast CSV: {out_path}")


if __name__ == "__main__":
    main()
