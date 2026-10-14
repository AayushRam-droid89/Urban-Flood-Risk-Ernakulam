
from pathlib import Path
import json
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt

ROOT = Path(r"D:\Flood_Project_SDG")
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
MAPS = OUT / "maps"
MAPS.mkdir(parents=True, exist_ok=True)

GRAPH_PATH = RAW / "ernakulam_roads.graphml"

print("Loading road network...")
G = ox.load_graphml(GRAPH_PATH)

# Replace these with your chosen starting point and destination.
# Coordinates are (latitude, longitude).
START_LAT, START_LON = 9.9816, 76.2999
END_LAT, END_LON = 9.9674, 76.2420

start_node = ox.distance.nearest_nodes(G, X=START_LON, Y=START_LAT)
end_node = ox.distance.nearest_nodes(G, X=END_LON, Y=END_LAT)

print("Start node:", start_node)
print("End node:", end_node)

try:
    route = nx.shortest_path(G, start_node, end_node, weight="length")
except nx.NetworkXNoPath:
    raise SystemExit("No route found between these points.")

route_edges = ox.routing.route_to_gdf(G, route, weight="length")
distance_km = route_edges["length"].sum() / 1000

print(f"Route nodes: {len(route)}")
print(f"Route distance: {distance_km:.2f} km")

route_geojson = route_edges.to_json()
route_path = OUT / "evacuation_route.geojson"
route_path.write_text(route_geojson, encoding="utf-8")

fig, ax = ox.plot_graph_route(
    G, route,
    route_color="red",
    route_linewidth=2.5,
    node_size=0,
    bgcolor="white",
    show=False,
    close=False
)
fig.savefig(MAPS / "shortest_evacuation_route.png",
            dpi=200, bbox_inches="tight")
plt.close(fig)

summary = {
    "start": {"latitude": START_LAT, "longitude": START_LON},
    "destination": {"latitude": END_LAT, "longitude": END_LON},
    "route_nodes": len(route),
    "distance_km": round(distance_km, 3),
    "method": "Shortest distance using road-edge lengths",
    "limitation": "Not yet optimized for flood safety"
}

(OUT / "evacuation_route_summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)

print("Route map:", MAPS / "shortest_evacuation_route.png")
print("Route GeoJSON:", route_path)
print("Route summary:", OUT / "evacuation_route_summary.json")