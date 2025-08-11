#!/usr/bin/env python3
"""
Merge per-timepoint CSVs (T0–T3), compute deltas, and produce basic figures.

- Loads data/csv/resultados_t{0..3}.csv if present.
- Validates required columns; allows empty metadata in 'trivy_db_updated_at'.
- Writes:
    - data/csv/merged_all.csv       (row-wise concatenation)
    - data/csv/comparativa.csv      (pivoted metrics + deltas vs T0)
- Saves figures to data/fig/:
    - density_T0_T3.png             (grouped bars by image & timepoint, if ≥2 TPs)
    - density_T0_only.png           (bars by image, if only T0)
    - cves_over_time_<image>.png    (per-image lines CRITICAL/HIGH, if ≥2 TPs)
    - delta_density_T3_vs_T0.png    (bars of density change, if T3 & T0 exist)
"""

from __future__ import annotations
import sys
import json
from datetime import datetime, timezone
import pathlib
from typing import List

import pandas as pd
import matplotlib.pyplot as plt


# ---------- Paths ----------
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV_DIR   = REPO_ROOT / "data" / "csv"
FIG_DIR   = REPO_ROOT / "data" / "fig"
CSV_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

TIMEPOINTS: List[str] = ["t0", "t1", "t2", "t3"]


# ---------- Load ----------
dfs: List[pd.DataFrame] = []
for tp in TIMEPOINTS:
    f = CSV_DIR / f"resultados_{tp}.csv"
    if f.exists():
        df = pd.read_csv(f)
        df["tp"] = tp.upper()
        dfs.append(df)

if not dfs:
    print("No resultados_t*.csv files found under data/csv/. Nothing to do.", file=sys.stderr)
    sys.exit(1)

df = pd.concat(dfs, ignore_index=True)


# ---------- Basic validation ----------
# Required columns for analysis
required_cols = {
    "timepoint", "image", "tag", "repo", "image_ref",
    "size_mb", "cv_critical", "cv_high", "density", "tp",
    "trivy_version", "scan_utc"
}
missing = required_cols - set(df.columns)
if missing:
    raise AssertionError(f"Missing required columns: {sorted(missing)}")

# Allow nulls only in harmless metadata (Trivy DB stamp may be unavailable on some versions)
allowed_nulls = {"trivy_db_updated_at"}
nulls = df.isna()
bad_cols = [c for c in df.columns if c not in allowed_nulls]
if nulls[bad_cols].any().any():
    missing_cols = [c for c in bad_cols if nulls[c].any()]
    raise AssertionError(f"Found missing values in required columns: {missing_cols}")

# Fill safe metadata gaps for downstream operations
if "trivy_db_updated_at" in df.columns:
    df["trivy_db_updated_at"] = df["trivy_db_updated_at"].fillna("unknown")

