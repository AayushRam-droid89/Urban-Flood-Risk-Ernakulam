
"""
Script 16: Flood-aware evacuation route comparison
Project: Urban Flood Risk and Emergency Evacuation Planning
Study area: Ernakulam, Kerala

Important:
- Unknown flood values are tracked separately.
- Unknown values are NOT treated as confirmed safe.
- The output is an experimental route comparison, not a certified safe route.
"""

from pathlib import Path
import json
import math
import warnings

import networkx as nx
import numpy as np
import rasterio
from rasterio.warp import transform as transform_coords
from shapely.geometry import LineString, mapping
import geopandas as gpd


# --------------------------------------------------
# 1. PROJECT PATHS AND SETTINGS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

GRAPH_PATH = ROOT / "data" / "raw" / "ernakulam_roads.graphml"

OUTPUT_DIR = ROOT / "outputs"
MAP_DIR = OUTPUT_DIR / "maps"
MAP_DIR.mkdir(parents=True, exist_ok=True)

# These are the illustrative endpoints used in Script 15.
START_NODE = "4334997194"
END_NODE = "430768919"

# Increase this to make known hazard values influence routing more.
HAZARD_PENALTY = 4.0

# Unknown hazard data receives an explicit uncertainty penalty.
UNKNOWN_PENALTY = 1.0

# Try common locations for the relative hazard raster.
RASTER_CANDIDATES = [
    OUTPUT_DIR / "relative_hazard_index.tif",
    OUTPUT_DIR / "rasters" / "relative_hazard_index.tif",
    OUTPUT_DIR / "hazard" / "relative_hazard_index.tif",
    ROOT / "data" / "processed" / "relative_hazard_index.tif",
    ROOT / "data" / "processed" / "relative_hazard.tif",
]


# --------------------------------------------------
# 2. FIND INPUT RASTER
# --------------------------------------------------

def find_hazard_raster():
    for path in RASTER_CANDIDATES:
        if path.exists():
            return path

    # Search project folders for a likely raster filename.
    matches = []
    for folder in [ROOT / "outputs", ROOT / "data"]:
        if folder.exists():
            matches.extend(folder.rglob("*relative*hazard*.tif"))

    if matches:
        return matches[0]

    raise FileNotFoundError(
        "Could not find the relative hazard raster.\n"
        "Place it in outputs/relative_hazard_index.tif, or update "
        "RASTER_CANDIDATES in this script."
    )


# --------------------------------------------------
# 3. GRAPH HELPERS
# --------------------------------------------------

def get_edge_length(data, u, v, graph):
    """Return edge length in metres when available."""
    length = data.get("length")

    if length is not None:
        try:
            length = float(length)
            if math.isfinite(length) and length > 0:
                return length
        except (TypeError, ValueError):
            pass

    x1 = float(graph.nodes[u]["x"])
    y1 = float(graph.nodes[u]["y"])
    x2 = float(graph.nodes[v]["x"])
    y2 = float(graph.nodes[v]["y"])

    # Approximate geographic distance for lon/lat coordinates.
    mean_lat = math.radians((y1 + y2) / 2)
    dx = (x2 - x1) * 111320 * math.cos(mean_lat)
    dy = (y2 - y1) * 110540
    return math.hypot(dx, dy)


def sample_hazard(dataset, lon, lat):
    """Sample raster at a lon/lat point; return None if unknown."""
    try:
        x, y = lon, lat

        if dataset.crs and dataset.crs.to_epsg() != 4326:
            xs, ys = transform_coords(
                "EPSG:4326", dataset.crs, [lon], [lat]
            )
            x, y = xs[0], ys[0]

        row, col = dataset.index(x, y)

        if (
            row < 0 or col < 0
            or row >= dataset.height
            or col >= dataset.width
        ):
            return None

        value = dataset.read(1, masked=True)[row, col]

        if np.ma.is_masked(value):
            return None

        value = float(value)

        if not math.isfinite(value):
            return None

        # Relative hazard index is expected to be in [0, 1].
        # Do not silently reinterpret other scales.
        if value < 0 or value > 1:
            return None

        return value

    except (ValueError, IndexError, TypeError):
        return None


def make_edge_key(u, v):
    return (str(u), str(v))


# --------------------------------------------------
# 4. MAIN ROUTING WORKFLOW
# --------------------------------------------------

