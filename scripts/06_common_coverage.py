
from pathlib import Path

import numpy as np
import rasterio
import matplotlib.pyplot as plt

ROOT = Path(r"D:\Flood_Project_SDG")
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs" / "maps"
OUTPUTS.mkdir(parents=True, exist_ok=True)

files = {
    "10-year": PROCESSED / "aligned_flood_10year.tif",
    "25-year": PROCESSED / "aligned_flood_25year.tif",
    "50-year": PROCESSED / "aligned_flood_50year.tif",
}

arrays = {}
profile = None

for name, path in files.items():
    with rasterio.open(path) as src:
        arr = src.read(1, masked=True).astype("float32").filled(np.nan)
        arrays[name] = arr
        if profile is None:
            profile = src.profile.copy()

# Pixels must be valid in every scenario
common_mask = np.logical_and.reduce([
    np.isfinite(arr) for arr in arrays.values()
])

if not common_mask.any():
    raise ValueError("No common valid pixels across the three rasters.")

common = {
    name: np.where(common_mask, arr, np.nan)
    for name, arr in arrays.items()
}

print(f"Common valid pixels: {common_mask.sum():,}")

for name, arr in common.items():
    values = arr[common_mask]
    print(
        f"{name}: min={values.min():.2f}, "
        f"median={np.median(values):.2f}, "
        f"max={values.max():.2f}"
    )

# Save the common-coverage rasters
profile.update(
    dtype="float32",
    count=1,
    nodata=np.nan,
    compress="lzw",
)

for name, arr in common.items():
    output = PROCESSED / f"common_flood_{name.replace('-', '')}.tif"
    with rasterio.open(output, "w", **profile) as dst:
        dst.write(arr.astype("float32"), 1)

# Plot
all_values = np.concatenate([
    arr[common_mask] for arr in common.values()
])
vmin, vmax = np.percentile(all_values, [2, 98])

fig, axes = plt.subplots(1, 3, figsize=(16, 6))

for ax, (name, arr) in zip(axes, common.items()):
    im = ax.imshow(
        np.ma.masked_invalid(arr),
        cmap="Blues",
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_title(name)
    ax.set_xlabel("Grid column")
    ax.set_ylabel("Grid row")

fig.colorbar(
    im,
    ax=axes,
    orientation="horizontal",
    fraction=0.06,
    pad=0.12,
    label="Original raster value (meaning to verify)",
)

fig.suptitle("Flood Scenarios — Common Valid Coverage")
plt.savefig(
    OUTPUTS / "common_coverage_flood_scenarios.png",
    dpi=300,
    bbox_inches="tight",
)
plt.close()

print("Saved common-coverage rasters and comparison map.")
