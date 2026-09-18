import os
import json
import logging
from pathlib import Path
import geopandas as gpd
import rasterio

logging.basicConfig(level=logging.INFO, format="%(message)s")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data_real" / "labels" / "footprints" / "raw"
MANIFEST_PATH = PROJECT_ROOT / "data_real" / "labels" / "footprints" / "manifest.json"

INVALID_KEYWORDS = ["reference", "administrative", "boundary", "background", "dem", "physiography", "transportation"]

def load_manifest():
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r") as f:
            return json.load(f)
    return {"events": []}

def save_manifest(manifest):
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

def validate_vector(path):
    try:
        gdf = gpd.read_file(path)
        if gdf.empty:
            return False, "Vector file contains zero features."
        if not gdf.crs:
            return False, "Vector file is missing a CRS."
        # Check for invalid keywords in geometry attributes/names
        import pandas as pd
        for col in gdf.columns:
            if pd.api.types.is_string_dtype(gdf[col]) or pd.api.types.is_object_dtype(gdf[col]):
                sample = " ".join(gdf[col].dropna().astype(str).str.lower().unique())
                for kw in INVALID_KEYWORDS:
                    if kw in sample:
                        return False, f"Potential reference/background data detected in column {col}."
        return True, "Valid Vector Geometry"
    except Exception as e:
        return False, f"Failed to parse vector: {e}"

def validate_raster(path):
    try:
        with rasterio.open(path) as src:
            if src.width == 0 or src.height == 0:
                return False, "Raster has zero dimensions."
            if not src.crs:
                return False, "Raster is missing a CRS."
            # Check bands
            if src.count < 1:
                return False, "Raster has zero bands."
        return True, "Valid Raster Array"
    except Exception as e:
        return False, f"Failed to parse raster: {e}"

def is_forbidden_filename(filename):
    lower = filename.lower()
    for kw in INVALID_KEYWORDS:
        if kw in lower:
            return True, f"Filename contains forbidden keyword: {kw}"
    return False, ""

def ingest():
    if not RAW_DIR.exists():
        logging.error(f"Raw directory does not exist: {RAW_DIR}")
        return

    manifest = load_manifest()
    events_dict = {ev["event_id"]: ev for ev in manifest.get("events", [])}
    
    files = list(RAW_DIR.rglob("*"))
    valid_exts = {".shp", ".geojson", ".gpkg", ".tif", ".tiff"}
    
    found_any = False
    
    for f in files:
        if f.is_file() and f.suffix.lower() in valid_exts:
            found_any = True
            logging.info(f"\nEvaluating: {f.name}")
            
            forbidden, reason = is_forbidden_filename(f.name)
            if forbidden:
                logging.error(f"REJECTED: {reason}")
                continue
                
            is_valid = False
            msg = ""
            if f.suffix.lower() in {".shp", ".geojson", ".gpkg"}:
                is_valid, msg = validate_vector(f)
            else:
                is_valid, msg = validate_raster(f)
                
            if not is_valid:
                logging.error(f"REJECTED: {msg}")
                continue
                
            logging.info(f"ACCEPTED: {msg}")
            
            # Map to an event if possible
            matched_event = None
            for eid in events_dict.keys():
                if eid in f.name:
                    matched_event = eid
                    break
                    
            if matched_event:
                events_dict[matched_event]["status"] = "ACQUIRED"
                events_dict[matched_event]["local_path"] = str(f.relative_to(PROJECT_ROOT))
                events_dict[matched_event]["format"] = f.suffix.lower()
                logging.info(f"Matched file to event: {matched_event}")
            else:
                logging.warning(f"File {f.name} is valid but does not match any known event ID in its filename. It is unassigned.")
                
    manifest["events"] = list(events_dict.values())
    save_manifest(manifest)
    logging.info("\nIngestion complete. Updated manifest.json.")

if __name__ == "__main__":
    ingest()
