from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from shapely.geometry import box, mapping

ROOT = Path(r"D:\Flood_Project_SDG")
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

DEM = RAW / "ernakulam_dem.tif"
RAINFALL = RAW / "rainfall_manual_daily_kerala-sw_kl_1991_2020.csv"

FLOODS = {
    "10yr": RAW / "Kerala_Flood_10_yr_Historical.tif",
    "25yr": RAW / "Kerala_Flood_25_yr_Historical.tif",
    "50yr": RAW / "Kerala_Flood_50_yr_Historical.tif",
}

# 1. Use the DEM extent as the initial study area.
with rasterio.open(DEM) as dem:
    if dem.crs is None:
        raise ValueError("DEM has no CRS.")

    study_bounds = dem.bounds
    study_polygon = box(
        study_bounds.left, study_bounds.bottom,
        study_bounds.right, study_bounds.top
    )
    study_crs = dem.crs

print("Study extent:", study_bounds)
print("Study CRS:", study_crs)

# 2. Clip all flood return-period rasters.
for label, path in FLOODS.items():
    print(f"\nProcessing {label} flood raster...")

    if not path.exists():
        print("Missing:", path)
        continue

    with rasterio.open(path) as src:
        if src.crs != study_crs:
            raise ValueError(
                f"CRS mismatch: {path.name} is {src.crs}, "
                f"but DEM is {study_crs}. Reproject the study geometry first."
            )

        clipped, transform = mask(
            src,
            [mapping(study_polygon)],
            crop=True,
            filled=False
        )

        values = clipped[0].compressed()
        profile = src.profile.copy()
        profile.update(
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=transform,
            compress="deflate"
        )

        # Preserve the raster's original NoData value.
        output = OUT / f"flood_{label}_ernakulam.tif"
        with rasterio.open(output, "w", **profile) as dst:
            dst.write(clipped.filled(src.nodata))

        print("Saved:", output.name)
        print("Valid pixels:", len(values))

        if len(values):
            print("Minimum:", float(values.min()))
            print("Maximum:", float(values.max()))
            print("Mean:", float(values.mean()))

# 3. Filter rainfall stations to the DEM extent.
print("\nProcessing rainfall data...")

if not RAINFALL.exists():
    raise FileNotFoundError(f"Rainfall CSV not found: {RAINFALL}")

rain = pd.read_csv(RAINFALL)
rain["Latitude"] = pd.to_numeric(rain["Latitude"], errors="coerce")
rain["Longitude"] = pd.to_numeric(rain["Longitude"], errors="coerce")
rain["Manual Daily Rainfall (mm)"] = pd.to_numeric(
    rain["Manual Daily Rainfall (mm)"], errors="coerce"
)

rain = rain.dropna(subset=["Latitude", "Longitude"])
rain = rain[
    rain["Longitude"].between(study_bounds.left, study_bounds.right)
    & rain["Latitude"].between(study_bounds.bottom, study_bounds.top)
].copy()

rain["Data Acquisition Time"] = pd.to_datetime(
    rain["Data Acquisition Time"],
    dayfirst=True,
    errors="coerce"
)

rain = rain.dropna(subset=["Data Acquisition Time"])
rain = rain.sort_values(["Station", "Data Acquisition Time"])

rain_output = OUT / "rainfall_stations_ernakulam.csv"
rain.to_csv(rain_output, index=False)

print("Saved:", rain_output.name)
print("Rows:", len(rain))
print("Unique stations:", rain["Station"].nunique())

if len(rain):
    print("Date range:",
          rain["Data Acquisition Time"].min(),
          "to",
          rain["Data Acquisition Time"].max())
    print(rain.groupby("Station").size().sort_values(ascending=False).head(10))
else:
    print("No rainfall stations fall inside the DEM extent.")
    print("We may need to use nearby stations outside the DEM extent.")

print("\nPreparation complete.")