# Enforce numeric types
for col in ["size_mb", "cv_critical", "cv_high", "density"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[col].isna().any():
        raise AssertionError(f"Non-numeric values found in column: {col}")

# Save raw merged rows for auditing
merged_csv = CSV_DIR / "merged_all.csv"
df.to_csv(merged_csv, index=False)
print(f"Saved -> {merged_csv}")


# ---------- Pivot (per-image metrics by timepoint) ----------
base_cols = ["image", "tag", "repo"]
metrics   = ["cv_critical", "cv_high", "size_mb", "density"]

pivot = (
    df.pivot_table(index=base_cols, columns="tp", values=metrics, aggfunc="first")
      .reset_index()
)
# Flatten MultiIndex columns like ('density','T0') -> 'density_T0'
pivot.columns = ['_'.join([c for c in col if c]).rstrip('_') for col in pivot.columns.values]

# ---------- Deltas vs T0 ----------
def add_delta(col_base: str):
    # Create delta_<metric>_<LATER>_vs_T0 if both columns present
    for later in ["T1", "T2", "T3"]:
        col_later = f"{col_base}_{later}"
        col_t0    = f"{col_base}_T0"
        if col_later in pivot.columns and col_t0 in pivot.columns:
            pivot[f"delta_{col_base}_{later}_vs_T0"] = pivot[col_later] - pivot[col_t0]

for m in ["cv_critical", "cv_high", "density"]:
    add_delta(m)

# Save comparative table
comparativa_csv = CSV_DIR / "comparativa.csv"
pivot.to_csv(comparativa_csv, index=False)
print(f"Saved -> {comparativa_csv}")


# ---------- Figures ----------
# Helper to save a figure and close it (one chart per file; no seaborn; no colour spec)
def save_fig(path: pathlib.Path):
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    print(f"Saved -> {path}")

# 1) Density grouped bars (if ≥2 timepoints), else single-timepoint bars
density_cols = [c for c in pivot.columns if c.startswith("density_") and c[-2:] in {"T0","T1","T2","T3"}]
# Make sure they are in chronological order T0..T3
density_cols_sorted = [c for c in [f"density_{tp}" for tp in ["T0","T1","T2","T3"]] if c in density_cols]

if len(density_cols_sorted) >= 2:
    plot_df = pivot[["image"] + density_cols_sorted].set_index("image")
    ax = plot_df.plot(kind="bar")
    ax.set_ylabel("Vulnerability density (CRITICAL+HIGH per MB)")
    ax.set_title("Density by image across timepoints (T0–T3)")
    ax.legend(title="Timepoint")
    save_fig(FIG_DIR / "density_T0_T3.png")
elif "density_T0" in pivot.columns:
    plot_df = pivot[["image", "density_T0"]].set_index("image")
    ax = plot_df.plot(kind="bar")
    ax.set_ylabel("Vulnerability density (CRITICAL+HIGH per MB)")
    ax.set_title("Density by image (T0)")
    ax.legend().remove()
    save_fig(FIG_DIR / "density_T0_only.png")

# 2) Per-image lines: CVEs over time (CRITICAL & HIGH), only if ≥2 timepoints
available_tps = sorted(df["tp"].unique().tolist())  # e.g., ['T0','T1']
if len(available_tps) >= 2:
    for img, g in df.groupby("image"):
        # Build a small time-indexed frame with CRITICAL/HIGH per tp
        tmp = (
            g.set_index("tp")[["cv_critical", "cv_high"]]
             .sort_index()
             .astype(float)
        )
        ax = tmp.plot(marker="o")
        ax.set_title(f"CVEs over time: {img}")
        ax.set_xlabel("Timepoint")
        ax.set_ylabel("Count")
        save_fig(FIG_DIR / f"cves_over_time_{img.replace('/', '_')}.png")

# 3) Delta density (T3 vs T0) if both exist
if {"density_T0", "density_T3"}.issubset(pivot.columns):
    tmp = pivot[["image", "density_T0", "density_T3"]].copy()
    tmp["delta_density_T3_vs_T0"] = tmp["density_T3"] - tmp["density_T0"]
    ax = tmp.set_index("image")["delta_density_T3_vs_T0"].plot(kind="bar")
    ax.set_ylabel("Δ density (T3 – T0)")
    ax.set_title("Change in vulnerability density from T0 to T3")
    save_fig(FIG_DIR / "delta_density_T3_vs_T0.png")


# ---------- Provenance note ----------
provenance = {
    "script": "analysis/merge_and_plot.py",
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "inputs_present": [tp for tp in TIMEPOINTS if (CSV_DIR / f"resultados_{tp}.csv").exists()],
    "outputs": {
        "merged_all_csv": str(merged_csv),
        "comparativa_csv": str(comparativa_csv),
        "fig_dir": str(FIG_DIR),
    },
}
prov_path = CSV_DIR / "analysis_provenance.json"
with open(prov_path, "w", encoding="utf-8") as f:
    json.dump(provenance, f, indent=2)
print(f"Saved -> {prov_path}")
