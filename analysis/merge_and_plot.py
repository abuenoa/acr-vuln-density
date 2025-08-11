import pathlib, sys, json
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "csv"
OUT  = pathlib.Path(__file__).resolve().parents[1] / "data"

# Load all timepoints found (t0..t3)
dfs = []
for tp in ["t0", "t1", "t2", "t3"]:
    f = DATA / f"resultados_{tp}.csv"
    if f.exists():
        df = pd.read_csv(f)
        df["tp"] = tp.upper()
        dfs.append(df)

if not dfs:
    sys.exit("No resultados_t*.csv files found.")

df = pd.concat(dfs, ignore_index=True)

# Basic integrity checks
assert not df.isna().any().any(), "Found missing values in CSVs."
assert df.duplicated(subset=["timepoint","image","tag","scan_utc"]).sum() == 0, "Found duplicate rows."

# Consolidated pivot tables
base_cols = ["image","tag","repo"]
metrics   = ["cv_critical","cv_high","size_mb","density"]
pivot     = df.pivot_table(index=base_cols, columns="tp", values=metrics, aggfunc="first").reset_index()
pivot.columns = ['_'.join([c for c in col if c]).rstrip('_') for col in pivot.columns.values]

# Deltas (T0 is baseline)
for m in ["cv_critical","cv_high","density"]:
    for later in ["T1","T2","T3"]:
        if f"{m}_{later}" in pivot.columns and f"{m}_T0" in pivot.columns:
            pivot[f"delta_{m}_{later}_vs_T0"] = pivot[f"{m}_{later}"] - pivot[f"{m}_T0"]

# Save comparativa
comp_csv = DATA / "comparativa.csv"
pivot.to_csv(comp_csv, index=False)
print(f"Saved -> {comp_csv}")

# Plots
OUT_FIG = OUT / "fig"
OUT_FIG.mkdir(exist_ok=True)

# 1) Bar charts: density per TP
if {"density_T0","density_T1","density_T2","density_T3"} <= set(pivot.columns):
    plot_df = pivot[["image","density_T0","density_T1","density_T2","density_T3"]].set_index("image")
    ax = plot_df.plot(kind="bar")
    ax.set_ylabel("Vulnerability density (CRITICAL+HIGH per MB)")
    ax.set_title("Density by image (T0–T3)")
    plt.tight_layout()
    p1 = OUT_FIG / "density_T0_T3.png"
    plt.savefig(p1, dpi=200)
    plt.close()
    print(f"Saved -> {p1}")

# 2) Line chart: CVEs over time
long = df.melt(
    id_vars=["image","tp"],
    value_vars=["cv_critical","cv_high"],
    var_name="metric",
    value_name="count"
)
for img, g in long.groupby("image"):
    ax = g.pivot_table(index="tp", columns="metric", values="count", aggfunc="first").plot(marker="o")
    ax.set_title(f"CVEs over time: {img}")
    ax.set_xlabel("Timepoint")
    ax.set_ylabel("Count")
    plt.tight_layout()
    p2 = OUT_FIG / f"cves_over_time_{img}.png"
    plt.savefig(p2, dpi=200)
    plt.close()
    print(f"Saved -> {p2}")

# 3) Cumulative growth (CRIT+HIGH vs T0)
for img, g in df.groupby("image"):
    series = g.set_index("tp")[["cv_critical","cv_high"]].sum(axis=1).sort_index()
    if "T0" in series.index:
        base = series["T0"]
        growth = (series - base).cumsum()
        ax = growth.plot(marker="o")
        ax.set_title(f"Cumulative growth (CRIT+HIGH) from T0: {img}")
        ax.set_xlabel("Timepoint")
        ax.set_ylabel("Δ CVEs (cumulative)")
        plt.tight_layout()
        p3 = OUT_FIG / f"cum_growth_{img}.png"
        plt.savefig(p3, dpi=200)
        plt.close()
        print(f"Saved -> {p3}")
