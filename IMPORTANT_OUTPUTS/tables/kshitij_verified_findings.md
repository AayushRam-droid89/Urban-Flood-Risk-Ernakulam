# Kshitij — Scenario and Supporting Analysis

## Scripts executed
- `scripts/04_plot_flood_scenarios.py`
- `scripts/11_analyse_rainfall.py`

## Flood scenario comparison
The scenario comparison figure was generated successfully at `outputs/maps/flood_scenario_comparison_v2.png`. The 10-, 25- and 50-year rasters use a shared colour scale of 14–791.

**Limitation:** Raster units and physical meaning have not yet been verified from source metadata. Do not interpret the values as flood probabilities or water depths without confirmation.

## Rainfall analysis
Input: `data/processed/rainfall_stations_ernakulam.csv`

The script processed 8,910 records across six stations. It reported zero invalid dates, missing/non-numeric rainfall values, negative rainfall records and duplicate station-date records.

- Piravam had the highest mean observed daily rainfall: approximately 30.10 mm.
- Vannapuram had the highest recorded single-day rainfall: 295.2 mm.
- The dataset contains 64 station-year summaries.
- Zero station-years met the script's 80% daily observation coverage threshold.

## Outputs
- `outputs/maps/flood_scenario_comparison_v2.png`
- `outputs/maps/rainfall_station_comparison.png`
- `outputs/maps/rainfall_annual_observations.png`
- `data/processed/rainfall_station_summary.csv`
- `data/processed/rainfall_annual_summary.csv`

## Limitations and reporting caveats
The rainfall data have incomplete daily coverage. Observed rainfall sums must not be presented as complete annual totals, and the results do not establish long-term rainfall trends. The 80% threshold is an analysis threshold, not an official meteorological standard.

The flood raster units and interpretation remain unverified. Scenario comparisons should be presented with this caveat until the source metadata are checked.

## Handover status
Figures and summary CSVs have been generated. Outputs should be reviewed before inclusion in the final technical report.
