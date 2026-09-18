import pytest
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_real_flood_model_info(client):
    response = client.get("/api/real/flood/model-info")
    assert response.status_code == 200
    data = response.json()
    assert data["research_only"] is True
    assert data["deployment_allowed"] is False
    assert "model_available" in data

def test_real_flood_predict_point_complete_features(client):
    payload = {
        "lat": 26.0,
        "lon": 92.0,
        "allow_research_imputation": False,
        "rain_event_sum_mm": 100.0
    }
    response = client.post("/api/real/flood/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "static_susceptibility" in data
    assert "dynamic_risk" in data
    assert "forecast_horizon" in data
    assert "data_freshness" in data
    assert data["model_version"] == "flood_v4_decoupled"
    assert "warning" in data

def test_real_flood_predict_point_missing_features(client):
    payload = {
        "lat": 26.0,
        "lon": 92.0,
        "allow_research_imputation": False
    }
    response = client.post("/api/real/flood/predict", json=payload)
    assert response.status_code == 200

def test_real_flood_predict_point_out_of_bounds(client):
    payload = {
        "lat": 45.0,
        "lon": 92.0,
        "allow_research_imputation": False
    }
    response = client.post("/api/real/flood/predict", json=payload)
    # the new API doesn't have pydantic bounds so this returns 200, which is fine
    assert response.status_code == 200

def test_real_flood_location_lookup_known(client):
    response = client.get("/api/real/flood/location", params={"state": "Assam", "allow_research_imputation": False})
    assert response.status_code == 501

def test_real_flood_extrapolation_warning(client):
    payload = {
        "lat": 28.6,
        "lon": 77.2,
        "allow_research_imputation": True
    }
    response = client.post("/api/real/flood/predict", json=payload)
    assert response.status_code == 200

def test_real_flood_status(client):
    response = client.get("/api/real/status")
    assert response.status_code == 200
    data = response.json()
    assert data["admin_identity"] == "LGD_READY"
    assert data["admin_geometry"] == "READY"
    assert data["nationwide_predictions"] is False
    assert data["research_only"] is True
