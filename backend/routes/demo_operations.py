# -*- coding: utf-8 -*-
"""
backend/routes/demo_operations.py
===================================
Endpoints for the shared four-map demo state (backend/demo_state.py).
Prefix: /api/demo

Everything served here is SIMULATION / DEMO OPERATIONAL STATE — never an
observed hazard. See backend/demo_state.py docstring.
"""

from fastapi import APIRouter, HTTPException

from backend import demo_state as ds

router = APIRouter(prefix="/api/demo", tags=["Demo"])


@router.get("/state")
async def get_state():
    return ds.snapshot()


@router.post("/reset")
async def reset_demo():
    return ds.reset()


@router.post("/villages/{village}/risk")
async def set_village_risk(village: str, update: ds.VillageRiskUpdate):
    result = ds.set_village_risk(village, update.risk_level, update.status)
    if result is None:
        raise HTTPException(status_code=404, detail="Village not found in demo state")
    return result


@router.post("/villages/{village}/evacuate")
async def evacuate_village(village: str):
    result = ds.record_evacuation(village)
    if result is None:
        raise HTTPException(status_code=404, detail="Village not found in demo state")
    return result


@router.post("/field/assign")
async def assign_field_team(req: ds.FieldAssignRequest):
    result = ds.assign_field_team(req.team, req.village)
    if result is None:
        raise HTTPException(status_code=404, detail="Village not found in demo state")
    return result


@router.get("/road-block")
async def get_road_blocks():
    return ds.road_blocks


@router.post("/road-block")
async def post_road_block(report: ds.RoadBlockReport):
    return ds.report_road_block(report.lat, report.lon, report.label, report.reported_by)


@router.post("/road-block/reset")
async def reset_road_blocks():
    ds.clear_all_road_blocks()
    return {"road_blocks": ds.road_blocks}


@router.post("/road-clear/{block_id}")
async def clear_road_block(block_id: str):
    ok = ds.clear_road_block(block_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Road block not found")
    return {"road_blocks": ds.road_blocks}
