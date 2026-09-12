from pathlib import Path

import numpy as np
import rasterio


BASE = Path("data/gis/geology_soil")

inputs = {
    "clay": BASE / "soilgrids_clay_0_5cm_mean.tif",
    "sand": BASE / "soilgrids_sand_0_5cm_mean.tif",
    "silt": BASE / "soilgrids_silt_0_5cm_mean.tif",
}

OUTPUT = BASE / "soil_texture_mandi_pandoh_0_5cm.tif"

arrays = {}
reference = None
profile = None

for name, path in inputs.items():
    with rasterio.open(path) as src:
        if reference is None:
            reference = {
                "crs": src.crs,
                "transform": src.transform,
                "width": src.width,
                "height": src.height,
                "bounds": src.bounds,
            }
            profile = src.profile.copy()
        else:
            assert src.crs == reference["crs"]
            assert src.transform == reference["transform"]
            assert src.width == reference["width"]
            assert src.height == reference["height"]
            assert src.bounds == reference["bounds"]

        arrays[name] = src.read(1, masked=True)

nodata = profile.get("nodata")
if nodata is None:
    nodata = -32768

profile.update(
    count=3,
    nodata=nodata,
    compress="deflate",
)

with rasterio.open(OUTPUT, "w", **profile) as dst:
    for band, name in enumerate(("clay", "sand", "silt"), start=1):
        data = arrays[name].filled(nodata)
        dst.write(data.astype(profile["dtype"]), band)
        dst.set_band_description(band, name)

    dst.update_tags(
        source="ISRIC SoilGrids",
        depth="0-5cm",
        statistic="mean",
        pilot_id="HP_MANDI_PANDOH_CORRIDOR",
    )

print("Created:", OUTPUT)

with rasterio.open(OUTPUT) as src:
    print("CRS:", src.crs)
    print("Size:", src.width, "x", src.height)
    print("Bands:", src.count)
    print("Descriptions:", src.descriptions)
    print("Bounds:", src.bounds)

    for band in range(1, 4):
        values = src.read(band, masked=True)
        print(
            src.descriptions[band - 1],
            "min:", float(values.min()),
            "max:", float(values.max()),
        )
