# -*- coding: utf-8 -*-
"""
real_pipeline/rainfall/ingest_chirps_v2.py
===========================================
Download CHIRPS for new pilot regions added in flood event expansion v2.

New regions requiring CHIRPS:
  - bihar_ganga_plains
  - odisha_coastal
  - odisha_mahanadi
  - maharashtra_kolhapur
  - himachal_pradesh

For each new event:
  1. Event window (positive samples)
  2. Pre-event antecedent window (14 days before event start)
  3. Matched negative window + its antecedent window

CHIRPS v2.0 source: UCSB Climate Hazards Group
  URL: https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/

Note: Existing pilot regions (uttarakhand, kerala_wayanad, assam) already have
CHIRPS downloaded. Only new regions are fetched here.
"""

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ingest_chirps_v2")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Import existing CHIRPS ingester
try:
    from real_pipeline.rainfall.ingest_chirps import download_chirps_day, RAW_DIR as CHIRPS_DIR
except ImportError:
    log.error("Cannot import ingest_chirps. Run from project root.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# New pilot bboxes for event-expanded regions
# ─────────────────────────────────────────────────────────────────────────────

NEW_PILOT_BBOXES = {
    "bihar_ganga_plains":    {"lat_min": 24.5, "lat_max": 27.5, "lon_min": 83.5, "lon_max": 88.5},
    "odisha_coastal":        {"lat_min": 18.5, "lat_max": 21.5, "lon_min": 84.0, "lon_max": 87.5},
    "odisha_mahanadi":       {"lat_min": 19.5, "lat_max": 22.0, "lon_min": 83.5, "lon_max": 87.0},
    "maharashtra_kolhapur":  {"lat_min": 15.5, "lat_max": 18.5, "lon_min": 73.0, "lon_max": 77.0},
    "himachal_pradesh":      {"lat_min": 30.5, "lat_max": 33.5, "lon_min": 75.5, "lon_max": 79.5},
}

# ─────────────────────────────────────────────────────────────────────────────
# Download windows: (region, window_label, start_date, end_date)
# Includes event window + 14-day antecedent + matched negative + its antecedent
# ─────────────────────────────────────────────────────────────────────────────

DOWNLOAD_WINDOWS = [
    # Bihar 2017 flood
    ("bihar_ganga_plains", "event",      date(2017, 8, 10), date(2017, 8, 31)),
    ("bihar_ganga_plains", "antecedent", date(2017, 7, 27), date(2017, 8,  9)),
    ("bihar_ganga_plains", "negative",   date(2017, 2,  1), date(2017, 2, 14)),
    ("bihar_ganga_plains", "neg_ant",    date(2017, 1, 18), date(2017, 1, 31)),

    # Bihar 2019 flood
    ("bihar_ganga_plains", "event",      date(2019, 7, 11), date(2019, 8, 15)),
    ("bihar_ganga_plains", "antecedent", date(2019, 6, 27), date(2019, 7, 10)),

    # Odisha coastal 2018 (Cyclone Titli)
    ("odisha_coastal", "event",      date(2018, 9, 23), date(2018, 10, 5)),
    ("odisha_coastal", "antecedent", date(2018, 9,  9), date(2018, 9, 22)),
    ("odisha_coastal", "negative",   date(2019, 2,  1), date(2019, 2, 14)),
    ("odisha_coastal", "neg_ant",    date(2019, 1, 18), date(2019, 1, 31)),

    # Odisha Mahanadi 2020
    ("odisha_mahanadi", "event",      date(2020, 8, 20), date(2020, 9,  5)),
    ("odisha_mahanadi", "antecedent", date(2020, 8,  6), date(2020, 8, 19)),
    ("odisha_mahanadi", "negative",   date(2020, 1,  1), date(2020, 1, 14)),
    ("odisha_mahanadi", "neg_ant",    date(2019, 12, 18), date(2019, 12, 31)),

    # Maharashtra Kolhapur 2021
    ("maharashtra_kolhapur", "event",      date(2021, 7, 21), date(2021, 8,  2)),
    ("maharashtra_kolhapur", "antecedent", date(2021, 7,  7), date(2021, 7, 20)),
    ("maharashtra_kolhapur", "negative",   date(2021, 1, 10), date(2021, 1, 23)),
    ("maharashtra_kolhapur", "neg_ant",    date(2020, 12, 27), date(2021, 1,  9)),

    # Himachal Pradesh 2023
    ("himachal_pradesh", "event",      date(2023, 8, 13), date(2023, 8, 16)),
    ("himachal_pradesh", "antecedent", date(2023, 7, 30), date(2023, 8, 12)),
    ("himachal_pradesh", "negative",   date(2023, 4,  1), date(2023, 4, 14)),
    ("himachal_pradesh", "neg_ant",    date(2023, 3, 18), date(2023, 3, 31)),

    # Assam 2017 (same region as existing assam, new event window)
    ("assam", "event",      date(2017, 7,  5), date(2017, 7, 30)),
    ("assam", "antecedent", date(2017, 6, 21), date(2017, 7,  4)),
    ("assam", "negative",   date(2017, 4,  1), date(2017, 4, 14)),
    ("assam", "neg_ant",    date(2017, 3, 18), date(2017, 3, 31)),
]

# Existing assam bbox already in ingest_chirps.py
EXISTING_BBOXES = {
    "uttarakhand":    {"lat_min": 28.5, "lat_max": 32.0, "lon_min": 77.5, "lon_max": 81.5},
    "kerala_wayanad": {"lat_min":  9.0, "lat_max": 12.5, "lon_min": 75.0, "lon_max": 78.0},
    "assam":          {"lat_min": 24.0, "lat_max": 28.5, "lon_min": 89.0, "lon_max": 96.5},
}

ALL_BBOXES = {**EXISTING_BBOXES, **NEW_PILOT_BBOXES}


def estimate_download_size() -> dict:
    """Estimate total download before starting."""
    total_days = 0
    regions_seen = set()

    for region, window_type, start, end in DOWNLOAD_WINDOWS:
        n_days = (end - start).days + 1
        total_days += n_days
        regions_seen.add(region)

    # CHIRPS global daily: ~300KB-1MB per day at 0.05 deg
    estimated_mb = total_days * 0.5  # conservative
    return {
        "total_days": total_days,
        "unique_regions": len(regions_seen),
        "estimated_mb": round(estimated_mb, 1),
        "note": "Each CHIRPS daily file is ~300-600KB. Only clipped tiles saved.",
    }


def already_downloaded(region: str, d: date) -> bool:
    """Check if CHIRPS tile already exists."""
    tif_path = CHIRPS_DIR / f"chirps_{region}_{d.strftime('%Y%m%d')}.tif"
    return tif_path.exists()


def main():
    import json

    log.info("=" * 65)
    log.info("ResQ Shield — CHIRPS v2 (New Regions)  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)

    est = estimate_download_size()
    log.info(f"\nDownload estimate:")
    log.info(f"  Total event days: {est['total_days']}")
    log.info(f"  Regions: {est['unique_regions']}")
    log.info(f"  Estimated disk: ~{est['estimated_mb']:.0f} MB")
    log.info(f"  (Only clipped regional tiles saved, not global files)")

    downloaded_ok = 0
    downloaded_skip = 0
    downloaded_fail = 0

    for region, window_type, start, end in DOWNLOAD_WINDOWS:
        bbox = ALL_BBOXES.get(region)
        if not bbox:
            log.warning(f"  No bbox for {region} — skipping")
            continue

        current = start
        while current <= end:
            if already_downloaded(region, current):
                downloaded_skip += 1
            else:
                ok = download_chirps_day(current, region, bbox)
                if ok:
                    downloaded_ok += 1
                else:
                    downloaded_fail += 1
            current += timedelta(days=1)

        log.info(f"  [{window_type}] {region} {start}--{end}: done")

    log.info(f"\n{'='*50}")
    log.info(f"CHIRPS v2 download complete:")
    log.info(f"  Downloaded: {downloaded_ok}")
    log.info(f"  Already existed: {downloaded_skip}")
    log.info(f"  Failed: {downloaded_fail}")

    summary = {
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "downloaded_ok": downloaded_ok,
        "downloaded_skip": downloaded_skip,
        "downloaded_fail": downloaded_fail,
        "total_windows": len(DOWNLOAD_WINDOWS),
        "new_regions": list(NEW_PILOT_BBOXES.keys()),
        "data_type": "REAL_DATA — NOT SYNTHETIC",
    }
    out = PROJECT_ROOT / "data_real" / "rainfall" / "processed" / "chirps_v2_download_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    log.info(f"[OK] Summary: {out}")


if __name__ == "__main__":
    main()
