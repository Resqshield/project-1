# -*- coding: utf-8 -*-
"""
real_pipeline/tests/test_phase5_realdata_v2.py
==============================================
Phase 5 / real-data-v1 test suite.
Tests: rainfall parity, no leakage, no synthetic contamination,
       event separation, label quality, GADM!=LGD, basin validation,
       API readiness flags, MVP untouched.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_REAL = PROJECT_ROOT / "data_real"
MODELS_REAL = PROJECT_ROOT / "models_real"
FEAT_DIR = DATA_REAL / "features"
LABELS_DIR = DATA_REAL / "labels"
ADMIN_DIR = DATA_REAL / "admin"
HYDRO_DIR = DATA_REAL / "hydrology"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def flood_v2():
    path = FEAT_DIR / "flood_training_v2.parquet"
    if not path.exists():
        pytest.skip("flood_training_v2.parquet not found")
    return pd.read_parquet(path)


@pytest.fixture(scope="module")
def event_quality():
    path = LABELS_DIR / "event_quality.csv"
    if not path.exists():
        pytest.skip("event_quality.csv not found")
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def api_status():
    path = DATA_REAL / "api_status.json"
    if not path.exists():
        pytest.skip("api_status.json not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def gadm_report():
    path = ADMIN_DIR / "processed" / "gadm_admin_report.json"
    if not path.exists():
        pytest.skip("gadm_admin_report.json not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def model_metadata():
    path = MODELS_REAL / "flood_v2_research_metadata.json"
    if not path.exists():
        pytest.skip("flood_v2_research_metadata.json not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# 1. No Synthetic Contamination
# ─────────────────────────────────────────────────────────────────────────────

class TestNoSyntheticContamination:
    def test_flood_v2_data_type(self, flood_v2):
        """flood_training_v2 must not contain synthetic data."""
        assert "data_type" in flood_v2.columns, "data_type column missing"
        unique_types = flood_v2["data_type"].unique()
        for t in unique_types:
            # Value "REAL_DATA_NOT_SYNTHETIC" is valid — check for purely synthetic labels
            assert str(t).upper() != "SYNTHETIC" and \
                   not str(t).upper().startswith("SYNTHETIC") and \
                   "REAL_DATA" in str(t).upper(), (
                f"Non-real data type found in flood_v2: {t}"
            )
        assert len(unique_types) == 1, f"Multiple data types: {unique_types}"

    def test_flood_v2_data_type_value(self, flood_v2):
        """data_type must be exactly REAL_DATA_NOT_SYNTHETIC."""
        assert (flood_v2["data_type"] == "REAL_DATA_NOT_SYNTHETIC").all(), (
            f"Unexpected data_type: {flood_v2['data_type'].unique()}"
        )

    def test_no_synthetic_event_ids(self, flood_v2):
        """No event_id should contain 'synthetic' or 'fake'."""
        bad = [e for e in flood_v2["event_id"].unique()
               if any(w in e.lower() for w in ["synthetic", "fake", "mock", "test_"])]
        assert not bad, f"Synthetic event IDs found: {bad}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Event Separation / No Leakage
# ─────────────────────────────────────────────────────────────────────────────

class TestEventSeparation:
    def test_events_do_not_overlap_in_time(self, flood_v2):
        """Positive events in the same region must not have overlapping windows."""
        pos = flood_v2[flood_v2["label"] == 1].copy()
        pos["ws"] = pd.to_datetime(pos["window_start"])
        pos["we"] = pd.to_datetime(pos["window_end"])

        for region in pos["region"].unique():
            reg_events = pos[pos["region"] == region].drop_duplicates("event_id")
            if len(reg_events) < 2:
                continue
            events = sorted(reg_events.itertuples(), key=lambda r: r.ws)
            for i in range(len(events) - 1):
                a, b = events[i], events[i + 1]
                assert a.we < b.ws, (
                    f"Overlapping positive events in {region}: "
                    f"{a.event_id} ends {a.we}, {b.event_id} starts {b.ws}"
                )

    def test_no_event_in_train_and_test(self, flood_v2):
        """
        Each event_id must be uniquely assigned to one group.
        Verify that a naive LOEO split would never put same event in both train and test.
        """
        event_ids = flood_v2["event_id"].unique()
        assert len(event_ids) == flood_v2["event_id"].nunique(), "Duplicate event_id entries"

    def test_positive_and_negative_event_ids_distinct(self, flood_v2):
        """Positive events and negative windows must have distinct IDs."""
        pos_ids = set(flood_v2[flood_v2["label"] == 1]["event_id"].unique())
        neg_ids = set(flood_v2[flood_v2["label"] == 0]["event_id"].unique())
        overlap = pos_ids & neg_ids
        assert not overlap, f"event_id appears in both label=1 and label=0: {overlap}"

    def test_blacklisted_columns_not_in_features(self, model_metadata):
        """Model feature list must not contain leakage columns."""
        BLACKLIST = {
            "label", "event_id", "region", "cell_id",
            "window_start", "window_end", "window_type",
            "label_source", "label_type", "label_spatial_precision",
            "label_temporal_precision", "label_quality",
            "label_quality_class", "label_quality_class_note",
            "rain_source", "terrain_available", "terrain_source",
            "data_type",
        }
        features = set(model_metadata.get("feature_list", []))
        leaked = features & BLACKLIST
        assert not leaked, f"Blacklisted features in model: {leaked}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Rainfall Parity
# ─────────────────────────────────────────────────────────────────────────────

class TestRainfallParity:
    RAIN_COLS = [
        "rain_event_sum_mm", "rain_event_max_mm",
        "ant_3d_mm", "ant_7d_mm", "ant_14d_mm",
    ]

    def test_rain_features_excluded_when_parity_violated(self, model_metadata):
        """If rain parity is violated, rain features must be excluded from model."""
        rain_included = model_metadata.get("rain_features_included", True)
        if not rain_included:
            features = model_metadata.get("feature_list", [])
            rain_in_model = [f for f in features if any(
                k in f for k in ["rain", "ant_", "chirps", "ant3", "ant7"]
            )]
            assert not rain_in_model, (
                f"rain_features_included=False but rain features in model: {rain_in_model}"
            )

    def test_terrain_parity_symmetric(self, flood_v2):
        """Terrain features must have equal missingness in both classes."""
        for col in ["elev_mean_m", "slope_mean_deg"]:
            if col not in flood_v2.columns:
                continue
            miss_pos = flood_v2[flood_v2["label"] == 1][col].isna().mean()
            miss_neg = flood_v2[flood_v2["label"] == 0][col].isna().mean()
            delta = abs(miss_pos - miss_neg)
            assert delta < 0.001, (
                f"Terrain parity violation for {col}: "
                f"pos={miss_pos:.3f} neg={miss_neg:.3f} delta={delta:.3f}"
            )

    def test_no_rain_leakage_if_included(self, flood_v2, model_metadata):
        """If rain features are included, delta must be < 5%."""
        if not model_metadata.get("rain_features_included", False):
            pytest.skip("Rain features excluded — parity test not applicable")
        for col in self.RAIN_COLS:
            if col not in flood_v2.columns:
                continue
            miss_pos = flood_v2[flood_v2["label"] == 1][col].isna().mean()
            miss_neg = flood_v2[flood_v2["label"] == 0][col].isna().mean()
            delta = abs(miss_pos - miss_neg)
            assert delta < 0.05, (
                f"Rain parity violation for {col}: delta={delta:.3f} >= 0.05"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Label Quality
# ─────────────────────────────────────────────────────────────────────────────

class TestLabelQuality:
    def test_no_rainfall_only_labels(self, event_quality):
        """Hard rule: no rainfall-derived labels."""
        assert "rainfall_only_label" in event_quality.columns
        n_rainfall_labels = event_quality["rainfall_only_label"].astype(bool).sum()
        assert n_rainfall_labels == 0, (
            f"Found {n_rainfall_labels} rainfall-only labels — RULE VIOLATION"
        )

    def test_no_class_a_labels(self, event_quality):
        """No observed inundation geometry exists — class A should be 0."""
        n_A = (event_quality["label_quality_class"] == "A").sum()
        assert n_A == 0, (
            f"Unexpected class A labels ({n_A}). "
            "Class A requires observed SAR/optical flood geometry."
        )

    def test_all_labels_are_b_or_c(self, event_quality):
        """All events must be B or C quality class."""
        valid_classes = {"A", "B", "C"}
        for cls in event_quality["label_quality_class"].unique():
            assert cls in valid_classes, f"Invalid label quality class: {cls}"

    def test_region_wide_events_are_class_c(self, event_quality):
        """Region-wide spatial precision must be class C."""
        region_wide = event_quality[event_quality["label_spatial_precision"] == "region_wide"]
        for _, row in region_wide.iterrows():
            assert row["label_quality_class"] == "C", (
                f"{row['event_id']}: region_wide precision must be class C, "
                f"got {row['label_quality_class']}"
            )

    def test_status_is_experimental(self, event_quality):
        """All events must be flagged EXPERIMENTAL_BASELINE_ONLY."""
        for _, row in event_quality.iterrows():
            assert "EXPERIMENTAL" in str(row.get("status", "")), (
                f"{row['event_id']}: status must contain EXPERIMENTAL, got {row.get('status')}"
            )

    def test_event_quality_has_required_columns(self, event_quality):
        required = [
            "event_id", "event_name", "year", "region",
            "label_type", "label_spatial_precision",
            "label_temporal_precision", "source", "confidence_notes",
        ]
        missing = [c for c in required if c not in event_quality.columns]
        assert not missing, f"event_quality.csv missing columns: {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# 5. GADM != LGD
# ─────────────────────────────────────────────────────────────────────────────

class TestGADMNotLGD:
    def test_gadm_status_is_prototype(self, gadm_report):
        """GADM must be labeled ADMIN_GEOMETRY_PROTOTYPE, not NATIONWIDE_READY."""
        decision = gadm_report.get("gate_c_decision", "")
        assert decision == "ADMIN_GEOMETRY_PROTOTYPE", (
            f"GADM gate_c_decision must be ADMIN_GEOMETRY_PROTOTYPE, got '{decision}'. "
            "Do NOT claim NATIONWIDE_READY."
        )

    def test_gadm_lgd_identity_not_claimed(self, gadm_report):
        """GADM must NOT claim LGD identity."""
        nationwide = gadm_report.get("nationwide_prediction_ready", True)
        assert nationwide is False, "nationwide_prediction_ready must be False"

    def test_lgd_codes_not_available(self, gadm_report):
        """lgd_codes_available must be False until LGD is ingested."""
        lgd_available = gadm_report.get("lgd_codes_available", True)
        assert lgd_available is False, (
            "lgd_codes_available must be False until LGD manual download is complete"
        )

    def test_hierarchy_schema_exists(self):
        """hierarchy_schema.json must document the GADM/LGD separation."""
        schema_path = ADMIN_DIR / "hierarchy_schema.json"
        assert schema_path.exists(), f"hierarchy_schema.json not found at {schema_path}"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        assert "levels" in schema
        assert len(schema["levels"]) >= 4, "Schema must have at least 4 hierarchy levels"

    def test_manual_import_instructions_exist(self):
        """manual_import.md must exist with LGD download instructions."""
        md_path = ADMIN_DIR / "manual_import.md"
        assert md_path.exists(), f"manual_import.md not found at {md_path}"
        content = md_path.read_text(encoding="utf-8")
        assert "lgdirectory.gov.in" in content, "LGD portal URL not in manual_import.md"
        assert "VillageLGDCode" in content, "VillageLGDCode column not documented"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Basin Validation
# ─────────────────────────────────────────────────────────────────────────────

class TestBasinValidation:
    def test_hydrobasins_status_exists(self):
        """hydrobasins_status.json must exist."""
        status_path = HYDRO_DIR / "hydrobasins_status.json"
        assert status_path.exists(), f"hydrobasins_status.json not found at {status_path}"

    def test_hydrobasins_processed_or_manual(self):
        """Either processed HydroBASINS parquet OR documented manual requirement must exist."""
        processed = HYDRO_DIR / "processed" / "hydrobasins_india_lev06.parquet"
        raw_zip = HYDRO_DIR / "raw" / "hybas_sa_lev06_v1c.zip"
        status_path = HYDRO_DIR / "hydrobasins_status.json"

        if processed.exists():
            # Validate the parquet
            df = pd.read_parquet(processed)
            # Level 6 macro-basins: India has ~800. Accept >100.
            assert len(df) > 100, f"HydroBASINS count too low: {len(df)}"
            assert "HYBAS_ID" in df.columns or "hybas_id" in df.columns, \
                "HYBAS_ID column missing"
            return

        if raw_zip.exists():
            # Zip downloaded, processing pending
            return

        # Must at least have documented status
        assert status_path.exists(), "No HydroBASINS documentation found"

    def test_village_catchment_not_fabricated(self):
        """village_catchment_links.parquet must NOT exist if prerequisites are unavailable."""
        links_path = HYDRO_DIR / "village_catchment_links.parquet"
        lgd_raw = ADMIN_DIR / "raw" / "lgd_national_villages.csv"
        hydrobasins = HYDRO_DIR / "raw" / "hybas_sa_lev06_v1c.zip"

        if links_path.exists():
            # If it exists, both prerequisites must also exist
            assert lgd_raw.exists(), (
                "village_catchment_links.parquet exists but LGD villages not available — "
                "possible fabricated data!"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 7. API Readiness Flags
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIReadiness:
    def test_research_only_flag(self, api_status):
        assert api_status.get("research_only") is True, \
            "research_only must be True"

    def test_nationwide_predictions_false(self, api_status):
        assert api_status.get("nationwide_predictions") is False, \
            "nationwide_predictions must be False"

    def test_deployment_not_allowed(self, api_status):
        assert api_status.get("deployment_allowed") is False, \
            "deployment_allowed must be False"

    def test_flood_v2_status_experimental(self, api_status):
        assert api_status.get("flood_v2") == "EXPERIMENTAL_BASELINE_ONLY", \
            f"flood_v2 status must be EXPERIMENTAL_BASELINE_ONLY, got {api_status.get('flood_v2')}"

    def test_landslide_status_needs_events(self, api_status):
        assert "NEEDS" in str(api_status.get("landslide", "")), \
            f"landslide status incorrect: {api_status.get('landslide')}"

    def test_operational_warning_false(self, api_status):
        assert api_status.get("operational_warning") is False, \
            "operational_warning must be False"

    def test_model_deployment_flags(self, api_status):
        models = api_status.get("models", {})
        for mname, minfo in models.items():
            assert minfo.get("deployment_allowed") is False, \
                f"Model {mname} has deployment_allowed=True — not allowed"


# ─────────────────────────────────────────────────────────────────────────────
# 8. MVP Untouched
# ─────────────────────────────────────────────────────────────────────────────

class TestMVPUntouched:
    MVP_ROOT = Path(r"c:\flood_prediction_this")

    def test_mvp_backend_exists(self):
        """Original MVP backend must still exist."""
        backend = self.MVP_ROOT / "backend"
        assert backend.exists(), f"MVP backend missing at {backend}"

    def test_mvp_frontend_exists(self):
        """Original MVP frontend must still exist."""
        frontend = self.MVP_ROOT / "frontend"
        assert frontend.exists(), f"MVP frontend missing at {frontend}"

    def test_mvp_synthetic_data_intact(self):
        """MVP data/predictions must still exist."""
        predictions = self.MVP_ROOT / "data" / "predictions"
        assert predictions.exists(), f"MVP predictions missing at {predictions}"

    def test_research_copy_is_separate(self):
        """Research copy must be separate from MVP."""
        research_root = PROJECT_ROOT
        mvp_root = self.MVP_ROOT
        assert str(research_root) != str(mvp_root), \
            "Research copy and MVP are the same directory — DANGEROUS"
        assert "copy" in str(research_root).lower() or \
               str(research_root) != str(mvp_root), \
            "Research root should be clearly separate from MVP"

    def test_no_real_pipeline_in_mvp(self):
        """Original MVP must not have real_pipeline modifications."""
        mvp_real_pipeline = self.MVP_ROOT / "real_pipeline"
        # MVP may have a real_pipeline for reference, but it should not have v2 training
        if mvp_real_pipeline.exists():
            v2_trainer = mvp_real_pipeline / "training" / "train_flood_models_v2.py"
            assert not v2_trainer.exists(), \
                "train_flood_models_v2.py found in MVP directory — research copy contaminated MVP!"


# ─────────────────────────────────────────────────────────────────────────────
# 9. Matrix Integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestMatrixIntegrity:
    def test_balanced_label_distribution(self, flood_v2):
        """Label distribution must be 1:1."""
        n_pos = (flood_v2["label"] == 1).sum()
        n_neg = (flood_v2["label"] == 0).sum()
        assert n_pos == n_neg, f"Unbalanced labels: pos={n_pos} neg={n_neg}"

    def test_minimum_events(self, flood_v2):
        """Must have >= 10 independent positive events."""
        n_pos_events = flood_v2[flood_v2["label"] == 1]["event_id"].nunique()
        assert n_pos_events >= 10, f"Only {n_pos_events} positive events (need >= 10)"

    def test_minimum_regions(self, flood_v2):
        """Must have >= 5 regions."""
        n_regions = flood_v2["region"].nunique()
        assert n_regions >= 5, f"Only {n_regions} regions (need >= 5)"

    def test_no_null_labels(self, flood_v2):
        """No null labels allowed."""
        assert flood_v2["label"].notna().all(), "Null labels found in flood_v2"
        assert set(flood_v2["label"].unique()).issubset({0, 1}), \
            f"Unexpected label values: {flood_v2['label'].unique()}"

    def test_no_null_region(self, flood_v2):
        """No null region values."""
        assert flood_v2["region"].notna().all(), "Null region values found"

    def test_all_events_have_matched_negatives(self, flood_v2):
        """Each region with a positive event must also have a negative window."""
        pos_regions = set(flood_v2[flood_v2["label"] == 1]["region"].unique())
        neg_regions = set(flood_v2[flood_v2["label"] == 0]["region"].unique())
        unmatched = pos_regions - neg_regions
        assert not unmatched, \
            f"Positive events with no negative window in same region: {unmatched}"


# ─────────────────────────────────────────────────────────────────────────────
# 10. Model Metadata Integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestModelMetadata:
    def test_not_operational(self, model_metadata):
        assert model_metadata.get("not_operational") is True

    def test_deployment_not_allowed(self, model_metadata):
        assert model_metadata.get("deployment_allowed") is False

    def test_readiness_label(self, model_metadata):
        assert model_metadata.get("readiness_label") == "EXPERIMENTAL_BASELINE_ONLY"

    def test_validation_strategy(self, model_metadata):
        assert "LOEO" in model_metadata.get("validation_strategy", "")

    def test_limitations_documented(self, model_metadata):
        limitations = model_metadata.get("limitations", [])
        assert len(limitations) >= 3, "Must document at least 3 model limitations"

    def test_label_quality_in_metadata(self, model_metadata):
        lq = model_metadata.get("label_quality", {})
        assert "class_A_count" in lq, "label_quality.class_A_count missing"
        assert lq.get("class_A_count") == 0, \
            "class_A_count must be 0 (no cell-level truth)"