def main():
    if not GRAPH_PATH.exists():
        raise FileNotFoundError(
            f"Road graph not found: {GRAPH_PATH}"
        )

    raster_path = find_hazard_raster()

    print("Loading road network...")
    graph = nx.read_graphml(GRAPH_PATH)

    # OSM road graphs are often MultiDiGraphs. Convert to an
    # undirected graph and retain the shortest parallel edge.
    simple_graph = nx.Graph()

    for node, attrs in graph.nodes(data=True):
        simple_graph.add_node(node, **attrs)

    for u, v, attrs in graph.edges(data=True):
        length = get_edge_length(attrs, u, v, graph)

        if (
            not simple_graph.has_edge(u, v)
            or length < simple_graph[u][v].get("length", float("inf"))
        ):
            simple_graph.add_edge(u, v, **attrs)
            simple_graph[u][v]["length"] = length

    graph = simple_graph

    if START_NODE not in graph:
        raise ValueError(
            f"Start node {START_NODE} not found in road graph."
        )

    if END_NODE not in graph:
        raise ValueError(
            f"End node {END_NODE} not found in road graph."
        )

    print(f"Road nodes: {graph.number_of_nodes():,}")
    print(f"Road edges: {graph.number_of_edges():,}")
    print(f"Hazard raster: {raster_path}")

    edge_hazard = {}
    valid_samples = 0
    unknown_samples = 0

    print("Sampling flood hazard along road edges...")

    with rasterio.open(raster_path) as raster:
        print(f"Raster CRS: {raster.crs}")
        print(f"Raster size: {raster.width} x {raster.height}")

        for u, v, attrs in graph.edges(data=True):
            lon1 = float(graph.nodes[u]["x"])
            lat1 = float(graph.nodes[u]["y"])
            lon2 = float(graph.nodes[v]["x"])
            lat2 = float(graph.nodes[v]["y"])

            midpoint_lon = (lon1 + lon2) / 2
            midpoint_lat = (lat1 + lat2) / 2

            hazard = sample_hazard(
                raster, midpoint_lon, midpoint_lat
            )

            key = make_edge_key(u, v)
            edge_hazard[key] = hazard

            if hazard is None:
                unknown_samples += 1
            else:
                valid_samples += 1

            length = float(attrs["length"])

            if hazard is None:
                # This is an uncertainty penalty, not a claim that
                # the road is flooded or safe.
                factor = 1.0 + UNKNOWN_PENALTY
            else:
                factor = 1.0 + HAZARD_PENALTY * hazard

            graph[u][v]["hazard"] = (
                float(hazard) if hazard is not None else None
            )
            graph[u][v]["risk_cost"] = length * factor

    total_edges = valid_samples + unknown_samples
    coverage = (
        100 * valid_samples / total_edges
        if total_edges else 0
    )

    print(f"Edges with valid hazard samples: {valid_samples:,}")
    print(f"Edges with unknown hazard: {unknown_samples:,}")
    print(f"Valid hazard coverage: {coverage:.2f}%")

    # Find the shortest-distance route.
    print("Calculating shortest-distance route...")
    shortest_route = nx.shortest_path(
        graph,
        source=START_NODE,
        target=END_NODE,
        weight="length"
    )

    # Find the route that penalizes known hazard and unknown data.
    print("Calculating experimental hazard-aware route...")
    hazard_route = nx.shortest_path(
        graph,
        source=START_NODE,
        target=END_NODE,
        weight="risk_cost"
    )

    # --------------------------------------------------
    # 5. ROUTE STATISTICS
    # --------------------------------------------------

    def route_stats(route):
        distance = 0.0
        known_values = []
        unknown_edges = 0
        edge_count = max(0, len(route) - 1)

        for u, v in zip(route[:-1], route[1:]):
            attrs = graph[u][v]
            distance += float(attrs["length"])

            hazard = attrs.get("hazard")
            if hazard is None:
                unknown_edges += 1
            else:
                known_values.append(float(hazard))

        return {
            "distance_km": round(distance / 1000, 3),
            "edge_count": edge_count,
            "known_hazard_edges": len(known_values),
            "unknown_hazard_edges": unknown_edges,
            "known_hazard_coverage_percent": round(
                100 * len(known_values) / edge_count, 2
            ) if edge_count else 0,
            "mean_hazard_on_known_edges": round(
                float(np.mean(known_values)), 4
            ) if known_values else None,
        }

    shortest_stats = route_stats(shortest_route)
    hazard_stats = route_stats(hazard_route)

    # --------------------------------------------------
    # 6. SAVE ROUTES AS GEOJSON
    # --------------------------------------------------

    features = []

    for route_name, route in [
        ("shortest_distance", shortest_route),
        ("experimental_hazard_aware", hazard_route),
    ]:
        coords = [
            (
                float(graph.nodes[node]["x"]),
                float(graph.nodes[node]["y"])
            )
            for node in route
        ]

        features.append({
            "type": "Feature",
            "geometry": mapping(LineString(coords)),
            "properties": {
                "route_type": route_name,
                **(
                    shortest_stats if route_name == "shortest_distance"
                    else hazard_stats
                ),
            },
        })

    geojson_path = OUTPUT_DIR / "flood_aware_route_comparison.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump({
            "type": "FeatureCollection",
            "features": features,
        }, f, indent=2)

    # --------------------------------------------------
    # 7. SAVE SUMMARY
    # --------------------------------------------------

    summary = {
        "project": "Urban Flood Risk and Emergency Evacuation Planning",
        "study_area": "Ernakulam, Kerala",
        "start_node": START_NODE,
        "end_node": END_NODE,
        "hazard_raster": str(raster_path.relative_to(ROOT)),
        "hazard_penalty": HAZARD_PENALTY,
        "unknown_data_penalty": UNKNOWN_PENALTY,
        "road_network": {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
        },
        "hazard_data_coverage": {
            "valid_edges": valid_samples,
            "unknown_edges": unknown_samples,
            "valid_coverage_percent": round(coverage, 2),
        },
        "shortest_distance_route": shortest_stats,
        "experimental_hazard_aware_route": hazard_stats,
        "limitations": [
            "Unknown raster samples are not evidence of low flood risk.",
            "The unknown-data penalty is a modelling assumption.",
            "The relative hazard index is not a calibrated flood depth.",
            "The start and end nodes are illustrative, not verified shelters.",
            "This comparison does not certify a route as safe during a flood.",
        ],
    }

    summary_path = OUTPUT_DIR / "flood_aware_route_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # --------------------------------------------------
    # 8. PRINT RESULTS
    # --------------------------------------------------

    print("\n--- ROUTE COMPARISON ---")
    print("Shortest-distance route:")
    print(json.dumps(shortest_stats, indent=2))

    print("\nExperimental hazard-aware route:")
    print(json.dumps(hazard_stats, indent=2))

    print("\nFiles saved:")
    print(f"GeoJSON: {geojson_path}")
    print(f"Summary: {summary_path}")
    print("\nImportant: do not label the experimental route as flood-safe.")


if __name__ == "__main__":
    main()
