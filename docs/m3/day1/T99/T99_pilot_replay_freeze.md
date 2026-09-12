# T99 - Pilot Geography and Replay Protocol Freeze

**Day:** 1
**Owner:** M3 - SW Backend & Data
**Priority:** P0
**Task:** T99 - Pilot geography + replay protocol freeze
**Hard dependencies:** T51, T52

## Primary Pilot - FROZEN

**State:** Himachal Pradesh
**District:** Mandi
**Primary corridor:** Pandoh -> Mandi Beas corridor
**Initial MVP scope:** 5-10 villages / connected sub-catchments, selected according to actual station, catchment and GIS-data availability.

This replaces the earlier mixed Uttarakhand-vs-Himachal pilot planning.

The MVP must not silently mix another primary geography into configuration, GIS, datasets, thresholds or demo claims.

## Landslide Validation Area

**Tarna Hill / Suketi side, Mandi**

Use as a documented rainfall-triggered landslide validation example.

Do not generalize one slope to the entire Himalaya.

## External Geographic Holdout - FROZEN

**Region:** Raipur-Kumalda / Dehradun foothills, Uttarakhand
**Purpose:** spatial/generalization holdout outside the Himachal primary pilot.

The external region must remain excluded from pilot-specific fitting/calibration when used for transfer evaluation.

## Historical Event Protocol

| Role | Geography | Period | Hazard | Use |
|---|---|---|---|---|
| Primary flood replay | Himachal / Mandi context | 07-11 Jul 2023 | Extreme rainfall / flash flood | Historical replay + lead-time evaluation |
| Primary landslide replay | Tarna Hill, Mandi | 14 Aug 2023 | Rainfall-triggered landslide | Dynamic slope-risk validation |
| Temporal event holdout | Himachal / Mandi context | 22-23 Aug 2023 | Extreme rainfall spell | Keep untouched where matching observations/labels are verified |
| External spatial holdout | Raipur-Kumalda, Uttarakhand | 20-21 Aug 2022 | Cloudburst / flash flood | Cross-region transfer evaluation |
| Negative control | Mandi pilot | TO BE VERIFIED FROM TELEMETRY + EVENT INVENTORY | Heavy rain without major local event | False-alarm evaluation |

## Data/Evidence Rules

- Use observed timestamps; do not invent warning lead time.
- Historical replay events must have matching observations and event evidence.
- Temporal holdout data must remain outside training/fitting where possible.
- External holdout geography must remain outside pilot-specific fitting.
- Negative controls must be heavy-rain windows with no verified major local flood/landslide.
- Any unavailable variable must be marked missing or fallback; never fabricate observations.

## Available Data Evidence

Primary Himachal pilot currently has access to hourly hydrometeorological/rainfall sources covering the 2023 replay periods.

The Uttarakhand external holdout has hourly rainfall telemetry covering the 2022 event period and an independently documented flash-flood event.

## Remaining Verification Before T99 Can Be Marked DONE

Select and freeze at least one exact heavy-rain negative/control period for the Mandi pilot after checking:

1. rainfall telemetry confirms meaningful rain;
2. event inventories / official records show no major local flood or landslide during that period.

Do not invent a control period merely to complete the checklist.

## T99 Acceptance Check

- One primary pilot geography is frozen.
- One different external geographical holdout is frozen.
- Flood replay period is explicit.
- Landslide replay period is explicit.
- Temporal event holdout is explicit.
- External spatial holdout event is explicit.
- Negative/control period must be verified before final DONE status.
- Mixed-geometry implementation is prohibited.

## Negative-Control Verification Note

The downloaded CWC Himachal Pradesh hourly rainfall dataset was reviewed for the Mandi pilot.

Findings:

- The file contains only 10 Mandi-district records.
- All Mandi records are from Parashar Lake.
- Mandi records are available only in 2025 in this downloaded file.
- No Pandoh record is available in this file.
- Therefore this dataset cannot provide the required 2023 Mandi/Pandoh negative-control period.
- A 26-Nov-2025 Parashar Lake observation reports 28.7 mm hourly rainfall, but this value is NOT accepted as the negative control because independent IMD reporting describes 26-Nov-2025 as dry at the state level.
- This disagreement is treated as a source-quality/provenance issue rather than silently accepting one source.

### Current T99 Status

Primary geography, external holdout and historical replay periods are frozen.

The exact Mandi heavy-rain / no-major-event negative-control period remains BLOCKED pending a better verified historical rainfall source plus incident cross-check.

No control date will be fabricated merely to close the task.

## Negative-Control Resolution

**Frozen negative-control period:** 06-Jun-2023
**Location:** Bijahi, Mandi district, Himachal Pradesh
**Role:** Heavy-rain non-disaster control for false-alarm evaluation
**Label confidence:** MEDIUM

Evidence basis:

- IMD Himachal Monsoon Report 2023 identifies 06-Jun-2023 at Bijahi, Mandi as the first heavy-rainfall spell of the season.
- No major Mandi flood/landslide incident for this date was found in the official incident material reviewed.
- Because absence-of-event evidence is less certain than positive disaster evidence, this control label is retained with MEDIUM confidence rather than treated as perfect ground truth.

Usage rule:

- Use this period for false-alarm / specificity testing.
- Do not treat it as a guaranteed zero-hazard period.
- Preserve source, timestamp and label-confidence provenance in the common event dataset.

### Final T99 Status

T99 is now considered IMPLEMENTED for the Day-1 pilot freeze:

- Primary pilot: Mandi district, Himachal Pradesh
- Primary corridor: Pandoh -> Mandi Beas corridor
- Landslide validation: Tarna Hill / Suketi side
- Flood replay: 07-11 Jul 2023
- Landslide replay: 14 Aug 2023
- Temporal holdout: 22-23 Aug 2023
- External spatial holdout: Raipur-Kumalda / Dehradun foothills, Uttarakhand, 20-21 Aug 2022
- Negative control: 06-Jun-2023 Bijahi, Mandi, label confidence MEDIUM

No mixed primary geography is permitted.
