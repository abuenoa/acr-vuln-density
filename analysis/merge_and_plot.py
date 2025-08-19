
#!/usr/bin/env python3
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
        df["timepoint"] = df["timepoint"].str.upper()
        dfs.append(df)

if not dfs:
    print("No resultados_t*.csv files found under data/csv/. Nothing to do.", file=sys.stderr)
    sys.exit(1)

df = pd.concat(dfs, ignore_index=True)

# Extract short image name for plotting
df["short_image"] = df["image_ref"].str.extract(r"/([^/:]+):")[0]

# ---------- Validation ----------
required_cols = {
    "timepoint", "image", "tag", "repo", "image_ref",
    "size_mb", "cv_critical", "cv_high", "density",
    "trivy_version", "scan_utc"
}
missing = required_cols - set(df.columns)
if missing:
    raise AssertionError(f"Missing required columns: {sorted(missing)}")

allowed_nulls = {"trivy_db_updated_at"}
nulls = df.isna()
bad_cols = [c for c in df.columns if c not in allowed_nulls]
if nulls[bad_cols].any().any():
    missing_cols = [c for c in bad_cols if nulls[c].any()]
    raise AssertionError(f"Found missing values in required columns: {missing_cols}")

if "trivy_db_updated_at" in df.columns:
    df["trivy_db_updated_at"] = df["trivy_db_updated_at"].fillna("unknown")

for col in ["size_mb", "cv_critical", "cv_high", "density"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[col].isna().any():
        raise AssertionError(f"Non-numeric values found in column: {col}")

# Save merged
merged_csv = CSV_DIR / "merged_all.csv"
df.to_csv(merged_csv, index=False)
print(f"Saved -> {merged_csv}")

# ---------- Pivot and deltas ----------
base_cols = ["image", "tag", "repo", "short_image"]
metrics   = ["cv_critical", "cv_high", "size_mb", "density"]

pivot = (
    df.pivot_table(index=base_cols, columns="timepoint", values=metrics, aggfunc="first")
      .reset_index()
)
pivot.columns = ['_'.join([c for c in col if c]).rstrip('_') for col in pivot.columns.values]

def add_delta(col_base: str):
    for later in ["T1", "T2", "T3"]:
        col_later = f"{col_base}_{later}"
        col_t0    = f"{col_base}_T0"
        if col_later in pivot.columns and col_t0 in pivot.columns:
            pivot[f"delta_{col_base}_{later}_vs_T0"] = pivot[col_later] - pivot[col_t0]

for m in ["cv_critical", "cv_high", "density"]:
    add_delta(m)

comparativa_csv = CSV_DIR / "comparativa.csv"
pivot.to_csv(comparativa_csv, index=False)
print(f"Saved -> {comparativa_csv}")

# ---------- Figures ----------
def save_fig(path: pathlib.Path):
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    print(f"Saved -> {path}")

# 1) Density grouped bars
density_cols = [c for c in pivot.columns if c.startswith("density_")]
density_cols_sorted = [c for c in [f"density_{tp}" for tp in ["T0","T1","T2","T3"]] if c in density_cols]

if len(density_cols_sorted) >= 2:
    plot_df = pivot[["short_image"] + density_cols_sorted].copy()
    
    plot_df = plot_df.set_index("short_image")[density_cols_sorted]
    ax = plot_df.plot(kind="bar")
    ax.set_ylabel("Vulnerability density (CRITICAL+HIGH per MB)")
    ax.set_title("Density by image across timepoints (T0–T3)")
    ax.legend(title="Timepoint")
    save_fig(FIG_DIR / "density_T0_T3.png")
elif "density_T0" in pivot.columns:
    plot_df = pivot[["image", "density_T0"]].copy()
    
    plot_df = plot_df.set_index("short_image")
    ax = plot_df.plot(kind="bar")
    ax.set_ylabel("Vulnerability density (CRITICAL+HIGH per MB)")
    ax.set_title("Density by image (T0)")
    ax.legend().remove()
    save_fig(FIG_DIR / "density_T0_only.png")

# 2) CVEs over time (per image)
available_tps = sorted(df["timepoint"].unique().tolist())
if len(available_tps) >= 2:
    for img, g in df.groupby("short_image"):
        tmp = (
            g.set_index("timepoint")[["cv_critical", "cv_high"]]
             .sort_index()
             .astype(float)
        )
        ax = tmp.plot(marker="o")
        ax.set_title(f"CVEs over time: {img}")
        ax.set_xlabel("Timepoint")
        ax.set_ylabel("Count")
        save_fig(FIG_DIR / f"cves_over_time_{img}.png")

# 3) Delta density (T3 vs T0)
if {"density_T0", "density_T3"}.issubset(pivot.columns):
    tmp = pivot[["image", "density_T0", "density_T3"]].copy()
    tmp["short_image"] = tmp["image"].str.extract(r"/([^/:]+):")[0]
    tmp["delta_density_T3_vs_T0"] = tmp["density_T3"] - tmp["density_T0"]
    ax = tmp.set_index("short_image")["delta_density_T3_vs_T0"].plot(kind="bar")
    ax.set_ylabel("Δ density (T3 – T0)")
    ax.set_title("Change in vulnerability density from T0 to T3")
    save_fig(FIG_DIR / "delta_density_T3_vs_T0.png")

# ---------- Provenance ----------
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
print("Analysis complete. Merged data and figures saved.")
