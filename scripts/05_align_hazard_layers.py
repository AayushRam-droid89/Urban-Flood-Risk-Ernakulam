from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import matplotlib.pyplot as plt

# Project folders
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs" / "maps"
OUTPUTS.mkdir(parents=True, exist_ok=True)

files = {
    "10-year": PROCESSED / "flood_10yr_ernakulam.tif",
    "25-year": PROCESSED / "flood_25yr_ernakulam.tif",
    "50-year": PROCESSED / "flood_50yr_ernakulam.tif",
}

# Use the 10-year raster as the reference grid
with rasterio.open(files["10-year"]) as ref:
    reference_profile = ref.profile.copy()
    reference_transform = ref.transform
    reference_crs = ref.crs
    width, height = ref.width, ref.height
    reference_bounds = ref.bounds

aligned = {}

for name, path in files.items():
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with rasterio.open(path) as src:
        source = src.read(1, masked=True).astype("float32").filled(np.nan)

        destination = np.full((height, width), np.nan, dtype="float32")

        reproject(
            source=source,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=reference_transform,
            dst_crs=reference_crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )

        aligned[name] = destination

        # Save aligned raster
        output_path = PROCESSED / f"aligned_flood_{name.replace('-', '')}.tif"

        profile = reference_profile.copy()
        profile.update(
            dtype="float32",
            count=1,
            nodata=np.nan,
            compress="lzw",
        )

        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(destination, 1)

        valid = destination[np.isfinite(destination)]

        print(f"\n{name}")
        print(f"Valid pixels: {len(valid):,}")
        if len(valid):
            print(f"Min: {np.min(valid):.2f}")
            print(f"Median: {np.median(valid):.2f}")
            print(f"Max: {np.max(valid):.2f}")

# Shared colour scale for fair visual comparison
valid_values = [
    arr[np.isfinite(arr)]
    for arr in aligned.values()
]
valid_values = [v for v in valid_values if len(v)]

if not valid_values:
    raise ValueError("No valid raster pixels found.")

all_values = np.concatenate(valid_values)
vmin, vmax = np.percentile(all_values, [2, 98])

fig, axes = plt.subplots(1, 3, figsize=(16, 6))

for ax, (name, arr) in zip(axes, aligned.items()):
    image = ax.imshow(
        np.ma.masked_invalid(arr),
        cmap="Blues",
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_title(f"{name} return period")
    ax.set_xlabel("Grid column")
    ax.set_ylabel("Grid row")

fig.colorbar(
    image,
    ax=axes,
    orientation="horizontal",
    fraction=0.06,
    pad=0.12,
    label="Original raster value (units/meaning to verify)",
)

fig.suptitle("Aligned Flood-Hazard Scenarios — Ernakulam Study Extent")
plt.savefig(
    OUTPUTS / "aligned_flood_scenarios.png",
    dpi=300,
    bbox_inches="tight",
)
plt.close()

print("\nDone!")
print(f"Map saved to: {OUTPUTS / 'aligned_flood_scenarios.png'}")
print(f"Aligned rasters saved in: {PROCESSED}")