from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.plot import plotting_extent

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
MAPS = ROOT / "outputs" / "maps"
MAPS.mkdir(parents=True, exist_ok=True)

files = {
    "10-year": DATA / "common_flood_10year.tif",
    "25-year": DATA / "common_flood_25year.tif",
    "50-year": DATA / "common_flood_50year.tif",
}

arrays = {}
profile = None
transform = None

for name, path in files.items():
    with rasterio.open(path) as src:
        arrays[name] = src.read(1, masked=True).astype("float32").filled(np.nan)

        if profile is None:
            profile = src.profile.copy()
            transform = src.transform
        elif (src.profile["width"], src.profile["height"]) != (profile["width"], profile["height"]):
            raise ValueError(f"Raster dimensions for {name} do not match the base raster.")

# Restrict analysis to pixels valid in all scenarios
common_mask = np.logical_and.reduce([np.isfinite(arr) for arr in arrays.values()])

if not common_mask.any():
    raise ValueError("No common valid pixels found across scenarios.")

pooled_values = np.concatenate([arr[common_mask] for arr in arrays.values()])

# Shared robust scaling limits across all scenarios
lower, upper = np.percentile(pooled_values, [2, 98])

if upper <= lower:
    raise ValueError(f"Invalid scaling limits: lower={lower}, upper={upper}")

indices = {}

for name, arr in arrays.items():
    index = np.full(arr.shape, np.nan, dtype=np.float32)
    scaled = (arr[common_mask] - lower) / (upper - lower)
    index[common_mask] = np.clip(scaled, 0.0, 1.0)
    indices[name] = index

    output = DATA / f"relative_hazard_{name.replace('-', '')}.tif"
    out_profile = profile.copy()
    out_profile.update(
        dtype="float32",
        count=1,
        nodata=np.nan,
        compress="lzw",
    )

    with rasterio.open(output, "w", **out_profile) as dst:
        dst.write(index, 1)

    print(
        f"{name}: mean index={np.nanmean(index):.3f}, "
        f"median index={np.nanmedian(index):.3f}"
    )

# Compute bounds safely for plotting
sample_arr = next(iter(indices.values()))
extent = plotting_extent(sample_arr, transform)

fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharey=True)

for ax, (name, index) in zip(axes, indices.items()):
    im = ax.imshow(
        np.ma.masked_invalid(index),
        cmap="YlOrRd",
        vmin=0,
        vmax=1,
        extent=extent,
        origin="upper",
    )
    ax.set_title(f"{name} Scenario")
    ax.set_xlabel("Longitude")

axes[0].set_ylabel("Latitude")

fig.colorbar(
    im,
    ax=axes,
    orientation="horizontal",
    fraction=0.06,
    pad=0.14,
    label="Relative hazard index (0–1; normalized across all return periods)",
)

fig.suptitle("Relative Flood-Hazard Index — Ernakulam Study Extent", fontsize=14)

plt.savefig(
    MAPS / "relative_hazard_index.png",
    dpi=300,
    bbox_inches="tight",
)
plt.close()

print("\nSaved relative hazard rasters and map.")
print(f"Scaling limits: {lower:.3f} to {upper:.3f}")