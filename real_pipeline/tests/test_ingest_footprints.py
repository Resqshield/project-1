import pytest
import geopandas as gpd
from shapely.geometry import Polygon
import rasterio
import numpy as np
from pathlib import Path
from real_pipeline.labels.ingest_footprints import is_forbidden_filename, validate_vector, validate_raster, INVALID_KEYWORDS

def test_forbidden_filename():
    assert is_forbidden_filename("event_reference_map.shp")[0] is True
    assert is_forbidden_filename("EMSR049_boundary_data.geojson")[0] is True
    assert is_forbidden_filename("IND_FLOOD_2013_UK_001_flood_extent.shp")[0] is False
    assert is_forbidden_filename("UNOSAT_flood_polygons.gpkg")[0] is False

def test_validate_vector(tmp_path):
    # Create a valid shapefile
    p1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    gdf_valid = gpd.GeoDataFrame({'geometry': [p1]}, crs="EPSG:4326")
    valid_path = tmp_path / "valid.shp"
    gdf_valid.to_file(valid_path)
    
    is_valid, msg = validate_vector(valid_path)
    assert is_valid is True
    assert "Valid" in msg

    # Create an empty shapefile
    gdf_empty = gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")
    empty_path = tmp_path / "empty.shp"
    gdf_empty.to_file(empty_path)
    
    is_valid, msg = validate_vector(empty_path)
    assert is_valid is False
    assert "zero features" in msg

    # Create a shapefile missing CRS
    gdf_nocrs = gpd.GeoDataFrame({'geometry': [p1]})
    nocrs_path = tmp_path / "nocrs.shp"
    # Suppress warning for writing no CRS
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gdf_nocrs.to_file(nocrs_path)
        
    is_valid, msg = validate_vector(nocrs_path)
    assert is_valid is False
    assert "missing a CRS" in msg

    # Create a shapefile with forbidden keywords in attributes
    gdf_bad_attr = gpd.GeoDataFrame({'class': ['reference zone'], 'geometry': [p1]}, crs="EPSG:4326")
    bad_attr_path = tmp_path / "bad_attr.shp"
    gdf_bad_attr.to_file(bad_attr_path)
    
    is_valid, msg = validate_vector(bad_attr_path)
    assert is_valid is False
    assert "reference" in msg.lower()

def test_validate_raster(tmp_path):
    import rasterio.transform
    # Create valid raster
    valid_path = tmp_path / "valid.tif"
    arr = np.ones((10, 10), dtype=rasterio.uint8)
    transform = rasterio.transform.from_origin(0, 0, 1, 1)
    
    with rasterio.open(
        valid_path, 'w', driver='GTiff', 
        height=arr.shape[0], width=arr.shape[1], 
        count=1, dtype=arr.dtype, 
        crs='+proj=latlong', transform=transform
    ) as dst:
        dst.write(arr, 1)
        
    is_valid, msg = validate_raster(valid_path)
    assert is_valid is True
    assert "Valid" in msg

    # Create raster missing CRS
    nocrs_path = tmp_path / "nocrs.tif"
    with rasterio.open(
        nocrs_path, 'w', driver='GTiff', 
        height=arr.shape[0], width=arr.shape[1], 
        count=1, dtype=arr.dtype, 
        transform=transform
    ) as dst:
        dst.write(arr, 1)
        
    is_valid, msg = validate_raster(nocrs_path)
    assert is_valid is False
    assert "missing a CRS" in msg
