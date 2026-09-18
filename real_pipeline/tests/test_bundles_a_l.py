# -*- coding: utf-8 -*-
"""
real_pipeline/tests/test_bundles_a_l.py
=========================================
Tests for Bundles A-L:
  Gate A: Flood event expansion (>=10 events, >=5 regions, no rainfall-threshold labels)
  Gate B: Landslide event expansion (N events, decision gate)
  Gate C: GADM admin foundation (states/districts/subdistricts)
  Gate D: HydroBASINS (report exists with status)
  Gate F: Label quality metadata
  Gate G: Flood matrix v2 (if exists)
  Gate I/J: MapLibre frontend files (existence, no 600k GeoJSON)
  Gate K: Admin search logic
  Gate L: Coverage schema
  MVP: Synthetic MVP untouched
"""

import json
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_REAL    = PROJECT_ROOT / "data_real"
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "src"


class TestGateAFloodEvents(unittest.TestCase):
    """Gate A: Flood event expansion."""

    @classmethod
    def setUpClass(cls):
        p = DATA_REAL / "events" / "flood" / "processed" / "flood_events_v2.parquet"
        cls.exists = p.exists()
        cls.df = pd.read_parquet(p) if cls.exists else None

    def test_events_v2_exists(self):
        self.assertTrue(self.exists, "flood_events_v2.parquet missing — run expand_flood_events.py")

    def test_gate_a_min_10_events(self):
        self.assertGreaterEqual(len(self.df), 10,
            f"Only {len(self.df)} events — Gate A requires >= 10")

    def test_gate_a_min_5_regions(self):
        n_regions = self.df["region"].nunique()
        self.assertGreaterEqual(n_regions, 5,
            f"Only {n_regions} regions — Gate A requires >= 5")

    def test_gate_a_min_physiographic_zones(self):
        n_zones = self.df["physiographic_zone"].nunique()
        self.assertGreaterEqual(n_zones, 4, f"Only {n_zones} zones")

    def test_no_duplicate_event_ids(self):
        dupes = self.df["event_id"].duplicated().sum()
        self.assertEqual(int(dupes), 0, f"Duplicate event IDs: {dupes}")

    def test_no_rainfall_threshold_labels(self):
        bad = self.df[self.df["label_type"] == "rainfall_threshold"]
        self.assertEqual(len(bad), 0, "Found rainfall_threshold label type — FORBIDDEN")

    def test_all_events_have_evidence(self):
        no_ev = self.df[self.df["evidence"].str.len() < 20]
        self.assertEqual(len(no_ev), 0, f"{len(no_ev)} events have inadequate evidence")

    def test_label_quality_column_exists(self):
        self.assertIn("label_quality", self.df.columns)

    def test_label_spatial_precision_column_exists(self):
        self.assertIn("label_spatial_precision", self.df.columns)

    def test_label_temporal_precision_column_exists(self):
        self.assertIn("label_temporal_precision", self.df.columns)

    def test_all_real_data(self):
        self.assertTrue(
            (self.df["data_type"] == "REAL_DATA — NOT SYNTHETIC").all(),
            "Some events not tagged as REAL_DATA"
        )

    def test_gate_a_report_exists(self):
        p = DATA_REAL / "events" / "flood" / "processed" / "event_expansion_report.json"
        self.assertTrue(p.exists(), "event_expansion_report.json missing")

    def test_gate_a_report_pass(self):
        p = DATA_REAL / "events" / "flood" / "processed" / "event_expansion_report.json"
        with open(p) as f:
            rep = json.load(f)
        self.assertEqual(rep.get("gate_a_decision"), "GATE_A_PASS",
                         f"Gate A decision: {rep.get('gate_a_decision')}")

    def test_negative_windows_v2_exists(self):
        p = DATA_REAL / "events" / "flood" / "processed" / "negative_windows_v2.parquet"
        self.assertTrue(p.exists(), "negative_windows_v2.parquet missing")

    def test_negative_windows_matched(self):
        p = DATA_REAL / "events" / "flood" / "processed" / "negative_windows_v2.parquet"
        neg_df = pd.read_parquet(p)
        # Each new positive event region should have a negative window
        pos_regions = set(self.df["region"].unique())
        neg_regions = set(neg_df["region"].unique())
        missing = pos_regions - neg_regions
        self.assertEqual(len(missing), 0,
            f"Positive regions without matched negatives: {missing}")


