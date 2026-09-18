# -*- coding: utf-8 -*-
"""
real_pipeline/admin/correct_gadm_status.py
============================================
Corrects the GADM admin status from the erroneous NATIONWIDE_READY
to ADMIN_GEOMETRY_PROTOTYPE.

Documents:
  - Why GADM yields 41 level-1 records (not 36 States/UTs)
  - GADM ≠ LGD identity (NEVER equate GADM codes to LGD codes)
  - GADM licensing constraints
  - What GADM is used for vs. what LGD is the canonical authority for
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROC_DIR     = PROJECT_ROOT / "data_real" / "admin" / "processed"
CROSSWALK    = PROJECT_ROOT / "data_real" / "admin" / "crosswalk"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gadm_correction")


def explain_41_level1_records():
    """
    GADM v4.1 India Level 1 yields ~41 records.
    Official Government of India count: 28 States + 8 Union Territories = 36.
    The extra records are explained by:
      1. GADM includes disputed territories / boundary variations not recognised
         as separate administrative units by the GoI (e.g., parts of J&K).
      2. GADM may include island territories (Andaman & Nicobar, Lakshadweep)
         as multi-polygon entries that differ from administrative records.
      3. GADM versions may reflect different reference years.
      4. The GoI count can vary depending on whether recent reorganisations
         (e.g., J&K bifurcation in 2019 into J&K UT and Ladakh UT) are reflected.

    THEREFORE: GADM level-1 count (41) MUST NOT be reported as the official
    State/UT count of India. LGD is the canonical authority for this.
    """
    return {
        "gadm_level1_count": 41,
        "official_india_states_uts": 36,
        "discrepancy": 5,
        "explanation": [
            "GADM includes disputed territory geometries not in GoI admin count",
            "GADM may split island territories differently than GoI admin records",
            "GADM reference year may predate 2019 J&K reorganisation",
            "GoI: 28 States + 8 UTs = 36. GADM adds geometry variants/disputed areas",
        ],
        "action": (
            "GADM level-1 records are used ONLY as geometry approximations for "
            "prototype visualisation. LGD state count is the authoritative reference."
        ),
        "lgd_state_count": "MANUAL_REQUIRED — data.gov.in unreachable; expected ~36",
    }


def gadm_role_documentation():
    """Document exactly what GADM is and isn't used for."""
    return {
        "gadm_role": "ADMIN_GEOMETRY_PROTOTYPE",
        "gadm_version": "4.1",
        "source_url": "https://gadm.org/download_country.html",
        "license": (
            "GADM data are freely available for non-commercial use. "
            "Redistribution or commercial use requires permission from GADM. "
            "Do NOT distribute GADM data as part of a commercial product. "
            "See: https://gadm.org/license.html"
        ),
        "what_gadm_is_used_for": [
            "Prototype geographic visualisation in MapLibre experimental map",
            "Spatial join approximation for pilot region bounding boxes",
            "Rough boundary display for prototype UI only",
        ],
        "what_gadm_is_NOT_used_for": [
            "Canonical administrative identity (LGD is canonical)",
            "Primary keys or entity IDs (only LGD codes are used as primary keys)",
            "Production administrative hierarchy (LGD is authoritative)",
            "Official state/district/village counts",
        ],
        "critical_rules": [
            "GADM GID codes are NOT LGD codes and MUST NOT be treated as such",
            "GADM name strings may differ from LGD name strings — do not use as join key",
            "A crosswalk (GADM geometry ↔ LGD code) is REQUIRED before any production use",
            "GADM level-1 count (41) ≠ official India State+UT count (36)",
        ],
        "crosswalk_status": "NOT_DONE — MANUAL_REQUIRED (needs LGD data first)",
        "production_ready": False,
    }


def update_gadm_admin_report():
    """Read existing report and correct the gate_c_decision field."""
    report_path = PROC_DIR / "gadm_admin_report.json"

    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)
        old_decision = report.get("gate_c_decision", "")
        log.info(f"Old gate_c_decision: {old_decision}")
    else:
        report = {}
        log.warning("gadm_admin_report.json not found — creating fresh")

    # MANDATORY CORRECTION
    report["gate_c_decision"] = "ADMIN_GEOMETRY_PROTOTYPE"
    report["gate_c_decision_changed_from"] = "NATIONWIDE_READY"
    report["gate_c_correction_reason"] = (
        "NATIONWIDE_READY was incorrect. GADM provides geometry only. "
        "LGD canonical identity (codes, hierarchy) not yet ingested. "
        "Village level not available. GADM codes ≠ LGD codes. "
        "Status corrected to ADMIN_GEOMETRY_PROTOTYPE."
    )
    report["gadm_role"] = gadm_role_documentation()
    report["level1_record_explanation"] = explain_41_level1_records()
    report["lgd_identity_status"] = "MANUAL_REQUIRED"
    report["village_level"] = (
        "MANUAL_REQUIRED — LGD village data requires OTP login at lgdirectory.gov.in. "
        "data.gov.in API returned timeout. No village data ingested."
    )
    report["nationwide_predictions"] = False
    report["production_ready"] = False
    report["correction_timestamp"] = datetime.now(timezone.utc).isoformat()

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"[OK] Corrected: {report_path}")

    # Also write a separate crosswalk status file
    xwalk_status = {
        "gadm_to_lgd_crosswalk": "NOT_DONE",
        "reason": "LGD data not yet ingested (MANUAL_REQUIRED)",
        "rule": "GADM GID codes MUST NOT be used as LGD codes",
        "required_before_production": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    xwalk_path = CROSSWALK / "gadm_lgd_crosswalk_status.json"
    xwalk_path.parent.mkdir(parents=True, exist_ok=True)
    with open(xwalk_path, "w") as f:
        json.dump(xwalk_status, f, indent=2)
    log.info(f"[OK] Crosswalk status: {xwalk_path}")

    return report


def main():
    log.info("=" * 65)
    log.info("ResQ Shield — GADM Status Correction")
    log.info("=" * 65)
    report = update_gadm_admin_report()
    log.info(f"\n  gate_c_decision: {report['gate_c_decision']}")
    log.info(f"  gadm_level1_count: {report['level1_record_explanation']['gadm_level1_count']}")
    log.info(f"  official_india_states_uts: {report['level1_record_explanation']['official_india_states_uts']}")
    log.info(f"  lgd_identity_status: {report['lgd_identity_status']}")
    log.info(f"  village_level: MANUAL_REQUIRED")
    log.info("=" * 65)


if __name__ == "__main__":
    main()
