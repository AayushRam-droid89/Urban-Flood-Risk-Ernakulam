"""
Urban Flood Risk — Ernakulam interactive dashboard.

Reads the existing project outputs (rasters, CSVs, GeoJSON, PNG maps) and
presents them. It never recalculates hazard classes, rainfall statistics or
routes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

_DASHBOARD_DIR = Path(__file__).resolve().parent
if str(_DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_DIR))

from map_utils import (  # noqa: E402
    GeoAssetError,
    build_elevation_figure,
    build_hazard_class_figure,
    build_route_figure,
    load_json_file,
    load_route_geojson,
    maplibre_available,
    panel_to_bytes,
    read_geotiff_band,
    split_scenario_panels,
)
from paths import (  # noqa: E402
    ALIGNED_FLOOD_MAP,
    DASHBOARD_OUTPUT_DIR,
    ELEVATION_DEM_PNG,
    ELEVATION_MAP_PNG,
    ELEVATION_RASTER,
    FLOOD_AWARE_ROUTE_GEOJSON,
    FLOOD_AWARE_ROUTE_SUMMARY_JSON,
    FLOOD_COMPARISON_FALLBACK,
    FLOOD_COMPARISON_MAP,
    HAZARD_CLASS_RASTERS,
    HAZARD_SUMMARY_CSV,
    MAPS_DIR,
    RAINFALL_ANNUAL_CSV,
    RAINFALL_ANNUAL_PLOT,
    RAINFALL_STATION_CSV,
    RAINFALL_STATION_PLOT,
    ROOT,
    ROUTE_COMPARISON_CSV,
    ROUTE_COMPARISON_MAP_PNG,
    ROUTE_GEOJSON,
    ROUTE_MAP_PNG,
    ROUTE_SUMMARY_JSON,
    SCENARIO_KEYS,
    SCENARIO_LABELS,
)

# Match hazard-class colours from scripts/13_classify_hazard.py
CLASS_ORDER = ["Low", "Moderate", "High", "Very High"]
CLASS_COLORS = {
    "Low": "#2ca25f",
    "Moderate": "#fee08b",
    "High": "#fc8d59",
    "Very High": "#d73027",
}
CLASS_COLORS_LIST = [CLASS_COLORS[name] for name in CLASS_ORDER]

SCENARIO_DISPLAY = {
    "10year": "10-year",
    "25year": "25-year",
    "50year": "50-year",
}

SECTIONS = (
    "Overview",
    "Flood scenario maps",
    "Hazard classification",
    "Elevation",
    "Rainfall analysis",
    "Evacuation route",
    "Limitations",
)


def rel(path: Path) -> str:
    """Repository-relative path for display."""
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');

        html, body, [class*="css"] {
            font-family: "DM Sans", sans-serif;
        }

        .stApp {
            background: linear-gradient(180deg, #07111f 0%, #0c1a2e 45%, #0a1628 100%);
            color: #e8eef7;
        }

        [data-testid="stSidebar"] {
            background-color: #081018;
            border-right: 1px solid #1e3a5f;
        }

        [data-testid="stSidebar"] * {
            color: #c9d6e8 !important;
        }

        .hero {
            padding: 1.5rem 0 2rem 0;
        }

        .hero h1 {
            font-size: 2.35rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin: 0 0 0.35rem 0;
            background: linear-gradient(90deg, #7dd3fc, #38bdf8 40%, #a5f3fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero p {
            font-size: 1.05rem;
            color: #94a3b8;
            max-width: 52rem;
            line-height: 1.55;
            margin: 0;
        }

        .metric-card {
            background: rgba(15, 32, 56, 0.85);
            border: 1px solid #1e3a5f;
            border-radius: 12px;
            padding: 1rem 1.15rem;
            min-height: 5.5rem;
        }

        .metric-card .label {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #64748b;
            margin-bottom: 0.35rem;
        }

        .metric-card .value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #f1f5f9;
        }

        .metric-card .hint {
            font-size: 0.82rem;
            color: #94a3b8;
            margin-top: 0.25rem;
        }

        .section-title {
            font-size: 1.35rem;
            font-weight: 600;
            color: #e2e8f0;
            margin: 2rem 0 0.75rem 0;
            padding-bottom: 0.35rem;
            border-bottom: 1px solid #1e3a5f;
        }

        .limitation-box {
            background: rgba(120, 53, 15, 0.25);
            border: 1px solid #92400e;
            border-radius: 10px;
            padding: 1rem 1.25rem;
            color: #fde68a;
            line-height: 1.55;
        }

        .experimental-box {
            background: rgba(120, 53, 15, 0.25);
            border: 1px solid #b45309;
            border-left: 4px solid #f59e0b;
            border-radius: 10px;
            padding: 0.85rem 1.1rem;
            color: #fde68a;
            line-height: 1.5;
            margin-bottom: 0.75rem;
        }

        .legend-row {
            display: flex;
            flex-wrap: wrap;
            gap: 1.1rem;
            align-items: center;
            margin: 0.25rem 0 0.5rem 0;
            font-size: 0.9rem;
            color: #cbd5e1;
        }

        .legend-swatch {
            display: inline-block;
            width: 0.85rem;
            height: 0.85rem;
            border-radius: 3px;
            border: 1px solid #0b1a2b;
            margin-right: 0.4rem;
            vertical-align: -0.08rem;
        }

        div[data-testid="stMetric"] {
            background: rgba(15, 32, 56, 0.85);
            border: 1px solid #1e3a5f;
            border-radius: 12px;
            padding: 0.75rem 1rem;
        }

        div[data-testid="stMetric"] label {
            color: #94a3b8 !important;
        }

        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #f8fafc !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hazard_legend_html() -> str:
    swatches = "".join(
        f'<span><span class="legend-swatch" style="background:{CLASS_COLORS[name]};"></span>'
        f"{name}</span>"
        for name in CLASS_ORDER
    )
    codes = " · ".join(f"{index} = {name}" for index, name in enumerate(CLASS_ORDER, start=1))
    return (
        f'<div class="legend-row">{swatches}'
        f'<span style="color:#64748b;">Class codes: {codes} · 0 = NoData / outside valid area</span>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def load_hazard_summary() -> pd.DataFrame:
    df = pd.read_csv(HAZARD_SUMMARY_CSV)
    df["scenario_label"] = df["scenario"].map(SCENARIO_DISPLAY)
    df["class"] = pd.Categorical(df["class"], categories=CLASS_ORDER, ordered=True)
    return df.sort_values(["scenario", "class"])


@st.cache_data(show_spinner=False)
def load_raster(path_str: str):
    return read_geotiff_band(path_str)


@st.cache_data(show_spinner=False)
def load_route(path_str: str):
    return load_route_geojson(path_str)


@st.cache_data(show_spinner=False)
def load_json(path_str: str):
    return load_json_file(path_str)


@st.cache_data(show_spinner=False)
def load_csv(path_str: str, numeric_columns: tuple[str, ...]) -> pd.DataFrame:
    df = pd.read_csv(path_str)
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


RAINFALL_STATION_NUMERIC = (
    "observation_days",
    "mean_observed_daily_mm",
    "median_observed_daily_mm",
    "maximum_observed_daily_mm",
    "latitude",
    "longitude",
    "years_observed",
)
RAINFALL_ANNUAL_NUMERIC = (
    "Year",
    "observation_days",
    "mean_observed_daily_mm",
    "median_observed_daily_mm",
    "maximum_observed_daily_mm",
    "observed_rainfall_sum_mm",
    "calendar_days",
    "coverage_fraction",
    "coverage_percent",
)


@st.cache_data(show_spinner=False)
def load_rainfall_station_summary() -> pd.DataFrame:
    return load_csv(str(RAINFALL_STATION_CSV), RAINFALL_STATION_NUMERIC)


@st.cache_data(show_spinner=False)
def load_rainfall_annual_summary() -> pd.DataFrame:
    return load_csv(str(RAINFALL_ANNUAL_CSV), RAINFALL_ANNUAL_NUMERIC)


def dark_layout(fig, *, height: int | None = None, legend_title: str | None = None):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,16,28,0.6)",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    if height is not None:
        fig.update_layout(height=height)
    if legend_title is not None:
        fig.update_layout(legend_title_text=legend_title)
    return fig


def resolve_flood_map_path() -> Path | None:
    if FLOOD_COMPARISON_MAP.is_file():
        return FLOOD_COMPARISON_MAP
    if FLOOD_COMPARISON_FALLBACK.is_file():
        return FLOOD_COMPARISON_FALLBACK
    if ALIGNED_FLOOD_MAP.is_file():
        return ALIGNED_FLOOD_MAP
    return None


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


def render_overview(hazard_df: pd.DataFrame | None) -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Urban Flood Risk in Ernakulam</h1>
            <p>
                Open, exploratory view of flood-hazard scenarios, relative hazard classes,
                elevation, rainfall context and an experimental evacuation route for the
                Ernakulam study extent — inspired by transparent flood atlases such as
                <a href="https://flood.neer.io/" target="_blank" style="color:#38bdf8;">India Flood Atlas (NEER)</a>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if hazard_df is not None and not hazard_df.empty:
        latest = hazard_df[hazard_df["scenario"] == "50year"]
        high_vh_value = (
            f"{latest[latest['class'].isin(['High', 'Very High'])]['percent_of_valid_pixels'].sum():.1f}%"
        )
        high_vh_hint = "Share of valid raster pixels"
    else:
        high_vh_value = "n/a"
        high_vh_hint = "Hazard summary CSV unavailable"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            """
            <div class="metric-card">
                <div class="label">Return periods</div>
                <div class="value">3</div>
                <div class="hint">10-, 25-, 50-year scenarios</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="metric-card">
                <div class="label">Hazard classes</div>
                <div class="value">4</div>
                <div class="hint">Low → Very High (relative index)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="label">50-year High + Very High</div>
                <div class="value">{high_vh_value}</div>
                <div class="hint">{high_vh_hint}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            """
            <div class="metric-card">
                <div class="label">Study area</div>
                <div class="value">Ernakulam</div>
                <div class="hint">Kerala, India · CEP project</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(
        "Sections: flood scenario maps · hazard classification · elevation · rainfall · "
        "experimental evacuation route. Use the sidebar scenario selector to change the scenario."
    )


# ---------------------------------------------------------------------------
# Flood scenario maps
# ---------------------------------------------------------------------------


def render_flood_maps(scenario_label: str) -> None:
    st.markdown('<div class="section-title">Flood scenario maps</div>', unsafe_allow_html=True)
    map_path = resolve_flood_map_path()

    if map_path is None:
        st.error(
            f"No flood comparison map found under `{rel(MAPS_DIR)}`. "
            "Expected `flood_scenario_comparison_v2.png`, `flood_scenario_comparison.png` "
            "or `aligned_flood_scenarios.png` (generated by `scripts/04_plot_flood_scenarios.py`)."
        )
        return

    st.caption(
        f"Panels extracted from `{rel(map_path)}` "
        "(shared colour scale across scenarios; raster units not verified against source metadata)."
    )

    try:
        panels = split_scenario_panels(map_path)
    except OSError as exc:
        st.error(f"Could not load map image `{map_path.name}`: {exc}")
        return

    if len(panels) != len(SCENARIO_LABELS):
        st.error(
            f"Expected {len(SCENARIO_LABELS)} panels in `{map_path.name}`, "
            f"found {len(panels)}. The file may not be a 1×3 comparison figure."
        )
        return

    index = list(SCENARIO_LABELS).index(scenario_label)
    st.image(
        panels[index],
        caption=f"{scenario_label} return period — selected in the sidebar",
        use_container_width=True,
    )

    with st.expander(f"All {len(SCENARIO_LABELS)} scenario panels"):
        tabs = st.tabs(list(SCENARIO_LABELS))
        for tab, label, panel in zip(tabs, SCENARIO_LABELS, panels):
            with tab:
                st.image(panel, use_container_width=True, caption=f"{label} return period")

    st.download_button(
        label=f"Download {scenario_label} panel (PNG)",
        data=panel_to_bytes(panels[index]),
        file_name=f"flood_{scenario_label.replace('-', '_')}.png",
        mime="image/png",
        key="dl_selected_panel",
    )

    with st.expander("Full comparison figure"):
        st.image(str(map_path), use_container_width=True)
        with open(map_path, "rb") as handle:
            st.download_button(
                label=f"Download {map_path.name}",
                data=handle.read(),
                file_name=map_path.name,
                mime="image/png",
                key="dl_full_comparison",
            )


# ---------------------------------------------------------------------------
# Hazard classification
# ---------------------------------------------------------------------------


def render_hazard_charts(hazard_df: pd.DataFrame | None, scenario_label: str) -> None:
    st.markdown('<div class="section-title">Hazard classification</div>', unsafe_allow_html=True)

    if hazard_df is None:
        st.error(
            f"Missing hazard summary CSV: `{rel(HAZARD_SUMMARY_CSV)}`. "
            "Generate it with `scripts/13_classify_hazard.py`."
        )
        return

    if hazard_df.empty:
        st.warning(f"No records found in `{rel(HAZARD_SUMMARY_CSV)}`.")
        return

    required = {"scenario", "class", "pixel_count", "percent_of_valid_pixels"}
    missing = sorted(required - set(hazard_df.columns))
    if missing:
        st.error(
            f"`{rel(HAZARD_SUMMARY_CSV)}` is missing required column(s): "
            + ", ".join(f"`{name}`" for name in missing)
        )
        return

    scenario_key = SCENARIO_KEYS[scenario_label]
    st.caption(
        f"Source: `{rel(HAZARD_SUMMARY_CSV)}` · selected scenario: **{scenario_label}** · "
        "classes are preliminary relative-index classes (not official KSDMA designations)."
    )

    left, right = st.columns([3, 2])
    with left:
        st.markdown(f"**{scenario_label} scenario**")
        selected = hazard_df[hazard_df["scenario"] == scenario_key]
        if selected.empty:
            st.warning(
                f"No rows for scenario `{scenario_key}` in `{rel(HAZARD_SUMMARY_CSV)}`."
            )
        else:
            fig = px.bar(
                selected,
                x="class",
                y="percent_of_valid_pixels",
                color="class",
                category_orders={"class": CLASS_ORDER},
                color_discrete_map=CLASS_COLORS,
                labels={"percent_of_valid_pixels": "% of valid pixels", "class": "Hazard class"},
                text="percent_of_valid_pixels",
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(showlegend=False)
            st.plotly_chart(dark_layout(fig, height=380), use_container_width=True)

    with right:
        st.markdown("**All scenarios (share of valid pixels)**")
        compare = hazard_df.copy()
        compare["scenario_label"] = compare["scenario_label"].astype(str)
        fig_all = px.bar(
            compare,
            x="scenario_label",
            y="percent_of_valid_pixels",
            color="class",
            category_orders={"class": CLASS_ORDER, "scenario_label": list(SCENARIO_DISPLAY.values())},
            color_discrete_map=CLASS_COLORS,
            labels={
                "scenario_label": "Return period",
                "percent_of_valid_pixels": "% of valid pixels",
                "class": "Hazard class",
            },
            barmode="stack",
        )
        st.plotly_chart(
            dark_layout(fig_all, height=380, legend_title="Class"), use_container_width=True
        )

    st.dataframe(
        hazard_df.assign(scenario=hazard_df["scenario_label"])[
            ["scenario", "class", "pixel_count", "percent_of_valid_pixels"]
        ].rename(columns={"scenario": "return_period"}),
        use_container_width=True,
        hide_index=True,
    )

    render_hazard_map(scenario_label)


def render_hazard_map(scenario_label: str) -> None:
    st.markdown("#### Interactive hazard-class map")
    st.markdown(hazard_legend_html(), unsafe_allow_html=True)

    scenario_key = SCENARIO_KEYS[scenario_label]
    raster_path = HAZARD_CLASS_RASTERS.get(scenario_key)

    if raster_path is None or not raster_path.is_file():
        st.warning(
            f"Hazard-class raster for the {scenario_label} scenario is not available: "
            f"`{rel(raster_path) if raster_path else 'unknown'}`. "
            "Expected files: "
            + ", ".join(f"`{rel(p)}`" for p in HAZARD_CLASS_RASTERS.values())
            + ". Generate them with `scripts/13_classify_hazard.py`."
        )
        return

    try:
        values, extent, resolution, epsg = load_raster(str(raster_path))
        fig, step = build_hazard_class_figure(
            values, extent, class_colors=CLASS_COLORS_LIST, epsg=epsg
        )
    except GeoAssetError as exc:
        st.error(f"Could not display `{rel(raster_path)}`: {exc}")
        return

    st.plotly_chart(fig, use_container_width=True)

    valid = values[values > 0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Valid classified pixels", f"{int(valid.size):,}")
    c2.metric("Grid", f"{values.shape[1]} × {values.shape[0]} px")
    c3.metric(
        "Pixel size",
        f"{resolution[0] * 111.32:.0f} m (approx.)" if epsg == 4326 else f"{resolution[0]:.5f}",
    )

    caption = (
        f"`{rel(raster_path)}` · EPSG:{epsg if epsg is not None else 'unknown'} · "
        "rendered with nearest-neighbour decimation (display only)"
    )
    if step > 1:
        caption += f", 1 pixel shown per {step}×{step} source pixels"
    st.caption(caption + ".")
    st.caption(
        "Class values are read directly from the processed raster; the dashboard does not "
        "reclassify or recompute hazard."
    )


# ---------------------------------------------------------------------------
# Elevation
# ---------------------------------------------------------------------------


def render_elevation() -> None:
    st.markdown('<div class="section-title">Elevation</div>', unsafe_allow_html=True)

    if not ELEVATION_RASTER.is_file():
        st.warning(
            f"Aligned elevation raster not available: `{rel(ELEVATION_RASTER)}`. "
            "Generate it with `scripts/10_align_elevation.py`."
        )
    else:
        try:
            values, extent, resolution, epsg = load_raster(str(ELEVATION_RASTER))
            fig, step = build_elevation_figure(values, extent, epsg=epsg)
        except GeoAssetError as exc:
            st.error(f"Could not display `{rel(ELEVATION_RASTER)}`: {exc}")
        else:
            finite = values[np.isfinite(values)]
            if finite.size == 0:
                st.warning(
                    f"`{rel(ELEVATION_RASTER)}` contains no valid (non-NoData) pixels, "
                    "so there is nothing to display."
                )
            else:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Valid pixels", f"{int(finite.size):,}")
                c2.metric("Minimum", f"{finite.min():.1f}")
                c3.metric("Median", f"{float(np.median(finite)):.1f}")
                c4.metric("Maximum", f"{finite.max():.1f}")

                st.plotly_chart(fig, use_container_width=True)

                crs_text = f"EPSG:{epsg}" if epsg is not None else "unknown CRS"
                caption = (
                    f"`{rel(ELEVATION_RASTER)}` · {crs_text} · "
                    f"grid {values.shape[1]} × {values.shape[0]} px"
                )
                if epsg == 4326:
                    caption += (
                        f" · pixel size ≈ {resolution[0] * 111.32:.0f} m "
                        f"({resolution[0]:.6f}° longitude)"
                    )
                if step > 1:
                    caption += f" · displayed with 1 pixel per {step}×{step} source pixels"
                st.caption(caption + ".")

                st.caption(
                    "Elevation values are the aligned DEM values carried over from the source DEM "
                    "(labelled “source units” by `scripts/10_align_elevation.py`; the units have not "
                    "been verified against the DEM metadata, and are assumed to be metres). The colour "
                    "scale uses the 2nd–98th percentile of valid pixels; values below sea level "
                    "(negative) appear in dark blue."
                )

    samples = [(ELEVATION_MAP_PNG, "Aligned DEM map (existing figure)"), (ELEVATION_DEM_PNG, "Source DEM map (existing figure)")]
    available = [(path, label) for path, label in samples if path.is_file()]
    if available:
        with st.expander("Existing elevation figures generated by the analysis scripts"):
            for path, label in available:
                st.image(str(path), caption=f"{label} — `{rel(path)}`", use_container_width=True)
    else:
        st.info(
            "No pre-generated elevation figure found under "
            f"`{rel(MAPS_DIR)}` (`aligned_elevation_ernakulam.png` / `elevation_dem.png`)."
        )


# ---------------------------------------------------------------------------
# Rainfall
# ---------------------------------------------------------------------------


def render_rainfall() -> None:
    st.markdown('<div class="section-title">Rainfall analysis</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="limitation-box">
        <strong>Incomplete temporal coverage.</strong> The rainfall records have gaps: no
        station-year in this dataset met the analysis script's 80&nbsp;% daily-observation
        threshold. Values labelled <em>“observed sum”</em> are the sum of the available
        observations only and must <strong>not</strong> be read as complete annual rainfall
        totals. No values are interpolated or filled with zeros.
        </div>
        """,
        unsafe_allow_html=True,
    )

    missing_plots = [
        path for path in (RAINFALL_STATION_PLOT, RAINFALL_ANNUAL_PLOT) if not path.is_file()
    ]
    if missing_plots:
        st.warning(
            "Rainfall figure(s) not found: "
            + ", ".join(f"`{rel(path)}`" for path in missing_plots)
            + ". Generate them with `scripts/11_analyse_rainfall.py`."
        )
    else:
        left, right = st.columns(2)
        with left:
            st.image(
                str(RAINFALL_STATION_PLOT),
                caption=(
                    "Rainfall data availability by station — number of distinct dates with "
                    "observations (existing figure)"
                ),
                use_container_width=True,
            )
        with right:
            st.image(
                str(RAINFALL_ANNUAL_PLOT),
                caption=(
                    "Observed days per year by station — coverage varies by station and year "
                    "(existing figure)"
                ),
                use_container_width=True,
            )

    st.markdown("#### Interactive rainfall summaries")

    station_df = _load_rainfall_frame(
        RAINFALL_STATION_CSV, load_rainfall_station_summary, "station summary"
    )
    annual_df = _load_rainfall_frame(
        RAINFALL_ANNUAL_CSV, load_rainfall_annual_summary, "annual summary"
    )

    if station_df is not None and not station_df.empty:
        required = {"Station", "observation_days", "mean_observed_daily_mm", "maximum_observed_daily_mm"}
        missing = sorted(required - set(station_df.columns))
        if missing:
            st.error(
                f"`{rel(RAINFALL_STATION_CSV)}` is missing required column(s): "
                + ", ".join(f"`{name}`" for name in missing)
            )
        else:
            usable = station_df.dropna(subset=["observation_days"])
            if len(usable) < len(station_df):
                st.caption(
                    f"{len(station_df) - len(usable)} station row(s) with non-numeric values were "
                    "excluded from the charts."
                )
            left, right = st.columns(2)
            with left:
                fig = px.bar(
                    usable.sort_values("mean_observed_daily_mm"),
                    x="mean_observed_daily_mm",
                    y="Station",
                    orientation="h",
                    labels={
                        "mean_observed_daily_mm": "Mean observed daily rainfall (mm/day)",
                        "Station": "Station",
                    },
                )
                st.plotly_chart(dark_layout(fig, height=340), use_container_width=True)
                st.caption(
                    "Mean of observed daily values only (mm/day). Stations with few observation "
                    "days (e.g. Vettilappara, Boothathankettu, Neriyamangalam) are based on a "
                    "short record."
                )
            with right:
                fig = px.bar(
                    usable.sort_values("observation_days"),
                    x="observation_days",
                    y="Station",
                    orientation="h",
                    labels={
                        "observation_days": "Distinct dates with observations",
                        "Station": "Station",
                    },
                )
                st.plotly_chart(dark_layout(fig, height=340), use_container_width=True)
                st.caption("Number of distinct observed dates per station (data availability, not rainfall amount).")
    elif station_df is not None:
        _empty_frame_notice(RAINFALL_STATION_CSV)

    if annual_df is None:
        return

    if annual_df.empty:
        _empty_frame_notice(RAINFALL_ANNUAL_CSV)
        return

    required = {
        "Station",
        "Year",
        "observation_days",
        "coverage_percent",
        "observed_rainfall_sum_mm",
    }
    missing = sorted(required - set(annual_df.columns))
    if missing:
        st.error(
            f"`{rel(RAINFALL_ANNUAL_CSV)}` is missing required column(s): "
            + ", ".join(f"`{name}`" for name in missing)
            + ". Interactive annual charts are skipped."
        )
        return

    years = annual_df["Year"].dropna()
    if years.empty:
        st.warning(
            f"No valid year values in `{rel(RAINFALL_ANNUAL_CSV)}`; annual charts are skipped."
        )
        return

    stations = sorted(annual_df["Station"].dropna().unique().tolist())
    min_year, max_year = int(years.min()), int(years.max())

    filter_left, filter_right = st.columns([2, 3])
    with filter_left:
        chosen_stations = st.multiselect(
            "Stations",
            options=stations,
            default=stations,
            help="Filters the annual charts and table below.",
        )
    with filter_right:
        if min_year < max_year:
            year_range = st.slider(
                "Year range",
                min_value=min_year,
                max_value=max_year,
                value=(min_year, max_year),
                step=1,
            )
        else:
            year_range = (min_year, max_year)
            st.caption(f"Year range: {min_year} (only one year available)")

    if not chosen_stations:
        st.info("No station selected — choose at least one station to see the annual charts.")
        return

    filtered = annual_df[
        annual_df["Station"].isin(chosen_stations)
        & annual_df["Year"].between(year_range[0], year_range[1])
    ]

    if filtered.empty:
        st.info(
            "No annual records match the selected stations and year range. "
            "Adjust the filters to see data."
        )
        return

    coverage = filtered.dropna(subset=["coverage_percent"])
    if coverage.empty:
        st.warning("Selected records have no valid coverage values to plot.")
    else:
        fig = px.line(
            coverage.sort_values("Year"),
            x="Year",
            y="coverage_percent",
            color="Station",
            markers=True,
            labels={
                "coverage_percent": "Observed days as % of calendar days",
                "Year": "Year",
                "Station": "Station",
            },
        )
        fig.add_hline(
            y=80,
            line_dash="dash",
            line_color="#f59e0b",
            annotation_text="80% analysis threshold",
            annotation_position="top left",
        )
        fig.update_yaxes(range=[0, 105])
        st.plotly_chart(dark_layout(fig, height=400, legend_title="Station"), use_container_width=True)

        threshold_hits = int((coverage["coverage_percent"] >= 80).sum())
        st.caption(
            f"Observation coverage by station-year. The 80 % line is the analysis threshold used by "
            f"`scripts/11_analyse_rainfall.py`, not an official meteorological standard. "
            f"{threshold_hits} of {len(coverage)} station-year(s) shown reach it."
        )

    sums = filtered.dropna(subset=["observed_rainfall_sum_mm"])
    if sums.empty:
        st.warning("Selected records have no valid observed rainfall sums to plot.")
    else:
        fig = px.bar(
            sums.sort_values("Year"),
            x="Year",
            y="observed_rainfall_sum_mm",
            color="Station",
            barmode="group",
            labels={
                "observed_rainfall_sum_mm": "Observed rainfall sum (mm) — incomplete records",
                "Year": "Year",
                "Station": "Station",
            },
        )
        st.plotly_chart(dark_layout(fig, height=420, legend_title="Station"), use_container_width=True)
        st.caption(
            "Sum of available daily observations per station-year (mm). Because the daily series is "
            "incomplete, these values are NOT annual rainfall totals and cannot be compared with "
            "long-term annual rainfall statistics."
        )

    with st.expander("Annual rainfall summary table (filtered)"):
        st.dataframe(filtered, use_container_width=True, hide_index=True)
        st.download_button(
            label="Download filtered table (CSV)",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name="rainfall_annual_summary_filtered.csv",
            mime="text/csv",
            key="dl_rainfall_filtered",
        )


