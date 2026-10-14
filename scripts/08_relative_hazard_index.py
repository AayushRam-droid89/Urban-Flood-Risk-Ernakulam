
from pathlib import Path

import numpy as np
import rasterio
import matplotlib.pyplot as plt

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
        arrays[name] = src.read(1, masked=True).astype(
            "float32"
        ).filled(np.nan)

        if profile is None:
            profile = src.profile.copy()
            transform = src.transform

# Restrict analysis to pixels valid in all scenarios
common_mask = np.logical_and.reduce([
    np.isfinite(arr) for arr in arrays.values()
])

if not common_mask.any():
    raise ValueError("No common valid pixels found.")

pooled_values = np.concatenate([
    arr[common_mask] for arr in arrays.values()
])

# Shared robust scaling limits across all scenarios
lower, upper = np.percentile(pooled_values, [2, 98])

if upper <= lower:
    raise ValueError("Invalid scaling limits.")

indices = {}

for name, arr in arrays.items():
    index = np.full(arr.shape, np.nan, dtype=np.float32)

    scaled = (arr[common_mask] - lower) / (upper - lower)
    index[common_mask] = np.clip(scaled, 0, 1)

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

# Geographic coordinate extent
height, width = next(iter(indices.values())).shape
left = transform.c
top = transform.f
right = left + width * transform.a
bottom = top + height * transform.e

fig, axes = plt.subplots(1, 3, figsize=(16, 6))

for ax, (name, index) in zip(axes, indices.items()):
    im = ax.imshow(
        np.ma.masked_invalid(index),
        cmap="YlOrRd",
        vmin=0,
        vmax=1,
        extent=[left, right, bottom, top],
        origin="upper",
    )
    ax.set_title(f"{name} scenario")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

fig.colorbar(
    im,
    ax=axes,
    orientation="horizontal",
    fraction=0.06,
    pad=0.14,
    label="Relative hazard index (0–1; not probability or depth)",
)

fig.suptitle("Relative Flood-Hazard Index — Ernakulam Study Extent")

plt.savefig(
    MAPS / "relative_hazard_index.png",
    dpi=300,
    bbox_inches="tight",
)
plt.close()

print("\nSaved relative hazard rasters and map.")
print("Scaling limits:", lower, "to", upper)
print("Note: This is a relative index, not a calibrated flood probability.")