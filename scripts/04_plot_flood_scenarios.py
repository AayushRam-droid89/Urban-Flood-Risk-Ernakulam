from pathlib import Path
import numpy as np
import rasterio
import matplotlib.pyplot as plt

ROOT = Path(r"D:\Flood_Project_SDG")
DATA = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "maps"
OUT.mkdir(parents=True, exist_ok=True)

periods = ["10yr", "25yr", "50yr"]
arrays = []
all_values = []

# Load all scenarios first to calculate one shared colour scale.
for period in periods:
    path = DATA / f"flood_{period}_ernakulam.tif"

    with rasterio.open(path) as src:
        arr = src.read(1, masked=True)
        arrays.append(arr)

        values = arr.compressed()
        if len(values):
            all_values.append(values)

if not all_values:
    raise ValueError("No valid flood-raster pixels found.")

all_values = np.concatenate(all_values)

# Shared scale: robust to extreme outliers.
vmin, vmax = np.percentile(all_values, [2, 98])

fig, axes = plt.subplots(1, 3, figsize=(17, 7))

for ax, period, arr in zip(axes, periods, arrays):
    image = ax.imshow(
        arr,
        cmap="YlOrRd",
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest"
    )

    ax.set_title(f"{period.replace('yr', '-year')} return period")
    ax.set_axis_off()

# One shared colour bar for a fair comparison.
fig.colorbar(
    image,
    ax=axes,
    orientation="horizontal",
    fraction=0.06,
    pad=0.06,
    label="Original flood-raster value (units to be verified)"
)

fig.suptitle(
    "Kerala Flood Return-Period Comparison\n"
    "Ernakulam study extent",
    fontsize=15
)

output_path = OUT / "flood_scenario_comparison_v2.png"

fig.savefig(
    str(output_path),
    format="png",
    dpi=200,
    bbox_inches="tight"
)

plt.close(fig)
print(f"Map saved successfully: {output_path}")

print("Updated map saved to outputs/maps/flood_scenario_comparison.png")
print(f"Shared colour scale: {vmin:.2f} to {vmax:.2f}")
print("Note: raster units and meaning must be verified from the source metadata.")