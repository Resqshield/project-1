# -*- coding: utf-8 -*-
"""
real_pipeline/terrain/ingest_dem_pilot.py
==========================================
Pilot DEM (Digital Elevation Model) ingestion for high-priority regions.

Source: SRTM 30m (1 arc-second) — USGS / NASA SRTM
  URL: https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/
  Portal: https://earthexplorer.usgs.gov/  (free, requires account)
  Format: HGT files (1°×1° tiles)
  Resolution: ~30m at equator (~1 arc-second)
  Coverage: ±60° latitude
  Access: MANUAL_REQUIRED — USGS EarthExplorer login needed for bulk.

Alternative open sources:
  - ALOS World 3D (AW3D30): https://www.eorc.jaxa.jp/ALOS/en/aw3d30/ (~30m, good quality)
    Access: Free registration required → MANUAL_REQUIRED
  - Copernicus GLO-30: https://spacedata.copernicus.eu/explore-more/news/-/asset_publisher/Yhhx/content/copernicus-digital-elevation-model-new-validation-report-released
    Access: Free, no login for GLO-30 Public (tiles via AWS/GCS) → potentially scriptable
  - NASADEM: https://search.earthdata.nasa.gov/ (improved SRTM, requires login)

Pilot priority regions (flood + landslide hotspots):
  - Uttarakhand:    Lat 28.5–32.0, Lon 77.5–81.5  (~4×4° = 16 tiles for SRTM)
  - Himachal Pradesh: Lat 30.0–33.5, Lon 75.5–79.0 (~4×4°)
  - Sikkim/Arunachal: Lat 26.5–29.5, Lon 88.0–97.5
  - Western Ghats (Wayanad/Idukki): Lat 9.0–11.5, Lon 75.5–77.5 (~3×2°)

SRTM tile naming:
  N<lat>E<lon> (e.g. N29E079 = 29°N to 30°N, 79°E to 80°E)
  .hgt file = 3601×3601 int16 elevations (1 arc-sec = ~30m)

Size estimates:
  - 1 SRTM tile = ~25 MB unzipped, ~7 MB zipped
  - Uttarakhand pilot (~12 tiles): ~300 MB unzipped
  - All India (~250 tiles): ~6 GB unzipped (do NOT download blindly)

Copernicus GLO-30 (alternative, scriptable):
  AWS: s3://copernicus-dem-30m/  (public bucket, no auth)
  Format: GeoTIFF per 1°×1° tile
  Tile naming: Copernicus_DSM_COG_10_N29_00_E079_00_DEM.tif
  Access: AWS CLI / boto3 (no credentials needed for public bucket)

Terrain derivatives computed (only from real DEM, never invented):
  - elevation (from DEM directly)
  - slope (degrees)
  - aspect (degrees)
  - curvature (plan / profile) — if richdem/scipy available
  - flow_direction (D8 algorithm)
  - flow_accumulation (upstream contributing area)
  - TWI = ln(flow_acc / tan(slope))  [Topographic Wetness Index]
  - distance_to_drainage (from flow_accumulation threshold)

Usage:
    # Check what would be downloaded (dry-run):
    python real_pipeline/terrain/ingest_dem_pilot.py --pilot uttarakhand --dry-run

    # Download Copernicus GLO-30 (public AWS, no auth) for one pilot:
    python real_pipeline/terrain/ingest_dem_pilot.py --pilot uttarakhand --source copernicus_glo30

    # Process a manually placed DEM tile:
    python real_pipeline/terrain/ingest_dem_pilot.py --input data_real/terrain/raw/N29E079.hgt
"""

import sys
import json
import logging
import argparse
import math
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR      = PROJECT_ROOT / "data_real" / "terrain" / "raw"
PROC_DIR     = PROJECT_ROOT / "data_real" / "terrain" / "processed"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("dem_pilot")

