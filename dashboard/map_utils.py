"""Helpers for reading dashboard geo assets and building map figures.

Two groups of helpers live here:

* ``split_scenario_panels`` / ``panel_to_bytes`` (Member 7) — crop the existing
  1x3 matplotlib comparison PNG into per-scenario panels.
* GeoTIFF / GeoJSON readers and Plotly figure builders (Member 8) — used to
  show the aligned elevation raster, the classified hazard rasters and the
  experimental evacuation route with their real geometry and coordinate
  reference system.

Rasters are read with Pillow only (no extra dependency). Georeferencing is
taken from the GeoTIFF tags written by the analysis scripts, so the data are
placed with their original coordinates rather than an assumed extent.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from PIL import Image

# ---------------------------------------------------------------------------
# Scenario panel extraction (existing behaviour, unchanged)
# ---------------------------------------------------------------------------


def split_scenario_panels(
    image_path,
    *,
    top_frac: float = 0.11,
    bottom_frac: float = 0.17,
    gap_frac: float = 0.012,
) -> list[Image.Image]:
    """
    Split a 1×3 matplotlib comparison PNG into three scenario panels.

    Margins are proportional so cropping works across DPI/export sizes.
    """
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    top = int(height * top_frac)
    bottom = int(height * (1.0 - bottom_frac))
    panel_height = bottom - top

    gap = int(width * gap_frac)
    usable = width - 2 * gap
    panel_width = usable // 3

    panels: list[Image.Image] = []
    for i in range(3):
        left = gap + i * panel_width
        right = left + panel_width if i < 2 else width - gap
        panels.append(img.crop((left, top, right, top + panel_height)))

    return panels


def panel_to_bytes(panel: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = BytesIO()
    panel.save(buffer, format=fmt)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# GeoTIFF reading (Pillow only)
# ---------------------------------------------------------------------------

MODEL_PIXEL_SCALE_TAG = 33550
MODEL_TIEPOINT_TAG = 33922
GEO_KEY_DIRECTORY_TAG = 34735

PROJECTED_CRS_KEY = 3072
GEOGRAPHIC_CRS_KEY = 2048

# Display-only downsampling limit (nearest neighbour, never averaged).
MAX_DISPLAY_DIM = 420


class GeoAssetError(Exception):
    """Raised when a dashboard geo asset cannot be read or interpreted."""


def _raster_geometry(tags, height: int, width: int):
    """Derive (extent, resolution) from GeoTIFF tags; (None, None) if absent."""
    scale = tags.get(MODEL_PIXEL_SCALE_TAG)
    tiepoint = tags.get(MODEL_TIEPOINT_TAG)
    if not scale or not tiepoint or len(scale) < 2 or len(tiepoint) < 6:
        return None, None

    x_res = float(scale[0])
    y_res = float(scale[1])

    tie_i = float(tiepoint[0])
    tie_j = float(tiepoint[1])
    tie_x = float(tiepoint[3])
    tie_y = float(tiepoint[4])

    left = tie_x - tie_i * x_res
    top = tie_y + tie_j * y_res
    right = left + width * x_res
    bottom = top - height * y_res

    return (left, right, bottom, top), (x_res, y_res)


def _epsg_from_geokeys(tags):
    """Return the EPSG code stored in the GeoTIFF GeoKeyDirectory, if inline."""
    directory = tags.get(GEO_KEY_DIRECTORY_TAG)
    if not directory or len(directory) < 4:
        return None

    values: dict[int, int] = {}
    key_count = int(directory[3])
    for index in range(key_count):
        offset = 4 + index * 4
        if offset + 3 >= len(directory):
            break
        key_id = int(directory[offset])
        location = int(directory[offset + 1])
        value = int(directory[offset + 3])
        if location == 0:  # value stored inline (not in a separate TIFF tag)
            values[key_id] = value

    for key in (PROJECTED_CRS_KEY, GEOGRAPHIC_CRS_KEY):
        if values.get(key, 0) > 0:
            return values[key]
    return None


def read_geotiff_band(path):
    """Read a single-band GeoTIFF and derive its geographic extent.

    Returns ``(values, extent, resolution, epsg)`` where ``extent`` is
    ``(left, right, bottom, top)`` in the raster's own coordinates.

    Raises :class:`GeoAssetError` when the file is missing, unreadable or has
    no georeferencing tags (rather than silently inventing an extent).
    """
    raster_path = Path(path)
    if not raster_path.is_file():
        raise GeoAssetError(f"Raster not found: {raster_path}")

    try:
        with Image.open(raster_path) as image:
            values = np.asarray(image).astype("float64")
            tags = dict(getattr(image, "tag_v2", {}) or {})
    except Exception as exc:  # noqa: BLE001 - reported in the dashboard
        raise GeoAssetError(f"Could not read raster {raster_path.name}: {exc}") from exc

    if values.ndim != 2:
        raise GeoAssetError(
            f"{raster_path.name} is not a single-band raster (shape {values.shape})."
        )
    if values.size == 0:
        raise GeoAssetError(f"{raster_path.name} contains no pixels.")

    height, width = values.shape
    extent, resolution = _raster_geometry(tags, height, width)
    if extent is None:
        raise GeoAssetError(
            f"{raster_path.name} has no GeoTIFF georeferencing tags, "
            "so it cannot be placed on a map."
        )

    return values, extent, resolution, _epsg_from_geokeys(tags)


def decimate_for_display(values, *, max_dim: int = MAX_DISPLAY_DIM):
    """Nearest-neighbour decimation for display; returns (array, step)."""
    height, width = values.shape
    step = max(1, int(np.ceil(max(height, width) / max_dim)))
    if step == 1:
        return values, step
    return values[::step, ::step], step


def cell_centres(extent, shape):
    """Cell-centre longitude/latitude arrays for a grid on ``extent``."""
    height, width = shape
    left, right, bottom, top = extent
    lons = left + (np.arange(width) + 0.5) * ((right - left) / width)
    lats = top - (np.arange(height) + 0.5) * ((top - bottom) / height)
    return lons, lats


# ---------------------------------------------------------------------------
# Route GeoJSON reading
# ---------------------------------------------------------------------------


def load_route_geojson(path):
    """Load a route GeoJSON file as a list of line segments.

    Returns a dict with ``segments`` (list of ``(lons, lats)``), ``n_segments``,
    ``length_m`` (summed OSM ``length`` attribute when present, else ``None``)
    and ``warnings``.

    Raises :class:`GeoAssetError` when the file is missing, is not valid
    GeoJSON, or contains no usable line geometry.
    """
    route_path = Path(path)
    if not route_path.is_file():
        raise GeoAssetError(f"Route file not found: {route_path}")

    try:
        payload = json.loads(route_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GeoAssetError(f"Could not parse {route_path.name}: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise GeoAssetError(f"{route_path.name} is not a GeoJSON FeatureCollection.")

    features = payload.get("features")
    if not isinstance(features, list):
        raise GeoAssetError(f"{route_path.name} has no feature list.")

    segments: list[tuple[list[float], list[float]]] = []
    warnings: list[str] = []
    skipped = 0
    total_length = 0.0
    has_length = False

    for feature in features:
        if not isinstance(feature, dict):
            skipped += 1
            continue

        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if geometry_type == "LineString":
            parts = [coordinates]
        elif geometry_type == "MultiLineString":
            parts = coordinates or []
        else:
            skipped += 1
            continue

        for part in parts:
            lons: list[float] = []
            lats: list[float] = []
            for pair in part or []:
                try:
                    lon = float(pair[0])
                    lat = float(pair[1])
                except (TypeError, ValueError, IndexError, KeyError):
                    continue
                if not (np.isfinite(lon) and np.isfinite(lat)):
                    continue
                lons.append(lon)
                lats.append(lat)
            if len(lons) >= 2:
                segments.append((lons, lats))
            else:
                skipped += 1

        properties = feature.get("properties") or {}
        length = properties.get("length")
        if isinstance(length, (int, float)) and np.isfinite(length):
            has_length = True
            total_length += float(length)

    if skipped:
        warnings.append(f"{skipped} feature(s) skipped (empty or unsupported geometry).")
    if not segments:
        raise GeoAssetError(
            f"{route_path.name} contains no usable line geometry "
            f"({len(features)} feature(s) present)."
        )

    return {
        "segments": segments,
        "n_segments": len(segments),
        "length_m": total_length if has_length else None,
        "warnings": warnings,
    }


def geometry_bounds(segments):
    """Return (min_lon, max_lon, min_lat, max_lat) for line segments."""
    lons = np.concatenate([np.asarray(seg[0], dtype=float) for seg in segments])
    lats = np.concatenate([np.asarray(seg[1], dtype=float) for seg in segments])
    return float(lons.min()), float(lons.max()), float(lats.min()), float(lats.max())


def load_json_file(path):
    """Load a small JSON file, raising :class:`GeoAssetError` on failure."""
    json_path = Path(path)
    if not json_path.is_file():
        raise GeoAssetError(f"File not found: {json_path}")
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GeoAssetError(f"Could not parse {json_path.name}: {exc}") from exc


# ---------------------------------------------------------------------------
# Map figure builders
# ---------------------------------------------------------------------------

# Approximates the matplotlib "terrain" colormap used by the analysis scripts.
ELEVATION_COLORSCALE = [
    (0.00, "#08306b"),
    (0.06, "#2171b5"),
    (0.12, "#6baed6"),
    (0.18, "#c6dbef"),
    (0.28, "#74c476"),
    (0.45, "#41ab5d"),
    (0.62, "#fdd835"),
    (0.78, "#d19a3f"),
    (0.92, "#9c5a2d"),
    (1.00, "#f7f7f7"),
]

# Hazard-class colours are the documented colours from scripts/13_classify_hazard.py
# (1 = Low, 2 = Moderate, 3 = High, 4 = Very High); code 0 is NoData.
HAZARD_CLASS_CODES = {1: "Low", 2: "Moderate", 3: "High", 4: "Very High"}

_MAP_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(8,16,28,0.6)",
    margin=dict(l=10, r=10, t=30, b=10),
)


def discrete_colorscale(colors: list[str]):
    """Build a Plotly colorscale that maps discrete class codes to colours."""
    count = len(colors)
    scale = []
    for index, color in enumerate(colors):
        lower = index / count
        upper = (index + 1) / count
        scale.append((lower, color))
        scale.append((max(upper - 1e-6, lower), color))
    return scale


def _cartesian_raster_layout(height: int, x_label: str, y_label: str) -> dict:
    return dict(
        height=height,
        **_MAP_LAYOUT,
        xaxis=dict(title=x_label, constrain="domain"),
        yaxis=dict(title=y_label, scaleanchor="x", scaleratio=1),
    )


def build_elevation_figure(values, extent, *, height: int = 560, epsg=None):
    """Build an interactive elevation map for a georeferenced raster."""
    if epsg is not None and epsg != 4326:
        raise GeoAssetError(
            f"Elevation raster is in EPSG:{epsg}, but longitude/latitude axes "
            "are assumed. Reprojection is not available in the dashboard."
        )

    display, step = decimate_for_display(values)
    display = np.where(np.isfinite(display), display, np.nan)

    finite = display[np.isfinite(display)]
    if finite.size == 0:
        raise GeoAssetError("Elevation raster contains no valid (non-NoData) pixels.")

    lons, lats = cell_centres(extent, display.shape)

    fig = go.Figure(
        go.Heatmap(
            z=display,
            x=lons,
            y=lats,
            colorscale=ELEVATION_COLORSCALE,
            zmin=float(finite.min()),
            zmax=float(np.percentile(finite, 98)),
            hoverongaps=False,
            colorbar=dict(title="Elevation<br>(source units)", thickness=14),
            hovertemplate=(
                "Lon %{x:.4f}<br>Lat %{y:.4f}<br>Elevation %{z:.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(**_cartesian_raster_layout(height, "Longitude", "Latitude"))
    return fig, step


def build_hazard_class_figure(
    values,
    extent,
    *,
    class_colors: list[str],
    height: int = 560,
    epsg=None,
):
    """Build a scenario hazard-class map using the documented class colours."""
    if epsg is not None and epsg != 4326:
        raise GeoAssetError(
            f"Hazard raster is in EPSG:{epsg}, but longitude/latitude axes "
            "are assumed. Reprojection is not available in the dashboard."
        )

    display, step = decimate_for_display(values)
    classes = np.where(display > 0, display, np.nan)

    if not np.isfinite(classes).any():
        raise GeoAssetError("Hazard raster contains no classified pixels (all NoData).")

    lons, lats = cell_centres(extent, classes.shape)

    fig = go.Figure(
        go.Heatmap(
            z=classes,
            x=lons,
            y=lats,
            colorscale=discrete_colorscale(class_colors),
            zmin=0.5,
            zmax=len(class_colors) + 0.5,
            showscale=False,
            hoverongaps=False,
            hovertemplate=(
                "Lon %{x:.4f}<br>Lat %{y:.4f}<br>Class code %{z:.0f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(**_cartesian_raster_layout(height, "Longitude", "Latitude"))
    return fig, step


def maplibre_available() -> bool:
    """True when the installed Plotly build provides maplibre map traces."""
    return hasattr(go, "Scattermap")


def _auto_zoom(min_lon, max_lon, min_lat, max_lat) -> float:
    span = max(max_lon - min_lon, max_lat - min_lat, 1e-6)
    zoom = float(np.log2(360.0 / span) - 1.2)
    return float(np.clip(zoom, 3.0, 15.0))


def _merged_line(segments):
    """Flatten route segments into one lon/lat pair of lists, split by None gaps."""
    lons: list = []
    lats: list = []
    for index, (segment_lons, segment_lats) in enumerate(segments):
        if index:
            lons.append(None)
            lats.append(None)
        lons.extend(float(value) for value in segment_lons)
        lats.extend(float(value) for value in segment_lats)
    return lons, lats


def build_route_figure(
    segments,
    *,
    height: int = 620,
    color: str = "#f97316",
    trace_name: str = "Evacuation route (experimental)",
    start=None,
    end=None,
    title: str | None = None,
):
    """Build a route map from real line geometry.

    ``start`` / ``end`` are optional ``(lon, lat)`` tuples (shown when the route
    summary provides them). Uses the OSM basemap when the Plotly build supports
    maplibre traces, otherwise falls back to a plain longitude/latitude plot so
    the geometry is still visible.
    """
    if not segments:
        raise GeoAssetError("No route segments to draw.")

    min_lon, max_lon, min_lat, max_lat = geometry_bounds(segments)
    center_lon = (min_lon + max_lon) / 2.0
    center_lat = (min_lat + max_lat) / 2.0

    fig = go.Figure()
    route_lons, route_lats = _merged_line(segments)

    if maplibre_available():
        fig.add_trace(
            go.Scattermap(
                lon=route_lons,
                lat=route_lats,
                mode="lines",
                line=dict(width=3, color=color),
                name=trace_name,
                hoverinfo="skip",
                showlegend=False,
            )
        )

        if start is not None and end is not None:
            fig.add_trace(
                go.Scattermap(
                    lon=[start[0], end[0]],
                    lat=[start[1], end[1]],
                    mode="markers+text",
                    marker=dict(size=13, color=["#22c55e", "#ef4444"]),
                    text=["Start (illustrative)", "Destination (illustrative)"],
                    textposition="top center",
                    textfont=dict(color="#e2e8f0", size=11),
                    name="Endpoints",
                    hovertemplate="%{text}<br>Lon %{lon:.4f}<br>Lat %{lat:.4f}<extra></extra>",
                    showlegend=False,
                )
            )

        fig.update_layout(
            height=height,
            **_MAP_LAYOUT,
            map=dict(
                style="open-street-map",
                center=dict(lon=center_lon, lat=center_lat),
                zoom=_auto_zoom(min_lon, max_lon, min_lat, max_lat),
            ),
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=route_lons,
                y=route_lats,
                mode="lines",
                line=dict(width=3, color=color),
                name=trace_name,
                hoverinfo="skip",
                showlegend=False,
            )
        )
        if start is not None and end is not None:
            fig.add_trace(
                go.Scatter(
                    x=[start[0], end[0]],
                    y=[start[1], end[1]],
                    mode="markers+text",
                    marker=dict(size=12, color=["#22c55e", "#ef4444"]),
                    text=["Start (illustrative)", "Destination (illustrative)"],
                    textposition="top center",
                    textfont=dict(color="#e2e8f0", size=11),
                    name="Endpoints",
                    showlegend=False,
                )
            )
        fig.update_layout(**_cartesian_raster_layout(height, "Longitude", "Latitude"))

    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=14)))

    return fig
