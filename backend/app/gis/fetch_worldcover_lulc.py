from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds


URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
    "v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_N30E075_Map.tif"
)

OUTPUT = Path(
    "data/gis/lulc/"
    "esa_worldcover_2021_mandi_pandoh_10m.tif"
)

WEST = 76.85
SOUTH = 31.60
EAST = 77.15
NORTH = 31.80


print("Reading ESA WorldCover 2021...")

with rasterio.Env(
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"
):
    with rasterio.open(URL) as src:
        print("Source CRS:", src.crs)

        window = from_bounds(
            WEST,
            SOUTH,
            EAST,
            NORTH,
            transform=src.transform,
        )

        window = window.round_offsets().round_lengths()

        data = src.read(1, window=window)

        transform = src.window_transform(window)

        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            transform=transform,
            count=1,
            compress="deflate",
        )

        with rasterio.open(OUTPUT, "w", **profile) as dst:
            dst.write(data, 1)

            dst.update_tags(
                source="ESA WorldCover",
                product="WorldCover 2021 v200",
                resolution="10m",
                pilot_id="HP_MANDI_PANDOH_CORRIDOR",
            )

print("Created:", OUTPUT)

with rasterio.open(OUTPUT) as src:
    values = src.read(1)

    unique, counts = np.unique(values, return_counts=True)

    print("CRS:", src.crs)
    print("Size:", src.width, "x", src.height)
    print("Bounds:", src.bounds)
    print("Classes:")

    for value, count in zip(unique, counts):
        print(" ", int(value), ":", int(count), "pixels")
