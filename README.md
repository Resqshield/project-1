# ResQShield — Backend

> **Milestone M4 · B01 & B02** — Repository foundation, shared configuration, PostgreSQL/PostGIS/TimescaleDB models, Alembic migrations, dev fixtures, and object storage conventions.

## Project Structure

```
project-1/
├── alembic/
│   ├── versions/
│   │   └── 0001_initial_schema.py   # PostGIS, Timescale hypertable & core entities
│   ├── env.py                       # Alembic environment with PostGIS/Timescale exclusion
│   └── script.py.mako
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI application factory
│   │   ├── config.py                # Pydantic Settings (RESQ_ prefix)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── health.py            # GET /api/v1/health
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # SQLAlchemy DeclarativeBase
│   │   │   └── session.py           # Async session & sync engine management
│   │   ├── models/
│   │   │   ├── __init__.py          # Export all 14 ORM models
│   │   │   ├── geography.py         # Region, Catchment, Village (PostGIS)
│   │   │   ├── users.py             # User persistence
│   │   │   ├── sensing.py           # Sensor, Observation (Timescale hypertable)
│   │   │   ├── operations.py        # Road, Shelter (PostGIS)
│   │   │   ├── events.py            # Prediction, Warning, Incident, FieldReport
│   │   │   └── governance.py        # AuditLog, ModelRegistry
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   └── convention.py        # Deterministic object-storage key builder
│   │   └── seed/
│   │       ├── __init__.py
│   │       └── seed_dev_data.py     # Idempotent DEV_* synthetic fixtures
│   └── tests/
│       ├── __init__.py
│       ├── test_config.py           # Configuration & override tests
│       ├── test_health.py           # Health endpoint tests
│       ├── test_models_schema.py    # ORM metadata, constraints & disaster rules
│       ├── test_storage.py          # Storage convention & key determinism
│       └── test_b02_live_acceptance.py # 12 acceptance criteria against live DB
├── .env.example                     # Environment template
├── .gitignore
├── alembic.ini                      # Alembic CLI configuration
├── docker-compose.yml               # Pinned PostgreSQL 16 + PostGIS + TimescaleDB
├── pyproject.toml                   # Project dependencies & build config
└── README.md                        # Documentation
```

## Quick Start (Windows PowerShell)

### 1. Create and activate a virtual environment

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -e ".[dev]"
```

### 3. Create your local `.env`

```powershell
Copy-Item .env.example .env
```

Edit `.env` as needed. **Do not commit `.env`** — it is git-ignored.

### 4. Database Development Prerequisites

A local container service providing PostgreSQL 16 + PostGIS 3.4 + TimescaleDB 2.15 is specified in `docker-compose.yml`.

#### Start the database container:

```powershell
docker compose up -d
```

#### Run database migrations:

```powershell
alembic upgrade head
```

#### Seed development fixtures (DEV_*):

```powershell
python -m backend.app.seed.seed_dev_data
```

> [!NOTE]
> All seeded fixtures use synthetic identifiers (`DEV_REGION_001`, `DEV_CATCHMENT_001`, `DEV_VILLAGE_001`, etc.).
> Real pilot seed data replacement remains **blocked by T01** until the geography is frozen.

#### Stop or reset the development database safely:

```powershell
# Stop container:
docker compose down

# Full reset (erases database volume):
docker compose down -v
```

### 5. Run the development server

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

- Health endpoint: `http://127.0.0.1:8000/api/v1/health`
- OpenAPI Swagger docs: `http://127.0.0.1:8000/api/v1/docs`

### 6. Run tests

```powershell
pytest -v
```

> [!TIP]
> When Docker / live database is not running, live database acceptance tests automatically report `SKIPPED (BLOCKED: Live PostgreSQL/PostGIS/TimescaleDB database is not reachable)` while all schema, model, storage, config, and health tests pass (57 tests).

## Configuration Reference

All settings are environment-driven with the `RESQ_` prefix. See [`.env.example`](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `RESQ_ENV` | `development` | Environment name |
| `RESQ_APP_NAME` | `ResQShield` | Application display name |
| `RESQ_API_HOST` | `127.0.0.1` | Uvicorn bind address |
| `RESQ_API_PORT` | `8000` | Uvicorn bind port |
| `RESQ_API_PREFIX` | `/api/v1` | API route prefix |
| `RESQ_DATABASE_URL` | `postgresql+asyncpg://...` | Async database URL (FastAPI) |
| `RESQ_DATABASE_URL_SYNC` | `postgresql+psycopg2://...` | Sync database URL (Alembic / scripts) |
| `RESQ_MQTT_BROKER_HOST` | `localhost` | MQTT broker hostname (B04) |
| `RESQ_MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `RESQ_MQTT_BASE_TOPIC` | `resqshield/` | MQTT topic prefix |
| `RESQ_STORAGE_ENDPOINT` | `http://localhost:9000` | S3/MinIO endpoint |
| `RESQ_STORAGE_BUCKET` | `resqshield-data` | Object storage bucket |
| `RESQ_STORAGE_BASE_PREFIX` | `""` | Optional base key prefix |
| `RESQ_MODEL_ARTIFACT_DIR` | `./artifacts` | ML model artifact directory |
| `RESQ_PILOT_ID` | `PILOT_PLACEHOLDER` | Configurable pilot identifier |
| `RESQ_HOLDOUT_ID` | `HOLDOUT_PLACEHOLDER` | Configurable holdout identifier |

## Object Storage Convention

The storage convention (`backend/app/storage/convention.py`) generates deterministic object keys:

- **Raw Ingest:** `[prefix/]raw/<source>/<YYYY>/<MM>/<DD>/<filename>`
- **Derived Datasets:** `[prefix/]derived/<dataset>/<version>/<filename>`
- **Model Registry:** `[prefix/]models/<model>/<version>/<filename>`
- **Operational Attachments:** `[prefix/]attachments/<entity_type>/<entity_code>/<YYYY>/<MM>/<filename>`

## Rainfall Feature Foundation (T04)

The rainfall history feature layer (`backend/app/features/rainfall.py`) converts timestamped environmental observations into historical accumulation features for downstream hazard models:

- **Observation Semantics:** Incremental precipitation (in mm) measured during the sampling interval ending at `observed_at`.
- **Supported Windows:** `rain_30m` (30m), `rain_1h` (1h), `rain_3h` (3h), `rain_6h` (6h), `rain_24h` (24h), `rain_3d` (3d), `rain_7d` (7d).
- **Boundary Rule:** Half-open interval `(evaluation_time - window_duration, evaluation_time]`.
- **Missing Data Safety (Missing != Zero):**
  - Empty window (no readings) results in `value = None` and `quality_status = "EMPTY"`.
  - Missing/failed readings result in `value = None` and `quality_status = "MISSING"`.
  - Incomplete windows result in `quality_status = "PARTIAL"` with explicit `coverage_ratio < 1.0` (never coerced to 0.0 mm).
  - Genuine zero rainfall reports `value = 0.0` with `quality_status = "COMPLETE"`.
- **Staleness Tracking:** Freshness is calculated dynamically from `evaluation_time - latest_observation_timestamp`. Readings exceeding `stale_threshold_seconds` are flagged as `is_stale = True`.

### Run T04 Tests

```powershell
pytest backend/tests/test_rainfall_features.py -v
```

## License

Internal — SIH 2024 project.
