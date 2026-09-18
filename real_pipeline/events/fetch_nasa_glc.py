import os
import requests
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fetch_nasa_glc")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data_real" / "events" / "landslide" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    # NASA GLC is hosted on data.nasa.gov (Socrata)
    # Dataset ID for Global Landslide Catalog: "dd9e-wu2v"
    url = "https://data.nasa.gov/resource/dd9e-wu2v.json?$limit=50000&$where=country_name='India'"
    out_file = OUT_DIR / "nasa_glc_india.json"
    
    log.info(f"Querying NASA GLC for India landslides...")
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            with open(out_file, 'w') as f:
                json.dump(data, f)
            log.info(f"Saved {len(data)} events to {out_file.name}")
            
            # Write provenance
            prov = OUT_DIR / "provenance_nasa.txt"
            prov.write_text("Source: NASA Global Landslide Catalog (data.nasa.gov)\nLicense: Open\nAcquired via fetch_nasa_glc.py")
        else:
            log.warning(f"Failed to fetch NASA GLC: HTTP {response.status_code}")
    except Exception as e:
        log.error(f"Error fetching NASA GLC: {e}")

if __name__ == "__main__":
    main()
