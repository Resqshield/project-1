import os
import requests
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("download_osm")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data_real" / "osm" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PILOTS = {
    "uttarakhand": [77.5, 28.5, 81.5, 31.5],
    "kerala": [74.5, 8.0, 77.5, 13.0],
    "assam": [89.5, 24.0, 96.5, 28.5]
}

def overpass_query(bbox_list, query_str):
    # bbox in overpass is [south, west, north, east]
    # our bbox is [min_lon, min_lat, max_lon, max_lat] -> [west, south, east, north]
    west, south, east, north = bbox_list
    bbox_fmt = f"{south},{west},{north},{east}"
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json][timeout:25];
    (
      {query_str.format(bbox=bbox_fmt)}
    );
    out body;
    >;
    out skel qt;
    """
    
    log.info(f"Querying Overpass: {query_str.split()[0]}...")
    try:
        headers = {'User-Agent': 'ResQShield-Research-Agent/1.0 (test)'}
        response = requests.post(overpass_url, data={'data': query}, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            log.warning(f"Overpass returned HTTP {response.status_code}")
            return None
    except Exception as e:
        log.error(f"Overpass query failed: {e}")
        return None

def main():
    log.info("Starting OSM data acquisition (roads, shelters)...")
    for region, bbox in PILOTS.items():
        # Roads (primary, secondary, trunk)
        roads_query = """
          way["highway"~"primary|secondary|trunk"]({bbox});
        """
        roads_data = overpass_query(bbox, roads_query)
        if roads_data:
            roads_file = OUT_DIR / f"{region}_roads.json"
            with open(roads_file, 'w') as f:
                json.dump(roads_data, f)
            log.info(f"Saved {roads_file.name}")
        
        # Shelters (amenity=shelter or emergency=designated)
        shelters_query = """
          node["amenity"="shelter"]({bbox});
          way["amenity"="shelter"]({bbox});
        """
        shelters_data = overpass_query(bbox, shelters_query)
        if shelters_data:
            shelters_file = OUT_DIR / f"{region}_shelters.json"
            with open(shelters_file, 'w') as f:
                json.dump(shelters_data, f)
            log.info(f"Saved {shelters_file.name}")

    prov = OUT_DIR / "provenance.txt"
    prov.write_text("Source: OpenStreetMap via Overpass API\nLicense: ODbL\nAcquired via download_osm.py")
    log.info("OSM data acquisition complete.")

if __name__ == "__main__":
    main()
