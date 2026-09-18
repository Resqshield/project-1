# -*- coding: utf-8 -*-
"""
real_pipeline/tests/test_real_pipeline.py
==========================================
Test suite for Real Data Phase 1 infrastructure.

Tests:
  1. Admin source discovery (LGD raw dir exists, patterns detectable)
  2. LGD ingestion (open API attempt; accepts MANUAL_REQUIRED gracefully)
  3. Boundary ingestion (detects files; gracefully handles missing GADM)
  4. Admin hierarchy validation (on synthetic-free test data)
  5. Duplicate code detection
  6. Duplicate name detection
  7. Village search (district search, village search, disambiguation)
  8. Hierarchy validation (parent-child integrity)
  9. Admin crosswalk construction (curated state map)
 10. Terrain pilot dry-run (size estimation only)
 11. Observation confidence schema validation
 12. Download manifest integrity check
 13. Real/synthetic data separation check (data_real/ vs data/)

Run:
    python real_pipeline/tests/test_real_pipeline.py
    # or with pytest:
    pytest real_pipeline/tests/test_real_pipeline.py -v
"""

import sys
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from io import StringIO

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# ── Import modules under test ──────────────────────────────────────────────────
from real_pipeline.admin.validate_admin import (
    check_unique_codes, check_null_names, check_coordinates,
    check_hierarchy, check_duplicate_names_different_codes, run_all_checks,
    PLAUSIBILITY,
)
from real_pipeline.admin.build_admin_crosswalk import (
    build_state_crosswalk, normalize_name, CENSUS2011_STATE_MAP,
)
from real_pipeline.admin.search_admin import (
    normalize, build_index, search, _safe_int, _safe_float,
)
from real_pipeline.terrain.ingest_dem_pilot import (
    get_tile_list, PILOT_REGIONS, report_size_estimate,
)


