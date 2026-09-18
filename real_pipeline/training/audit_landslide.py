# -*- coding: utf-8 -*-
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = PROJECT_ROOT / "data_real/events/landslide/processed/landslide_events_v2.parquet"
ARTIFACT_DIR = Path("C:/Users/Asus/.gemini/antigravity-ide/brain/43bea67b-b26d-4a69-aca4-18817bf231d0")

def run_audit():
    if not INVENTORY_PATH.exists():
        report = "Landslide inventory not found."
        with open(ARTIFACT_DIR / "landslide_audit.md", "w") as f:
            f.write(report)
        return
    
    df = pd.read_parquet(INVENTORY_PATH)
    total_events = len(df)
    
    triggers = df['trigger'].value_counts().to_dict()
    has_date = df['date'].notna().sum()
    has_start_date = df['start_date'].notna().sum() if 'start_date' in df.columns else 0
    
    is_ready = total_events >= 30
    status = "NEEDS_MORE_EVENTS" if not is_ready else "READY_FOR_RESEARCH_PILOT"
    
    report = f"""# Landslide Inventory Audit

**Status**: `{status}`
**Total Events**: {total_events} (Gate requirement: >=30)
**Audit Timestamp**: {datetime.now(timezone.utc).isoformat()}

## Evidence Gate Failure
The current inventory contains {total_events} events, which is below the minimum evidence gate threshold of 30 independent qualifying events. Training a landslide model is BLOCKED until this threshold is met.

## Inventory Breakdown
- **Dated Events (has 'date')**: {has_date}
- **Dated Events (has precise 'start_date')**: {has_start_date}
- **Triggers**: {json.dumps(triggers, indent=2)}

## Missing Attributes
- Precise `start_date` and `end_date` are missing for all/most records.
- CHIRPS matching has not been completed.
- DEM coverage has not been validated against these coordinates.

## Action Required
- Ingest additional landslide events to cross the 30-event threshold.
- Refine event dates to exact start dates so rainfall triggering windows can be aligned.
"""
    
    with open(ARTIFACT_DIR / "landslide_audit.md", "w", encoding="utf-8") as f:
        f.write(report)
        
    print(f"Audit complete. Status: {status}")

if __name__ == "__main__":
    run_audit()
