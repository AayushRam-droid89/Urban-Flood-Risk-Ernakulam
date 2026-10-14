# Urban Flood Risk and Emergency Evacuation Planning

**Study Area:** Ernakulam District, Kerala, India  
**Project Type:** Complex Engineering Problem (CEP)

## Project Overview

This project analyzes flood-hazard scenarios and elevation data to support urban flood-risk assessment and emergency evacuation planning in Ernakulam, Kerala.

## Current Features

- Flood-hazard scenario analysis for 10-, 25-, and 50-year return periods
- Raster alignment and common-coverage analysis
- Relative hazard index generation and classification
- Elevation analysis
- Rainfall station data analysis
- OpenStreetMap road-network analysis
- Basic shortest-distance evacuation route generation

## Project Structure

- `data/raw/` — Original datasets
- `data/processed/` — Processed raster layers and CSV summaries
- `scripts/` — Python scripts for analysis
- `outputs/maps/` — Generated maps
- `outputs/` — Route outputs and summaries
- `requirements.txt` — Python dependencies

## Setup

Use Python 3.14 only if all dependencies support it; otherwise, use a compatible Python version.

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run scripts from the project root in numerical order where applicable.

## Important Limitations

- The current study extent is based on raster coverage and has not yet been confirmed against the official Ernakulam district boundary.
- Flood-raster values have not been verified as calibrated flood depths or probabilities.
- Hazard classes are preliminary relative-index classes, not official KSDMA classifications.
- The current evacuation route minimizes distance; it is not yet a validated flood-safe route.
- Rainfall observations have incomplete coverage and should be interpreted cautiously.

## Team Workflow

Each team member should work on their assigned component, document the methods used, preserve the original datasets, and submit scripts and outputs for integration.

## Status

Initial data preparation, preliminary hazard analysis, map generation, and basic road-network routing have been completed. Further integration, validation, and documentation remain.