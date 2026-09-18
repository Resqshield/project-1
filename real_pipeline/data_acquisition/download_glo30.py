import os
import requests
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("download_glo30")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data_real" / "terrain" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Pilot bounding boxes: [min_lon, min_lat, max_lon, max_lat]
PILOTS = {
    "uttarakhand": [77.5, 28.5, 81.5, 31.5],
    "kerala": [74.5, 8.0, 77.5, 13.0],
    "assam": [89.5, 24.0, 96.5, 28.5]
}

def get_tile_names(bbox):
    min_lon, min_lat, max_lon, max_lat = bbox
    tiles = []
    for lat in range(int(min_lat), int(max_lat) + 1):
        for lon in range(int(min_lon), int(max_lon) + 1):
            lat_str = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
            lon_str = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
            tile_name = f"Copernicus_DSM_COG_10_{lat_str}_00_{lon_str}_00_DEM"
            tiles.append(tile_name)
    return tiles

def download_tile(tile_name):
    # s3.eu-central-1.amazonaws.com
    url = f"https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/{tile_name}/{tile_name}.tif"
    out_file = OUT_DIR / f"{tile_name}.tif"
    if out_file.exists() and out_file.stat().st_size > 100000:
        log.info(f"Skipping {tile_name}, already exists")
        return True
    
    log.info(f"Downloading {url} ...")
    try:
        r = requests.get(url, stream=True, timeout=15)
        if r.status_code == 200:
            with open(out_file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            log.info(f"Saved {out_file.name}")
            return True
        else:
            log.warning(f"Failed {tile_name}: HTTP {r.status_code}")
            return False
    except Exception as e:
        log.error(f"Error downloading {tile_name}: {e}")
        return False

def main():
    log.info("Starting Copernicus GLO-30 DEM acquisition...")
    success = 0
    failed = 0
    for region, bbox in PILOTS.items():
        log.info(f"Processing {region} bbox: {bbox}")
        tiles = get_tile_names(bbox)
        for t in tiles:
            if download_tile(t):
                success += 1
            else:
                failed += 1
    
    log.info(f"DEM Download Complete. Success: {success}, Failed: {failed}")
    # Write provenance
    prov = OUT_DIR / "provenance.txt"
    prov.write_text("Source: Copernicus GLO-30 DEM via AWS Open Data\nLicense: Open\nAcquired via download_glo30.py")

if __name__ == "__main__":
    main()
