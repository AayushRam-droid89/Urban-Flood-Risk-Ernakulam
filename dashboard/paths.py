"""Resolve project asset paths relative to the repository root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repository root (Urban-Flood-Risk-Ernakulam)

HAZARD_SUMMARY_CSV = ROOT / "data" / "processed" / "hazard_class_summary.csv"
MAPS_DIR = ROOT / "outputs" / "maps"

FLOOD_COMPARISON_MAP = MAPS_DIR / "flood_scenario_comparison_v2.png"
FLOOD_COMPARISON_FALLBACK = MAPS_DIR / "flood_scenario_comparison.png"
ALIGNED_FLOOD_MAP = MAPS_DIR / "aligned_flood_scenarios.png"

RAINFALL_STATION_PLOT = MAPS_DIR / "rainfall_station_comparison.png"
RAINFALL_ANNUAL_PLOT = MAPS_DIR / "rainfall_annual_observations.png"

SCENARIO_LABELS = ("10-year", "25-year", "50-year")