class TestGateBLandslide(unittest.TestCase):
    """Gate B: Landslide event expansion."""

    @classmethod
    def setUpClass(cls):
        p = DATA_REAL / "events" / "landslide" / "processed" / "landslide_events_v2.parquet"
        cls.exists = p.exists()
        cls.df = pd.read_parquet(p) if cls.exists else None
        rep_path = DATA_REAL / "events" / "landslide" / "processed" / "landslide_gate_b_report.json"
        cls.report = json.load(open(rep_path)) if rep_path.exists() else {}

    def test_landslide_events_v2_exists(self):
        self.assertTrue(self.exists)

    def test_all_dynamic_dated(self):
        """All events in v2 should be dynamic_dated."""
        dynamic = self.df[self.df["label_type"].str.startswith("dynamic_")]
        self.assertEqual(len(dynamic), len(self.df),
            f"{len(self.df)-len(dynamic)} non-dynamic events found")

    def test_no_synthetic_contamination(self):
        self.assertTrue(
            (self.df["data_type"] == "REAL_DATA — NOT SYNTHETIC").all()
        )

    def test_gate_b_report_exists(self):
        self.assertIn("gate_b_decision", self.report)

    def test_no_model_trained_if_insufficient(self):
        """If < 30 events, gate_b_decision must be NEEDS_MORE_EVENTS."""
        n_dynamic = self.report.get("n_curated_dynamic", 0)
        decision = self.report.get("gate_b_decision", "")
        if n_dynamic < 30:
            self.assertEqual(decision, "NEEDS_MORE_EVENTS",
                f"Only {n_dynamic} events but gate says {decision}")

    def test_excluded_events_documented(self):
        """GLOF and non-rainfall events must be documented as excluded."""
        excluded = self.report.get("excluded_events", [])
        self.assertGreater(len(excluded), 0, "No excluded events documented")

    def test_gsi_manual_required_documented(self):
        gsi = self.report.get("gsi_status", "")
        self.assertIn("MANUAL_REQUIRED", gsi, "GSI status not documented as MANUAL_REQUIRED")


class TestGateCAdmin(unittest.TestCase):
    """Gate C: GADM admin foundation."""

    def test_states_parquet_exists(self):
        p = DATA_REAL / "admin" / "processed" / "states.parquet"
        self.assertTrue(p.exists(), "states.parquet missing — run ingest_gadm.py")

    def test_districts_parquet_exists(self):
        p = DATA_REAL / "admin" / "processed" / "districts.parquet"
        self.assertTrue(p.exists(), "districts.parquet missing")

    def test_subdistricts_parquet_exists(self):
        p = DATA_REAL / "admin" / "processed" / "subdistricts.parquet"
        self.assertTrue(p.exists(), "subdistricts.parquet missing")

    def test_states_count(self):
        df = pd.read_parquet(DATA_REAL / "admin" / "processed" / "states.parquet")
        # India has 28 states + 8 UTs = 36; GADM may show ~36-41
        self.assertGreaterEqual(len(df), 28, f"Only {len(df)} states")

    def test_districts_count(self):
        df = pd.read_parquet(DATA_REAL / "admin" / "processed" / "districts.parquet")
        self.assertGreaterEqual(len(df), 600, f"Only {len(df)} districts")

    def test_subdistricts_count(self):
        df = pd.read_parquet(DATA_REAL / "admin" / "processed" / "subdistricts.parquet")
        self.assertGreaterEqual(len(df), 500, f"Only {len(df)} sub-districts")

    def test_no_duplicate_state_codes(self):
        df = pd.read_parquet(DATA_REAL / "admin" / "processed" / "states.parquet")
        dupes = df["state_code"].duplicated().sum()
        self.assertEqual(int(dupes), 0)

    def test_no_duplicate_district_codes(self):
        df = pd.read_parquet(DATA_REAL / "admin" / "processed" / "districts.parquet")
        dupes = df["district_code"].duplicated().sum()
        self.assertEqual(int(dupes), 0)

    def test_no_null_state_names(self):
        df = pd.read_parquet(DATA_REAL / "admin" / "processed" / "states.parquet")
        self.assertEqual(int(df["state_name"].isna().sum()), 0)

    def test_no_null_district_names(self):
        df = pd.read_parquet(DATA_REAL / "admin" / "processed" / "districts.parquet")
        self.assertEqual(int(df["district_name"].isna().sum()), 0)

    def test_hierarchy_crosswalk_exists(self):
        p = DATA_REAL / "admin" / "crosswalk" / "hierarchy_crosswalk.parquet"
        self.assertTrue(p.exists(), "hierarchy_crosswalk.parquet missing")

    def test_gadm_report_gate_c_decision(self):
        p = DATA_REAL / "admin" / "processed" / "gadm_admin_report.json"
        self.assertTrue(p.exists(), "gadm_admin_report.json missing")
        with open(p) as f:
            rep = json.load(f)
        self.assertIn(rep.get("gate_c_decision"), {"NATIONWIDE_READY", "ADMIN_GEOMETRY_PROTOTYPE"},
            f"Gate C: {rep.get('gate_c_decision')}")

    def test_geojson_states_exported(self):
        p = DATA_REAL / "admin" / "processed" / "geojson" / "states_india.geojson"
        self.assertTrue(p.exists(), "states_india.geojson missing — run export_geojson_pilot.py")

    def test_geojson_districts_exported(self):
        p = DATA_REAL / "admin" / "processed" / "geojson" / "districts_india.geojson"
        self.assertTrue(p.exists(), "districts_india.geojson missing")

    def test_geojson_states_valid(self):
        p = DATA_REAL / "admin" / "processed" / "geojson" / "states_india.geojson"
        with open(p) as f:
            gj = json.load(f)
        self.assertEqual(gj.get("type"), "FeatureCollection")
        self.assertGreater(len(gj.get("features", [])), 0)

    def test_geojson_districts_size_reasonable(self):
        """District GeoJSON should be < 10 MB (no uncompressed nationwide disaster)."""
        p = DATA_REAL / "admin" / "processed" / "geojson" / "districts_india.geojson"
        size_mb = p.stat().st_size / 1e6
        self.assertLess(size_mb, 10, f"districts_india.geojson is {size_mb:.1f} MB — too large for prototype")

    def test_village_level_documented_manual(self):
        p = DATA_REAL / "admin" / "processed" / "gadm_admin_report.json"
        with open(p) as f:
            rep = json.load(f)
        village_status = rep.get("village_level", "")
        self.assertIn("MANUAL_REQUIRED", village_status, "Village level not documented as MANUAL_REQUIRED")


