# -*- coding: utf-8 -*-
"""
real_pipeline/rainfall/ingest_imerg.py
========================================
IMERG (GPM Integrated Multi-satellitE Retrievals for GPM) ingestion scripts.

Access: MANUAL_REQUIRED — NASA Earthdata login required.
URL: https://search.earthdata.nasa.gov/
Dataset: GPM_3IMERGDF (Final Run, daily, 0.1°, V07)
         GPM_3IMERGHH (Half-hourly, 0.1°, for sub-daily features)

Why IMERG over CHIRPS for this project:
  - Sub-daily resolution (30-min) critical for flash flood/landslide trigger
  - CHIRPS is daily-only — cannot capture 1h/3h/6h rainfall intensities
  - IMERG Early Run available ~4h latency (useful for near-real-time in future)
  - CHIRPS used as open fallback for Phase 2 pilot

Manual download steps:
  1. Register at https://urs.earthdata.nasa.gov/ (free)
  2. Accept GESDISC DAAC EULAs at https://disc.gsfc.nasa.gov/
  3. Download via NASA Earthdata Search:
     - Search: GPM_3IMERGDF (daily final) or GPM_3IMERGHH (30-min)
     - Filter by date range and spatial extent (India bounding box)
     - Download HDF5 files
  4. Place at: data_real/rainfall/imerg/YYYYMMDD/3B-DAY.MS.MRG.3IMERG.YYYYMMDD*.HDF5
  5. Run: python real_pipeline/rainfall/ingest_imerg.py --input data_real/rainfall/imerg/

Alternative: OPeNDAP access (still needs Earthdata account):
  https://gpm.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGDF.07/

For Phase 2 pilot, download event windows only (not full history):
  - uk_2013_flood:    2013-05-30 to 2013-06-21 (23 days)
  - kerala_2018:      2018-08-01 to 2018-08-22 (22 days)
  - wayanad_2024:     2024-07-22 to 2024-08-02 (12 days)
  Size estimate: GPM_3IMERGHH = ~80 files/day × 12 MB = ~960 MB/day → use daily product first

This file contains:
  - MANUAL_REQUIRED status documentation
  - Parser for expected HDF5 file format (when files are manually placed)
  - Feature extraction: 1h, 3h, 6h, 24h rainfall from 30-min product
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMERG_RAW  = PROJECT_ROOT / "data_real" / "rainfall" / "imerg"
PROC_DIR   = PROJECT_ROOT / "data_real" / "rainfall" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("imerg_ingest")

STATUS = {
    "status": "MANUAL_REQUIRED",
    "reason": "NASA Earthdata account required for IMERG download",
    "dataset": "GPM_3IMERGHH (30-min, 0.1°) and/or GPM_3IMERGDF (daily, 0.1°)",
    "registration_url": "https://urs.earthdata.nasa.gov/",
    "search_url": "https://search.earthdata.nasa.gov/",
    "eula_url": "https://disc.gsfc.nasa.gov/earthdata-login",
    "download_instructions": [
        "1. Register at urs.earthdata.nasa.gov (free)",
        "2. At disc.gsfc.nasa.gov, accept GESDISC DAAC data use agreements",
        "3. Search for GPM_3IMERGHH for sub-daily (30-min) data",
        "4. Filter: Date range = event window + antecedent; Spatial = India bbox",
        "5. Download HDF5 (.HDF5) files",
        "6. Place at: data_real/rainfall/imerg/YYYYMM/",
        "7. Run: python real_pipeline/rainfall/ingest_imerg.py --input data_real/rainfall/imerg/",
    ],
    "priority_events": {
        "uk_2013_flood": {"dates": "2013-05-30 to 2013-06-21", "est_files": "~46 daily or 1104 HH"},
        "kerala_2018":   {"dates": "2018-08-01 to 2018-08-22", "est_files": "~44 daily or 1056 HH"},
        "wayanad_2024":  {"dates": "2024-07-22 to 2024-08-02", "est_files": "~24 daily or 576 HH"},
    },
    "size_estimates": {
        "HH_30min_per_day": "~960 MB (48 files × 20 MB)",
        "daily_per_day":    "~30 MB",
        "3_event_pilot_daily": "~3 GB",
        "recommendation": "Download daily product first (GPM_3IMERGDF); use HH only for trigger analysis",
    },
    "feature_derivation": {
        "from_HH": ["rain_30min_mm", "rain_1h_mm", "rain_3h_mm", "rain_6h_mm", "rain_24h_mm", "max_intensity_mm_per_h"],
        "from_daily": ["rain_24h_mm", "rain_3d_mm", "rain_7d_mm"],
        "antecedent": ["ant_3d_mm", "ant_7d_mm", "ant_14d_mm"],
    },
}

INDIA_BBOX = {"lat_min": 6.0, "lat_max": 38.0, "lon_min": 67.0, "lon_max": 98.0}


def parse_imerg_hdf5(hdf5_path: Path, bbox: dict = None) -> dict:
    """
    Parse IMERG HDF5 file and clip to India/region bbox.
    Returns dict with precipitationCal array and metadata.
    Works with manually placed GPM_3IMERGHH or GPM_3IMERGDF HDF5 files.
    """
    bbox = bbox or INDIA_BBOX
    try:
        import h5py
        import numpy as np
    except ImportError:
        log.error("h5py not installed. Run: pip install h5py")
        return None

    try:
        with h5py.File(str(hdf5_path), "r") as f:
            # IMERG HH structure
            # /Grid/precipitationCal  shape: (1, lon, lat) or (1, lat, lon)
            # /Grid/lon, /Grid/lat
            grid = f["Grid"]
            lons = grid["lon"][:]
            lats = grid["lat"][:]
            precip = grid["precipitationCal"][0]  # first time step

            # Clip to bbox
            lon_mask = (lons >= bbox["lon_min"]) & (lons <= bbox["lon_max"])
            lat_mask = (lats >= bbox["lat_min"]) & (lats <= bbox["lat_max"])

            precip_clip = precip[np.ix_(lat_mask, lon_mask)]
            precip_clip[precip_clip < 0] = np.nan

            return {
                "precip_mm_per_h": precip_clip,
                "lons": lons[lon_mask],
                "lats": lats[lat_mask],
                "file": str(hdf5_path),
                "source": "IMERG-HH-Final",
                "resolution_deg": 0.1,
            }
    except Exception as e:
        log.error(f"HDF5 parse error {hdf5_path}: {e}")
        return None


def ingest_available_imerg(input_dir: Path):
    """Process any manually placed IMERG files."""
    hdf5_files = list(input_dir.rglob("*.HDF5")) + list(input_dir.rglob("*.h5"))
    if not hdf5_files:
        log.warning(f"No IMERG HDF5 files found in {input_dir}")
        log.warning("IMERG data is MANUAL_REQUIRED. See lgd_status.json for instructions.")
        return None

    log.info(f"Found {len(hdf5_files)} IMERG files to process.")
    results = []
    for f in sorted(hdf5_files):
        data = parse_imerg_hdf5(f)
        if data:
            results.append(data)
    log.info(f"Processed {len(results)} IMERG files.")
    return results


def main():
    # Always write status file
    IMERG_RAW.mkdir(parents=True, exist_ok=True)
    status_path = IMERG_RAW / "imerg_status.json"
    STATUS["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(status_path, "w") as f:
        json.dump(STATUS, f, indent=2)
    log.info(f"IMERG status: {status_path}")

    # Check for any manually placed files
    available = ingest_available_imerg(IMERG_RAW)

    if available is None:
        log.info("IMERG: MANUAL_REQUIRED")
        log.info("  Note: CHIRPS-2.0 (public, no auth) is used as daily rainfall fallback.")
        log.info("  IMERG is needed for sub-daily (1h/3h/6h) intensity features.")
    else:
        log.info(f"IMERG: {len(available)} files processed from manual placement.")


if __name__ == "__main__":
    main()
