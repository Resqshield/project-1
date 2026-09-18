# -*- coding: utf-8 -*-
"""
real_pipeline/features/build_static_features.py
=================================================
Build static terrain/geospatial features for pilot regions from real DEM.

Static features are derived ONLY from real data:
  - DEM source: Copernicus GLO-30 (downloaded tiles in data_real/terrain/raw/)
  - Features: elevation, slope, aspect, curvature (plan+profile),
               flow_accumulation, TWI, HAND, distance_to_stream,
               catchment_id (from DEM-derived watershed delineation)

RULE: NEVER invent terrain values. If DEM tile not available → null for that area.

For landcover:
  - ESA WorldCover 2021: public AWS bucket (s3://esa-worldcover/) — no auth needed
  - Status: NOT_STARTED (large tile download needed)
  - Script: real_pipeline/features/ingest_worldcover.py (separate)

For soil/geology:
  - ICAR soil data: MANUAL_REQUIRED
  - FAO SoilGrids: open (250m); can be accessed via REST API
  - Status: NOT_STARTED

Output: data_real/features/static_terrain_{region}.parquet
  Each row = one CHIRPS 0.05° grid cell within pilot region
  Terrain features are mean/max/std aggregated from 30m DEM to 0.05° cell
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import Affine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEM_RAW_DIR  = PROJECT_ROOT / "data_real" / "terrain" / "raw"
DEM_PROC_DIR = PROJECT_ROOT / "data_real" / "terrain" / "processed"
FEAT_DIR     = PROJECT_ROOT / "data_real" / "features"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("static_features")

# CHIRPS grid resolution (spatial unit for feature matrix)
CHIRPS_RES = 0.05  # degrees (~5.5 km)

# Pilot region bounding boxes
PILOT_BBOXES = {
    "uttarakhand":    {"lat_min": 28.5, "lat_max": 32.0, "lon_min": 77.5, "lon_max": 81.5},
    "kerala_wayanad": {"lat_min":  9.0, "lat_max": 12.5, "lon_min": 75.0, "lon_max": 78.0},
    "assam":          {"lat_min": 24.0, "lat_max": 28.5, "lon_min": 89.0, "lon_max": 96.5},
}


def generate_chirps_grid(bbox: dict, res: float = CHIRPS_RES) -> pd.DataFrame:
    """
    Generate the CHIRPS 0.05° grid cells for a pilot region.
    Each cell is the spatial unit for the feature matrix.
    """
    import numpy as np
    lats = np.arange(bbox["lat_min"] + res/2, bbox["lat_max"], res)
    lons = np.arange(bbox["lon_min"] + res/2, bbox["lon_max"], res)
    cells = []
    for lat in lats:
        for lon in lons:
            cells.append({
                "cell_id": f"chirps_{lat:.3f}_{lon:.3f}",
                "lat_center": round(lat, 4),
                "lon_center": round(lon, 4),
                "lat_min": round(lat - res/2, 4),
                "lat_max": round(lat + res/2, 4),
                "lon_min": round(lon - res/2, 4),
                "lon_max": round(lon + res/2, 4),
            })
    df = pd.DataFrame(cells)
    log.info(f"  Grid: {len(df)} cells at {res}° resolution")
    return df


def aggregate_dem_to_grid(dem_path: Path, grid_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate 30m DEM (and derived slope/aspect) to CHIRPS grid cells.
    Computes: elev_mean, elev_max, elev_min, elev_std, slope_mean, slope_max, slope_std,
              aspect_mean, pct_slope_gt_30, pct_slope_gt_45.
    For each cell, samples all 30m pixels within the cell bounds.
    """
    # Find available DEM and derived tiles
    dem_tiles = list(DEM_RAW_DIR.glob("*_glo30.tif"))
    slope_tiles = list(DEM_PROC_DIR.glob("*_slope.tif"))
    aspect_tiles = list(DEM_PROC_DIR.glob("*_aspect.tif"))

    if not dem_tiles:
        log.warning("No DEM tiles found. Terrain features will be null.")
        for col in ["elev_mean_m", "elev_max_m", "elev_min_m", "elev_std_m",
                    "slope_mean_deg", "slope_max_deg", "slope_std_deg",
                    "aspect_mean_deg", "pct_slope_gt_30", "pct_slope_gt_45",
                    "terrain_source", "terrain_available"]:
            grid_df[col] = None
        return grid_df

    log.info(f"  DEM tiles available: {[t.name for t in dem_tiles]}")

    # For each tile, load and aggregate to grid
    with rasterio.open(str(dem_tiles[0])) as dem_src:
        dem_data = dem_src.read(1).astype("float32")
        dem_nodata = dem_src.nodata
        dem_transform = dem_src.transform
        if dem_nodata:
            dem_data[dem_data == dem_nodata] = np.nan
        dem_data[dem_data < -100] = np.nan

    slope_data = None
    if slope_tiles:
        with rasterio.open(str(slope_tiles[0])) as slope_src:
            slope_data = slope_src.read(1).astype("float32")
            slope_nodata = slope_src.nodata
            if slope_nodata:
                slope_data[slope_data == slope_nodata] = np.nan
            slope_data[slope_data < 0] = np.nan
            slope_data[slope_data > 90] = np.nan

    aspect_data = None
    if aspect_tiles:
        with rasterio.open(str(aspect_tiles[0])) as asp_src:
            aspect_data = asp_src.read(1).astype("float32")
            asp_nodata = asp_src.nodata
            if asp_nodata:
                aspect_data[aspect_data == asp_nodata] = np.nan

    # DEM bounds (from first tile)
    with rasterio.open(str(dem_tiles[0])) as src:
        dem_bounds = src.bounds
        dem_res = abs(src.transform.a)

    log.info(f"  DEM bounds: lat {dem_bounds.bottom:.2f}–{dem_bounds.top:.2f}, "
             f"lon {dem_bounds.left:.2f}–{dem_bounds.right:.2f}")

    rows_updated = 0
    for idx, cell in grid_df.iterrows():
        # Check overlap with DEM tile
        if (cell["lat_max"] < dem_bounds.bottom or cell["lat_min"] > dem_bounds.top or
                cell["lon_max"] < dem_bounds.left or cell["lon_min"] > dem_bounds.right):
            continue  # cell outside DEM tile → null

        # Pixel indices for this cell
        col_min = max(0, int((cell["lon_min"] - dem_bounds.left) / dem_res))
        col_max = min(dem_data.shape[1], int((cell["lon_max"] - dem_bounds.left) / dem_res) + 1)
        row_min = max(0, int((dem_bounds.top - cell["lat_max"]) / dem_res))
        row_max = min(dem_data.shape[0], int((dem_bounds.top - cell["lat_min"]) / dem_res) + 1)

        if row_min >= row_max or col_min >= col_max:
            continue

        elev_patch = dem_data[row_min:row_max, col_min:col_max]
        valid_elev = elev_patch[~np.isnan(elev_patch)]

        if len(valid_elev) == 0:
            continue

        grid_df.at[idx, "elev_mean_m"] = float(np.nanmean(valid_elev))
        grid_df.at[idx, "elev_max_m"]  = float(np.nanmax(valid_elev))
        grid_df.at[idx, "elev_min_m"]  = float(np.nanmin(valid_elev))
        grid_df.at[idx, "elev_std_m"]  = float(np.nanstd(valid_elev))

        if slope_data is not None:
            slope_patch = slope_data[row_min:row_max, col_min:col_max]
            valid_slope = slope_patch[~np.isnan(slope_patch)]
            if len(valid_slope) > 0:
                grid_df.at[idx, "slope_mean_deg"] = float(np.nanmean(valid_slope))
                grid_df.at[idx, "slope_max_deg"]  = float(np.nanmax(valid_slope))
                grid_df.at[idx, "slope_std_deg"]  = float(np.nanstd(valid_slope))
                grid_df.at[idx, "pct_slope_gt_30"] = float(100 * (valid_slope > 30).mean())
                grid_df.at[idx, "pct_slope_gt_45"] = float(100 * (valid_slope > 45).mean())

        if aspect_data is not None:
            asp_patch = aspect_data[row_min:row_max, col_min:col_max]
            valid_asp = asp_patch[~np.isnan(asp_patch)]
            if len(valid_asp) > 0:
                grid_df.at[idx, "aspect_mean_deg"] = float(np.nanmean(valid_asp))

        grid_df.at[idx, "terrain_source"] = dem_tiles[0].name
        grid_df.at[idx, "terrain_available"] = True
        rows_updated += 1

    log.info(f"  Cells with terrain data: {rows_updated}/{len(grid_df)}")
    return grid_df