def _load_rainfall_frame(path: Path, loader, label: str) -> pd.DataFrame | None:
    """Load a rainfall summary CSV, reporting problems instead of crashing."""
    if not path.is_file():
        st.warning(f"Rainfall {label} not available: `{rel(path)}`.")
        return None
    try:
        return loader()
    except pd.errors.EmptyDataError:
        st.warning(f"`{rel(path)}` is empty (no rows and no header).")
        return None
    except (OSError, ValueError) as exc:
        st.error(f"Could not read `{rel(path)}`: {exc}")
        return None


def _empty_frame_notice(path: Path) -> None:
    st.warning(f"`{rel(path)}` contains headers but no data records.")


# ---------------------------------------------------------------------------
# Evacuation route
# ---------------------------------------------------------------------------


def _route_source_options() -> dict[str, dict]:
    options: dict[str, dict] = {}
    if ROUTE_GEOJSON.is_file():
        options["Shortest-distance route (experimental)"] = {
            "geojson": ROUTE_GEOJSON,
            "summary": ROUTE_SUMMARY_JSON,
            "color": "#f97316",
        }
    if FLOOD_AWARE_ROUTE_GEOJSON.is_file():
        options["Hazard-penalized route (experimental)"] = {
            "geojson": FLOOD_AWARE_ROUTE_GEOJSON,
            "summary": FLOOD_AWARE_ROUTE_SUMMARY_JSON,
            "color": "#a78bfa",
        }
    return options


