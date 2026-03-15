from __future__ import annotations

import argparse
import pickle
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
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
class SARIMAArtifactPaths:
	tpv_model_pkl: Path
	tcr_model_pkl: Path
	metadata_pkl: Path


class SARIMAArtifactService:
	"""Train and export composite-market SARIMA artifacts for TPV and TCR."""

	def __init__(
		self,
		db_path: Path,
		seasonal_period: int = 52,
		input_n_weeks: int = 4,
	) -> None:
		self.db_path = Path(db_path)
		self.seasonal_period = seasonal_period
		self.input_n_weeks = input_n_weeks

		if not self.db_path.exists():
			raise FileNotFoundError(f"SQLite DB not found: {self.db_path}")

	@staticmethod
	def _iso_year_week(series: pd.Series) -> pd.Series:
		iso = series.dt.isocalendar()
		return iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)

	def load_merchant_weekly(self, merchant_ids: List[int]) -> Dict[int, pd.DataFrame]:
		if not merchant_ids:
			return {}

		placeholders = ",".join(["?"] * len(merchant_ids))
		query = f"""
			SELECT merchant_id, date, amount, proc_cost
			FROM transactions
			WHERE merchant_id IN ({placeholders})
			  AND amount > 0
		"""

		with sqlite3.connect(self.db_path) as conn:
			df = pd.read_sql(query, conn, params=merchant_ids)

		if df.empty:
			return {}

		df["date"] = pd.to_datetime(df["date"], errors="coerce")
		df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
		df["proc_cost"] = pd.to_numeric(df["proc_cost"], errors="coerce").fillna(0.0)
		df = df.dropna(subset=["date", "amount"])
		df["year_week"] = self._iso_year_week(df["date"])

		series_by_merchant: Dict[int, pd.DataFrame] = {}
		for mid, grp in df.groupby("merchant_id"):
			weekly = (
				grp.groupby("year_week")
				.agg(TPV=("amount", "sum"), TPC=("proc_cost", "sum"), n_tx=("amount", "count"))
				.sort_index()
			)
			weekly["TCR"] = np.where(weekly["TPV"] > 0, weekly["TPC"] / weekly["TPV"] * 100, np.nan)
			series_by_merchant[int(str(mid))] = weekly

		return series_by_merchant

	@staticmethod
	def build_composite(weekly_data: Dict[int, pd.DataFrame], distances: Dict[int, float]) -> pd.DataFrame:
		if not weekly_data:
			return pd.DataFrame(columns=["TPV", "TCR"])

		missing_distance = [mid for mid in weekly_data.keys() if mid not in distances]
		if missing_distance:
			raise ValueError(f"Missing distances for merchants: {missing_distance}")

		raw_weights = {mid: 1.0 / (float(d) + 1e-6) for mid, d in distances.items()}
		w_sum = sum(raw_weights.values())
		weights = {mid: w / w_sum for mid, w in raw_weights.items()}

		all_weeks = sorted({wk for df_w in weekly_data.values() for wk in df_w.index})
		rows: List[Dict[str, float]] = []

		for week in all_weeks:
			tpv_num = 0.0
			tcr_num = 0.0
			tpv_w = 0.0
			tcr_w = 0.0

			for mid, df_w in weekly_data.items():
				if week not in df_w.index:
					continue
				row = df_w.loc[week]
				w = weights[mid]

				if pd.notna(row["TPV"]):
					tpv_num += w * float(row["TPV"])
					tpv_w += w
				if pd.notna(row["TCR"]):
					tcr_num += w * float(row["TCR"])
					tcr_w += w

			rows.append(
				{
					"year_week": week,
					"TPV": (tpv_num / tpv_w) if tpv_w > 0 else np.nan,
					"TCR": (tcr_num / tcr_w) if tcr_w > 0 else np.nan,
				}
			)

		return pd.DataFrame(rows).set_index("year_week").sort_index()

	def _fallback_order(self, series: pd.Series) -> Tuple[Tuple[int, int, int], Tuple[int, int, int, int]]:
		n = len(series.dropna())
		s = self.seasonal_period if n >= self.seasonal_period * 2 else 4
		return (1, 1, 1), (1, 1, 1, s)

	def select_order(self, series: pd.Series) -> Tuple[Tuple[int, int, int], Tuple[int, int, int, int]]:
		clean = series.ffill().bfill().dropna()
		if len(clean) < 16:
			return self._fallback_order(clean)

		s = self.seasonal_period if len(clean) >= self.seasonal_period * 2 else 4
		if not has_pmdarima or auto_arima is None:
			return self._fallback_order(clean)

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
			return fitted.order, fitted.seasonal_order
		except Exception:
			return self._fallback_order(clean)

	@staticmethod
	def fit_sarima(series: pd.Series, order: Tuple[int, int, int], seasonal_order: Tuple[int, int, int, int]):
		clean = series.ffill().bfill().dropna()
		model = SARIMAX(
			clean,
			order=order,
			seasonal_order=seasonal_order,
			enforce_stationarity=False,
			enforce_invertibility=False,
		)
		try:
			return model.fit(disp=False, method="lbfgs", maxiter=200)
		except Exception:
			return model.fit(disp=False, method="nm", maxiter=500)

	def train_artifacts(
		self,
		neighbour_ids: List[int],
		neighbour_distances: Dict[int, float],
		output_dir: Path,
		artifact_prefix: str = "sarima_composite",
		extra_metadata: Optional[Dict[str, Any]] = None,
	) -> SARIMAArtifactPaths:
		weekly_data = self.load_merchant_weekly(neighbour_ids)
		if len(weekly_data) == 0:
			raise ValueError("No weekly data loaded for provided neighbour_ids")

		composite = self.build_composite(weekly_data, neighbour_distances)
		if composite.empty:
			raise ValueError("Composite series is empty after construction")

		tpv_order, tpv_sorder = self.select_order(composite["TPV"])
		tcr_order, tcr_sorder = self.select_order(composite["TCR"])

		tpv_model = self.fit_sarima(composite["TPV"], tpv_order, tpv_sorder)
		tcr_model = self.fit_sarima(composite["TCR"], tcr_order, tcr_sorder)

		output_dir = Path(output_dir)
		output_dir.mkdir(parents=True, exist_ok=True)

		paths = SARIMAArtifactPaths(
			tpv_model_pkl=output_dir / f"{artifact_prefix}_tpv_model.pkl",
			tcr_model_pkl=output_dir / f"{artifact_prefix}_tcr_model.pkl",
			metadata_pkl=output_dir / f"{artifact_prefix}_metadata.pkl",
		)

		with paths.tpv_model_pkl.open("wb") as f:
			pickle.dump(tpv_model, f)

		with paths.tcr_model_pkl.open("wb") as f:
			pickle.dump(tcr_model, f)

		metadata: Dict[str, Any] = {
			"db_path": str(self.db_path),
			"neighbour_ids": neighbour_ids,
			"neighbour_distances": neighbour_distances,
			"seasonal_period": self.seasonal_period,
			"input_n_weeks": self.input_n_weeks,
			"tpv_order": tpv_order,
			"tpv_seasonal_order": tpv_sorder,
			"tcr_order": tcr_order,
			"tcr_seasonal_order": tcr_sorder,
			"composite_last_weeks": composite.tail(12).to_dict(orient="index"),
			"tpv_aic": float(tpv_model.aic),
			"tcr_aic": float(tcr_model.aic),
		}
		if extra_metadata:
			metadata.update(extra_metadata)

		with paths.metadata_pkl.open("wb") as f:
			pickle.dump(metadata, f)

		return paths