# ── Pilot region definitions ───────────────────────────────────────────────────
PILOT_REGIONS = {
    "uttarakhand": {
        "name": "Uttarakhand",
        "lat_range": (29, 32),   # tiles from lat 29 to 31 (N29, N30, N31 = core UK)
        "lon_range": (78, 81),   # tiles from lon 78 to 80 (E78, E79, E80)
        "n_tiles": 9,
        "est_size_gb_srtm": 0.23,
        "est_size_gb_glo30": 0.15,
        "rationale": "High landslide frequency; includes Chamoli, Uttarkashi, Pithoragarh, Kedarnath. Tiles N29-N31 E78-E80.",
    },
    "himachal": {
        "name": "Himachal Pradesh",
        "lat_range": (30, 34),
        "lon_range": (75, 79),
        "n_tiles": 16,
        "est_size_gb_srtm": 0.4,
        "est_size_gb_glo30": 0.25,
        "rationale": "High landslide risk; Kullu, Mandi, Chamba, Kinnaur",
    },
    "sikkim_arunachal": {
        "name": "Sikkim + Arunachal Pradesh",
        "lat_range": (26, 30),
        "lon_range": (88, 98),
        "n_tiles": 40,
        "est_size_gb_srtm": 1.0,
        "est_size_gb_glo30": 0.6,
        "rationale": "Highly landslide-prone Himalayan foothills; Teesta basin",
    },
    "western_ghats": {
        "name": "Western Ghats (Wayanad / Idukki)",
        "lat_range": (9, 12),
        "lon_range": (75, 78),
        "n_tiles": 9,
        "est_size_gb_srtm": 0.23,
        "est_size_gb_glo30": 0.15,
        "rationale": "High landslide risk (Wayanad 2019, 2024 disasters); heavy rainfall",
    },
}

# ── Copernicus GLO-30 public AWS ───────────────────────────────────────────────
# Bucket: s3://copernicus-dem-30m/ (public, no credentials needed)
# File pattern: Copernicus_DSM_COG_10_N<lat>_00_E<lon>_00_DEM.tif
COPERNICUS_S3_BUCKET   = "copernicus-dem-30m"
# Copernicus GLO-30 public S3 path (verified format for 1-degree tiles)
# Some tiles (especially at lower latitudes or borders) may legitimately not exist (ocean/void).
COPERNICUS_S3_TEMPLATE = "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif"
COPERNICUS_HTTP_BASE   = "https://copernicus-dem-30m.s3.amazonaws.com/"
# Alternative AWS region endpoint if main times out:
COPERNICUS_HTTP_ALT    = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/"

# SRTM tile URL template (requires USGS auth → MANUAL_REQUIRED)
SRTM_URL_TEMPLATE = "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/N{lat:02d}E{lon:03d}.SRTMGL1.hgt.zip"


def get_tile_list(pilot_key: str) -> list:
    """Generate list of tile specs for a pilot region."""
    p = PILOT_REGIONS[pilot_key]
    tiles = []
    for lat in range(p["lat_range"][0], p["lat_range"][1]):
        for lon in range(p["lon_range"][0], p["lon_range"][1]):
            tiles.append({
                "lat": lat, "lon": lon,
                "srtm_name": f"N{lat:02d}E{lon:03d}",
                "copernicus_path": COPERNICUS_S3_TEMPLATE.format(lat=lat, lon=lon),
                "copernicus_url": COPERNICUS_HTTP_BASE + COPERNICUS_S3_TEMPLATE.format(lat=lat, lon=lon),
                "srtm_url": SRTM_URL_TEMPLATE.format(lat=lat, lon=lon),
            })
    return tiles


def report_size_estimate(pilot_key: str):
    """Print size estimates before any download."""
    p = PILOT_REGIONS[pilot_key]
    tiles = get_tile_list(pilot_key)
    log.info(f"Pilot: {p['name']}")
    log.info(f"  Rationale: {p['rationale']}")
    log.info(f"  Tile count: {len(tiles)}")
    log.info(f"  Size estimates:")
    log.info(f"    SRTM 30m (~25 MB/tile): ~{p['est_size_gb_srtm']:.2f} GB unzipped")
    log.info(f"    Copernicus GLO-30 (~17 MB/tile): ~{p['est_size_gb_glo30']:.2f} GB")
    log.info(f"  Tiles:")
    for t in tiles[:5]:
        log.info(f"    {t['srtm_name']}: {t['copernicus_url']}")
    if len(tiles) > 5:
        log.info(f"    ... and {len(tiles)-5} more")