class TestGateDHydroBASINS(unittest.TestCase):
    """Gate D: HydroBASINS report."""

    def test_hydrobasins_report_exists(self):
        p = DATA_REAL / "hydrology" / "catchments" / "hydrobasins" / "hydrobasins_report.json"
        self.assertTrue(p.exists(), "hydrobasins_report.json missing — run ingest_hydrobasins.py")

    def test_hydrobasins_status_documented(self):
        p = DATA_REAL / "hydrology" / "catchments" / "hydrobasins" / "hydrobasins_report.json"
        with open(p) as f:
            rep = json.load(f)
        self.assertIn("gate_d_decision", rep)
        # Either PILOT_READY or MANUAL_REQUIRED — both are valid
        self.assertIn(rep["gate_d_decision"], ["PILOT_READY", "MANUAL_REQUIRED", "PARTIAL"],
            f"Unexpected gate D status: {rep['gate_d_decision']}")

    def test_hydrobasins_manual_url_documented_if_blocked(self):
        p = DATA_REAL / "hydrology" / "catchments" / "hydrobasins" / "hydrobasins_report.json"
        with open(p) as f:
            rep = json.load(f)
        if rep["gate_d_decision"] == "MANUAL_REQUIRED":
            self.assertIn("note", rep, "MANUAL_REQUIRED but no instructions given")


class TestGateIJMapLibre(unittest.TestCase):
    """Gates I/J: MapLibre experimental map prototype."""

    def test_realmap_directory_exists(self):
        d = FRONTEND_DIR / "realmap"
        self.assertTrue(d.exists(), "frontend/src/realmap/ missing")

    def test_real_admin_map_jsx_exists(self):
        p = FRONTEND_DIR / "realmap" / "RealAdminMap.jsx"
        self.assertTrue(p.exists(), "RealAdminMap.jsx missing")

    def test_real_admin_map_uses_maplibre(self):
        p = FRONTEND_DIR / "realmap" / "RealAdminMap.jsx"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn("maplibre-gl", content, "MapLibre GL not imported")

    def test_realmap_not_replacing_riskmap(self):
        """RiskMap.jsx must still exist and be unmodified in structure."""
        p = FRONTEND_DIR / "components" / "RiskMap.jsx"
        self.assertTrue(p.exists(), "RiskMap.jsx missing — synthetic MVP broken")

    def test_no_nationwide_risk_in_realmap(self):
        """RealAdminMap must not claim nationwide hazard predictions."""
        p = FRONTEND_DIR / "realmap" / "RealAdminMap.jsx"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertNotIn("nationwide_predictions = True", content)
        self.assertNotIn("nationwide_risk", content.lower())

    def test_experimental_label_in_realmap(self):
        p = FRONTEND_DIR / "realmap" / "RealAdminMap.jsx"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn("EXPERIMENTAL", content, "No EXPERIMENTAL label in RealAdminMap")

    def test_real_map_page_exists(self):
        p = FRONTEND_DIR / "realmap" / "RealMapPage.jsx"
        self.assertTrue(p.exists(), "RealMapPage.jsx missing")

    def test_admin_search_bar_exists(self):
        p = FRONTEND_DIR / "realmap" / "AdminSearchBar.jsx"
        self.assertTrue(p.exists(), "AdminSearchBar.jsx missing")

    def test_main_jsx_has_hash_routing(self):
        p = FRONTEND_DIR / "main.jsx"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn("RealMapPage", content, "No RealMapPage in main.jsx")

    def test_geojson_not_too_large(self):
        """No single GeoJSON file should be > 10 MB (prevents frontend freeze)."""
        geojson_dir = DATA_REAL / "admin" / "processed" / "geojson"
        if not geojson_dir.exists():
            self.skipTest("GeoJSON dir not yet generated")
        for gj in geojson_dir.glob("*.geojson"):
            size_mb = gj.stat().st_size / 1e6
            self.assertLess(size_mb, 10,
                f"{gj.name} is {size_mb:.1f} MB — too large for browser GeoJSON")

    def test_no_600k_markers(self):
        """RealAdminMap must not render individual markers for large datasets."""
        p = FRONTEND_DIR / "realmap" / "RealAdminMap.jsx"
        content = p.read_text(encoding="utf-8", errors="replace")
        # Should NOT use Leaflet Marker for mass rendering
        self.assertNotIn("new maplibregl.Marker", content,
            "Using individual Marker objects — would create too many DOM nodes")


