"""
Urban Flood Risk — Ernakulam interactive dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

_DASHBOARD_DIR = Path(__file__).resolve().parent
if str(_DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_DIR))

from map_utils import panel_to_bytes, split_scenario_panels  # noqa: E402
from paths import (  # noqa: E402
    ROOT,
    ALIGNED_FLOOD_MAP,
    FLOOD_COMPARISON_FALLBACK,
    FLOOD_COMPARISON_MAP,
    HAZARD_SUMMARY_CSV,
    MAPS_DIR,
    RAINFALL_ANNUAL_PLOT,
    RAINFALL_STATION_PLOT,
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

SCENARIO_DISPLAY = {
    "10year": "10-year",
    "25year": "25-year",
    "50year": "50-year",
}


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


@st.cache_data(show_spinner=False)
def load_hazard_summary() -> pd.DataFrame:
    df = pd.read_csv(HAZARD_SUMMARY_CSV)
    df["scenario_label"] = df["scenario"].map(SCENARIO_DISPLAY)
    df["class"] = pd.Categorical(df["class"], categories=CLASS_ORDER, ordered=True)
    return df.sort_values(["scenario", "class"])


def resolve_flood_map_path() -> Path | None:
    if FLOOD_COMPARISON_MAP.is_file():
        return FLOOD_COMPARISON_MAP
    if FLOOD_COMPARISON_FALLBACK.is_file():
        return FLOOD_COMPARISON_FALLBACK
    if ALIGNED_FLOOD_MAP.is_file():
        return ALIGNED_FLOOD_MAP
    return None


def render_overview(hazard_df: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>Urban Flood Risk in Ernakulam</h1>
            <p>
                Open, exploratory view of flood-hazard scenarios, relative hazard classes,
                and rainfall context for the Ernakulam study extent — inspired by transparent
                flood atlases such as
                <a href="https://flood.neer.io/" target="_blank" style="color:#38bdf8;">India Flood Atlas (NEER)</a>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    latest = hazard_df[hazard_df["scenario"] == "50year"]
    high_vh = latest[latest["class"].isin(["High", "Very High"])]["percent_of_valid_pixels"].sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
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
            f"""
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
                <div class="value">{high_vh:.1f}%</div>
                <div class="hint">Share of valid raster pixels</div>
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


def render_flood_maps() -> None:
    st.markdown('<div class="section-title">Flood scenario maps</div>', unsafe_allow_html=True)
    map_path = resolve_flood_map_path()

    if map_path is None:
        st.error(
            f"No flood comparison map found under `{MAPS_DIR}`. "
            "Run `scripts/04_plot_flood_scenarios.py` to generate outputs."
        )
        return

    st.caption(
        f"Panels extracted from `{map_path.relative_to(ROOT)}` "
        "(shared colour scale across scenarios; raster units to be verified)."
    )

    try:
        panels = split_scenario_panels(map_path)
    except OSError as exc:
        st.error(f"Could not load map image: {exc}")
        return

    tabs = st.tabs(list(SCENARIO_LABELS))
    for tab, label, panel in zip(tabs, SCENARIO_LABELS, panels):
        with tab:
            st.image(panel, use_container_width=True, caption=f"{label} return period")
            st.download_button(
                label=f"Download {label} panel (PNG)",
                data=panel_to_bytes(panel),
                file_name=f"flood_{label.replace('-', '_')}.png",
                mime="image/png",
                key=f"dl_{label}",
            )

    with st.expander("Full comparison figure"):
        st.image(str(map_path), use_container_width=True)


def render_hazard_charts(hazard_df: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Hazard classification</div>', unsafe_allow_html=True)
    st.caption(f"Source: `{HAZARD_SUMMARY_CSV.relative_to(ROOT)}`")

    scenario = st.selectbox(
        "Scenario",
        options=["All scenarios", *SCENARIO_DISPLAY.values()],
        index=0,
    )

    if scenario == "All scenarios":
        plot_df = hazard_df.copy()
        plot_df["scenario_label"] = plot_df["scenario_label"].astype(str)
        fig = px.bar(
            plot_df,
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
            height=420,
        )
    else:
        rev = {v: k for k, v in SCENARIO_DISPLAY.items()}
        key = rev[scenario]
        plot_df = hazard_df[hazard_df["scenario"] == key]
        fig = px.bar(
            plot_df,
            x="class",
            y="percent_of_valid_pixels",
            color="class",
            category_orders={"class": CLASS_ORDER},
            color_discrete_map=CLASS_COLORS,
            labels={"percent_of_valid_pixels": "% of valid pixels", "class": "Hazard class"},
            height=380,
        )
        fig.update_layout(showlegend=False)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,16,28,0.6)",
        legend_title_text="Class",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        hazard_df.assign(
            scenario=hazard_df["scenario_label"],
        )[
            ["scenario", "class", "pixel_count", "percent_of_valid_pixels"]
        ].rename(columns={"scenario": "return_period"}),
        use_container_width=True,
        hide_index=True,
    )


def render_rainfall() -> None:
    st.markdown('<div class="section-title">Rainfall analysis</div>', unsafe_allow_html=True)

    missing = [
        p for p in (RAINFALL_STATION_PLOT, RAINFALL_ANNUAL_PLOT) if not p.is_file()
    ]
    if missing:
        st.warning(
            "Rainfall plots not found. Run `scripts/11_analyse_rainfall.py` to generate: "
            + ", ".join(f"`{m.name}`" for m in missing)
        )
        return

    left, right = st.columns(2)
    with left:
        st.image(
            str(RAINFALL_STATION_PLOT),
            caption="Station comparison — mean daily rainfall",
            use_container_width=True,
        )
    with right:
        st.image(
            str(RAINFALL_ANNUAL_PLOT),
            caption="Annual observations by station (coverage varies)",
            use_container_width=True,
        )


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
            <li><strong>Evacuation routing</strong> — Any evacuation route shown in related
            project outputs is <em>experimental</em> (shortest-distance or heuristic);
            it is <strong>not validated</strong> as flood-safe for emergency use.</li>
            <li><strong>Study extent</strong> — Coverage follows aligned rasters and may not
            match the full Ernakulam district administrative boundary.</li>
        </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        (
            "Overview",
            "Flood scenario maps",
            "Hazard classification",
            "Rainfall analysis",
            "Limitations",
        ),
        label_visibility="collapsed",
    )

    if not HAZARD_SUMMARY_CSV.is_file():
        st.error(f"Missing hazard summary CSV: `{HAZARD_SUMMARY_CSV}`")
        st.stop()

    hazard_df = load_hazard_summary()

    if section == "Overview":
        render_overview(hazard_df)
        st.markdown("---")
        render_flood_maps()
    elif section == "Flood scenario maps":
        render_flood_maps()
    elif section == "Hazard classification":
        render_hazard_charts(hazard_df)
    elif section == "Rainfall analysis":
        render_rainfall()
    else:
        render_limitations()

    st.sidebar.markdown("---")
    st.sidebar.caption("Urban Flood Risk · Ernakulam CEP")
    st.sidebar.caption("Dashboard reads existing outputs only; no live model runs.")


if __name__ == "__main__":
    main()
