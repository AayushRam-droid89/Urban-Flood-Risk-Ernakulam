import osmnx as ox

place = "Ernakulam, Kerala, India"

G = ox.graph_from_place(
    place,
    network_type="drive",
    simplify=True
)

ox.save_graphml(G, "ernakulam_roads.graphml")

nodes, edges = ox.graph_to_gdfs(G)
edges.to_file("ernakulam_roads.gpkg", driver="GPKG")

print("Road network downloaded successfully.")