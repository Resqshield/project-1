from pathlib import Path

import numpy as np
import rasterio


INPUT = Path("data/gis/dem/srtm_gl1_mandi_pandoh_30m.tif")
OUTPUT = Path("data/gis/slope/slope_mandi_pandoh_deg.tif")

if not INPUT.exists():
    raise FileNotFoundError(f"DEM not found: {INPUT}")

with rasterio.open(INPUT) as src:
    dem = src.read(1).astype("float64")
    profile = src.profile.copy()

    nodata = src.nodata

    if nodata is not None:
        invalid = dem == nodata
        dem[invalid] = np.nan
    else:
        invalid = np.isnan(dem)

    centre_latitude = (src.bounds.top + src.bounds.bottom) / 2.0

    metres_per_degree_lat = 111132.0
    metres_per_degree_lon = (
        111320.0 * np.cos(np.deg2rad(centre_latitude))
    )

    pixel_width_m = abs(src.transform.a) * metres_per_degree_lon
    pixel_height_m = abs(src.transform.e) * metres_per_degree_lat

    dz_dy, dz_dx = np.gradient(
        dem,
        pixel_height_m,
        pixel_width_m,
    )

    rise_run = np.sqrt(dz_dx ** 2 + dz_dy ** 2)
    slope = np.degrees(np.arctan(rise_run)).astype("float32")

    output_nodata = -9999.0
    slope[np.isnan(slope) | invalid] = output_nodata

    profile.update(
        dtype="float32",
        count=1,
        nodata=output_nodata,
        compress="deflate",
    )

    with rasterio.open(OUTPUT, "w", **profile) as dst:
        dst.write(slope, 1)

print(f"Created: {OUTPUT}")

with rasterio.open(OUTPUT) as src:
    values = src.read(1, masked=True)

    print("CRS:", src.crs)
    print("Size:", src.width, "x", src.height)
    print("Bounds:", src.bounds)
    print("Min slope:", float(values.min()))
    print("Max slope:", float(values.max()))
    print("Mean slope:", float(values.mean()))
