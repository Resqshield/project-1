"""Validation contract for the T03 static GIS package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


REQUIRED_LAYER_IDS = {
    "dem",
    "slope",
    "drainage",
    "geology_soil",
    "lulc",
    "roads",
    "villages",
    "hazard_history",
}


class GISLayerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    description: str
    status: Literal["PENDING", "READY"]
    file_path: Optional[str] = None

    @field_validator("layer_id", "description")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class StaticGISManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_id: str
    crs: str
    layers: list[GISLayerSpec]

    @field_validator("pilot_id", "crs")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


def load_manifest(path: str | Path) -> StaticGISManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return StaticGISManifest.model_validate(data)


def validate_manifest_contract(manifest: StaticGISManifest) -> None:
    if manifest.pilot_id != "HP_MANDI_PANDOH_CORRIDOR":
        raise ValueError("GIS package does not use the frozen T01 pilot")

    if manifest.crs != "EPSG:4326":
        raise ValueError("T03 shared exchange CRS must be EPSG:4326")

    ids = [layer.layer_id for layer in manifest.layers]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate GIS layer IDs are not allowed")

    missing = REQUIRED_LAYER_IDS - set(ids)
    if missing:
        raise ValueError(f"Missing required GIS layers: {sorted(missing)}")


def pending_layers(manifest: StaticGISManifest) -> list[str]:
    return [
        layer.layer_id
        for layer in manifest.layers
        if layer.status != "READY" or not layer.file_path
    ]
