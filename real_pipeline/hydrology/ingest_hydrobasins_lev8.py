import geopandas as gpd
from pathlib import Path
import json

IN_FILE = Path("data_real/hydrology/raw/hybas_extracted/hybas_as_lev08_v1c.shp")
OUT_FILE = Path("data_real/hydrology/catchments/processed/hydrobasins_india_lev08.parquet")
STATUS_FILE = Path("data_real/hydrology/catchments/hydrobasins/hydrobasins_status.json")

def main():
    print(f"Reading {IN_FILE}...")
    gdf = gpd.read_file(IN_FILE)
    print(f"Initial count: {len(gdf)}")
    
    # Check validity and fix if needed
    if not gdf.is_valid.all():
        print("Fixing invalid geometries with buffer(0)...")
        gdf["geometry"] = gdf["geometry"].buffer(0)
    
    # Clip to India approximate bounding box (Longitude: 68 to 97, Latitude: 8 to 37)
    india_bbox = (68.0, 8.0, 97.0, 37.0)
    print(f"Clipping to India bounding box {india_bbox}...")
    gdf_india = gdf.cx[india_bbox[0]:india_bbox[2], india_bbox[1]:india_bbox[3]]
    print(f"Count after clipping: {len(gdf_india)}")
    
    # Save to Parquet
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Saving to {OUT_FILE}...")
    gdf_india.to_parquet(OUT_FILE, index=False)
    
    status = {
        "status": "PARTIAL",
        "gate_d": "PARTIAL",
        "source": "HydroSHEDS Asia Level 8",
        "n_basins_india": len(gdf_india),
        "level": 8,
        "note": "Village-level linkage blocked due to missing village coordinates in LGD data."
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)
    print("Done.")

if __name__ == "__main__":
    main()
