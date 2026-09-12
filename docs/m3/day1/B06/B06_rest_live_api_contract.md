# B06 — REST + Live API Contract

## Scope

B06 establishes the versioned backend API transport foundation used by
later dashboards and backend workflows.

It does not implement hazard, routing, shelter, or alert business logic.
Those remain extension points for later tasks.

## REST Base

API prefix:

`/api/v1`

Implemented REST endpoints:

- `GET /api/v1/health`
- `GET /api/v1/contract`
- `GET /api/v1/live/status`

OpenAPI remains available at:

- `/api/v1/openapi.json`
- `/api/v1/docs`

## Contract Endpoint

`GET /api/v1/contract`

Returns:

- contract version
- API version
- REST base path
- WebSocket path
- implemented REST paths
- supported client messages
- future extension points

Extension points currently include:

- events
- source_health
- hazards
- routes
- shelters
- alerts

Listing an extension point does not claim that the corresponding
domain endpoint has already been implemented.

## Live Transport

WebSocket endpoint:

`/api/v1/ws/live`

Current B06 protocol supports:

Client:

`{"type": "ping"}`

Server:

`{"type": "pong", "protocol_version": "1"}`

Optional `request_id` is echoed back.

Unsupported message types receive a structured error and do not close
the connection.

## Live Data Status

`GET /api/v1/live/status`

The current mode is explicitly:

`contract_only`

This confirms transport readiness without claiming that live hazard,
sensor, alert, routing, or shelter event streams already exist.

## Compatibility

The pre-existing `/api/v1/health` endpoint remains unchanged.

B06 adds transport and schema foundations only; downstream task owners
can extend the contract without redefining the application's API base.

## Acceptance Verification

B06 verifies:

- versioned REST contract
- live transport capability
- successful WebSocket connection
- ping/pong round-trip
- structured error handling
- WebSocket remains usable after an invalid message
- OpenAPI exposes implemented REST paths
- existing health endpoint remains functional
