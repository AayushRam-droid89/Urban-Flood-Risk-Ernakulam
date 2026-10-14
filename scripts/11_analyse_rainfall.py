
from pathlib import Path
import calendar

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(r"D:\Flood_Project_SDG")
PROCESSED = ROOT / "data" / "processed"
MAPS = ROOT / "outputs" / "maps"

MAPS.mkdir(parents=True, exist_ok=True)

INPUT = PROCESSED / "rainfall_stations_ernakulam.csv"

# Outputs
STATION_CSV = PROCESSED / "rainfall_station_summary.csv"
ANNUAL_CSV = PROCESSED / "rainfall_annual_summary.csv"
STATION_PLOT = MAPS / "rainfall_station_comparison.png"
ANNUAL_PLOT = MAPS / "rainfall_annual_observations.png"

DATE_COL = "Data Acquisition Time"
RAIN_COL = "Manual Daily Rainfall (mm)"
STATION_COL = "Station"

# Minimum daily coverage for treating a station-year as reasonably complete.
# This is an analysis threshold, not an official meteorological standard.
MIN_COVERAGE = 0.80

# -----------------------------------------------------
# 1. Load and clean data
# -----------------------------------------------------

df = pd.read_csv(INPUT)

required = [DATE_COL, RAIN_COL, STATION_COL, "Latitude", "Longitude"]
missing_columns = [c for c in required if c not in df.columns]

if missing_columns:
    raise ValueError(f"Missing required columns: {missing_columns}")

df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
df[RAIN_COL] = pd.to_numeric(df[RAIN_COL], errors="coerce")
df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

invalid_dates = df[DATE_COL].isna().sum()
invalid_rainfall = df[RAIN_COL].isna().sum()
negative_rainfall = (df[RAIN_COL] < 0).sum()

print("=== DATA QUALITY ===")
print("Input rows:", len(df))
print("Invalid dates:", invalid_dates)
print("Missing/non-numeric rainfall:", invalid_rainfall)
print("Negative rainfall records:", negative_rainfall)

# Exclude unusable records; do not replace missing values with zero.
df = df.dropna(subset=[DATE_COL, RAIN_COL, STATION_COL]).copy()
df = df[df[RAIN_COL] >= 0].copy()

df["Year"] = df[DATE_COL].dt.year
df["Month"] = df[DATE_COL].dt.month
df["Date"] = df[DATE_COL].dt.date

# Duplicate station-date records need inspection before aggregation.
duplicates = df.duplicated(
    subset=[STATION_COL, "Date"],
    keep=False
)

print("Records involved in duplicate station-dates:", int(duplicates.sum()))

if duplicates.any():
    print("Warning: duplicate station-date records found.")
    print("They will be averaged for daily summaries.")

# Create one observation per station per calendar date.
daily = (
    df.groupby([STATION_COL, "Date"], as_index=False)
    .agg(
        Rainfall_mm=(RAIN_COL, "mean"),
        Year=("Year", "first"),
        Month=("Month", "first"),
        Latitude=("Latitude", "first"),
        Longitude=("Longitude", "first"),
    )
)

# -----------------------------------------------------
# 2. Station-level summary
# -----------------------------------------------------

station_summary = (
    daily.groupby(STATION_COL)
    .agg(
        observation_days=("Rainfall_mm", "count"),
        first_observation=("Date", "min"),
        last_observation=("Date", "max"),
        mean_observed_daily_mm=("Rainfall_mm", "mean"),
        median_observed_daily_mm=("Rainfall_mm", "median"),
        maximum_observed_daily_mm=("Rainfall_mm", "max"),
        latitude=("Latitude", "first"),
        longitude=("Longitude", "first"),
        years_observed=("Year", "nunique"),
    )
    .reset_index()
    .sort_values("observation_days", ascending=False)
)

station_summary.to_csv(STATION_CSV, index=False)

print("\n=== STATION SUMMARY ===")
print(station_summary.to_string(index=False))
print("\nSaved:", STATION_CSV)

# -----------------------------------------------------
# 3. Annual summaries and observation coverage
# -----------------------------------------------------

annual = (
    daily.groupby([STATION_COL, "Year"])
    .agg(
        observation_days=("Rainfall_mm", "count"),
        mean_observed_daily_mm=("Rainfall_mm", "mean"),
        median_observed_daily_mm=("Rainfall_mm", "median"),
        maximum_observed_daily_mm=("Rainfall_mm", "max"),
        observed_rainfall_sum_mm=("Rainfall_mm", "sum"),
    )
    .reset_index()
)

def days_in_year(year):
    return 366 if calendar.isleap(int(year)) else 365

annual["calendar_days"] = annual["Year"].apply(days_in_year)
annual["coverage_fraction"] = (
    annual["observation_days"] / annual["calendar_days"]
)

annual["coverage_percent"] = 100 * annual["coverage_fraction"]
annual["meets_80pct_coverage"] = (
    annual["coverage_fraction"] >= MIN_COVERAGE
)

annual.to_csv(ANNUAL_CSV, index=False)

print("\n=== ANNUAL COVERAGE ===")
print("Station-years:", len(annual))
print(
    "Station-years meeting 80% daily coverage:",
    int(annual["meets_80pct_coverage"].sum())
)

print("\nStation-years with best coverage:")
print(
    annual.sort_values("coverage_fraction", ascending=False)
    .head(15)
    .to_string(index=False)
)

print("\nSaved:", ANNUAL_CSV)

# Important: an observed sum is NOT an annual rainfall total
# unless the daily series is sufficiently complete.
print(
    "\nNote: observed_rainfall_sum_mm is the sum of available "
    "observations. Do not treat it as a complete annual total "
    "when coverage is low."
)

# -----------------------------------------------------
# 4. Plot observation counts by station
# -----------------------------------------------------

plot_data = station_summary.sort_values("observation_days")

fig, ax = plt.subplots(figsize=(10, 6))

ax.barh(
    plot_data[STATION_COL],
    plot_data["observation_days"],
)

ax.set_xlabel("Distinct dates with rainfall observations")
ax.set_ylabel("Rainfall station")
ax.set_title("Rainfall Data Availability by Station")
ax.grid(axis="x", linestyle="--", alpha=0.3)

fig.tight_layout()
fig.savefig(STATION_PLOT, dpi=200, bbox_inches="tight")
plt.close(fig)

print("\nSaved:", STATION_PLOT)

# -----------------------------------------------------
# 5. Plot yearly observation counts
# -----------------------------------------------------

fig, ax = plt.subplots(figsize=(12, 6))

for station, group in annual.groupby(STATION_COL):
    ax.plot(
        group["Year"],
        group["observation_days"],
        marker="o",
        markersize=3,
        linewidth=1.2,
        label=station,
    )

ax.set_xlabel("Year")
ax.set_ylabel("Observed days per year")
ax.set_title("Annual Rainfall Observation Coverage by Station")
ax.grid(True, linestyle="--", alpha=0.3)
ax.legend(fontsize=8, ncol=2)

fig.tight_layout()
fig.savefig(ANNUAL_PLOT, dpi=200, bbox_inches="tight")
plt.close(fig)

print("Saved:", ANNUAL_PLOT)

print("\nRainfall analysis complete.")