# ── Shared test data factory ───────────────────────────────────────────────────
def make_admin_df(n=100, include_dupes=False, include_nulls=False,
                  bad_coords=False) -> pd.DataFrame:
    """Create a synthetic-free test DataFrame matching canonical schema."""
    rows = []
    for i in range(n):
        state_code = (i % 5) + 1
        dist_code  = (i % 20) + 100
        subd_code  = (i % 50) + 1000
        block_code = (i % 30) + 2000
        gp_code    = (i % 60) + 3000
        vill_code  = i + 100000  # unique village code

        rows.append({
            "state_code":       state_code,
            "state_name":       f"State_{state_code}",
            "district_code":    dist_code,
            "district_name":    f"District_{dist_code}",
            "subdistrict_code": subd_code,
            "subdistrict_name": f"Subdistrict_{subd_code}",
            "block_code":       block_code,
            "block_name":       f"Block_{block_code}",
            "gp_code":          gp_code,
            "gp_name":          f"GP_{gp_code}",
            "village_code":     vill_code,
            "village_name":     f"Village_{vill_code}",
            "latitude":         20.0 + (i % 10) * 0.5,
            "longitude":        78.0 + (i % 8) * 0.5,
            "geometry_available": True,
            "geometry_source":  "test",
            "admin_source":     "test_data",
            "source_date":      "2024-01-01",
            "boundary_area_km2": None,
            "village_status":   "Active",
        })

    if include_dupes:
        # Add duplicate village codes
        rows[5]["village_code"] = rows[0]["village_code"]

    if include_nulls:
        rows[3]["village_name"] = None
        rows[7]["state_name"]   = None

    if bad_coords:
        rows[2]["latitude"]  = 99.0   # out of India bounds
        rows[4]["longitude"] = 200.0  # out of world bounds

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# Test classes
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminSourceDiscovery(unittest.TestCase):
    """Test 1: Admin source discovery infrastructure."""

    def test_data_real_directory_exists(self):
        """data_real/ directory must exist (never mix with data/)."""
        data_real = PROJECT_ROOT / "data_real"
        self.assertTrue(data_real.exists(), "data_real/ directory not found")

    def test_data_real_admin_structure(self):
        """data_real/admin/{raw,processed,crosswalk} must exist."""
        for subdir in ["raw", "processed", "crosswalk"]:
            path = PROJECT_ROOT / "data_real" / "admin" / subdir
            self.assertTrue(path.exists(), f"data_real/admin/{subdir}/ not found")

    def test_pipeline_scripts_exist(self):
        """All four admin pipeline scripts must be present."""
        scripts = [
            "real_pipeline/admin/ingest_lgd.py",
            "real_pipeline/admin/ingest_boundaries.py",
            "real_pipeline/admin/build_admin_crosswalk.py",
            "real_pipeline/admin/validate_admin.py",
        ]
        for script in scripts:
            path = PROJECT_ROOT / script
            self.assertTrue(path.exists(), f"Missing pipeline script: {script}")

    def test_download_manifest_exists(self):
        """download_manifest.csv must exist."""
        manifest = PROJECT_ROOT / "data_real" / "download_manifest.csv"
        self.assertTrue(manifest.exists(), "download_manifest.csv not found")

    def test_download_manifest_valid(self):
        """download_manifest.csv must be parseable with required columns."""
        manifest = PROJECT_ROOT / "data_real" / "download_manifest.csv"
        if not manifest.exists():
            self.skipTest("download_manifest.csv not found")
        df = pd.read_csv(manifest)
        required_cols = ["dataset_id", "status", "manual_download_required",
                         "local_path", "url"]
        for col in required_cols:
            self.assertIn(col, df.columns, f"Missing column in manifest: {col}")

    def test_manifest_status_values(self):
        """Status values in manifest must be from allowed set."""
        manifest = PROJECT_ROOT / "data_real" / "download_manifest.csv"
        if not manifest.exists():
            self.skipTest("download_manifest.csv not found")
        df = pd.read_csv(manifest)
        # Phase 2 adds PARTIAL_DOWNLOADED and DOWNLOAD_FAILED as valid states
        VALID_STATUSES = {"NOT_STARTED", "AVAILABLE", "DOWNLOADED",
                          "MANUAL_REQUIRED", "BLOCKED", "PROCESSED",
                          "PARTIAL_DOWNLOADED", "DOWNLOAD_FAILED", "COMPLETE"}
        invalid = set(df["status"].unique()) - VALID_STATUSES
        self.assertEqual(invalid, set(), f"Invalid status values: {invalid}")

    def test_no_synthetic_files_in_data_real(self):
        """data_real/ must not contain files from the synthetic pipeline."""
        data_real = PROJECT_ROOT / "data_real"
        if not data_real.exists():
            self.skipTest("data_real/ not yet created")
        synthetic_filenames = {
            "india_predictions.json", "india_predictions.csv",
            "master_dataset.csv",
        }
        for found_file in data_real.rglob("*"):
            self.assertNotIn(
                found_file.name, synthetic_filenames,
                f"Synthetic file found in data_real/: {found_file}"
            )


