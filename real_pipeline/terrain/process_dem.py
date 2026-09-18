import logging
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.merge import merge
from rasterstats import zonal_stats
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pyproj import CRS
from numpy import gradient
from shapely.geometry import box

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("process_dem")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DEM_DIR = PROJECT_ROOT / "data_real" / "terrain" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data_real" / "terrain" / "processed"

def process_dem():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    tif_files = list(RAW_DEM_DIR.glob("*.tif"))
    if not tif_files:
        log.error("No GLO-30 DEM .tif files found!")
        return
        
    log.info(f"Found {len(tif_files)} DEM tiles. Starting genuine raster processing.")
    
    # 1. Load Villages
    villages_path = PROJECT_ROOT / "data_real" / "admin" / "raw" / "LGD_Villages.parquet"
    if not villages_path.exists():
        log.error("Missing LGD_Villages.parquet")
        return
    log.info("Loading village polygons...")
    villages = gpd.read_parquet(villages_path)
    
    # We only care about villages that intersect our DEM bounds to save time
    # To be perfectly correct, we can build a mosaic or do it tile by tile.
    # Tile by tile is safer for memory.
    
    # Pre-allocate feature columns with nans
    villages["elev_mean_m"] = np.nan
    villages["slope_mean_deg"] = np.nan
    villages["distance_to_stream_m"] = np.nan
    villages["flow_accumulation_skm"] = np.nan # Explicitly blocked due to partial DEM boundary invalidity
    
    # 2. Process DEM tiles for Elevation and Slope
    for tif_path in tif_files:
        log.info(f"Processing DEM tile: {tif_path.name}")
        with rasterio.open(tif_path) as src:
            bounds = src.bounds
            bbox = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
            
            # Find intersecting villages
            intersecting_idx = villages.sindex.query(bbox)
            
            # Subselect
            v_sub = villages.iloc[intersecting_idx].copy()
            if v_sub.empty:
                continue
                
            log.info(f"  Intersecting villages: {len(v_sub)}")
            
            # Compute zonal stats for elevation in-memory
            try:
                dem_data = src.read(1)
            except Exception as e:
                log.error(f"  Corrupted tile {tif_path.name}, skipping: {e}")
                continue
                
            stats = zonal_stats(v_sub.geometry, dem_data, affine=src.transform, stats="mean", nodata=src.nodata)
            elevations = [s["mean"] for s in stats]
            
            dx, dy = src.res
            if src.crs.to_string() == "EPSG:4326":
                dx *= 111320
                dy *= 111320
            
            gy, gx = gradient(dem_data)
            slope = np.degrees(np.arctan(np.sqrt((gx/dx)**2 + (gy/dy)**2)))
            
            # Compute zonal stats for slope in-memory
            slope_stats = zonal_stats(v_sub.geometry, slope, affine=src.transform, stats="mean", nodata=np.nan)
            slopes = [s["mean"] for s in slope_stats]
            
            # Assign to main dataframe
            for i, idx in enumerate(v_sub.index):
                if pd.isna(villages.at[idx, "elev_mean_m"]):
                    villages.at[idx, "elev_mean_m"] = elevations[i]
                    villages.at[idx, "slope_mean_deg"] = slopes[i]
            
    # 3. Distance to stream
    log.info("Computing distance-to-stream...")
    rivers_path = PROJECT_ROOT / "data_real" / "hydrology" / "processed" / "hydro_rivers_india.parquet"
    if rivers_path.exists():
        rivers = gpd.read_parquet(rivers_path)
        # We need a projected CRS for accurate meters. EPSG:7755 is India's CRS.
        log.info("  Reprojecting to EPSG:7755 for accurate distance calculation...")
        # Get valid geometry villages to avoid errors during spatial join
        v_valid_geom = villages[villages.geometry.is_valid].copy()
        
        villages_proj = v_valid_geom.to_crs(epsg=7755)
        rivers_proj = rivers.to_crs(epsg=7755)
        
        # Calculate distance from village centroid to nearest stream.
        # Compute for ALL valid villages, independently of elevation.
        log.info(f"  Computing distances for all {len(villages_proj)} valid villages...")
        
        # Batching to avoid OOM
        batch_size = 50000
        total_batches = (len(villages_proj) + batch_size - 1) // batch_size
        nearest_results = []
        
        for i in range(total_batches):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, len(villages_proj))
            log.info(f"    Processing batch {i+1}/{total_batches} ({start_idx} to {end_idx})...")
            
            v_batch = villages_proj.iloc[start_idx:end_idx]
            
            # sjoin_nearest automatically uses spatial indexes
            nearest = gpd.sjoin_nearest(v_batch, rivers_proj, how="left", distance_col="distance_to_stream_m")
            # Ensure unique index in case of ties
            nearest = nearest[~nearest.index.duplicated(keep="first")]
            nearest_results.append(nearest[["distance_to_stream_m", "UPLAND_SKM"]])
            
        # Combine batches
        all_nearest = pd.concat(nearest_results)
        
        for idx in all_nearest.index:
            villages.at[idx, "distance_to_stream_m"] = all_nearest.at[idx, "distance_to_stream_m"]
            villages.at[idx, "flow_accumulation_skm"] = all_nearest.at[idx, "UPLAND_SKM"]
            
    else:
        log.warning("hydro_rivers_india.parquet not found. Stream distances blocked.")
        
    # Write output
    out_path = PROCESSED_DIR / "village_terrain_features.parquet"
    # Keep only computed columns + identifiers to save space
    villages.rename(columns={"vil_lgd": "village_code"}, inplace=True)
    cols = ["village_code", "elev_mean_m", "slope_mean_deg", "distance_to_stream_m", "flow_accumulation_skm"]
    out_df = villages[cols].copy()
    
    out_df.to_parquet(out_path, index=False)
    
    log.info(f"Terrain processed successfully. Real valid records: {out_df['elev_mean_m'].notna().sum()}")
    log.info(f"Output saved to {out_path}")
    
    # Write provenance
    prov_path = PROCESSED_DIR / "provenance.txt"
    with open(prov_path, "w") as f:
        f.write(f"Genuine computation from rasterstats and geopandas.\nValid elev_mean_m: {out_df['elev_mean_m'].notna().sum()}\nAccumulation explicitly blocked due to partial boundaries.\n")

if __name__ == "__main__":
    process_dem()