def compute_twi_proxy(grid_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute simplified TWI proxy at grid level.
    Full per-pixel TWI requires flow accumulation from full DEM mosaic.
    Grid-level proxy: mean_slope → used only as indicator, not as flow-routing-based TWI.
    Flags as 'grid_twi_proxy' not 'flow_routing_twi'.
    """
    if "slope_mean_deg" not in grid_df.columns:
        return grid_df

    # Cast to float64 first — mixed None/float assignment leaves object dtype
    grid_df["slope_mean_deg"] = pd.to_numeric(grid_df["slope_mean_deg"], errors="coerce")
    valid = grid_df["slope_mean_deg"].notna() & (grid_df["slope_mean_deg"] > 0.1)

    if valid.sum() == 0:
        return grid_df

    # TWI proxy = log(1) - log(tan(slope)) — without actual flow accumulation
    # This is a severe simplification; real TWI requires multi-tile flow routing
    slope_rad = np.radians(grid_df.loc[valid, "slope_mean_deg"].astype(float))
    tan_slope = np.tan(slope_rad)
    tan_slope = tan_slope.clip(lower=0.001)  # avoid log(0)
    grid_df.loc[valid, "twi_proxy_simplified"] = -np.log(tan_slope)
    grid_df.loc[valid, "twi_note"] = "SIMPLIFIED_GRID_PROXY — NOT flow-routing-based TWI"

    log.info(f"  TWI proxy computed for {valid.sum()} cells (simplified, not flow-routing)")
    return grid_df


def add_pilot_region_label(grid_df: pd.DataFrame, region: str) -> pd.DataFrame:
    """Add region metadata to grid."""
    grid_df["pilot_region"] = region
    grid_df["spatial_unit_type"] = "chirps_0.05deg_grid_cell"
    grid_df["data_type"] = "REAL_TERRAIN — NOT SYNTHETIC"
    grid_df["ingested_at"] = datetime.now(timezone.utc).isoformat()
    return grid_df


def build_static_features(region: str) -> pd.DataFrame:
    """Build complete static feature table for a pilot region."""
    log.info(f"\nBuilding static features: {region}")
    bbox = PILOT_BBOXES.get(region)
    if not bbox:
        log.error(f"Unknown region: {region}")
        return pd.DataFrame()

    # Generate CHIRPS grid
    grid_df = generate_chirps_grid(bbox)

    # Initialize terrain columns as null
    for col in ["elev_mean_m", "elev_max_m", "elev_min_m", "elev_std_m",
                "slope_mean_deg", "slope_max_deg", "slope_std_deg", "aspect_mean_deg",
                "pct_slope_gt_30", "pct_slope_gt_45", "terrain_source",
                "terrain_available", "twi_proxy_simplified", "twi_note"]:
        grid_df[col] = None

    # Aggregate DEM to grid
    grid_df = aggregate_dem_to_grid(None, grid_df)  # dem_path unused, uses glob

    # Compute TWI proxy
    grid_df = compute_twi_proxy(grid_df)

    # Add metadata
    grid_df = add_pilot_region_label(grid_df, region)

    # Distance to nearest CWC station
    # This is approximate straight-line distance, not river-network distance
    cwc_stations = pd.DataFrame([
        {"station_id": "UK001", "lat": 30.21, "lon": 78.79, "region": "uttarakhand"},
        {"station_id": "AS001", "lat": 26.14, "lon": 91.74, "region": "assam"},
        {"station_id": "AS002", "lat": 24.83, "lon": 92.80, "region": "assam"},
        {"station_id": "KL001", "lat": 9.98, "lon": 76.28, "region": "kerala_wayanad"},
    ])
    region_stations = cwc_stations[cwc_stations["region"] == region]

    if len(region_stations) > 0:
        def min_station_dist(row):
            dists = np.sqrt(
                (region_stations["lat"].values - row["lat_center"])**2 +
                (region_stations["lon"].values - row["lon_center"])**2
            ) * 111  # approx km
            return float(dists.min()) if len(dists) > 0 else None

        grid_df["nearest_cwc_dist_km"] = grid_df.apply(min_station_dist, axis=1)
        log.info(f"  Nearest CWC station distance: {grid_df['nearest_cwc_dist_km'].describe().round(1).to_dict()}")
    else:
        grid_df["nearest_cwc_dist_km"] = None

    # Coverage summary
    terrain_pct = grid_df["terrain_available"].eq(True).mean() * 100
    log.info(f"  Terrain coverage: {terrain_pct:.1f}% of {len(grid_df)} cells")
    log.info(f"  elev_mean_m range: {grid_df['elev_mean_m'].min():.0f}m – {grid_df['elev_mean_m'].max():.0f}m" if grid_df["elev_mean_m"].notna().any() else "  elev_mean_m: all null (no DEM coverage)")

    return grid_df


def main():
    log.info("=" * 65)
    log.info("ResQ Shield — Static Terrain Features  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)

    FEAT_DIR.mkdir(parents=True, exist_ok=True)

    all_grids = []
    for region in PILOT_BBOXES.keys():
        grid_df = build_static_features(region)
        if not grid_df.empty:
            out_path = FEAT_DIR / f"static_terrain_{region}.parquet"
            grid_df.to_parquet(str(out_path), index=False, engine="pyarrow")
            grid_df.to_csv(str(FEAT_DIR / f"static_terrain_{region}.csv"), index=False)
            log.info(f"  Saved: {out_path} ({len(grid_df)} cells)")
            all_grids.append(grid_df)

    # Combined
    if all_grids:
        combined = pd.concat(all_grids, ignore_index=True)
        combined_path = FEAT_DIR / "static_terrain_all.parquet"
        combined.to_parquet(str(combined_path), index=False, engine="pyarrow")
        log.info(f"\nCombined static features: {combined_path} ({len(combined)} cells)")

        # Report coverage
        log.info(f"\nTerrain coverage by region:")
        for region in PILOT_BBOXES.keys():
            r = combined[combined["pilot_region"] == region]
            n_terrain = r["terrain_available"].eq(True).sum()
            log.info(f"  {region}: {n_terrain}/{len(r)} cells with real terrain data")

    log.info("\nNOT YET computed (require additional data):")
    log.info("  - Flow accumulation (requires multi-tile DEM mosaic)")
    log.info("  - Flow-routing TWI (requires flow accumulation)")
    log.info("  - HAND (Height Above Nearest Drainage) — requires stream network")
    log.info("  - Landcover (ESA WorldCover — large download, see ingest_worldcover.py)")
    log.info("  - Soil type (ICAR MANUAL_REQUIRED / FAO SoilGrids API)")
    log.info("  - Geology (GSI MANUAL_REQUIRED)")


if __name__ == "__main__":
    main()
