"""Shared response schemas for the B06 API contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class APITransports(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rest_base_path: str
    websocket_path: str


class APIContractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"]
    api_version: Literal["v1"]
    transports: APITransports
    implemented_rest_paths: list[str]
    supported_client_messages: list[str]
    extension_points: list[str]


class LiveStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["websocket"]
    transport_status: Literal["ready"]
    data_mode: Literal["contract_only"]
    endpoint: str
    protocol_version: Literal["1"]
    supported_client_messages: list[str]
