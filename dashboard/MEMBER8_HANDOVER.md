# Member 8 — Dashboard Integration Handover

**Author:** Rohit Subramani (Member 8)
**Task:** Integrate elevation, rainfall, evacuation-route and scenario selection into the
existing Streamlit dashboard started by Member 7 (Rehan Aditya), without replacing it.

---

## 1. Exact command to run the dashboard

From the repository root (`Urban-Flood-Risk-Ernakulam/`):

```bash
python -m pip install -r dashboard/requirements-dashboard.txt
python -m streamlit run dashboard/app.py
```

Then open <http://localhost:8501>.

Sections can be deep-linked, e.g. `http://localhost:8501/?section=Elevation`
(valid values: `Overview`, `Flood scenario maps`, `Hazard classification`, `Elevation`,
`Rainfall analysis`, `Evacuation route`, `Limitations`).

---

## 2. Files changed / added

| File | Status | What changed |
|---|---|---|
| `dashboard/paths.py` | **rewritten** | Central path resolver. All paths derived from `ROOT = Path(__file__).resolve().parent.parent` (no absolute/hardcoded paths). Adds scenario identifiers, hazard-class rasters, elevation raster, rainfall CSVs/plots, route GeoJSON/summary paths. |
| `dashboard/map_utils.py` | **modified (extended)** | Preserved Rehan's `split_scenario_panels()` / `panel_to_bytes()`. Added GeoTIFF reading, rasters→Plotly figures, route GeoJSON loading, and `GeoAssetError`. |
| `dashboard/app.py` | **modified (extended)** | Preserved Rehan's structure/theme; added the Elevation, Rainfall, Evacuation-route and Hazard-class-map sections, the sidebar scenario selector, filters and error/empty states. |
| `dashboard/requirements-dashboard.txt` | **modified** | `plotly>=6.0.0` added (needed for maplibre `go.Scattermap`); `numpy`, `Pillow` pinned. |
| `README.md` | **modified** | `dashboard/` added to Project Structure; run instructions corrected; note on the scenario selector and `?section=` links. |
| `outputs/dashboard/*.png` | **new** | 6 dashboard screenshots (see §6). |
| `dashboard/MEMBER8_HANDOVER.md` | **new** | This file. |

**Not touched:** `dashboard/components.py` (was and remains empty), everything under `scripts/`,
`data/`, all pre-existing files under `outputs/`, `requirements.txt`, and other members' outputs.

---

## 3. Components integrated

### A. Elevation
- Source: `data/processed/aligned_elevation_ernakulam.tif` — 798 × 604 px (w × h), **EPSG:4326**,
  georeferenced via GeoTIFF `ModelPixelScale` (33550) + `ModelTiepoint` (33922) tags.
- Rendered as an interactive Plotly raster heatmap using the raster's own extent
  (left `76.162955`, top `10.295058`, bottom `9.791725`, right `76.827955`).
- Metrics row (valid pixels / min / median / max) + the two pre-existing PNG figures
  (`aligned_elevation_ernakulam.png`, `elevation_dem.png`) in an expander.
- Units are labelled **"source units"**, not metres (see §7).

### B. Rainfall
- Sources: `data/processed/rainfall_station_summary.csv` (6 stations),
  `data/processed/rainfall_annual_summary.csv` (64 station-years),
  plus the existing figures `rainfall_station_comparison.png` / `rainfall_annual_observations.png`.
- Existing figures are displayed, and interactive Plotly charts are built from those CSVs
  (mean observed daily rainfall per station, observation-day counts, coverage % per station-year
  with an 80 % threshold line, observed sums per station-year).