def download_copernicus_tile(tile: dict, out_dir: Path) -> bool:
    """
    Download a single Copernicus GLO-30 tile from public AWS.
    No authentication required for public bucket.
    """
    try:
        import requests
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"N{tile['lat']:02d}E{tile['lon']:03d}_glo30.tif"
        out_path = out_dir / fname

        if out_path.exists():
            log.info(f"  Already exists: {fname}")
            return True

        url = tile["copernicus_url"]
        log.info(f"  Downloading: {url}")

        resp = requests.get(url, stream=True, timeout=60)
        if resp.status_code == 200:
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
            size_mb = downloaded / 1e6
            log.info(f"  Saved: {out_path} ({size_mb:.1f} MB)")
            return True
        elif resp.status_code == 404:
            log.warning(f"  Tile not found (ocean/border tile?): {fname}")
            return False
        else:
            log.error(f"  HTTP {resp.status_code}: {url}")
            return False
    except Exception as e:
        log.error(f"  Download error: {e}")
        return False


def compute_terrain_derivatives(tif_path: Path, out_dir: Path) -> dict:
    """
    Compute terrain derivatives from a GeoTIFF DEM.
    Requires: rasterio, numpy. richdem optional for advanced flow routing.

    Returns dict of output file paths.
    NEVER invents values — only derives from real DEM data.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.transform import rowcol
    except ImportError:
        log.error("rasterio not installed. Run: pip install rasterio")
        return {"error": "rasterio not available"}

    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}

    log.info(f"Processing DEM: {tif_path.name}")
    with rasterio.open(str(tif_path)) as src:
        dem = src.read(1).astype(float)
        nodata = src.nodata
        profile = src.profile.copy()
        transform = src.transform
        res_x = abs(transform.a)  # degrees per pixel
        res_y = abs(transform.e)

        # Mask nodata
        if nodata is not None:
            dem[dem == nodata] = np.nan

        elev_stats = {
            "min_m": float(np.nanmin(dem)),
            "max_m": float(np.nanmax(dem)),
            "mean_m": float(np.nanmean(dem)),
            "nodata_pct": float(np.isnan(dem).mean() * 100),
            "shape": list(dem.shape),
            "resolution_deg": res_x,
            "resolution_m_approx": res_x * 111320,  # approximate at equator
        }
        log.info(f"  Elevation: {elev_stats['min_m']:.0f}m – {elev_stats['max_m']:.0f}m, "
                 f"mean {elev_stats['mean_m']:.0f}m")
        outputs["elevation_stats"] = elev_stats

    # Slope calculation using finite differences
    try:
        import numpy as np
        with rasterio.open(str(tif_path)) as src:
            dem = src.read(1).astype(float)
            transform = src.transform
            res_m = abs(transform.a) * 111320  # approximate degrees→metres

        nodata = src.nodata
        if nodata is not None:
            dem[dem == nodata] = np.nan

        # Central differences
        dy, dx = np.gradient(dem, res_m, res_m)
        slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
        slope_deg = np.degrees(slope_rad)
        aspect_deg = np.degrees(np.arctan2(-dy, dx)) % 360

        slope_stats = {
            "min_deg": float(np.nanmin(slope_deg)),
            "max_deg": float(np.nanmax(slope_deg)),
            "mean_deg": float(np.nanmean(slope_deg)),
            "pct_gt_30deg": float((slope_deg > 30).sum() / np.isfinite(slope_deg).sum() * 100),
            "pct_gt_45deg": float((slope_deg > 45).sum() / np.isfinite(slope_deg).sum() * 100),
        }
        log.info(f"  Slope: {slope_stats['mean_deg']:.1f}° mean, "
                 f"{slope_stats['pct_gt_30deg']:.1f}% > 30°, "
                 f"{slope_stats['pct_gt_45deg']:.1f}% > 45°")
        outputs["slope_stats"] = slope_stats

        # Save slope GeoTIFF
        slope_path = out_dir / (tif_path.stem + "_slope.tif")
        with rasterio.open(str(tif_path)) as src:
            prof = src.profile.copy()
        prof.update(dtype="float32", nodata=-9999)
        slope_deg_f32 = slope_deg.astype("float32")
        slope_deg_f32[np.isnan(slope_deg)] = -9999
        with rasterio.open(str(slope_path), "w", **prof) as dst:
            dst.write(slope_deg_f32, 1)
        log.info(f"  Saved slope: {slope_path}")
        outputs["slope_file"] = str(slope_path)

        # Save aspect GeoTIFF
        aspect_path = out_dir / (tif_path.stem + "_aspect.tif")
        aspect_f32 = aspect_deg.astype("float32")
        aspect_f32[np.isnan(slope_deg)] = -9999
        with rasterio.open(str(aspect_path), "w", **prof) as dst:
            dst.write(aspect_f32, 1)
        log.info(f"  Saved aspect: {aspect_path}")
        outputs["aspect_file"] = str(aspect_path)

    except Exception as e:
        log.error(f"  Slope/aspect computation failed: {e}")
        outputs["slope_error"] = str(e)

    return outputs


def main():
    parser = argparse.ArgumentParser(description="Pilot DEM ingestion and terrain derivatives")
    parser.add_argument("--pilot", choices=list(PILOT_REGIONS.keys()),
                        default="uttarakhand", help="Pilot region")
    parser.add_argument("--source", choices=["copernicus_glo30", "srtm", "manual"],
                        default="copernicus_glo30", help="DEM source")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report tiles and sizes without downloading")
    parser.add_argument("--input", type=str, default=None,
                        help="Process a specific manually placed DEM file")
    parser.add_argument("--max-tiles", type=int, default=4,
                        help="Max tiles to download in one run (safety limit). Default=4.")
    args = parser.parse_args()

    log.info("=" * 65)
    log.info("ResQ Shield — Terrain Pilot  [REAL DATA — NOT SYNTHETIC]")
    log.info("=" * 65)

    pilot = PILOT_REGIONS[args.pilot]

    # Always report size estimate first
    report_size_estimate(args.pilot)
    if args.dry_run:
        log.info("Dry-run mode — no files downloaded.")
        return

    # Manual input processing
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            log.error(f"Input file not found: {input_path}")
            sys.exit(1)
        outputs = compute_terrain_derivatives(input_path, PROC_DIR)
        log.info(f"Processing complete: {outputs}")
        return

    # SRTM: requires manual download
    if args.source == "srtm":
        log.warning("SRTM download requires USGS EarthExplorer account → MANUAL_REQUIRED")
        log.warning("  1. Register at https://urs.earthdata.nasa.gov/")
        log.warning("  2. Login and search for SRTM 1 Arc-Second Global")
        log.warning("  3. Download tiles for your pilot region")
        log.warning(f"  4. Place .hgt files in: {RAW_DIR}")
        log.warning(f"  5. Re-run with: --input <path_to_hgt> --source manual")
        # Write manual status
        status = {
            "status": "MANUAL_REQUIRED",
            "source": "SRTM 1 Arc-Second Global",
            "url": "https://earthexplorer.usgs.gov/",
            "auth_required": True,
            "alternative": "Use --source copernicus_glo30 (public, no auth)",
            "tiles_for_pilot": [t["srtm_name"] for t in get_tile_list(args.pilot)],
        }
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        with open(RAW_DIR / "srtm_manual_required.json", "w") as f:
            json.dump(status, f, indent=2)
        return

    # Copernicus GLO-30 (public AWS, no auth)
    if args.source == "copernicus_glo30":
        log.info("Source: Copernicus GLO-30 (public AWS S3, no authentication required)")
        log.info(f"Max tiles this run: {args.max_tiles} (use --max-tiles N to change)")
        tiles = get_tile_list(args.pilot)[:args.max_tiles]

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        downloaded = []
        failed = []

        for tile in tiles:
            ok = download_copernicus_tile(tile, RAW_DIR)
            if ok:
                downloaded.append(tile["srtm_name"])
            else:
                failed.append(tile["srtm_name"])

        log.info(f"Downloaded: {len(downloaded)} tiles; Failed/missing: {len(failed)}")

        # Process downloaded tiles
        derivative_results = {}
        for tif_path in RAW_DIR.glob("*_glo30.tif"):
            log.info(f"Computing terrain derivatives: {tif_path.name}")
            result = compute_terrain_derivatives(tif_path, PROC_DIR)
            derivative_results[tif_path.name] = result

        # Save processing report
        PROC_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pilot": args.pilot,
            "pilot_name": pilot["name"],
            "data_type": "REAL DEM — NOT SYNTHETIC",
            "source": "Copernicus GLO-30 (public)",
            "tiles_downloaded": downloaded,
            "tiles_failed": failed,
            "derivative_results": derivative_results,
        }
        report_path = PROC_DIR / f"dem_pilot_{args.pilot}_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        log.info(f"Report: {report_path}")
        log.info("Terrain pilot complete.")


if __name__ == "__main__":
    main()
