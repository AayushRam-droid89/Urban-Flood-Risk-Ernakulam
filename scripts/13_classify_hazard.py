
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import matplotlib.pyplot as plt

from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import array_bounds

# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "outputs"
MAPS = OUTPUT / "maps"

MAPS.mkdir(parents=True, exist_ok=True)

SCENARIOS = {
    "10-year": PROCESSED / "relative_hazard_10year.tif",
    "25-year": PROCESSED / "relative_hazard_25year.tif",
    "50-year": PROCESSED / "relative_hazard_50year.tif",
}

SUMMARY_PATH = PROCESSED / "hazard_class_summary.csv"
MAP_PATH = MAPS / "relative_hazard_classes.png"

# Classes: 1=Low, 2=Moderate, 3=High, 4=Very High
CLASS_NAMES = ["Low", "Moderate", "High", "Very High"]
CLASS_COLORS = ["#2ca25f", "#fee08b", "#fc8d59", "#d73027"]

# --------------------------------------------------
# OPTIONAL BASEMAP SUPPORT
# --------------------------------------------------

try:
    import contextily as cx
    BASEMAP_AVAILABLE = True
except ImportError:
    BASEMAP_AVAILABLE = False
    print("Contextily not installed. Maps will be generated without a basemap.")
    print("To enable basemaps, run: python -m pip install contextily")

# --------------------------------------------------
# CLASSIFICATION AND REPROJECTION
# --------------------------------------------------

def classify_hazard(values, valid_mask):
    """Classify relative hazard values from 0 to 1."""
    result = np.zeros(values.shape, dtype=np.uint8)

    result[valid_mask & (values < 0.25)] = 1
    result[valid_mask & (values >= 0.25) & (values < 0.50)] = 2
    result[valid_mask & (values >= 0.50) & (values < 0.75)] = 3
    result[valid_mask & (values >= 0.75) & (values <= 1.0)] = 4

    return result


def reproject_for_map(values, valid_mask, src):
    """Reproject hazard values to Web Mercator for background map tiles."""
    dst_crs = "EPSG:3857"

    transform, width, height = calculate_default_transform(
        src.crs,
        dst_crs,
        src.width,
        src.height,
        *src.bounds,
    )

    destination = np.full((height, width), np.nan, dtype=np.float32)

    source = np.where(valid_mask, values, np.nan).astype(np.float32)

    reproject(
        source=source,
        destination=destination,
        src_transform=src.transform,
        src_crs=src.crs,
        src_nodata=np.nan,
        dst_transform=transform,
        dst_crs=dst_crs,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )

    return destination, transform


# --------------------------------------------------
# PROCESS ALL SCENARIOS
# --------------------------------------------------

summary_rows = []
map_data = {}

for scenario, path in SCENARIOS.items():
    if not path.exists():
        raise FileNotFoundError(f"Missing input raster: {path}")

    print(f"\nProcessing {scenario} scenario...")

    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError(f"Raster has no CRS: {path}")

        hazard = src.read(1, masked=True)
        values = np.asarray(hazard.data, dtype=np.float32)

        valid = (
            ~np.ma.getmaskarray(hazard)
            & np.isfinite(values)
            & (values >= 0)
            & (values <= 1)
        )

        classes = classify_hazard(values, valid)

        # Save classified raster in its original CRS.
        class_path = PROCESSED / f"hazard_classes_{scenario.replace('-', '')}.tif"

        profile = src.profile.copy()
        profile.update(
            dtype="uint8",
            count=1,
            nodata=0,
            compress="lzw",
        )

        with rasterio.open(class_path, "w", **profile) as dst:
            dst.write(classes, 1)
            dst.set_band_description(1, "Relative hazard class: 1=Low, 4=Very High")

        valid_count = int(valid.sum())

        for class_id, class_name in enumerate(CLASS_NAMES, start=1):
            count = int(np.count_nonzero(classes == class_id))
            percent = count / valid_count * 100 if valid_count else 0

            summary_rows.append({
                "scenario": scenario.replace("-", ""),
                "class": class_name,
                "pixel_count": count,
                "percent_of_valid_pixels": round(percent, 2),
            })

        # Reproject the continuous index, then classify for display.
        # Nearest-neighbour preserves source values without inventing
        # intermediate hazard values.
        projected, transform = reproject_for_map(values, valid, src)

        projected_valid = (
            np.isfinite(projected)
            & (projected >= 0)
            & (projected <= 1)
        )

        projected_classes = classify_hazard(projected, projected_valid)

        west, south, east, north = array_bounds(
            projected.shape[0],
            projected.shape[1],
            transform,
        )

        map_data[scenario] = {
            "classes": np.ma.masked_where(
                projected_classes == 0,
                projected_classes,
            ),
            "extent": (west, east, south, north),
        }