- **Integrity:** a prominent caveat states the record is temporally incomplete and that
  *"observed sums"* are **not** annual totals; no interpolation or zero-filling.
  (Verified: 0 of 64 station-years meet the script's 80 % coverage threshold.)
- Filters: station multi-select + year-range slider, driving the charts and a downloadable table.

### C. Evacuation route
- Sources: `outputs/evacuation_route.geojson` (147 segments, ~14.544 km) and
  `outputs/flood_aware_route.geojson` (125 segments, ~14.754 km), plus their `*_summary.json`
  and `outputs/route_comparison.csv`.
- Geometry is read from the GeoJSON (EPSG:4326 lon/lat) and drawn as a single merged maplibre
  trace with correct coordinates. Summary metrics are shown **only for fields actually present**
  in the summary JSON.
- A persistent warning box marks the route as **experimental and unvalidated for flood safety**.
  The dashboard never generates a route and never claims it is flood-safe.

### D. Scenario selection & filters
- Sidebar selector offers the repository's actual scenario identifiers: `10year`, `25year`,
  `50year` (displayed as 10-/25-/50-year; default 50-year).
- Changing it updates the flood-map panel, the hazard bar charts and the interactive
  hazard-class map.
- Documented hazard classes/colours preserved exactly as in `scripts/13_classify_hazard.py`:
  `1 Low #2ca25f`, `2 Moderate #fee08b`, `3 High #fc8d59`, `4 Very High #d73027`, `0` = NoData.

### E. Error / empty / invalid states
- Missing file → names the exact file and the script that generates it.
- Empty data → "contains headers but no data records" / "No records found".
- Malformed/unreadable input → reported in an error box; the rest of the app keeps working.
- No silent zeros, fabricated records or synthetic routes anywhere.

---

## 4. Dependencies added / changed

| Package | Pin | Why |
|---|---|---|
| `plotly` | `>=6.0.0` | **Added.** maplibre `go.Scattermap` traces for the route map. Older Plotly falls back to a plain lon/lat plot. |
| `streamlit` | `>=1.32.0` | Unchanged. |
| `pandas` | `>=2.0.0` | Unchanged. |
| `numpy` | `>=1.24.0` | Explicit pin (was implicit). |
| `Pillow` | `>=10.0.0` | Explicit pin — used to read GeoTIFF band data + georeferencing tags. |

`requirements.txt` (the analysis pipeline) was **not** changed. No `rasterio`/`geopandas`
dependency was added; GeoTIFF reading is done with Pillow so the dashboard installs without GDAL.

---

## 5. Tests executed and actual results

All commands were run from the repository root on 2026-10-17 with Streamlit 1.66.0 / Plotly 7.1.0 /
pandas 3.0.6 / numpy 2.5.3 / Pillow 12.3.0, Python on Windows.

| # | Test | Result |
|---|---|---|
| 1 | **Unit/smoke suite** (`map_utils` + `paths`): raster read/extent/CRS, figure build + JSON serialisation, all 3 hazard rasters + documented colours, both route GeoJSONs, route figure, 7 error cases (missing file, malformed JSON, empty FeatureCollection, unsupported Point geometry, RGB PNG, TIFF without geotags), rainfall CSV loads, 80 %-coverage check, year span | **31/31 PASS — "FAILURES: none"** |
| 2 | **Functional suite** using Streamlit's official `AppTest` framework: boot, all 7 sections, all 3 scenarios × 2 scenario-driven sections, scenario caption actually changes, flood-map tabs/images, hazard charts+table, elevation metrics+chart+EPSG caption, rainfall charts+figures+caveats, station/year filters (including clearing all stations and single-year), route radio with 2 sources + source switching, limitations text | **63 checks, 0 failures (EXIT 0)** |
| 3 | **Fault injection — missing files** (all 21 assets redirected to non-existent paths; all 7 sections re-run) | **0 failures**, 0 exceptions; each section names the missing file |
| 4 | **Fault injection — empty data** (header-only CSVs, empty `FeatureCollection`) | **0 failures**, 0 exceptions; "no data records" / "no usable line geometry" messages shown |
| 5 | **Fault injection — malformed input** (binary-garbage CSVs, truncated JSON) | **0 failures**, 0 exceptions; problems reported, app keeps running |
| 6 | **Server start** (`python -m streamlit run dashboard/app.py`, port 8502) | Clean log — no traceback. `/_stcore/health` → **200 ok**, `/` → **200** |
| 7 | **Screenshots** via headless Chrome against the live server | 6 PNGs rendered; pairwise mean pixel difference 14.1–127.4, confirming each section rendered distinct content |

> Note: `rasterio`, `geopandas`, `kaleido`, `playwright` and `selenium` were **not installed** in the
> test environment. Test #7 therefore used headless Chrome (installed) rather than a Python
> screenshot library, and interactive behaviour was verified with Streamlit's `AppTest`
> framework rather than a browser automation library.

---

## 6. Screenshots

Saved in `outputs/dashboard/` (taken at 1600 × 1400 from the running dashboard):

| File | Section |
|---|---|
| `outputs/dashboard/overview.png` | Overview |
| `outputs/dashboard/scenario_maps.png` | Flood scenario maps |
| `outputs/dashboard/hazard.png` | Hazard classification (interactive map + charts) |
| `outputs/dashboard/elevation.png` | Elevation |
| `outputs/dashboard/rainfall.png` | Rainfall analysis |
| `outputs/dashboard/route.png` | Evacuation route (experimental) |

---

## 7. Missing data, assumptions and remaining limitations

1. **GeoTIFF reader is Pillow-based.** It supports single-band rasters carrying
   `ModelPixelScale` + `ModelTiepoint` tags. Rasters **not** in EPSG:4326 are refused with a
   clear message because no reprojection library is available in-dashboard. If `rasterio` is
   installed later, `read_geotiff_band()` in `dashboard/map_utils.py` is the single place to
   upgrade.
2. **Elevation units are unverified.** `scripts/10_align_elevation.py` carries values over in
   "source units"; the dashboard does not assert metres. Values range roughly −7.9 to 147.5
   over 57,612 valid pixels.
3. **Elevation/hazard display is decimated** (nearest neighbour, never averaged) to ≈420 px max
   dimension, purely for rendering. Statistics are computed on the **full** raster.
4. **Rainfall record is incomplete.** No station-year reaches 80 % daily coverage, so all
   annual figures are partial sums. This is stated in the UI and in the Limitations section.
5. **Route basemap needs internet.** The maplibre trace uses OpenStreetMap tiles; offline the
   geometry still renders but without a basemap.
6. **Route is unvalidated.** Experimental only — never to be presented as flood-safe.
7. **`use_container_width` deprecation warnings** are emitted by Streamlit 1.66.0
   ("will be removed after 2025-12-31"). They are non-blocking. They were left as-is to keep
   compatibility with the declared `streamlit>=1.32.0` pin; migrating to `width="stretch"`
   requires raising the Streamlit floor to ≈1.45.
8. **No automated test file was added to the repository**; the harness lived outside the repo
   (see §8). Recreate with `streamlit.testing.v1.AppTest` if a permanent suite is wanted.

---

## 8. Integration points for the next team member

- **Path changes:** edit `dashboard/paths.py` only. Every asset path is defined there; nothing
  else hardcodes a path. `ROOT` is derived from the file location, so the app works from any
  checkout on any machine.
- **New raster:** add the path in `paths.py`, then call `read_geotiff_band()` +
  `build_elevation_figure()` / `build_hazard_class_figure()` from `map_utils.py`.
- **New/renamed route output:** add the path in `paths.py` and an entry in
  `_route_source_options()` in `app.py`. If a newer route summary carries a
  `validation`/`method` field, `_render_route_summary()` already surfaces any field it finds —
  revisit the "experimental" wording only if documented validation exists.
- **If the hazard-class definitions change:** update `CLASS_ORDER` / `CLASS_COLORS` in
  `app.py` **and** `HAZARD_CLASS_CODES` in `map_utils.py` together, so the legend and the
  rendered colours stay consistent with `scripts/13_classify_hazard.py`.
- **If `rasterio` becomes available:** upgrading `read_geotiff_band()` is the only change needed
  to support non-EPSG:4326 rasters and to drop the Pillow tag parsing.
- **Do not** regenerate or edit anything under `scripts/`, `data/` or the pre-existing
  `outputs/` files from the dashboard — it is strictly a read-only consumer of those outputs.
