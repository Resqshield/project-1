# -*- coding: utf-8 -*-
"""
backend/demo_state.py
======================
Single shared in-memory demo/simulation state for the four-map ResQ Shield
demo (Technical/Admin, Authority, Citizen, Field Worker).

Everything here is SIMULATION / DEMO OPERATIONAL STATE, never an observed
hazard. Nothing in this module ever touches the genuine GloFAS layer, OSM
facility data, or OSRM routing — those stay real and untouched; this module
only tracks the demo village risk labels, field assignments and reported
road blocks that the four views read/write.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import BaseModel

# ── Baseline village state ──────────────────────────────────────────────────
# Kataula / Kamand coordinates: OpenStreetMap-backed public map reference.
# Arnehar coordinate: SIMULATION_LOCATION_ONLY — see frontend/src/realmap/demoVillages.js
# for full provenance (no verified LGD/OSM village node found; nearest OSM
# reference "Salgi-Arnehar Road" used as a demo-only visualization point).

def _baseline_villages() -> Dict[str, dict]:
    return {
        "Kataula": {"name": "Kataula", "risk_level": "RED", "status": "EVACUATE", "priority": 1},
        "Kamand": {"name": "Kamand", "risk_level": "ORANGE", "status": "PREPARE", "priority": 2},
        "Arnehar": {"name": "Arnehar", "risk_level": "GREEN", "status": "NORMAL", "priority": 3},
    }

# Simulated sensor feed — DEMO only. Never presented as LIVE/OBSERVED/SENSOR
# VERIFIED. See spec section 3 (Technical/Admin map).
def _baseline_sensors() -> Dict[str, dict]:
    return {
        "Kataula": {"rainfall_channel": "EXTREME", "water_level_trend": "RAPID_RISE", "demo_node_health": "HEALTHY"},
        "Kamand": {"rainfall_channel": "ELEVATED", "water_level_trend": "WATCH", "demo_node_health": "HEALTHY"},
        "Arnehar": {"rainfall_channel": "NORMAL", "water_level_trend": "STABLE", "demo_node_health": "HEALTHY"},
    }

villages: Dict[str, dict] = _baseline_villages()
sensors: Dict[str, dict] = _baseline_sensors()
evacuations: Dict[str, dict] = {}
field_assignments: Dict[str, dict] = {}
road_blocks: Dict[str, dict] = {}
_road_block_seq = 0
updated_at: str = datetime.now(timezone.utc).isoformat()


def _touch():
    global updated_at
    updated_at = datetime.now(timezone.utc).isoformat()


def snapshot() -> dict:
    """Full shared-state envelope returned by GET /api/demo/state."""
    return {
        "simulation": True,
        "observed_hazard": False,
        "villages": villages,
        "sensors": sensors,
        "evacuations": evacuations,
        "field_assignments": field_assignments,
        "road_blocks": road_blocks,
        "updated_at": updated_at,
    }


def reset():
    """Reset all DEMO operational state to baseline. Never touches GloFAS,
    OSM data, or OSRM — those are real, external, and untouched by design."""
    global villages, sensors, evacuations, field_assignments, road_blocks, _road_block_seq
    villages = _baseline_villages()
    sensors = _baseline_sensors()
    evacuations = {}
    field_assignments = {}
    road_blocks = {}
    _road_block_seq = 0
    _touch()
    return snapshot()


def set_village_risk(name: str, risk_level: str, status: str) -> Optional[dict]:
    if name not in villages:
        return None
    villages[name]["risk_level"] = risk_level
    villages[name]["status"] = status
    _touch()
    return villages[name]


def record_evacuation(name: str, meta: Optional[dict] = None) -> Optional[dict]:
    """Mark a village as ordered to evacuate and record when/why for provenance.
    Does not resolve a facility/route itself — that stays real OSM/OSRM,
    resolved client-side (or by the caller) using the existing evacuation
    endpoints, exactly as today."""
    updated = set_village_risk(name, "RED", "EVACUATE")
    if updated is None:
        return None
    evacuations[name] = {
        "village": name,
        "ordered_at": datetime.now(timezone.utc).isoformat(),
        **(meta or {}),
    }
    _touch()
    return updated


def assign_field_team(team: str, village: str) -> Optional[dict]:
    if village not in villages:
        return None
    field_assignments[team] = {
        "team": team,
        "village": village,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
    }
    _touch()
    return field_assignments[team]


def report_road_block(lat: float, lon: float, label: Optional[str], reported_by: Optional[str]) -> dict:
    global _road_block_seq
    _road_block_seq += 1
    block_id = f"block-{_road_block_seq}"
    road_blocks[block_id] = {
        "id": block_id,
        "lat": lat,
        "lon": lon,
        "label": label or "Reported road block",
        "reported_by": reported_by or "Unknown",
        "status": "BLOCKED",
        "reason": "ROAD_BLOCKED",
        "simulation": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _touch()
    return road_blocks[block_id]


def clear_road_block(block_id: str) -> bool:
    if block_id in road_blocks:
        del road_blocks[block_id]
        _touch()
        return True
    return False


def clear_all_road_blocks():
    global road_blocks
    road_blocks = {}
    _touch()


# ── Pydantic request models (used by backend/routes/demo_operations.py) ────

class VillageRiskUpdate(BaseModel):
    risk_level: str
    status: str


class FieldAssignRequest(BaseModel):
    team: str
    village: str


class RoadBlockReport(BaseModel):
    lat: float
    lon: float
    label: Optional[str] = None
    reported_by: Optional[str] = None