# --------------------------------------------------
# SAVE SUMMARY TABLE
# --------------------------------------------------

summary = pd.DataFrame(summary_rows)
summary.to_csv(SUMMARY_PATH, index=False)

print("\nHazard class summary:")
print(summary.to_string(index=False))


# --------------------------------------------------
# CLEAN THREE-PANEL MAP — NO INTERNET TILES
# --------------------------------------------------

from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
from rasterio.warp import reproject, Resampling

ELEVATION_FILE = PROCESSED / "aligned_elevation_ernakulam.tif"

COLORS = ["#2ca25f", "#fee08b", "#fc8d59", "#d73027"]
cmap = ListedColormap(COLORS)
norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5], cmap.N)

fig, axes = plt.subplots(1, 3, figsize=(18, 8))

with rasterio.open(ELEVATION_FILE) as elev_src:
    elevation = elev_src.read(1, masked=True)
    elev_values = elevation.filled(np.nan).astype(float)

    # Match the background elevation to the hazard grid.
    for ax, (scenario, path) in zip(axes, SCENARIOS.items()):
        with rasterio.open(path) as src:
            hazard = src.read(1, masked=True)
            values = np.asarray(hazard.data, dtype=np.float32)

            valid = (
                ~np.ma.getmaskarray(hazard)
                & np.isfinite(values)
                & (values >= 0)
                & (values <= 1)
            )

            classes = classify_hazard(values, valid)

            # Reproject elevation to the hazard raster grid.
            bg = np.full(values.shape, np.nan, dtype=np.float32)

            reproject(
                source=elev_values,
                destination=bg,
                src_transform=elev_src.transform,
                src_crs=elev_src.crs,
                src_nodata=np.nan,
                dst_transform=src.transform,
                dst_crs=src.crs,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )

            extent = (
                src.bounds.left, src.bounds.right,
                src.bounds.bottom, src.bounds.top
            )

            # Muted elevation background
            ax.imshow(
                bg,
                extent=extent,
                origin="upper",
                cmap="Greys",
                alpha=0.30,
                interpolation="nearest",
            )

            # Semi-transparent classified hazard
            overlay = np.ma.masked_where(classes == 0, classes)

            ax.imshow(
                overlay,
                extent=extent,
                origin="upper",
                cmap=cmap,
                norm=norm,
                alpha=0.78,
                interpolation="nearest",
            )

            ax.set_title(f"{scenario} Return Period", fontsize=13)
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.set_xlim(src.bounds.left, src.bounds.right)
            ax.set_ylim(src.bounds.bottom, src.bounds.top)

legend_items = [
    Patch(facecolor=COLORS[i], edgecolor="black", label=CLASS_NAMES[i])
    for i in range(4)
]

fig.suptitle(
    "Relative Flood Hazard Classes — Ernakulam",
    fontsize=17,
    fontweight="bold",
)

fig.legend(
    handles=legend_items,
    loc="lower center",
    ncol=4,
    bbox_to_anchor=(0.5, 0.045),
    frameon=True,
)

fig.text(
    0.5, 0.015,
    "Preliminary relative-hazard classes; not official flood probabilities or depths.",
    ha="center",
    fontsize=9,
)

fig.tight_layout(rect=[0, 0.12, 1, 0.93])

plt.savefig(
    MAP_PATH,
    dpi=250,
    bbox_inches="tight",
    facecolor="white",
)
plt.close(fig)

print("Clean map saved:", MAP_PATH)