def _parse_distances(distances_text: str) -> Dict[int, float]:
	"""Parse distances from 'id:dist,id:dist' format."""
	distances: Dict[int, float] = {}
	if not distances_text.strip():
		return distances

	for chunk in distances_text.split(","):
		merchant_text, dist_text = chunk.split(":", 1)
		distances[int(merchant_text.strip())] = float(dist_text.strip())
	return distances


def main() -> None:
	parser = argparse.ArgumentParser(description="Train SARIMA composite artifacts and export pkl files")
	parser.add_argument("--db-path", required=True, help="Path to SQLite DB containing transactions table")
	parser.add_argument("--neighbour-ids", required=True, help="Comma-separated merchant ids, e.g. 1,2,3,4,5")
	parser.add_argument(
		"--neighbour-distances",
		required=True,
		help="Comma-separated id:distance pairs, e.g. 1:0.3,2:0.7",
	)
	parser.add_argument("--output-dir", default="ml_pipeline/forecasting/artifacts", help="Output artifact directory")
	parser.add_argument("--artifact-prefix", default="sarima_composite", help="Output file prefix")
	parser.add_argument("--seasonal-period", type=int, default=52, help="Seasonal period (default 52 for weekly)")
	args = parser.parse_args()

	neighbour_ids = [int(x.strip()) for x in args.neighbour_ids.split(",") if x.strip()]
	neighbour_distances = _parse_distances(args.neighbour_distances)

	service = SARIMAArtifactService(db_path=Path(args.db_path), seasonal_period=args.seasonal_period)
	paths = service.train_artifacts(
		neighbour_ids=neighbour_ids,
		neighbour_distances=neighbour_distances,
		output_dir=Path(args.output_dir),
		artifact_prefix=args.artifact_prefix,
	)

	print("Created artifacts:")
	print(f"- {paths.tpv_model_pkl}")
	print(f"- {paths.tcr_model_pkl}")
	print(f"- {paths.metadata_pkl}")


if __name__ == "__main__":
	main()
