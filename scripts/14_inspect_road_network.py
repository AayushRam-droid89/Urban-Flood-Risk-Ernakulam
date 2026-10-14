
from pathlib import Path
import geopandas as gpd
import networkx as nx

ROOT = Path(r"D:\Flood_Project_SDG")
RAW = ROOT / "data" / "raw"

graph_path = RAW / "ernakulam_roads.graphml"
gpkg_path = RAW / "ernakulam_roads.gpkg"

print("=== ROAD NETWORK INSPECTION ===")

if graph_path.exists():
    G = nx.read_graphml(graph_path)
    print("Graph nodes:", G.number_of_nodes())
    print("Graph edges:", G.number_of_edges())
    print("Directed:", G.is_directed())
    print("Connected components (undirected):",
          nx.number_connected_components(G.to_undirected()))
else:
    print("GraphML file not found:", graph_path)

if gpkg_path.exists():
    roads = gpd.read_file(gpkg_path)
    print("\nGeoPackage CRS:", roads.crs)
    print("Road features:", len(roads))
    print("Columns:", list(roads.columns))
    print("Geometry types:", roads.geom_type.value_counts().to_dict())
    print("Bounds:", roads.total_bounds)

    print("\nRoad type counts:")
    road_type = "highway" if "highway" in roads.columns else None
    if road_type:
        print(roads[road_type].astype(str).value_counts().head(15))
    else:
        print("No 'highway' column found; inspect the columns above.")
else:
    print("GeoPackage file not found:", gpkg_path)

print("\nInspection complete.")