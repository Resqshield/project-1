# ResQShield — Backend

> **Milestone M4 · B01** — Repo foundation, shared configuration, and health endpoint.

## Project Structure

```
project-1/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI application factory
│   │   ├── config.py        # Pydantic Settings (env-driven)
│   │   └── api/
│   │       ├── __init__.py
│   │       └── health.py    # GET /api/v1/health
│   └── tests/
│       ├── __init__.py
│       ├── test_config.py
│       └── test_health.py
├── .env.example              # Template — copy to .env
├── .gitignore
├── pyproject.toml            # Python project & dependency config
└── README.md                 # ← you are here
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

### 4. Run the development server

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

The health endpoint will be available at:

```
http://127.0.0.1:8000/api/v1/health
```

Interactive API docs (Swagger UI):

```
http://127.0.0.1:8000/api/v1/docs
```

### 5. Run tests

```powershell
pytest -v
```

## Configuration

All settings are driven by environment variables with the `RESQ_` prefix.
See [`.env.example`](.env.example) for the full list with descriptions.

| Variable | Default | Purpose |
|---|---|---|
| `RESQ_ENV` | `development` | Environment name |
| `RESQ_APP_NAME` | `ResQShield` | Application display name |
| `RESQ_API_HOST` | `127.0.0.1` | Uvicorn bind address |
| `RESQ_API_PORT` | `8000` | Uvicorn bind port |
| `RESQ_API_PREFIX` | `/api/v1` | API route prefix |
| `RESQ_DATABASE_URL` | *(localhost placeholder)* | PostGIS / TimescaleDB URL |
| `RESQ_MQTT_BROKER_HOST` | `localhost` | MQTT broker hostname |
| `RESQ_MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `RESQ_MQTT_BASE_TOPIC` | `resqshield/` | MQTT topic prefix |
| `RESQ_STORAGE_ENDPOINT` | `http://localhost:9000` | S3-compatible endpoint |
| `RESQ_STORAGE_BUCKET` | `resqshield-data` | Object storage bucket |
| `RESQ_MODEL_ARTIFACT_DIR` | `./artifacts` | ML model/artifact directory |
| `RESQ_PILOT_ID` | `PILOT_PLACEHOLDER` | Pilot region identifier |
| `RESQ_HOLDOUT_ID` | `HOLDOUT_PLACEHOLDER` | Holdout region identifier |

> **Note:** `RESQ_PILOT_ID` and `RESQ_HOLDOUT_ID` are external dependencies.
> They remain configurable placeholders until the team freezes the final pilot geography.

## License

Internal — SIH 2024 project.
