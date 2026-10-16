"""Resolve project asset paths relative to the repository root.

All paths are derived from the repository location so the dashboard works
from any checkout on any machine (no hardcoded absolute paths).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repository root (Urban-Flood-Risk-Ernakulam)

# ---------------------------------------------------------------------------
# Hazard / flood rasters and summaries
# ---------------------------------------------------------------------------
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUTS_DIR = ROOT / "outputs"
MAPS_DIR = OUTPUTS_DIR / "maps"
DASHBOARD_OUTPUT_DIR = OUTPUTS_DIR / "dashboard"

HAZARD_SUMMARY_CSV = PROCESSED_DIR / "hazard_class_summary.csv"

FLOOD_COMPARISON_MAP = MAPS_DIR / "flood_scenario_comparison_v2.png"
FLOOD_COMPARISON_FALLBACK = MAPS_DIR / "flood_scenario_comparison.png"
ALIGNED_FLOOD_MAP = MAPS_DIR / "aligned_flood_scenarios.png"

# Scenario identifiers used by the analysis scripts (scripts/13_classify_hazard.py)
SCENARIO_LABELS = ("10-year", "25-year", "50-year")
SCENARIO_KEYS = {"10-year": "10year", "25-year": "25year", "50-year": "50year"}

HAZARD_CLASS_RASTERS = {
    key: PROCESSED_DIR / f"hazard_classes_{key}.tif" for key in SCENARIO_KEYS.values()
}

# ---------------------------------------------------------------------------
# Elevation
# ---------------------------------------------------------------------------
ELEVATION_RASTER = PROCESSED_DIR / "aligned_elevation_ernakulam.tif"
ELEVATION_MAP_PNG = MAPS_DIR / "aligned_elevation_ernakulam.png"
ELEVATION_DEM_PNG = MAPS_DIR / "elevation_dem.png"

# ---------------------------------------------------------------------------
# Rainfall
# ---------------------------------------------------------------------------
RAINFALL_STATION_CSV = PROCESSED_DIR / "rainfall_station_summary.csv"
RAINFALL_ANNUAL_CSV = PROCESSED_DIR / "rainfall_annual_summary.csv"
RAINFALL_STATION_PLOT = MAPS_DIR / "rainfall_station_comparison.png"
RAINFALL_ANNUAL_PLOT = MAPS_DIR / "rainfall_annual_observations.png"

# ---------------------------------------------------------------------------
# Evacuation routing (experimental)
# ---------------------------------------------------------------------------
ROUTE_GEOJSON = OUTPUTS_DIR / "evacuation_route.geojson"
ROUTE_SUMMARY_JSON = OUTPUTS_DIR / "evacuation_route_summary.json"

SHORTEST_ROUTE_GEOJSON = OUTPUTS_DIR / "shortest_route.geojson"
FLOOD_AWARE_ROUTE_GEOJSON = OUTPUTS_DIR / "flood_aware_route.geojson"
FLOOD_AWARE_ROUTE_SUMMARY_JSON = OUTPUTS_DIR / "flood_aware_route_summary.json"
ROUTE_COMPARISON_CSV = OUTPUTS_DIR / "route_comparison.csv"

ROUTE_MAP_PNG = MAPS_DIR / "shortest_evacuation_route.png"
ROUTE_COMPARISON_MAP_PNG = MAPS_DIR / "evacuation_route_comparison.png"
