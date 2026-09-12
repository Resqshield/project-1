# T01 - Frozen Pilot Configuration

**Day:** 1
**Owner:** M3 - SW Backend & Data
**Priority:** P0
**Dependency:** T99

## Primary Pilot

- Config ID: `HP_MANDI_PANDOH_CORRIDOR`
- State: Himachal Pradesh
- District: Mandi
- Primary hydrological scope: Pandoh -> Mandi Beas corridor
- Landslide validation area: Tarna Hill / Suketi side

## External Holdout

- Config ID: `UK_DEHRADUN_RAIPUR_KUMALDA`
- State: Uttarakhand
- Region: Raipur-Kumalda / Dehradun foothills
- Purpose: geographically separated transfer/generalization evaluation

The holdout must not be silently included in pilot-specific fitting or calibration.

## Village and Catchment Scope

The MVP targets 5-10 villages and connected sub-catchments within the Pandoh -> Mandi corridor.

Exact village names are NOT fabricated at this stage.

Final village/catchment membership must be selected only when station coverage, catchment boundaries and GIS/data availability have been verified.

Every selected village must therefore inherit the primary pilot ID:

`HP_MANDI_PANDOH_CORRIDOR`

## Development Fixtures

Existing `DEV_*` database seed records are synthetic development/test fixtures.

They are intentionally retained and must not be presented as real Mandi pilot observations.

Verified real pilot GIS/data will be loaded separately.

## Shared Configuration Rule

All backend, GIS, data, model and downstream integration work must use:

- Pilot: `HP_MANDI_PANDOH_CORRIDOR`
- External holdout: `UK_DEHRADUN_RAIPUR_KUMALDA`

No module may silently revert to Uttarakhand as the primary pilot or introduce another pilot identifier.

## T01 Acceptance Check

- Primary pilot matches T99.
- External holdout matches T99.
- Shared machine-readable IDs are frozen.
- Placeholder pilot IDs are removed from active configuration.
- Development fixtures remain clearly separated from real pilot data.
- Village/catchment scope does not invent unsupported locations.