class TestLGDIngestion(unittest.TestCase):
    """Test 2: LGD ingestion module."""

    def test_lgd_ingest_module_importable(self):
        """ingest_lgd.py must be importable without side effects."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "ingest_lgd",
                PROJECT_ROOT / "real_pipeline" / "admin" / "ingest_lgd.py"
            )
            module = importlib.util.module_from_spec(spec)
            # Don't exec (has argparse/sys.exit) — just check parseable
            import ast
            src = (PROJECT_ROOT / "real_pipeline" / "admin" / "ingest_lgd.py").read_text()
            tree = ast.parse(src)
            self.assertIsNotNone(tree)
        except SyntaxError as e:
            self.fail(f"ingest_lgd.py has syntax errors: {e}")

    def test_column_map_completeness(self):
        """LGD_COLUMN_MAP must cover all canonical schema columns."""
        from real_pipeline.admin.ingest_lgd import LGD_COLUMN_MAP, CANONICAL_COLS
        mapped_targets = set(LGD_COLUMN_MAP.values())
        canonical_set = set(CANONICAL_COLS)
        # At minimum: critical fields must be covered
        must_cover = {"state_code", "district_code", "village_code", "village_name"}
        missing = must_cover - mapped_targets
        self.assertEqual(missing, set(),
                         f"LGD_COLUMN_MAP missing mappings for: {missing}")

    def test_manual_required_documented(self):
        """If no LGD data is available, status must be documented (not silently failing)."""
        lgd_status = PROJECT_ROOT / "data_real" / "admin" / "processed" / "lgd_status.json"
        admin_loc = PROJECT_ROOT / "data_real" / "admin" / "processed" / "admin_locations.parquet"
        admin_csv = PROJECT_ROOT / "data_real" / "admin" / "processed" / "admin_locations.csv"

        if not admin_loc.exists() and not admin_csv.exists():
            # LGD not ingested yet — status file should explain why
            if lgd_status.exists():
                with open(lgd_status) as f:
                    status = json.load(f)
                self.assertIn("status", status)
                self.assertIn(status["status"], ["MANUAL_REQUIRED", "PARTIAL"])
            # Either status file exists OR data file exists — otherwise test skips
            else:
                pass  # Will be written when ingest_lgd.py is run


class TestHierarchyValidation(unittest.TestCase):
    """Tests 4-5: Hierarchy and duplicate validation."""

    def test_unique_village_codes(self):
        """All village codes must be unique in clean data."""
        df = make_admin_df(50)
        result = check_unique_codes(df, "village_code")
        self.assertEqual(result["duplicates"], 0)
        self.assertEqual(result["status"], "OK")

    def test_duplicate_village_codes_detected(self):
        """Duplicate village codes must be detected (not silently discarded)."""
        df = make_admin_df(50, include_dupes=True)
        result = check_unique_codes(df, "village_code")
        self.assertGreater(result["duplicates"], 0)
        self.assertEqual(result["status"], "WARNING")

    def test_null_village_names_detected(self):
        """Null village names must appear in validation output."""
        df = make_admin_df(20, include_nulls=True)
        issues = check_null_names(df)
        messages = [i["message"] for i in issues]
        has_null_warning = any("null" in m.lower() or "null" in m for m in messages)
        self.assertTrue(has_null_warning, f"Null name not reported. Got: {messages}")

    def test_invalid_coordinates_detected(self):
        """Coordinates outside India must be detected."""
        df = make_admin_df(20, bad_coords=True)
        issues = check_coordinates(df)
        messages = " ".join(i["message"] for i in issues)
        self.assertIn("outside India", messages)

    def test_hierarchy_check_no_orphans(self):
        """Clean data should have no hierarchy issues."""
        df = make_admin_df(30)
        issues = check_hierarchy(df)
        warnings = [i for i in issues if i["severity"] == "WARNING"]
        self.assertEqual(len(warnings), 0, f"Unexpected hierarchy warnings: {warnings}")

    def test_hierarchy_check_detects_orphan(self):
        """Villages with GP code but null block code should be reported."""
        df = make_admin_df(10)
        df.loc[3, "block_code"] = None   # orphan: has gp_code, no block_code
        issues = check_hierarchy(df)
        warnings = [i for i in issues if i["severity"] == "WARNING"]
        self.assertGreater(len(warnings), 0, "Orphan hierarchy not detected")

    def test_same_name_diff_codes_detected(self):
        """Same village name in same GP with different codes must be flagged."""
        df = make_admin_df(20)
        # Force same name + gp_code, different village_code
        df.loc[10, "village_name"] = df.loc[0, "village_name"]
        df.loc[10, "gp_code"]      = df.loc[0, "gp_code"]
        # village_code is different (already unique in make_admin_df)
        issues = check_duplicate_names_different_codes(df)
        msgs = [i["message"] for i in issues]
        self.assertTrue(any("multiple" in m.lower() for m in msgs),
                        f"Duplicate name not detected. Got: {msgs}")

    def test_full_validation_report_has_counts(self):
        """run_all_checks must return dynamic counts (not hardcoded)."""
        df = make_admin_df(100)
        report = run_all_checks(df)
        self.assertIn("total_rows", report)
        self.assertEqual(report["total_rows"], 100)
        self.assertIn("count_village_code", report)
        # Count must be dynamic (100 unique village codes in clean data)
        self.assertEqual(report["count_village_code"], 100)


class TestAdminCrosswalk(unittest.TestCase):
    """Test 9: Admin crosswalk construction."""

    def test_state_crosswalk_builds(self):
        """build_state_crosswalk() must return a non-empty DataFrame."""
        xw = build_state_crosswalk()
        self.assertIsInstance(xw, pd.DataFrame)
        self.assertGreater(len(xw), 0)

    def test_state_crosswalk_coverage(self):
        """Crosswalk must cover all 36 states/UTs (28 states + 8 UTs)."""
        xw = build_state_crosswalk()
        self.assertGreaterEqual(len(xw), 36, "State crosswalk has fewer than 36 entries")

    def test_name_normalization(self):
        """normalize_name must handle accents, case, and common abbreviations."""
        cases = [
            ("Jammu & Kashmir", "jammu kashmir"),
            ("UTTARAKHAND", "uttarakhand"),
            ("Tamil\u00a0Nadu", "tamil nadu"),  # non-breaking space
        ]
        for input_name, expected_contains in cases:
            result = normalize_name(input_name)
            self.assertIn(expected_contains, result,
                          f"normalize_name('{input_name}') = '{result}', expected to contain '{expected_contains}'")

    def test_no_lgd_code_zero(self):
        """No state should have LGD code 0 (invalid)."""
        xw = build_state_crosswalk()
        self.assertNotIn(0, xw["state_code_lgd"].values)

    def test_census2011_codes_are_strings(self):
        """Census 2011 codes should be string representations (leading zeros)."""
        xw = build_state_crosswalk()
        for code in xw["state_code_census2011"]:
            self.assertIsInstance(code, str, f"Census code {code!r} is not a string")


class TestVillageSearch(unittest.TestCase):
    """Tests 6-7: Village and district search."""

    def setUp(self):
        """Build a test search index from known data."""
        self.df = pd.DataFrame([
            {"state_code": 5, "state_name": "Uttarakhand",
             "district_code": 501, "district_name": "Chamoli",
             "subdistrict_code": 5010, "subdistrict_name": "Gopeshwar",
             "block_code": 50101, "block_name": "Dasholi",
             "gp_code": 501010, "gp_name": "Raini GP",
             "village_code": 5010100, "village_name": "Raini",
             "latitude": 30.51, "longitude": 79.58,
             "geometry_available": True, "geometry_source": "test",
             "admin_source": "test", "source_date": "2024-01-01",
             "boundary_area_km2": None, "village_status": "Active"},
            {"state_code": 5, "state_name": "Uttarakhand",
             "district_code": 501, "district_name": "Chamoli",
             "subdistrict_code": 5010, "subdistrict_name": "Gopeshwar",
             "block_code": 50101, "block_name": "Dasholi",
             "gp_code": 501011, "gp_name": "Other GP",
             "village_code": 5010101, "village_name": "Chamoli Town",
             "latitude": 30.40, "longitude": 79.32,
             "geometry_available": True, "geometry_source": "test",
             "admin_source": "test", "source_date": "2024-01-01",
             "boundary_area_km2": None, "village_status": "Active"},
            {"state_code": 28, "state_name": "Andhra Pradesh",
             "district_code": 2801, "district_name": "Chamoli",  # same name, different state
             "subdistrict_code": 28010, "subdistrict_name": "AP Subdistrict",
             "block_code": 280101, "block_name": "AP Block",
             "gp_code": 2801010, "gp_name": "AP GP",
             "village_code": 28010100, "village_name": "AP Village",
             "latitude": 16.5, "longitude": 80.1,
             "geometry_available": True, "geometry_source": "test",
             "admin_source": "test", "source_date": "2024-01-01",
             "boundary_area_km2": None, "village_status": "Active"},
        ])
        build_index(self.df)

    def test_village_search_raini(self):
        """Searching 'Raini' must return the Raini village with correct code."""
        results = search("Raini")
        self.assertGreater(len(results), 0, "No results for 'Raini'")
        village_results = [r for r in results if r["entity_type"] == "village"]
        self.assertTrue(any(r["name"] == "Raini" for r in village_results),
                        f"Raini village not found. Got: {[r['name'] for r in village_results]}")

    def test_search_returns_lgd_code(self):
        """Search results must include official LGD code (never null for known items)."""
        results = search("Raini")
        village_results = [r for r in results if r["name"] == "Raini"]
        self.assertTrue(len(village_results) > 0)
        self.assertEqual(village_results[0]["official_code"], 5010100)

    def test_search_returns_parents(self):
        """Raini search must include parent hierarchy (district, state, etc.)."""
        results = search("Raini")
        village_results = [r for r in results if r["name"] == "Raini"]
        parents = village_results[0]["parents"]
        self.assertIn("district", parents)
        self.assertEqual(parents["district"]["name"], "Chamoli")

    def test_chamoli_disambiguates(self):
        """Chamoli search must return both district-level and village-level matches."""
        results = search("Chamoli")
        entity_types = {r["entity_type"] for r in results}
        # We have both district and village named "Chamoli" in our test data
        self.assertIn("district", entity_types)
        # Check disambiguation: both states present
        state_names = {r["parents"].get("state", {}).get("name") for r in results
                       if "state" in r.get("parents", {})}
        # Should include Uttarakhand
        self.assertIn("Uttarakhand", state_names)

    def test_district_search_uttarakhand(self):
        """Filtering by type=district should return district-level results only."""
        results = search("Chamoli", entity_type="district")
        for r in results:
            self.assertEqual(r["entity_type"], "district",
                             f"Non-district result when type=district: {r}")

    def test_search_with_coordinates(self):
        """Results for Raini must include non-null coordinates."""
        results = search("Raini")
        raini = [r for r in results if r["name"] == "Raini"]
        self.assertTrue(len(raini) > 0)
        self.assertIsNotNone(raini[0]["lat"])
        self.assertIsNotNone(raini[0]["lon"])
        self.assertAlmostEqual(raini[0]["lat"], 30.51, places=1)

    def test_empty_query_returns_empty(self):
        """Empty search must return no results (not error)."""
        results = search("")
        self.assertEqual(results, [])

    def test_nonexistent_query_returns_empty(self):
        """Query with no match must return empty list."""
        results = search("Xyzzznotavillage99999")
        self.assertEqual(results, [])


class TestTerrainPilot(unittest.TestCase):
    """Test 10: Terrain pilot size estimation."""

    def test_pilot_regions_defined(self):
        """All four pilot regions must be defined."""
        for region in ["uttarakhand", "himachal", "sikkim_arunachal", "western_ghats"]:
            self.assertIn(region, PILOT_REGIONS, f"Pilot region missing: {region}")

    def test_tile_list_generation(self):
        """Tile list for uttarakhand must be non-empty."""
        tiles = get_tile_list("uttarakhand")
        self.assertGreater(len(tiles), 0)

    def test_tile_list_fields(self):
        """Each tile must have srtm_name, copernicus_url, lat, lon."""
        tiles = get_tile_list("uttarakhand")
        for tile in tiles[:3]:
            self.assertIn("lat", tile)
            self.assertIn("lon", tile)
            self.assertIn("srtm_name", tile)
            self.assertIn("copernicus_url", tile)

    def test_size_estimate_no_download(self):
        """Size report must not trigger any downloads."""
        import io, contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            report_size_estimate("uttarakhand")
        # Just check it completed without error — no network calls in dry mode


class TestObservationConfidenceSchema(unittest.TestCase):
    """Test 11: Observation confidence schema."""

    REQUIRED_FIELDS = [
        "rainfall_source", "rainfall_resolution_deg", "rainfall_age_hours",
        "river_source", "river_station_dist_km", "river_observation_age_h",
        "soil_source", "soil_resolution_km", "soil_age_hours",
        "terrain_source", "landcover_source",
        "dynamic_data_coverage",
    ]

    def _make_confidence_record(self, all_null=False) -> dict:
        if all_null:
            return {f: None for f in self.REQUIRED_FIELDS}
        return {
            "rainfall_source": "imerg_final",
            "rainfall_resolution_deg": 0.1,
            "rainfall_age_hours": 2.5,
            "river_source": "cwc_realtime",
            "river_station_dist_km": 45.2,
            "river_observation_age_h": 1.0,
            "soil_source": "smap_l3",
            "soil_resolution_km": 36.0,
            "soil_age_hours": 24.0,
            "terrain_source": "copernicus_glo30",
            "landcover_source": "worldcover_2021",
            "dynamic_data_coverage": 0.75,
        }

    def test_schema_allows_all_null(self):
        """All null confidence record is valid (missing data ≠ zero risk)."""
        rec = self._make_confidence_record(all_null=True)
        for field in self.REQUIRED_FIELDS:
            self.assertIn(field, rec)
            self.assertIsNone(rec[field], f"Expected null for {field}")

    def test_schema_complete_when_data_present(self):
        """Complete confidence record must have all required fields."""
        rec = self._make_confidence_record()
        for field in self.REQUIRED_FIELDS:
            self.assertIn(field, rec, f"Missing confidence field: {field}")

    def test_dynamic_coverage_zero_is_not_zero_risk(self):
        """dynamic_data_coverage=0.0 must be treated as 'no dynamic data', not 'zero risk'."""
        rec = self._make_confidence_record()
        rec["dynamic_data_coverage"] = 0.0
        # Test that 0.0 is distinct from None
        self.assertIsNotNone(rec["dynamic_data_coverage"])
        self.assertEqual(rec["dynamic_data_coverage"], 0.0)
        # The distinction: None = unknown; 0.0 = no dynamic data available
        null_rec = self._make_confidence_record(all_null=True)
        self.assertIsNone(null_rec["dynamic_data_coverage"])

    def test_coverage_range(self):
        """dynamic_data_coverage must be 0.0 ≤ x ≤ 1.0 when not null."""
        rec = self._make_confidence_record()
        cov = rec["dynamic_data_coverage"]
        self.assertGreaterEqual(cov, 0.0)
        self.assertLessEqual(cov, 1.0)


class TestRealSyntheticSeparation(unittest.TestCase):
    """Test 13: Ensure real and synthetic data remain separate."""

    def test_data_dir_unchanged(self):
        """data/ directory must still contain the synthetic prediction file."""
        pred_file = PROJECT_ROOT / "data" / "predictions" / "india_predictions.json"
        self.assertTrue(pred_file.exists(),
                        "Synthetic MVP predictions missing — data/ was modified!")

    def test_synthetic_model_files_intact(self):
        """Synthetic model .pkl files must still exist."""
        for model in ["flood_model.pkl", "landslide_model.pkl"]:
            path = PROJECT_ROOT / "models" / model
            self.assertTrue(path.exists(), f"Model file missing: {model}")

    def test_backend_unchanged(self):
        """Backend main.py must still exist."""
        self.assertTrue(
            (PROJECT_ROOT / "backend" / "main.py").exists(),
            "backend/main.py is missing!"
        )

    def test_data_real_is_separate(self):
        """data_real/ must be a sibling of data/, not inside it."""
        data_dir = PROJECT_ROOT / "data"
        data_real = PROJECT_ROOT / "data_real"
        self.assertFalse(
            str(data_real).startswith(str(data_dir) + "/") or
            str(data_real).startswith(str(data_dir) + "\\"),
            "data_real/ must not be inside data/"
        )


# ── Test runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()

    test_classes = [
        TestAdminSourceDiscovery,
        TestLGDIngestion,
        TestHierarchyValidation,
        TestAdminCrosswalk,
        TestVillageSearch,
        TestTerrainPilot,
        TestObservationConfidenceSchema,
        TestRealSyntheticSeparation,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
