from pathlib import Path

from backend.app.gis.static_layers import (
    REQUIRED_LAYER_IDS,
    load_manifest,
    pending_layers,
    validate_manifest_contract,
)


MANIFEST = "data/gis/manifest.json"


def get_layer(manifest, layer_id):
    return next(
        layer for layer in manifest.layers
        if layer.layer_id == layer_id
    )


def test_manifest_uses_frozen_pilot():
    manifest = load_manifest(MANIFEST)
    assert manifest.pilot_id == "HP_MANDI_PANDOH_CORRIDOR"


def test_manifest_uses_shared_crs():
    manifest = load_manifest(MANIFEST)
    assert manifest.crs == "EPSG:4326"


def test_manifest_contains_all_required_layers():
    manifest = load_manifest(MANIFEST)
    assert {
        layer.layer_id for layer in manifest.layers
    } == REQUIRED_LAYER_IDS
    validate_manifest_contract(manifest)


def test_dem_is_ready():
    manifest = load_manifest(MANIFEST)
    layer = get_layer(manifest, "dem")
    assert layer.status == "READY"
    assert layer.file_path == "data/gis/dem/srtm_gl1_mandi_pandoh_30m.tif"
    assert Path(layer.file_path).is_file()


def test_slope_is_ready():
    manifest = load_manifest(MANIFEST)
    layer = get_layer(manifest, "slope")
    assert layer.status == "READY"
    assert layer.file_path == "data/gis/slope/slope_mandi_pandoh_deg.tif"
    assert Path(layer.file_path).is_file()


def test_drainage_is_ready():
    manifest = load_manifest(MANIFEST)
    layer = get_layer(manifest, "drainage")
    assert layer.status == "READY"
    assert layer.file_path == (
        "data/gis/drainage/osm_waterways_mandi_pandoh.geojson"
    )
    assert Path(layer.file_path).is_file()


def test_geology_soil_is_ready():
    manifest = load_manifest(MANIFEST)
    layer = get_layer(manifest, "geology_soil")
    assert layer.status == "READY"
    assert layer.file_path == (
        "data/gis/geology_soil/soil_texture_mandi_pandoh_0_5cm.tif"
    )
    assert Path(layer.file_path).is_file()


def test_lulc_is_ready():
    manifest = load_manifest(MANIFEST)
    layer = get_layer(manifest, "lulc")
    assert layer.status == "READY"
    assert layer.file_path == (
        "data/gis/lulc/esa_worldcover_2021_mandi_pandoh_10m.tif"
    )
    assert Path(layer.file_path).is_file()


def test_roads_are_ready():
    manifest = load_manifest(MANIFEST)
    layer = get_layer(manifest, "roads")
    assert layer.status == "READY"
    assert layer.file_path == (
        "data/gis/roads/osm_roads_mandi_pandoh.geojson"
    )
    assert Path(layer.file_path).is_file()


def test_villages_are_ready():
    manifest = load_manifest(MANIFEST)
    layer = get_layer(manifest, "villages")

    assert layer.status == "READY"
    assert layer.file_path == (
        "data/gis/villages/osm_settlements_mandi_pandoh.geojson"
    )
    assert Path(layer.file_path).is_file()


def test_hazard_history_is_ready():
    manifest = load_manifest(MANIFEST)
    layer = get_layer(manifest, "hazard_history")

    assert layer.status == "READY"
    assert layer.file_path == (
        "data/gis/hazard_history/"
        "verified_hazard_history_mandi_pandoh_2023.geojson"
    )
    assert Path(layer.file_path).is_file()


def test_no_layers_are_pending():
    manifest = load_manifest(MANIFEST)

    assert set(pending_layers(manifest)) == set()
