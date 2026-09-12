from pathlib import Path
import urllib.parse
import urllib.request

import rasterio


OUT_DIR = Path("data/gis/geology_soil")
OUT_DIR.mkdir(parents=True, exist_ok=True)

WEST = 76.85
EAST = 77.15
SOUTH = 31.60
NORTH = 31.80

properties = ["clay", "sand", "silt"]

for soil_property in properties:
    output = OUT_DIR / f"soilgrids_{soil_property}_0_5cm_mean.tif"

    params = [
        ("map", f"/map/{soil_property}.map"),
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", f"{soil_property}_0-5cm_mean"),
        ("FORMAT", "image/tiff"),
        ("SUBSET", f"long({WEST},{EAST})"),
        ("SUBSET", f"lat({SOUTH},{NORTH})"),
        (
            "SUBSETTINGCRS",
            "http://www.opengis.net/def/crs/EPSG/0/4326",
        ),
        (
            "OUTPUTCRS",
            "http://www.opengis.net/def/crs/EPSG/0/4326",
        ),
    ]

    url = (
        "https://maps.isric.org/mapserv?"
        + urllib.parse.urlencode(params)
    )

    print(f"Downloading {soil_property}...")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ResQShield-SIH/0.1"},
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        content = response.read()

    output.write_bytes(content)

    try:
        with rasterio.open(output) as src:
            print(
                soil_property,
                "OK",
                "CRS:", src.crs,
                "Size:", f"{src.width}x{src.height}",
                "Bounds:", src.bounds,
            )
    except Exception:
        print(f"ERROR: {output} is not a valid raster")
        print(content[:500])
        raise

print("SoilGrids download complete")
