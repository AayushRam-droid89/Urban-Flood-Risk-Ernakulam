
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import matplotlib.pyplot as plt

ROOT = Path(r"D:\Flood_Project_SDG")
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MAPS = ROOT / "outputs" / "maps"
MAPS.mkdir(parents=True, exist_ok=True)

DEM_PATH = RAW / "ernakulam_dem.tif"
REFERENCE_PATH = PROCESSED / "common_flood_10year.tif"

OUTPUT_PATH = PROCESSED / "aligned_elevation_ernakulam.tif"
MAP_PATH = MAPS / "aligned_elevation_ernakulam.png"

# -----------------------------------------------------
# 1. Read the reference flood-hazard grid
# -----------------------------------------------------
with rasterio.open(REFERENCE_PATH) as ref:
    ref_crs = ref.crs
    ref_transform = ref.transform
    ref_width = ref.width
    ref_height = ref.height
    ref_bounds = ref.bounds
    ref_profile = ref.profile.copy()

print("=== REFERENCE FLOOD GRID ===")
print("CRS:", ref_crs)
print("Dimensions:", ref_width, "x", ref_height)
print("Bounds:", ref_bounds)
print("Resolution:", ref.res)

# -----------------------------------------------------
# 2. Reproject/resample the DEM to the reference grid
# -----------------------------------------------------
with rasterio.open(DEM_PATH) as src:
    source_dem = src.read(1, masked=True).astype(
        "float32"
    ).filled(np.nan)

    aligned_dem = np.full(
        (ref_height, ref_width),
        np.nan,
        dtype=np.float32,
    )

    reproject(
        source=source_dem,
        destination=aligned_dem,
        src_transform=src.transform,
        src_crs=src.crs,
        src_nodata=np.nan,
        dst_transform=ref_transform,
        dst_crs=ref_crs,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )

# Keep only locations where the 10-year hazard raster is valid.
# This makes the DEM coverage consistent with the reference mask.
with rasterio.open(REFERENCE_PATH) as ref:
    hazard = ref.read(1, masked=True).astype(
        "float32"
    ).filled(np.nan)

common_mask = np.isfinite(hazard) & np.isfinite(aligned_dem)
aligned_dem[~common_mask] = np.nan

valid = aligned_dem[np.isfinite(aligned_dem)]

if valid.size == 0:
    raise ValueError("No overlapping valid DEM pixels found.")

print("\n=== ALIGNED ELEVATION SUMMARY ===")
print("Valid pixels:", len(valid))
print("Minimum:", float(np.min(valid)))
print("Median:", float(np.median(valid)))
print("Maximum:", float(np.max(valid)))
print("Percentiles:", np.percentile(valid, [5, 25, 50, 75, 95]))

# -----------------------------------------------------
# 3. Save aligned DEM
# -----------------------------------------------------
out_profile = ref_profile.copy()
out_profile.update(
    dtype="float32",
    count=1,
    nodata=np.nan,
    compress="lzw",
)

with rasterio.open(OUTPUT_PATH, "w", **out_profile) as dst:
    dst.write(aligned_dem, 1)
    dst.set_band_description(1, "Aligned elevation")

print("\nAligned DEM saved to:", OUTPUT_PATH)

# -----------------------------------------------------
# 4. Plot aligned elevation with geographic coordinates
# -----------------------------------------------------
vmin, vmax = np.percentile(valid, [2, 98])

terrain_cmap = plt.get_cmap("terrain").copy()
terrain_cmap.set_bad("#ffffff")

extent = [
    ref_bounds.left,
    ref_bounds.right,
    ref_bounds.bottom,
    ref_bounds.top,
]

fig, ax = plt.subplots(figsize=(11, 8))

image = ax.imshow(
    np.ma.masked_invalid(aligned_dem),
    cmap=terrain_cmap,
    vmin=vmin,
    vmax=vmax,
    extent=extent,
    origin="upper",
    interpolation="nearest",
)

cbar = fig.colorbar(image, ax=ax, shrink=0.9, pad=0.04)
cbar.set_label("DEM elevation (source units)")

ax.set_title(
    "Aligned Digital Elevation Model — Ernakulam",
    fontsize=15,
    pad=14,
)
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_facecolor("#ffffff")

plt.tight_layout()

try:
    fig.savefig(
        str(MAP_PATH),
        format="png",
        dpi=200,
        bbox_inches="tight",
    )
    print("Map saved to:", MAP_PATH)
finally:
    plt.close(fig)

print("\nAlignment complete.")
