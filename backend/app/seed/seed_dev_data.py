"""Development seed data fixtures for B02 testing and verification.

WARNING:
These are synthetic DEVELOPMENT fixtures (DEV_*).
Do NOT treat these as real geographic boundaries, sensor feeds, or disaster ground truth.
Real pilot geography is blocked pending T01 freeze.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_sync_engine
from backend.app.models.events import Incident, Prediction, Warning
from backend.app.models.geography import Catchment, Region, Village
from backend.app.models.governance import AuditLog, ModelRegistry
from backend.app.models.operations import Road, Shelter
from backend.app.models.sensing import Observation, Sensor
from backend.app.models.users import User

# Development synthetic coordinates (generic Himalayan valley simulation)
# Centered around arbitrary synthetic point 30.50 N, 79.25 E
DEV_REGION_CODE = "DEV_REGION_001"
DEV_CATCHMENT_CODE = "DEV_CATCHMENT_001"
DEV_VILLAGE_CODE = "DEV_VILLAGE_001"
DEV_SENSOR_RAIN_CODE = "DEV_SENSOR_RAIN_001"
DEV_SENSOR_SOIL_CODE = "DEV_SENSOR_SOIL_001"
DEV_SENSOR_WATER_CODE = "DEV_SENSOR_WATER_001"
DEV_ROAD_CODE = "DEV_ROAD_001"
DEV_SHELTER_CODE = "DEV_SHELTER_001"
DEV_PRED_CODE = "DEV_PRED_001"
DEV_WARN_CODE = "DEV_WARN_001"
DEV_INCIDENT_CODE = "DEV_INCIDENT_001"
DEV_USER_EMAIL = "dev.operator@resqshield.local"
DEV_MODEL_NAME = "DEV_LANDSLIDE_PROBABILITY_MODEL"


def seed_dev_data(session: Session) -> dict[str, int]:
    """Insert or update development fixtures in an idempotent manner.

    Returns a summary dictionary of seeded entities.
    """
    counts: dict[str, int] = {}
    now = datetime.now(timezone.utc)

    # 1. Dev User
    user = session.scalars(select(User).where(User.email == DEV_USER_EMAIL)).first()
    if not user:
        user = User(
            email=DEV_USER_EMAIL,
            full_name="Development Test Operator",
            role_name="field_responder",
            is_active=True,
            created_at=now,
        )
        session.add(user)
        session.flush()
    counts["users"] = 1

    # 2. Dev Region
    region = session.scalars(select(Region).where(Region.code == DEV_REGION_CODE)).first()
    if not region:
        region = Region(
            code=DEV_REGION_CODE,
            name="Development Synthetic Valley Region",
            description="Synthetic placeholder region for M4 Day 1 B02 tests. Blocked by T01.",
            is_active=True,
            metadata_json={"env": "development", "is_fixture": True},
            created_at=now,
        )
        session.add(region)
        session.flush()
    counts["regions"] = 1

    # 3. Dev Catchment (Synthetic polygon around 30.45..30.55 N, 79.20..79.30 E)
    catchment = session.scalars(select(Catchment).where(Catchment.code == DEV_CATCHMENT_CODE)).first()
    if not catchment:
        catchment_wkt = (
            "POLYGON(("
            "79.20 30.45, "
            "79.30 30.45, "
            "79.30 30.55, "
            "79.20 30.55, "
            "79.20 30.45))"
        )
        catchment = Catchment(
            code=DEV_CATCHMENT_CODE,
            name="Development Synthetic Catchment A",
            region_id=region.id,
            geometry=WKTElement(catchment_wkt, srid=4326),
            metadata_json={"area_sqkm": 95.4, "is_fixture": True},
            created_at=now,
        )
        session.add(catchment)
        session.flush()
    counts["catchments"] = 1

    # 4. Dev Village (Synthetic point inside Catchment A: 30.50 N, 79.25 E)
    village = session.scalars(select(Village).where(Village.code == DEV_VILLAGE_CODE)).first()
    if not village:
        village_wkt = "POINT(79.25 30.50)"
        village = Village(
            code=DEV_VILLAGE_CODE,
            name="Development Synthetic Village 1",
            catchment_id=catchment.id,
            location=WKTElement(village_wkt, srid=4326),
            population=450,
            metadata_json={"elevation_m": 1620, "is_fixture": True},
            created_at=now,
        )
        session.add(village)
        session.flush()
    counts["villages"] = 1

    # 5. Dev Sensors
    # Sensor 1: Rain Gauge at village
    s_rain = session.scalars(select(Sensor).where(Sensor.sensor_code == DEV_SENSOR_RAIN_CODE)).first()
    if not s_rain:
        s_rain = Sensor(
            sensor_code=DEV_SENSOR_RAIN_CODE,
            sensor_type="rain_gauge",
            village_id=village.id,
            catchment_id=catchment.id,
            location=WKTElement("POINT(79.2505 30.5005)", srid=4326),
            status="ACTIVE",
            installation_date=now - timedelta(days=30),
            metadata_json={"hardware_rev": "v1.0-sim", "is_fixture": True},
            created_at=now,
        )
        session.add(s_rain)

    # Sensor 2: Soil Moisture
    s_soil = session.scalars(select(Sensor).where(Sensor.sensor_code == DEV_SENSOR_SOIL_CODE)).first()
    if not s_soil:
        s_soil = Sensor(
            sensor_code=DEV_SENSOR_SOIL_CODE,
            sensor_type="soil_moisture",
            village_id=village.id,
            catchment_id=catchment.id,
            location=WKTElement("POINT(79.2510 30.5010)", srid=4326),
            status="ACTIVE",
            installation_date=now - timedelta(days=30),
            metadata_json={"hardware_rev": "v1.0-sim", "is_fixture": True},
            created_at=now,
        )
        session.add(s_soil)

    # Sensor 3: Water Level (Stream)
    s_water = session.scalars(select(Sensor).where(Sensor.sensor_code == DEV_SENSOR_WATER_CODE)).first()
    if not s_water:
        s_water = Sensor(
            sensor_code=DEV_SENSOR_WATER_CODE,
            sensor_type="water_level",
            village_id=village.id,
            catchment_id=catchment.id,
            location=WKTElement("POINT(79.2520 30.4990)", srid=4326),
            status="ACTIVE",
            installation_date=now - timedelta(days=30),
            metadata_json={"hardware_rev": "v1.0-sim", "is_fixture": True},
            created_at=now,
        )
        session.add(s_water)
    session.flush()
    counts["sensors"] = 3

    # 6. Dev Observations
    # 6a. Valid rainfall observation
    t_obs_1 = now - timedelta(minutes=15)
    obs_1 = session.scalars(
        select(Observation).where(
            Observation.observed_at == t_obs_1,
            Observation.sensor_id == s_rain.id,
            Observation.metric_type == "rainfall_mm",
        )
    ).first()
    if not obs_1:
        obs_1 = Observation(
            observed_at=t_obs_1,
            sensor_id=s_rain.id,
            metric_type="rainfall_mm",
            numeric_value=12.5,
            unit="mm",
            quality_flag="VALID",
            source="sensor_telemetry",
            device_sequence=101,
            ingested_at=now - timedelta(minutes=14),
            provenance_metadata={"rssi": -78, "battery_v": 3.7},
        )
        session.add(obs_1)

    # 6b. MISSING observation (proves missing data != 0 principle)
    t_obs_2 = now - timedelta(minutes=10)
    obs_2 = session.scalars(
        select(Observation).where(
            Observation.observed_at == t_obs_2,
            Observation.sensor_id == s_soil.id,
            Observation.metric_type == "soil_moisture_pct",
        )
    ).first()
    if not obs_2:
        obs_2 = Observation(
            observed_at=t_obs_2,
            sensor_id=s_soil.id,
            metric_type="soil_moisture_pct",
            numeric_value=None,  # MISSING DATA IS EXPLICITLY NULL, NOT ZERO
            unit="%",
            quality_flag="MISSING",
            source="sensor_telemetry",
            device_sequence=102,
            ingested_at=now - timedelta(minutes=9),
            provenance_metadata={"reason": "sensor_timeout_probe_unresponsive"},
        )
        session.add(obs_2)

    # 6c. QoS-1 duplicate protection test observation
    t_obs_3 = now - timedelta(minutes=5)
    obs_3 = session.scalars(
        select(Observation).where(
            Observation.observed_at == t_obs_3,
            Observation.sensor_id == s_water.id,
            Observation.metric_type == "water_level_m",
        )
    ).first()
    if not obs_3:
        obs_3 = Observation(
            observed_at=t_obs_3,
            sensor_id=s_water.id,
            metric_type="water_level_m",
            numeric_value=1.85,
            unit="m",
            quality_flag="VALID",
            source="sensor_telemetry",
            device_sequence=103,
            ingested_at=now - timedelta(minutes=4),
            provenance_metadata={"rssi": -82},
        )
        session.add(obs_3)
    counts["observations"] = 3

    # 7. Dev Road (LineString from valley entry to village)
    road = session.scalars(select(Road).where(Road.road_code == DEV_ROAD_CODE)).first()
    if not road:
        road_wkt = "LINESTRING(79.22 30.46, 79.24 30.48, 79.25 30.50)"
        road = Road(
            road_code=DEV_ROAD_CODE,
            name="Development Valley Access Road",
            surface_type="single_lane_paved",
            status="OPEN",
            region_id=region.id,
            geometry=WKTElement(road_wkt, srid=4326),
            metadata_json={"length_km": 6.2, "is_fixture": True},
            created_at=now,
        )
        session.add(road)
    counts["roads"] = 1

    # 8. Dev Shelter (Point near village center)
    shelter = session.scalars(select(Shelter).where(Shelter.shelter_code == DEV_SHELTER_CODE)).first()
    if not shelter:
        shelter_wkt = "POINT(79.2515 30.5020)"
        shelter = Shelter(
            shelter_code=DEV_SHELTER_CODE,
            name="Development Village Community Hall Shelter",
            capacity=150,
            status="AVAILABLE",
            village_id=village.id,
            location=WKTElement(shelter_wkt, srid=4326),
            metadata_json={"supplies": "water, blankets", "is_fixture": True},
            created_at=now,
        )
        session.add(shelter)
    counts["shelters"] = 1

    # 9. Dev Prediction
    pred = session.scalars(select(Prediction).where(Prediction.prediction_code == DEV_PRED_CODE)).first()
    if not pred:
        pred = Prediction(
            prediction_code=DEV_PRED_CODE,
            model_name=DEV_MODEL_NAME,
            model_version="0.1.0-sim",
            catchment_id=catchment.id,
            village_id=village.id,
            target_metric="landslide_risk_score",
            predicted_value=0.78,
            risk_level="HIGH",
            confidence=0.85,
            valid_from=now,
            valid_to=now + timedelta(hours=6),
            metadata_json={"factors": ["heavy_rainfall", "steep_slope"], "is_fixture": True},
            created_at=now,
        )
        session.add(pred)
        session.flush()
    counts["predictions"] = 1

    # 10. Dev Warning
    warn = session.scalars(select(Warning).where(Warning.warning_code == DEV_WARN_CODE)).first()
    if not warn:
        warn = Warning(
            warning_code=DEV_WARN_CODE,
            severity="WARNING",
            status="ACTIVE",
            title="DEVELOPMENT TEST: High Landslide Warning",
            description="Synthetic warning for testing B02 decision records. Blocked by T01.",
            catchment_id=catchment.id,
            village_id=village.id,
            prediction_id=pred.id,
            issued_at=now,
            expires_at=now + timedelta(hours=6),
            metadata_json={"channel": "siren_and_sms", "is_fixture": True},
        )
        session.add(warn)
    counts["warnings"] = 1

    # 11. Dev Incident
    incident = session.scalars(select(Incident).where(Incident.incident_code == DEV_INCIDENT_CODE)).first()
    if not incident:
        incident = Incident(
            incident_code=DEV_INCIDENT_CODE,
            incident_type="LANDSLIDE",
            status="REPORTED",
            severity="HIGH",
            location=WKTElement("POINT(79.2450 30.4900)", srid=4326),
            village_id=village.id,
            road_id=road.id,
            reported_at=now - timedelta(hours=1),
            description="Development synthetic road debris blockage fixture. Blocked by T01.",
            metadata_json={"estimated_volume_m3": 120, "is_fixture": True},
        )
        session.add(incident)
    counts["incidents"] = 1

    # 12. Dev Audit Log
    audit = AuditLog(
        entity_type="SYSTEM",
        entity_id="SEED_FIXTURES",
        action="CREATE",
        performed_by_user_id=user.id,
        timestamp=now,
        changes_json={"seeded": counts, "is_fixture": True},
        ip_address="127.0.0.1",
    )
    session.add(audit)
    counts["audit_logs"] = 1

    # 13. Dev Model Registry
    model_reg = session.scalars(select(ModelRegistry).where(ModelRegistry.model_name == DEV_MODEL_NAME)).first()
    if not model_reg:
        model_reg = ModelRegistry(
            model_name=DEV_MODEL_NAME,
            version="0.1.0-sim",
            algorithm="GradientBoostingClassifier",
            artifact_uri="s3://resqshield-data/models/DEV_LANDSLIDE_PROBABILITY_MODEL/0.1.0-sim/model.joblib",
            input_schema_json={"features": ["rainfall_24h_mm", "slope_deg", "soil_moisture_pct"]},
            metrics_json={"f1": 0.88, "auc_roc": 0.92},
            status="EXPERIMENTAL",
            registered_at=now,
            description="Synthetic model registry entry for development testing.",
        )
        session.add(model_reg)
    counts["model_registry"] = 1

    session.commit()
    return counts


def main() -> None:
    """CLI entry point to run seed against database."""
    print("Connecting to database via sync engine...")
    engine = get_sync_engine()
    with Session(engine) as session:
        print("Seeding development fixtures (DEV_*)...")
        counts = seed_dev_data(session)
        print("Seed completed successfully:")
        for entity, count in counts.items():
            print(f"  - {entity}: {count}")


if __name__ == "__main__":
    main()
