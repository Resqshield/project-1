import os
import requests
import json
from pathlib import Path
import logging
import time

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fetch_evacuation")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data_real" / "infrastructure" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

REGIONS = {
    "North": [73.0, 28.0, 81.0, 37.5],      # J&K, Ladakh, HP, Punjab, UK, Haryana
    "West": [68.0, 20.0, 78.0, 28.0],       # Rajasthan, Gujarat
    "Central": [78.0, 20.0, 88.0, 28.0],    # UP, MP, CG, Bihar, Jharkhand
    "East": [88.0, 21.0, 98.0, 29.5],       # WB, Northeast
    "SouthWest": [72.0, 8.0, 80.0, 20.0],   # MH, Goa, KA, KL, TN
    "SouthEast": [80.0, 8.0, 85.0, 20.0],   # AP, TL, OD
}

def overpass_query(bbox_list, query_str):
    west, south, east, north = bbox_list
    bbox_fmt = f"{south},{west},{north},{east}"
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json][timeout:180];
    (
      {query_str.format(bbox=bbox_fmt)}
    );
    out center;
    """
    
    try:
        headers = {'User-Agent': 'ResQShield-Research-Agent/2.0'}
        for attempt in range(3):
            response = requests.post(overpass_url, data={'data': query}, headers=headers, timeout=180)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                log.warning("Rate limited (429), sleeping 15s...")
                time.sleep(15)
            elif response.status_code == 504:
                log.warning(f"Overpass returned HTTP 504 (timeout) on attempt {attempt+1}")
                time.sleep(15)
            else:
                log.warning(f"Overpass returned HTTP {response.status_code} (attempt {attempt+1})")
        return None
    except Exception as e:
        log.error(f"Overpass query failed: {e}")
        return None

def main():
    log.info("Starting Evacuation data acquisition (hospitals, clinics, shelters)...")
    
    features = []
    seen_coords = set()
    
    for region, bbox in REGIONS.items():
        log.info(f"Fetching for {region}...")
        q = """
          node["amenity"~"hospital|clinic|shelter"]({bbox});
          way["amenity"~"hospital|clinic|shelter"]({bbox});
          relation["amenity"~"hospital|clinic|shelter"]({bbox});
        """
        data = overpass_query(bbox, q)
        if not data:
            continue
            
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            amenity = tags.get("amenity")
            name = tags.get("name", "Unknown Facility")
            
            # extract lat/lon
            lat = el.get("lat") or (el.get("center", {}).get("lat"))
            lon = el.get("lon") or (el.get("center", {}).get("lon"))
            
            if lat is not None and lon is not None:
                coord_key = (round(lon, 5), round(lat, 5))
                if coord_key not in seen_coords:
                    seen_coords.add(coord_key)
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "properties": {
                            "amenity": amenity,
                            "name": name,
                            "region": region
                        }
                    })
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    out_file = OUT_DIR / "evacuation_points.geojson"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f)
        
    log.info(f"Saved {len(features)} evacuation points to {out_file.name}")

if __name__ == "__main__":
    main()
