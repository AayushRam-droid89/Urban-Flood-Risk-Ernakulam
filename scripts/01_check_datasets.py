from pathlib import Path
import rasterio
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

RASTERS = [
    "Kerala_Flood_10_yr_Historical.tif",
    "Kerala_Flood_25_yr_Historical.tif",
    "Kerala_Flood_50_yr_Historical.tif",
    "ernakulam_dem.tif",
]

print("\n========== RASTER CHECK ==========")

for filename in RASTERS:
    path = RAW / filename
    print(f"\n{filename}")

    if not path.exists():
        print("ERROR: File not found")
        continue

    with rasterio.open(path) as src:
        print("CRS:", src.crs)
        print("Dimensions:", src.width, "x", src.height)
        print("Resolution:", src.res)
        print("Bounds:", src.bounds)
        print("NoData:", src.nodata)

        # Check whether raster has valid pixel values
        sample = src.read(1, masked=True)
        print("Valid pixels in first band:", sample.count())

print("\n========== ROAD NETWORK CHECK ==========")

roads = RAW / "ernakulam_roads.gpkg"
graph = RAW / "ernakulam_roads.graphml"

if roads.exists():
    gdf = gpd.read_file(roads)
    print("Road GeoPackage: OK")
    print("CRS:", gdf.crs)
    print("Road features:", len(gdf))
    print("Bounds:", gdf.total_bounds)
else:
    print("ERROR: ernakulam_roads.gpkg not found")

if graph.exists():
    print("Road GraphML: OK")
else:
    print("ERROR: ernakulam_roads.graphml not found")

print("\n========== RAINFALL CSV CHECK ==========")

csv_files = list(RAW.glob("*.csv"))

if not csv_files:
    csv_files = list(RAW.glob("*.CSV"))

if csv_files:
    csv_path = csv_files[0]
    print("File:", csv_path.name)

    try:
        df = pd.read_csv(csv_path, nrows=5)
        print("Columns:", df.columns.tolist())
        print("\nFirst five rows:")
        print(df.to_string(index=False))
    except Exception as e:
        print("Could not read CSV:", e)
else:
    print("ERROR: No CSV file found in data/raw")

print("\n========== CHECK COMPLETE ==========")