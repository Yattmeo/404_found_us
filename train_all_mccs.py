"""
train_all_mccs.py — Aggregate raw transaction CSVs into v2 monthly format
and train M9 cost-forecast artifacts for MCCs 4121, 5499, 5812.

Usage:
    python train_all_mccs.py

Reads from  data/processed_transactions_{mcc}.csv
Writes v2   data/{mcc}_monthly_v2.csv
Writes artifacts to  ml_service/artifacts/m9/{mcc}/{ctx_len}/
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

# ══════════════════════════════════════════════════════════════════════════════
# Pipeline constants (must match ml_service/modules/cost_forecast/service.py)
# ══════════════════════════════════════════════════════════════════════════════
SUPPORTED_CONTEXT_LENS: list[int] = [1, 3, 6]
HORIZON_LEN: int = 3
TARGET_COV: float = 0.90
MIN_POOL: int = 10
KNN_K: int = 10
_VOL_EPS: float = 1e-6

VOL_MIN_GAIN_ABS: float = 0.05
VOL_MIN_GAIN_REL: float = 0.01
VOL_BUCKET_SCHEMES: dict[str, list[float]] = {
    "low-mid-high_50_85":          [0.00, 0.50, 0.85, 1.00],
    "low-mid-high_40_80":          [0.00, 0.40, 0.80, 1.00],
    "low-mid-high_60_90":          [0.00, 0.60, 0.90, 1.00],
    "low-mid-high-vhigh_50_75_90": [0.00, 0.50, 0.75, 0.90, 1.00],
    "low-mid-high-vhigh_40_70_88": [0.00, 0.40, 0.70, 0.88, 1.00],
    "low-mid-high-vhigh_60_85_95": [0.00, 0.60, 0.85, 0.95, 1.00],
}
GBR_N_ESTIMATORS: int = 120
GBR_LEARNING_RATE: float = 0.05
GBR_MAX_DEPTH: int = 2
GBR_MIN_SAMPLES_LEAF: int = max(20, MIN_POOL)
GBR_SUBSAMPLE: float = 0.8
GBR_RANDOM_STATE: int = 4121
DEFAULT_WINDOW_YEARS: int = 10  # Use all available data (2010–2019)
COST_TYPE_COLS: list[str] = [f"cost_type_{i}_pct" for i in range(1, 62)]
V2_REQUIRED_COLS: list[str] = [
    "std_proc_cost_pct", "iqr_proc_cost_pct", "std_txn_amount",
    "median_txn_amount", "n_unique_cost_types", "median_proc_cost_pct",
]

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_BASE_PATH = BASE_DIR / "ml_service" / "artifacts" / "m9"

MCCS_TO_TRAIN = [4121, 5499, 5812]


# ══════════════════════════════════════════════════════════════════════════════
# Step 1: Aggregate raw transactions → v2 monthly CSV
# ══════════════════════════════════════════════════════════════════════════════

def aggregate_to_monthly_v2(mcc: int) -> Path:
    """Reads processed_transactions_{mcc}.csv and produces {mcc}_monthly_v2.csv."""
    src = DATA_DIR / f"processed_transactions_{mcc}.csv"
    dst = DATA_DIR / f"{mcc}_monthly_v2.csv"

    if dst.exists():
        print(f"  v2 CSV already exists: {dst.name} — reusing")
        return dst

    print(f"  Loading {src.name} ...")
    df = pd.read_csv(src)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["proc_cost"] = pd.to_numeric(df["proc_cost"], errors="coerce").fillna(0)
    df["cost_type_ID"] = pd.to_numeric(df["cost_type_ID"], errors="coerce").fillna(1).astype(int)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df = df.dropna(subset=["transaction_date"])
    df["year"] = df["transaction_date"].dt.year.astype(int)
    df["month"] = df["transaction_date"].dt.month.astype(int)

    # Per-transaction cost percentage
    df["txn_cost_pct"] = np.where(
        df["amount"] > 0,
        df["proc_cost"] / df["amount"],
        0.0,
    )

    print(f"  Aggregating {len(df):,} rows → monthly v2 ...")
    rows = []
    for (mid, yr, mo), grp in df.groupby(["merchant_id", "year", "month"]):
        cost_pcts = grp["txn_cost_pct"].values
        amounts = grp["amount"].values

        # Cost type distribution
        ct_counts = grp["cost_type_ID"].value_counts()
        n_txn = len(grp)
        ct_pcts = {}
        for ct_id in range(1, 62):
            ct_pcts[f"cost_type_{ct_id}_pct"] = float(ct_counts.get(ct_id, 0)) / n_txn

        row = {
            "merchant_id": int(mid),
            "year": int(yr),
            "month": int(mo),
            "avg_proc_cost_pct": float(np.mean(cost_pcts)),
            "std_proc_cost_pct": float(np.std(cost_pcts)),
            "median_proc_cost_pct": float(np.median(cost_pcts)),
            "iqr_proc_cost_pct": float(np.percentile(cost_pcts, 75) - np.percentile(cost_pcts, 25)),
            "total_processing_value": float(np.sum(amounts)),
            "transaction_count": n_txn,
            "avg_transaction_value": float(np.mean(amounts)),
            "std_txn_amount": float(np.std(amounts)),
            "median_txn_amount": float(np.median(amounts)),
            "n_unique_cost_types": int(grp["cost_type_ID"].nunique()),
        }
        row.update(ct_pcts)
        rows.append(row)

    out = pd.DataFrame(rows)
    out.to_csv(dst, index=False)
    print(f"  Written {len(out):,} monthly rows for {out['merchant_id'].nunique():,} merchants → {dst.name}")
    return dst


# ══════════════════════════════════════════════════════════════════════════════
# Step 2: Training (copied from archive train.py, self-contained)
# ══════════════════════════════════════════════════════════════════════════════

def _build_scenarios(df: pd.DataFrame, context_len: int) -> List[dict]:
    scenarios: List[dict] = []
    for mid, mdf in df.groupby("merchant_id"):
        mdf = mdf.sort_values(["year", "month"]).reset_index(drop=True)
        n = len(mdf)
        for i in range(n - context_len - HORIZON_LEN + 1):
            ctx = mdf.iloc[i : i + context_len].copy().reset_index(drop=True)
            hor = mdf.iloc[i + context_len : i + context_len + HORIZON_LEN].copy().reset_index(drop=True)
            ctx_span = (
                (ctx.iloc[-1]["year"] - ctx.iloc[0]["year"]) * 12
                + ctx.iloc[-1]["month"] - ctx.iloc[0]["month"]
            )
            if ctx_span != context_len - 1:
                continue
            ctx_end_yr, ctx_end_mo = int(ctx.iloc[-1]["year"]), int(ctx.iloc[-1]["month"])
            expected_hor_yr = ctx_end_yr + (1 if ctx_end_mo == 12 else 0)
            expected_hor_mo = 1 if ctx_end_mo == 12 else ctx_end_mo + 1
            if int(hor.iloc[0]["year"]) != expected_hor_yr or int(hor.iloc[0]["month"]) != expected_hor_mo:
                continue
            hor_span = (
                (hor.iloc[-1]["year"] - hor.iloc[0]["year"]) * 12
                + hor.iloc[-1]["month"] - hor.iloc[0]["month"]
            )
            if hor_span != HORIZON_LEN - 1:
                continue
            scenarios.append({
                "merchant_id": mid,
                "context_data": ctx,
                "horizon_data": hor,
                "context_range": (
                    (int(ctx.iloc[0]["year"]), int(ctx.iloc[0]["month"])),
                    (ctx_end_yr, ctx_end_mo),
                ),
                "horizon_range": (
                    (expected_hor_yr, expected_hor_mo),
                    (int(hor.iloc[-1]["year"]), int(hor.iloc[-1]["month"])),
                ),
            })
    return scenarios


def _merchant_split(scenarios, seed=42):
    rng = np.random.default_rng(seed)
    all_mids = sorted({s["merchant_id"] for s in scenarios})
    perm = rng.permutation(len(all_mids))
    n = len(all_mids)
    n_train = int(0.60 * n)
    n_val = int(0.20 * n)
    train_mids = {all_mids[i] for i in perm[:n_train]}
    validate_mids = {all_mids[i] for i in perm[n_train : n_train + n_val]}
    test_mids = {all_mids[i] for i in perm[n_train + n_val :]}
    return (
        [s for s in scenarios if s["merchant_id"] in train_mids],
        [s for s in scenarios if s["merchant_id"] in validate_mids],
        [s for s in scenarios if s["merchant_id"] in test_mids],
    )


def _build_pool_caches(df, scenarios, cost_type_cols):
    unique_keys = {
        (s["merchant_id"], int(s["context_data"].iloc[-1]["year"]), int(s["context_data"].iloc[-1]["month"]))
        for s in scenarios
    }
    print(f"  Building flat pool mean cache ({len(unique_keys):,} keys)...")
    flat_cache: Dict[tuple, float] = {}
    for mid, yr, mo in unique_keys:
        snap = df[
            (df["merchant_id"] != mid)
            & ((df["year"] < yr) | ((df["year"] == yr) & (df["month"] <= mo)))
        ]
        flat_cache[(mid, yr, mo)] = float(snap["avg_proc_cost_pct"].mean()) if len(snap) > 0 else 0.0

    knn_cache: Dict[tuple, float] = dict(flat_cache)
    if not cost_type_cols:
        return flat_cache, knn_cache

    keys_by_date: Dict[tuple, list] = defaultdict(list)
    for mid, yr, mo in unique_keys:
        keys_by_date[(yr, mo)].append(mid)

    n_dates = len(keys_by_date)
    print(f"  Building kNN pool mean cache ({len(unique_keys):,} keys, {n_dates} dates, k={KNN_K})...")

    for idx, ((yr, mo), query_mids) in enumerate(sorted(keys_by_date.items())):
        snap = df[(df["year"] < yr) | ((df["year"] == yr) & (df["month"] <= mo))]
        fp_all = snap.groupby("merchant_id")[cost_type_cols].mean()
        cost_all = snap.groupby("merchant_id")["avg_proc_cost_pct"].mean()
        if len(fp_all) < KNN_K + 1:
            continue
        nn_date = NearestNeighbors(n_neighbors=min(KNN_K + 1, len(fp_all)), metric="cosine")
        nn_date.fit(fp_all.values)
        fp_index = fp_all.index.tolist()
        for mid in query_mids:
            ctx_row = df[(df["merchant_id"] == mid) & (df["year"] == yr) & (df["month"] == mo)]
            if len(ctx_row) == 0 or mid not in fp_all.index:
                continue
            _, raw_idx = nn_date.kneighbors(ctx_row[cost_type_cols].values)
            top_ids = [fp_index[i] for i in raw_idx[0] if fp_index[i] != mid][:KNN_K]
            if len(top_ids) == KNN_K:
                knn_cache[(mid, yr, mo)] = float(cost_all.loc[top_ids].mean())
        if (idx + 1) % 20 == 0:
            print(f"    {idx + 1}/{n_dates} dates processed...")

    print("  Pool caches complete.")
    return flat_cache, knn_cache


def _build_feature_matrix(scenarios, knn_cache):
    rows = []
    for s in scenarios:
        ctx = s["context_data"]
        vals = ctx["avg_proc_cost_pct"].values.astype(float)
        c_mean = float(np.mean(vals))
        c_std = float(np.std(vals))
        mom = float(vals[-1] - c_mean)
        key = (s["merchant_id"], int(ctx.iloc[-1]["year"]), int(ctx.iloc[-1]["month"]))
        p_mean = knn_cache[key]
        intra_std = float(ctx["std_proc_cost_pct"].fillna(0).mean())
        log_txn = float(np.log1p(ctx["transaction_count"].mean()))
        avg_med = float(np.mean(np.abs(vals - ctx["median_proc_cost_pct"].values)))
        rows.append([c_mean, c_std, mom, p_mean, intra_std, log_txn, avg_med])
    return np.array(rows, dtype=float)


def _build_risk_features(scenarios, flat_cache, knn_cache):
    rows = []
    for s in scenarios:
        ctx = s["context_data"]
        vals = ctx["avg_proc_cost_pct"].values.astype(float)
        c_mean = float(np.mean(vals))
        _denom = c_mean + _VOL_EPS
        intra_cov = float(ctx["std_proc_cost_pct"].fillna(0).mean()) / _denom
        mean_median_gap = float(np.mean(np.abs(vals - ctx["median_proc_cost_pct"].values))) / _denom
        log_txn_count = float(np.log1p(ctx["transaction_count"].mean()))
        ct_cols = [c for c in ctx.columns if c.startswith("cost_type_") and c.endswith("_pct")]
        ct_vals = ctx[ct_cols].mean().values if ct_cols else np.array([1.0])
        cost_type_hhi = float(np.sum(ct_vals ** 2))
        log_avg_txn_val = float(np.log1p(ctx["avg_transaction_value"].mean()))
        avg_txn_val = float(ctx["avg_transaction_value"].mean())
        txn_amount_cov = float(ctx["std_txn_amount"].fillna(0).mean()) / (avg_txn_val + _VOL_EPS)
        yr, mo = s["context_range"][1]
        mid = s["merchant_id"]
        flat_pm = float(flat_cache.get((mid, yr, mo), c_mean))
        knn_pm = float(knn_cache.get((mid, yr, mo), c_mean))
        pool_gap = abs(c_mean - flat_pm) / (flat_pm + _VOL_EPS)
        knn_gap = abs(c_mean - knn_pm) / (knn_pm + _VOL_EPS)
        ctx_cov = float(np.std(vals)) / _denom
        rows.append([
            intra_cov, mean_median_gap, log_txn_count,
            cost_type_hhi, log_avg_txn_val, txn_amount_cov,
            pool_gap, knn_gap, ctx_cov,
        ])
    return np.array(rows, dtype=float)


def _adaptive_q(residuals, target=TARGET_COV):
    n = len(residuals)
    level = math.ceil((n + 1) * target) / n
    return float(np.quantile(residuals, level)) if level <= 1.0 else None


def _effective_half_width(lo, hi):
    return float(np.mean((hi - lo) / 2.0))


def _make_percentile_bins(ref_vals, apply_vals, pct_edges, min_count=MIN_POOL):
    pct_edges = np.array(pct_edges, dtype=float)
    edges = np.quantile(ref_vals, pct_edges)
    edges = np.maximum.accumulate(edges)
    edges = np.unique(edges)
    n_eff = len(edges) - 1
    if n_eff < 2:
        return None
    ref_bins = np.digitize(ref_vals, edges[1:-1], right=False)
    counts = np.array([(ref_bins == b).sum() for b in range(n_eff)])
    if counts.min() < min_count:
        return None
    apply_bins = np.digitize(apply_vals, edges[1:-1], right=False)
    return edges, ref_bins, apply_bins, n_eff, counts


def _continuous_width_map(cal_scores_ref, apply_scores, cal_res, pct_edges, q_fallback):
    built = _make_percentile_bins(cal_scores_ref, apply_scores, pct_edges, min_count=MIN_POOL)
    if built is None:
        return None
    edges, ref_bins, apply_bins, n_eff, counts = built
    q_vals = []
    for b in range(n_eff):
        res_b = cal_res[ref_bins == b].tolist()
        q_local = _adaptive_q(res_b) if len(res_b) >= MIN_POOL else None
        q_vals.append(q_local if q_local is not None else q_fallback)
    q_vals = np.maximum.accumulate(np.array(q_vals, dtype=float))
    knot_x = 0.5 * (edges[:-1] + edges[1:])
    knot_x = np.maximum.accumulate(knot_x + np.arange(len(knot_x)) * 1e-9)
    hw_apply = np.interp(apply_scores, knot_x, q_vals, left=q_vals[0], right=q_vals[-1])
    return {
        "knot_x": knot_x, "q_vals": q_vals, "hw_apply": hw_apply,
    }


def _generate_pool_ids(df, merchant_id, yr, mo):
    pool = df[
        (df["merchant_id"] != merchant_id)
        & ((df["year"] < yr) | ((df["year"] == yr) & (df["month"] <= mo)))
    ]
    return set(int(p) for p in pool["merchant_id"].unique())


def _atomic_write(path: Path, write_fn):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    try:
        os.close(fd)
        write_fn(Path(tmp))
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _train_context_len(mcc, ctx_len, df, flat_cache, knn_cache, all_scenarios, window_start, window_end):
    t0 = time.monotonic()
    print(f"\n{'─'*60}")
    print(f"  ctx_len={ctx_len}")
    print(f"{'─'*60}")

    train_s, val_s, test_s = _merchant_split(all_scenarios)
    print(f"  train={len(train_s):,}  val={len(val_s):,}  test={len(test_s):,}")

    ci_years = sorted({int(s["horizon_data"].iloc[0]["year"]) for s in (train_s + val_s + test_s)})
    if len(ci_years) < 2:
        print(f"  SKIP: fewer than 2 horizon years for ctx={ctx_len}")
        return
    cal_year = ci_years[-2]
    test_year = ci_years[-1]

    train_ci = [s for s in train_s if int(s["horizon_data"].iloc[0]["year"]) < cal_year]
    cal_ci = [s for s in val_s if int(s["horizon_data"].iloc[0]["year"]) == cal_year]
    test_ci = [s for s in test_s if int(s["horizon_data"].iloc[0]["year"]) == test_year]

    if not train_ci or not cal_ci:
        print(f"  SKIP: empty train_ci or cal_ci for ctx={ctx_len}")
        return

    print(f"  cal_year={cal_year}  test_year={test_year}")
    print(f"  train_ci={len(train_ci):,}  cal_ci={len(cal_ci):,}  test_ci={len(test_ci):,}")

    y_tr = np.array([s["horizon_data"]["avg_proc_cost_pct"].values for s in train_ci])
    y_cal = np.array([s["horizon_data"]["avg_proc_cost_pct"].values for s in cal_ci])
    X_tr_raw = _build_feature_matrix(train_ci, knn_cache)
    X_cal_raw = _build_feature_matrix(cal_ci, knn_cache)
    sw = 1.0 / (X_tr_raw[:, 3] + 1.0)

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X_tr_raw)
    X_cal = scaler.transform(X_cal_raw)

    models: List[HuberRegressor] = []
    cal_preds = np.zeros_like(y_cal, dtype=float)
    for h in range(HORIZON_LEN):
        m = HuberRegressor(epsilon=1.35, max_iter=500)
        m.fit(X_tr, y_tr[:, h], sample_weight=sw)
        cal_preds[:, h] = m.predict(X_cal)
        models.append(m)
        print(f"  h={h+1}  coefs={m.coef_.round(4)}")

    cal_max_res = np.abs(y_cal - cal_preds).max(axis=1)
    global_q90 = float(np.quantile(cal_max_res, TARGET_COV))
    print(f"  global_q90 = +/-{global_q90:.4f}  (n_cal={len(cal_max_res)})")

    cal_merchant_ids = np.array([s["merchant_id"] for s in cal_ci])
    cal_residuals: Dict[int, List[float]] = defaultdict(list)
    for i, res in enumerate(cal_max_res):
        cal_residuals[int(cal_merchant_ids[i])].append(float(res))
    cal_residuals = dict(cal_residuals)

    # GBR risk models
    print("  Training GBR risk models (cross-fitted)...")
    train_feat = _build_risk_features(train_ci, flat_cache, knn_cache)

    train_years = np.array([int(s["horizon_data"].iloc[0]["year"]) for s in train_ci])
    fold_cuts = sorted(set(train_years.tolist()))[1:]
    train_cf_res = np.full((len(train_ci), HORIZON_LEN), np.nan)

    for cut in fold_cuts:
        cf_tr_mask = train_years < cut
        cf_te_mask = train_years == cut
        if cf_tr_mask.sum() == 0 or cf_te_mask.sum() == 0:
            continue
        cf_tr = [train_ci[j] for j in np.where(cf_tr_mask)[0]]
        cf_te = [train_ci[j] for j in np.where(cf_te_mask)[0]]
        y_cf_tr = np.array([s["horizon_data"]["avg_proc_cost_pct"].values for s in cf_tr])
        y_cf_te = np.array([s["horizon_data"]["avg_proc_cost_pct"].values for s in cf_te])
        X_cf_tr = _build_feature_matrix(cf_tr, knn_cache)
        X_cf_te = _build_feature_matrix(cf_te, knn_cache)
        sw_cf = 1.0 / (X_cf_tr[:, 3] + 1.0)
        sc_cf = StandardScaler()
        Xcf_tr = sc_cf.fit_transform(X_cf_tr)
        Xcf_te = sc_cf.transform(X_cf_te)
        preds_cf = np.zeros_like(y_cf_te, dtype=float)
        for h in range(HORIZON_LEN):
            mcf = HuberRegressor(epsilon=1.35, max_iter=500)
            mcf.fit(Xcf_tr, y_cf_tr[:, h], sample_weight=sw_cf)
            preds_cf[:, h] = mcf.predict(Xcf_te)
        train_cf_res[cf_te_mask] = np.abs(y_cf_te - preds_cf)

    cf_valid = np.isfinite(train_cf_res).all(axis=1)

    strat_enabled = False
    strat_scheme = None
    strat_knot_x = None
    strat_q_vals = None

    risk_models = []
    for h in range(HORIZON_LEN):
        gbr = GradientBoostingRegressor(
            loss="squared_error", n_estimators=GBR_N_ESTIMATORS,
            learning_rate=GBR_LEARNING_RATE, max_depth=GBR_MAX_DEPTH,
            min_samples_leaf=GBR_MIN_SAMPLES_LEAF, subsample=GBR_SUBSAMPLE,
            random_state=GBR_RANDOM_STATE,
        )
        if cf_valid.sum() >= 50:
            gbr.fit(train_feat[cf_valid], np.log1p(train_cf_res[cf_valid, h]))
        else:
            # Minimal fallback — fit on whatever is available
            gbr.fit(train_feat[:min(len(train_feat), 100)],
                     np.zeros(min(len(train_feat), 100)))
        risk_models.append(gbr)

    if cf_valid.sum() >= 50:
        # Scheme selection
        print("  Selecting stratification scheme (leak-free)...")
        cal_feat = _build_risk_features(cal_ci, flat_cache, knn_cache)
        cal_risk = np.max(
            np.column_stack([m.predict(cal_feat) for m in risk_models]), axis=1
        )
        cal_mids_arr = np.array(sorted(set(cal_merchant_ids.tolist())))
        rng = np.random.default_rng(GBR_RANDOM_STATE)
        perm = rng.permutation(cal_mids_arr)
        cut = min(max(1, int(round(len(perm) * 0.70))), len(perm) - 1)
        sel_mids = set(perm[:cut].tolist())
        sel_mask = np.isin(cal_merchant_ids, list(sel_mids))
        eval_mask = ~sel_mask

        if eval_mask.sum() > 0:
            y_eval = y_cal[eval_mask]
            preds_eval = cal_preds[eval_mask]
            eval_ci_list = [cal_ci[j] for j in np.where(eval_mask)[0]]

            merchant_sel_res = defaultdict(list)
            for mid_val, res in zip(cal_merchant_ids[sel_mask], cal_max_res[sel_mask]):
                merchant_sel_res[int(mid_val)].append(float(res))
            global_q_sel = _adaptive_q(cal_max_res[sel_mask].tolist())
            if global_q_sel is None:
                global_q_sel = global_q90

            hw_eval_pool = np.zeros(eval_mask.sum(), dtype=float)
            for i, s in enumerate(eval_ci_list):
                yr, mo = s["context_range"][1]
                peer_ids = _generate_pool_ids(df, int(s["merchant_id"]), yr, mo)
                peer_res = [r for pid in peer_ids for r in merchant_sel_res.get(pid, [])]
                q = _adaptive_q(peer_res) if len(peer_res) >= MIN_POOL else None
                hw_eval_pool[i] = q if q is not None else global_q_sel

            lo_ep = np.clip(preds_eval - hw_eval_pool[:, None], 0, None)
            hi_ep = preds_eval + hw_eval_pool[:, None]
            baseline_eval_hw = _effective_half_width(lo_ep, hi_ep)
            _min_gain_ho = max(VOL_MIN_GAIN_ABS, VOL_MIN_GAIN_REL * baseline_eval_hw)

            sel_risk = cal_risk[sel_mask]
            eval_risk = cal_risk[eval_mask]

            scheme_results = []
            for _name, _pct in VOL_BUCKET_SCHEMES.items():
                mapped = _continuous_width_map(
                    sel_risk, eval_risk, cal_max_res[sel_mask], np.array(_pct), global_q_sel,
                )
                if mapped is None:
                    continue
                hw = mapped["hw_apply"]
                lo_ = np.clip(preds_eval - hw[:, None], 0, None)
                hi_ = preds_eval + hw[:, None]
                in_ = (y_eval >= lo_) & (y_eval <= hi_)
                avg_hw = _effective_half_width(lo_, hi_)
                joint_cov = float(np.mean(in_.all(axis=1)))
                scheme_results.append({
                    "name": _name, "pct_edges": np.array(_pct),
                    "active": mapped.get("active", 0), "avg_hw": avg_hw,
                    "joint_cov": joint_cov,
                    "gain": baseline_eval_hw - avg_hw,
                })

            feasible = [
                r for r in scheme_results
                if r["joint_cov"] >= TARGET_COV and r["gain"] >= _min_gain_ho
            ]
            if feasible:
                best = min(feasible, key=lambda r: (r["avg_hw"], r["active"]))
                mapped_full = _continuous_width_map(
                    cal_risk, cal_risk, cal_max_res, best["pct_edges"], global_q90,
                )
                if mapped_full is not None:
                    strat_enabled = True
                    strat_scheme = best["name"]
                    strat_knot_x = mapped_full["knot_x"]
                    strat_q_vals = mapped_full["q_vals"]
                    print(f"  Stratification PASSED: scheme={strat_scheme}")
                else:
                    print("  Stratification failed on full calibration set")
            else:
                print(f"  No feasible stratification scheme (tested {len(scheme_results)})")
    else:
        print(f"  WARNING: only {cf_valid.sum()} cross-fit samples — global fallback only")

    # Write artifacts
    artifact_dir = ARTIFACTS_BASE_PATH / str(mcc) / str(ctx_len)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    _atomic_write(artifact_dir / "models.pkl", lambda p: joblib.dump(models, p))
    _atomic_write(artifact_dir / "scaler.pkl", lambda p: joblib.dump(scaler, p))
    _atomic_write(artifact_dir / "cal_residuals.pkl", lambda p: joblib.dump(cal_residuals, p))
    _atomic_write(artifact_dir / "global_q90.pkl", lambda p: joblib.dump(global_q90, p))
    _atomic_write(artifact_dir / "risk_models.pkl", lambda p: joblib.dump(risk_models, p))

    if strat_enabled and strat_knot_x is not None:
        _atomic_write(artifact_dir / "strat_knot_x.pkl", lambda p: joblib.dump(strat_knot_x, p))
        _atomic_write(artifact_dir / "strat_q_vals.pkl", lambda p: joblib.dump(strat_q_vals, p))

    snapshot = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "mcc": mcc,
        "context_len": ctx_len,
        "horizon_len": HORIZON_LEN,
        "window_start": window_start,
        "window_end": window_end,
        "n_train_ci": len(train_ci),
        "n_cal_ci": len(cal_ci),
        "n_test_ci": len(test_ci) if test_ci else 0,
        "cal_year": cal_year,
        "global_q90": global_q90,
        "knn_k": KNN_K,
        "target_cov": TARGET_COV,
        "strat_enabled": strat_enabled,
        "strat_scheme": strat_scheme,
        "n_model_features": 7,
        "n_risk_features": 9,
    }
    _atomic_write(
        artifact_dir / "config_snapshot.json",
        lambda p: p.write_text(json.dumps(snapshot, indent=2)),
    )

    elapsed = time.monotonic() - t0
    print(f"  Artifacts saved to {artifact_dir}  [{elapsed:.1f}s]")


def train(mcc: int, data_path: Path, window_years: int) -> None:
    t_start = time.monotonic()
    print(f"\n{'='*60}")
    print(f"M9 v2 Training  MCC={mcc}  window={window_years}yr  data={data_path.name}")
    print(f"{'='*60}")

    print("\n[1/5] Loading data...")
    df = pd.read_csv(data_path)
    required_cols = {"merchant_id", "year", "month", "avg_proc_cost_pct"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    v2_missing = [c for c in V2_REQUIRED_COLS if c not in df.columns]
    if v2_missing:
        raise ValueError(f"Missing v2 columns: {v2_missing}")

    print(f"  Loaded {len(df):,} rows, {df['merchant_id'].nunique():,} merchants, years {df['year'].min()}-{df['year'].max()}")

    print(f"\n[2/5] Filtering to rolling {window_years}-year window...")
    today = date.today()
    cutoff_year = today.year - window_years
    df = df[
        (df["year"] > cutoff_year) | ((df["year"] == cutoff_year) & (df["month"] >= today.month))
    ]
    window_start = f"{int(df['year'].min())}-{int(df['month'].min()):02d}"
    window_end = f"{int(df['year'].max())}-{int(df['month'].max()):02d}"
    print(f"  Window: {window_start} -> {window_end}  ({len(df):,} rows, {df['merchant_id'].nunique():,} merchants)")

    print(f"\n[3/5] Building scenarios for context lengths {SUPPORTED_CONTEXT_LENS}...")
    scenarios_by_ctx: Dict[int, List[dict]] = {}
    all_scenarios_combined: List[dict] = []
    for ctx_len in SUPPORTED_CONTEXT_LENS:
        scens = _build_scenarios(df, ctx_len)
        scenarios_by_ctx[ctx_len] = scens
        all_scenarios_combined.extend(scens)
        n_m = len({s["merchant_id"] for s in scens})
        print(f"  ctx={ctx_len}: {len(scens):,} scenarios from {n_m:,} merchants")

    print(f"\n[4/5] Building pool caches...")
    present_cost_cols = [c for c in COST_TYPE_COLS if c in df.columns]
    flat_cache, knn_cache = _build_pool_caches(df, all_scenarios_combined, present_cost_cols)

    print(f"\n[5/5] Training per context length...")
    for ctx_len in SUPPORTED_CONTEXT_LENS:
        scens = scenarios_by_ctx[ctx_len]
        if len(scens) < 50:
            print(f"\n  SKIP ctx_len={ctx_len}: only {len(scens)} scenarios")
            continue
        _train_context_len(
            mcc=mcc, ctx_len=ctx_len, df=df,
            flat_cache=flat_cache, knn_cache=knn_cache,
            all_scenarios=scens,
            window_start=window_start, window_end=window_end,
        )

    elapsed = time.monotonic() - t_start
    print(f"\n{'='*60}")
    print(f"All training complete for MCC {mcc} in {elapsed:.1f}s")
    print(f"{'='*60}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    total_t0 = time.monotonic()
    for mcc in MCCS_TO_TRAIN:
        print(f"\n\n{'#'*60}")
        print(f"# MCC {mcc}")
        print(f"{'#'*60}")

        # Step 1: aggregate raw transactions → v2 monthly
        v2_path = aggregate_to_monthly_v2(mcc)

        # Step 2: train M9 artifacts
        train(mcc=mcc, data_path=v2_path, window_years=DEFAULT_WINDOW_YEARS)

    total_elapsed = time.monotonic() - total_t0
    print(f"\n\nDone — all MCCs trained in {total_elapsed:.1f}s")
    print(f"Artifacts at: {ARTIFACTS_BASE_PATH}")
