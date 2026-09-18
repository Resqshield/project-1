import pytest
import os
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_evacuation_routing_valid():
    """Test valid OSRM routing."""
    # Mandi to nearby point
    resp = client.get("/api/real/evacuation/route?start_lat=31.5991&start_lon=76.9685&dest_lat=31.60&dest_lon=77.00")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" not in data, f"Unexpected error: {data.get('error')}"
    assert data["type"] == "Feature"
    assert "geometry" in data
    assert data["geometry"]["type"] == "LineString"
    assert "properties" in data
    assert "distance_m" in data["properties"]
    assert "duration_s" in data["properties"]
    assert "provider" in data["properties"]
    assert data["properties"]["provider"] == "OSRM"

def test_evacuation_routing_invalid_coords():
    """Test routing with unreachable coordinates (e.g., middle of the ocean)."""
    resp = client.get("/api/real/evacuation/route?start_lat=0&start_lon=0&dest_lat=1&dest_lon=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert data["error"] == "NoRoute" or "OSRM API error: 400" in data["error"]