def render_route() -> None:
    st.markdown('<div class="section-title">Evacuation route (experimental)</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="experimental-box">
        <strong>Experimental and unvalidated.</strong> The route shown here is a
        <em>shortest-distance / hazard-penalized road-network path</em> produced by
        <code>scripts/15_evacuation_route.py</code> on the OpenStreetMap road graph. It is
        <strong>not</strong> validated as flood-safe, has not been checked against evacuation
        shelters, and must not be used for emergency planning. The dashboard displays the
        stored geometry only — no route is generated here.
        </div>
        """,
        unsafe_allow_html=True,
    )

    options = _route_source_options()
    if not options:
        st.error(
            "No route GeoJSON found. Expected "
            f"`{rel(ROUTE_GEOJSON)}` (and optionally `{rel(FLOOD_AWARE_ROUTE_GEOJSON)}`). "
            "Generate them with `scripts/15_evacuation_route.py`."
        )
        _render_route_static_fallback()
        return

    names = list(options)
    choice = st.radio(
        "Route source",
        options=names,
        index=0,
        horizontal=True,
        help="Both routes are experimental outputs of the routing script.",
    )
    selected = options[choice]
    geojson_path: Path = selected["geojson"]
    summary_path: Path = selected["summary"]

    try:
        route = load_route(str(geojson_path))
    except GeoAssetError as exc:
        st.error(f"Could not display the route: {exc}")
        st.info(
            "The file may be missing, empty, malformed, or contain unsupported geometry. "
            "The rest of the dashboard is unaffected."
        )
        _render_route_static_fallback()
        return

    for warning in route["warnings"]:
        st.warning(warning)

    if route["n_segments"] == 0:
        st.warning(
            f"`{rel(geojson_path)}` contains no route geometry, so there is nothing to map."
        )
        return

    summary: dict | None = None
    if summary_path.is_file():
        try:
            summary = load_json(str(summary_path))
        except GeoAssetError as exc:
            st.warning(f"Route summary unavailable ({exc}). Showing route geometry only.")
    else:
        st.info(
            f"Route summary not found: `{rel(summary_path)}`. "
            "Only the route geometry is shown (no distance or endpoint values are assumed)."
        )

    start = end = None
    if isinstance(summary, dict):
        start = _latlon_pair(summary.get("start"))
        end = _latlon_pair(summary.get("destination"))

    try:
        fig = build_route_figure(
            route["segments"],
            color=selected["color"],
            start=start,
            end=end,
        )
    except GeoAssetError as exc:
        st.error(f"Could not build the route map: {exc}")
        return

    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Geometry: `{rel(geojson_path)}` (EPSG:4326 longitude/latitude from the OSM road graph).")
    if not maplibre_available():
        st.caption(
            "The installed Plotly version does not provide maplibre map traces, so the route is "
            "drawn on plain longitude/latitude axes without a basemap."
        )

    _render_route_summary(summary, summary_path, route, geojson_path)
    _render_route_comparison()
    _render_route_static_fallback()


def _latlon_pair(value) -> tuple[float, float] | None:
    """Accept either {'latitude','longitude'} or [lat, lon]; return (lon, lat)."""
    if isinstance(value, dict):
        lat = value.get("latitude")
        lon = value.get("longitude")
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        lat, lon = value[0], value[1]
    else:
        return None
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None
    if not (np.isfinite(lat) and np.isfinite(lon)):
        return None
    return (lon, lat)


def _render_route_summary(summary, summary_path: Path, route: dict, geojson_path: Path) -> None:
    st.markdown("#### Route summary")
    if not isinstance(summary, dict):
        st.caption(
            f"No summary values available for `{rel(geojson_path)}`. "
            f"Segments drawn: {route['n_segments']}."
        )
        return

    columns = st.columns(4)
    shown = 0
    for label, value, hint in (
        ("Distance (km)", summary.get("distance_km"), "Reported by the routing script"),
        ("Route nodes", summary.get("route_nodes"), "Graph nodes in the path"),
        ("Segments drawn", route["n_segments"], "Line features in the GeoJSON"),
        (
            "Geometry length (km)",
            round(route["length_m"] / 1000, 3) if route["length_m"] is not None else None,
            "Sum of OSM edge lengths in the file",
        ),
    ):
        if value is None:
            continue
        columns[shown % len(columns)].metric(label, f"{value}", help=hint)
        shown += 1

    details = []
    if summary.get("method"):
        details.append(f"Method: {summary['method']}")
    if summary.get("limitation"):
        details.append(f"Stated limitation: {summary['limitation']}")
    if summary.get("hazard_penalty_factor") is not None:
        details.append(f"Hazard penalty factor: {summary['hazard_penalty_factor']}")
    if details:
        st.caption(" · ".join(details))
    st.caption(f"Summary source: `{rel(summary_path)}` (shown only for fields present in the file).")

    limitations = summary.get("limitations")
    if isinstance(limitations, list) and limitations:
        with st.expander("Limitations recorded with the route output"):
            for item in limitations:
                st.markdown(f"- {item}")


def _render_route_comparison() -> None:
    if not ROUTE_COMPARISON_CSV.is_file():
        return
    with st.expander("Route comparison table (existing output)"):
        try:
            df = pd.read_csv(ROUTE_COMPARISON_CSV)
        except (OSError, ValueError, pd.errors.EmptyDataError) as exc:
            st.warning(f"Could not read `{rel(ROUTE_COMPARISON_CSV)}`: {exc}")
            return
        if df.empty:
            st.warning(f"`{rel(ROUTE_COMPARISON_CSV)}` contains no records.")
            return
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(
            "`mean_relative_hazard` is computed on the uncalibrated relative-hazard raster "
            "(0–1 index), not on flood depth or probability."
        )


def _render_route_static_fallback() -> None:
    for path, caption in (
        (ROUTE_MAP_PNG, "Shortest-distance evacuation route (existing figure)"),
        (ROUTE_COMPARISON_MAP_PNG, "Route comparison figure (existing)"),
    ):
        if path.is_file():
            with st.expander(caption):
                st.image(str(path), caption=f"`{rel(path)}`", use_container_width=True)


# ---------------------------------------------------------------------------
# Limitations
# ---------------------------------------------------------------------------


def render_limitations() -> None:
    st.markdown('<div class="section-title">Limitations</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="limitation-box">
        <ul style="margin:0; padding-left:1.2rem;">
            <li><strong>Incomplete data coverage</strong> — Rainfall station records have gaps;
            no station-year met the script’s 80% daily observation threshold. Do not treat
            partial sums as complete annual totals.</li>
            <li><strong>Unverified flood rasters</strong> — Scenario values are from source
            flood layers; units and physical meaning have not been confirmed against metadata.</li>
            <li><strong>Relative hazard classes</strong> — Low / Moderate / High / Very High are
            preliminary index classes, not official KSDMA designations.</li>
            <li><strong>Elevation units</strong> — The aligned DEM is carried over from the source
            DEM in its original units; the dashboard labels them “source units” rather than
            asserting metres.</li>
            <li><strong>Evacuation routing</strong> — Any evacuation route shown in related
            project outputs is <em>experimental</em> (shortest-distance or hazard-penalized);
            it is <strong>not validated</strong> as flood-safe for emergency use.</li>
            <li><strong>Study extent</strong> — Coverage follows aligned rasters and may not
            match the full Ernakulam district administrative boundary.</li>
            <li><strong>Dashboard scope</strong> — This app only reads and displays existing
            project outputs; it does not recompute hazard, rainfall or routing results.</li>
        </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _initial_section_index() -> int:
    """Allow deep links such as ``?section=Elevation`` (also used for screenshots)."""
    requested = st.query_params.get("section")
    if isinstance(requested, str) and requested in SECTIONS:
        return SECTIONS.index(requested)
    return 0


def main() -> None:
    st.set_page_config(
        page_title="Ernakulam Flood Risk Dashboard",
        page_icon="🌊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_theme()

    st.sidebar.title("Navigation")
    section = st.sidebar.radio(
        "Go to",
        SECTIONS,
        index=_initial_section_index(),
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Hazard scenario**")
    scenario_label = st.sidebar.selectbox(
        "Scenario",
        options=list(SCENARIO_LABELS),
        index=len(SCENARIO_LABELS) - 1,
        label_visibility="collapsed",
        help="Drives the flood scenario panel, the hazard charts and the hazard-class map.",
    )
    st.sidebar.caption(
        f"Scenario id `{SCENARIO_KEYS[scenario_label]}` · return period {scenario_label}"
    )

    if HAZARD_SUMMARY_CSV.is_file():
        try:
            hazard_df: pd.DataFrame | None = load_hazard_summary()
        except (OSError, ValueError, pd.errors.EmptyDataError, KeyError) as exc:
            st.sidebar.error(f"Could not read `{HAZARD_SUMMARY_CSV.name}`: {exc}")
            hazard_df = None
    else:
        hazard_df = None

    if section == "Overview":
        render_overview(hazard_df)
        if hazard_df is None:
            st.warning(
                f"Hazard summary CSV not available: `{rel(HAZARD_SUMMARY_CSV)}`. "
                "Hazard sections are shown with an unavailable-data message."
            )
        st.markdown("---")
        render_flood_maps(scenario_label)
    elif section == "Flood scenario maps":
        render_flood_maps(scenario_label)
    elif section == "Hazard classification":
        render_hazard_charts(hazard_df, scenario_label)
    elif section == "Elevation":
        render_elevation()
    elif section == "Rainfall analysis":
        render_rainfall()
    elif section == "Evacuation route":
        render_route()
    else:
        render_limitations()

    st.sidebar.markdown("---")
    st.sidebar.caption("Urban Flood Risk · Ernakulam CEP")
    st.sidebar.caption("Dashboard reads existing outputs only; no live model runs.")
    st.sidebar.caption(f"Screenshots folder: `{rel(DASHBOARD_OUTPUT_DIR)}`")


if __name__ == "__main__":
    main()