class TestGateKSearch(unittest.TestCase):
    """Gate K: Admin search endpoint logic."""

    def test_search_api_file_exists(self):
        p = PROJECT_ROOT / "backend" / "routes" / "real_research.py"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn('"/search"', content, "No /search endpoint in real_research.py")

    def test_search_logic_uses_disambiguation(self):
        p = PROJECT_ROOT / "backend" / "routes" / "real_research.py"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn("parent_path", content, "No parent_path disambiguation in search")

    def test_search_indexes_districts(self):
        p = PROJECT_ROOT / "backend" / "routes" / "real_research.py"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn("district_name", content)

    def test_search_indexes_states(self):
        p = PROJECT_ROOT / "backend" / "routes" / "real_research.py"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn("state_name", content)


class TestGateLCoverageSchema(unittest.TestCase):
    """Gate L: Observation coverage schema."""

    def test_coverage_schema_endpoint_exists(self):
        p = PROJECT_ROOT / "backend" / "routes" / "real_research.py"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn('"/coverage-schema"', content)

    def test_coverage_has_no_collapsed_score(self):
        p = PROJECT_ROOT / "backend" / "routes" / "real_research.py"
        content = p.read_text(encoding="utf-8", errors="replace")
        # Should NOT have a single confidence score collapse
        self.assertNotIn("confidence_score", content,
            "Coverage schema should not collapse into single confidence_score")

    def test_coverage_has_required_fields(self):
        p = PROJECT_ROOT / "backend" / "routes" / "real_research.py"
        content = p.read_text(encoding="utf-8", errors="replace")
        for field in ["rain_source", "river_source", "terrain_source",
                      "label_source", "label_spatial_precision"]:
            self.assertIn(field, content, f"Coverage field missing: {field}")

    def test_manual_required_documented_in_coverage(self):
        p = PROJECT_ROOT / "backend" / "routes" / "real_research.py"
        content = p.read_text(encoding="utf-8", errors="replace")
        self.assertIn("MANUAL_REQUIRED", content,
            "Coverage schema must document MANUAL_REQUIRED sources")


class TestMVPIntact(unittest.TestCase):
    """Ensure synthetic MVP is completely untouched."""

    def test_data_dir_unchanged(self):
        self.assertTrue((PROJECT_ROOT / "data").exists(),
            "data/ directory missing — synthetic MVP broken")

    def test_riskmap_jsx_intact(self):
        self.assertTrue((FRONTEND_DIR / "components" / "RiskMap.jsx").exists())

    def test_backend_main_intact(self):
        self.assertTrue((PROJECT_ROOT / "backend" / "main.py").exists())

    def test_api_locations_route_intact(self):
        content = (PROJECT_ROOT / "backend" / "main.py").read_text(
            encoding="utf-8", errors="replace")
        self.assertIn("/api/locations", content)

    def test_data_real_separate(self):
        data_files = list((PROJECT_ROOT / "data").rglob("*.parquet"))
        for f in data_files:
            self.assertNotIn("real", str(f.parent.name).lower(),
                f"Real data file found inside data/: {f}")


if __name__ == "__main__":
    unittest.main()
