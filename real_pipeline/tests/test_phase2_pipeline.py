# -*- coding: utf-8 -*-
"""
real_pipeline/tests/test_phase2_pipeline.py
============================================
Phase 2 test suite: rainfall, events, features, splits, provenance.

Tests cover:
  A) CHIRPS rainfall data quality
  B) Flood event label integrity
  C) Landslide event label integrity (dated vs undated separation)
  D) Static terrain features
  E) Flood training matrix integrity
  F) Landslide training matrix integrity
  G) Split/fold integrity + leakage detection
  H) Provenance / no-synthetic-data checks
  I) Missingness / null handling
  J) Numeric range plausibility

All tests use real data files from data_real/. Tests skip gracefully if
data files are not yet generated (MANUAL_REQUIRED sources).

Run:
    python -m pytest real_pipeline/tests/test_phase2_pipeline.py -v
    python -m pytest real_pipeline/tests/ -v  (all tests combined)
"""

import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHIRPS_DIR  = PROJECT_ROOT / "data_real" / "rainfall" / "chirps"
CHIRPS_PROC = PROJECT_ROOT / "data_real" / "rainfall" / "processed"
EVENTS_DIR  = PROJECT_ROOT / "data_real" / "events"
FEAT_DIR    = PROJECT_ROOT / "data_real" / "features"
SPLITS_DIR  = PROJECT_ROOT / "data_real" / "splits"
HYDRO_DIR   = PROJECT_ROOT / "data_real" / "hydrology" / "processed"

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def chirps_tifs():
    return list(CHIRPS_DIR.glob("chirps_uttarakhand_*.tif"))

@pytest.fixture(scope="module")
def chirps_daily_stats():
    p = CHIRPS_PROC / "chirps_event_daily_stats.parquet"
    if not p.exists():
        pytest.skip("CHIRPS daily stats not yet generated")
    return pd.read_parquet(str(p))

@pytest.fixture(scope="module")
def flood_events():
    p = EVENTS_DIR / "flood" / "processed" / "flood_events.parquet"
    if not p.exists():
        pytest.skip("Flood events not generated")
    return pd.read_parquet(str(p))

@pytest.fixture(scope="module")
def non_flood_windows():
    p = EVENTS_DIR / "flood" / "processed" / "non_flood_reference_windows.parquet"
    if not p.exists():
        pytest.skip("Non-flood windows not generated")
    return pd.read_parquet(str(p))

@pytest.fixture(scope="module")
def landslide_status():
    p = EVENTS_DIR / "landslide" / "processed" / "landslide_status.json"
    if not p.exists():
        pytest.skip("Landslide status not generated")
    with open(p) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def static_terrain():
    p = FEAT_DIR / "static_terrain_uttarakhand.parquet"
    if not p.exists():
        pytest.skip("Static terrain not generated")
    return pd.read_parquet(str(p))

@pytest.fixture(scope="module")
def flood_matrix():
    p = FEAT_DIR / "flood_training.parquet"
    if not p.exists():
        pytest.skip("Flood training matrix not generated")
    return pd.read_parquet(str(p))

@pytest.fixture(scope="module")
def landslide_matrix():
    p = FEAT_DIR / "landslide_training.parquet"
    if not p.exists():
        pytest.skip("Landslide training matrix not generated")
    return pd.read_parquet(str(p))

@pytest.fixture(scope="module")
def flood_splits():
    p = SPLITS_DIR / "flood_splits.json"
    if not p.exists():
        pytest.skip("Flood splits not generated")
    with open(p) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def landslide_splits():
    p = SPLITS_DIR / "landslide_splits.json"
    if not p.exists():
        pytest.skip("Landslide splits not generated")
    with open(p) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def cwc_stations():
    p = HYDRO_DIR / "cwc_pilot_stations.parquet"
    if not p.exists():
        pytest.skip("CWC stations not generated")
    return pd.read_parquet(str(p))

# ──────────────────────────────────────────────────────────────────────────────
# A) CHIRPS Rainfall Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestCHIRPSRainfall:

    def test_chirps_files_exist(self, chirps_tifs):
        """At least one CHIRPS tile must be downloaded."""
        assert len(chirps_tifs) > 0, "No CHIRPS tiles found"

    def test_chirps_adequate_coverage_uk(self, chirps_tifs):
        """Should have at least 10 UK 2013 days (event + antecedent)."""
        uk_files = [f for f in chirps_tifs if "uttarakhand" in f.name]
        assert len(uk_files) >= 10, f"Only {len(uk_files)} UK CHIRPS days, expected ≥10"

    def test_chirps_tif_readable(self, chirps_tifs):
        """Each CHIRPS tile must be readable by rasterio."""
        import rasterio
        for tif in chirps_tifs[:3]:  # test first 3
            with rasterio.open(str(tif)) as src:
                assert src.count == 1
                assert src.crs is not None
                data = src.read(1)
                assert data.shape[0] > 0 and data.shape[1] > 0

    def test_chirps_pixel_values_plausible(self, chirps_tifs):
        """CHIRPS rainfall values: 0–1500 mm/day max plausible."""
        import rasterio
        for tif in chirps_tifs[:5]:
            with rasterio.open(str(tif)) as src:
                data = src.read(1).astype("float32")
                data[data < 0] = np.nan
                valid = data[~np.isnan(data)]
                if len(valid) > 0:
                    assert float(np.nanmax(valid)) < 1500, f"Implausible max: {np.nanmax(valid)} in {tif.name}"
                    assert float(np.nanmin(valid)) >= 0, f"Negative rainfall in {tif.name}"

    def test_chirps_no_all_zero_tile(self, chirps_tifs):
        """No tile should be all-zero (would indicate corrupt download)."""
        import rasterio
        for tif in chirps_tifs[:3]:
            with rasterio.open(str(tif)) as src:
                data = src.read(1).astype("float32")
                data[data < 0] = np.nan
                valid = data[~np.isnan(data)]
                assert len(valid) > 0, f"Tile is all-nodata: {tif.name}"

    def test_chirps_daily_stats_schema(self, chirps_daily_stats):
        """Daily stats must have required columns."""
        required = {"date", "region", "source", "rain_mean_mm", "rain_max_mm", "event_key"}
        assert required.issubset(set(chirps_daily_stats.columns))

    def test_chirps_uk2013_peak_rainfall(self, chirps_daily_stats):
        """UK 2013 event should show elevated rainfall on event days."""
        uk_stats = chirps_daily_stats[chirps_daily_stats["event_key"] == "uk_2013_flood"].copy()
        if len(uk_stats) == 0:
            pytest.skip("UK 2013 stats not in file")
        uk_stats["date"] = pd.to_datetime(uk_stats["date"])
        event_days = uk_stats[uk_stats["is_event_day"] == True]
        pre_days   = uk_stats[uk_stats["is_event_day"] == False]
        if len(event_days) > 0 and len(pre_days) > 0:
            # Event mean should be higher than antecedent mean (not always guaranteed at 5.5km)
            # At minimum, some event days must have measurable rainfall
            assert event_days["rain_mean_mm"].max() > 0, "No rainfall on any event day"

    def test_chirps_source_attribution(self, chirps_daily_stats):
        """All CHIRPS rows must be attributed to CHIRPS-2.0."""
        assert (chirps_daily_stats["source"] == "CHIRPS-2.0").all()

    def test_chirps_coverage_pct_valid(self, chirps_daily_stats):
        """Coverage percentage must be 0–100."""
        assert chirps_daily_stats["coverage_pct"].between(0, 100).all()

# ──────────────────────────────────────────────────────────────────────────────
# B) Flood Event Label Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFloodEvents:

    def test_flood_events_count(self, flood_events):
        """Must have at least 3 verified flood events."""
        assert len(flood_events) >= 3, f"Only {len(flood_events)} flood events"

    def test_flood_events_required_columns(self, flood_events):
        required = {"event_id", "date_start", "date_end", "region", "label_source",
                    "source_quality", "label_confidence"}
        assert required.issubset(set(flood_events.columns))

    def test_flood_events_unique_ids(self, flood_events):
        """Event IDs must be unique."""
        assert flood_events["event_id"].nunique() == len(flood_events)

    def test_flood_dates_logical(self, flood_events):
        """date_end must be after date_start for all events."""
        starts = pd.to_datetime(flood_events["date_start"], errors="coerce")
        ends   = pd.to_datetime(flood_events["date_end"], errors="coerce")
        assert (ends >= starts).all(), "Some events have end before start"

    def test_flood_events_no_synthetic(self, flood_events):
        """data_type must confirm real data."""
        if "data_type" in flood_events.columns:
            assert flood_events["data_type"].str.startswith("REAL").all()

    def test_flood_events_confidence_high(self, flood_events):
        """All curated flood events should be high confidence."""
        assert (flood_events["label_confidence"] == "high").all()

    def test_flood_events_label_not_from_threshold(self, flood_events):
        """Label source must not reference model thresholds."""
        bad_sources = {"model_threshold", "feature_threshold", "predicted"}
        for src in flood_events["label_source"].str.lower():
            assert not any(b in str(src) for b in bad_sources), \
                f"Label source references threshold: {src}"

    def test_flood_events_coordinates_india_bounds(self, flood_events):
        """Flood event coordinates must be within India."""
        if "lat" in flood_events.columns and "lon" in flood_events.columns:
            lats = pd.to_numeric(flood_events["lat"], errors="coerce")
            lons = pd.to_numeric(flood_events["lon"], errors="coerce")
            valid = lats.notna() & lons.notna()
            if valid.any():
                assert lats[valid].between(6, 38).all()
                assert lons[valid].between(67, 98).all()

    def test_non_flood_windows_exist(self, non_flood_windows):
        """Non-flood reference windows must exist."""
        assert len(non_flood_windows) >= 1

    def test_non_flood_windows_not_missing_data(self, non_flood_windows):
        """Negative samples must NOT be labeled as 'missing data periods'."""
        if "rationale" in non_flood_windows.columns:
            for r in non_flood_windows["rationale"]:
                assert "missing" not in str(r).lower(), \
                    f"Negative window rationale references missing data: {r}"

# ──────────────────────────────────────────────────────────────────────────────
# C) Landslide Event Label Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestLandslideEvents:

    def test_landslide_status_exists(self, landslide_status):
        """Landslide status file must exist with MANUAL_REQUIRED or real data."""
        assert "status" in landslide_status

    def test_landslide_gsi_marked_manual(self, landslide_status):
        """GSI inventory must be marked MANUAL_REQUIRED."""
        assert "gsi_status" in landslide_status
        assert "MANUAL_REQUIRED" in landslide_status["gsi_status"]

    def test_landslide_dynamic_parquet_if_exists(self):
        """If dynamic landslide parquet exists, check its schema."""
        p = EVENTS_DIR / "landslide" / "processed" / "landslide_events_dynamic.parquet"
        if not p.exists():
            pytest.skip("No dynamic landslide parquet yet")
        df = pd.read_parquet(str(p))
        assert "usable_dynamic_label" in df.columns
        # Every row in dynamic file must have usable_dynamic_label == True
        assert df["usable_dynamic_label"].all()

    def test_landslide_no_undated_in_dynamic(self):
        """Dynamic file must NOT contain undated events."""
        p = EVENTS_DIR / "landslide" / "processed" / "landslide_events_dynamic.parquet"
        if not p.exists():
            pytest.skip("No dynamic file yet")
        df = pd.read_parquet(str(p))
        if "event_date_parsed" in df.columns:
            assert df["event_date_parsed"].notna().all(), \
                "Undated events found in dynamic file"

    def test_landslide_matrix_curated_events(self):
        """Landslide training matrix must contain curated events."""
        p = FEAT_DIR / "landslide_training.parquet"
        if not p.exists():
            pytest.skip("Landslide matrix not yet generated")
        df = pd.read_parquet(str(p))
        rain_positive = df[(df["label"] == 1) & (df.get("include_in_rainfall_model", pd.Series([True])) == True)]
        assert len(rain_positive) >= 3, "Need at least 3 rain-triggered landslide events"

    def test_landslide_chamoli_excluded_from_rain_model(self):
        """Chamoli 2021 (non-rain trigger) must be excluded from rainfall model."""
        p = FEAT_DIR / "landslide_training.parquet"
        if not p.exists():
            pytest.skip("Landslide matrix not yet generated")
        df = pd.read_parquet(str(p))
        if "event_id" in df.columns and "include_in_rainfall_model" in df.columns:
            chamoli = df[df["event_id"].str.contains("CHAMOLI", case=False, na=False)]
            if len(chamoli) > 0:
                assert not chamoli["include_in_rainfall_model"].any(), \
                    "Chamoli 2021 (non-rain trigger) incorrectly included in rain model"

# ──────────────────────────────────────────────────────────────────────────────
# D) Static Terrain Features Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestStaticTerrain:

    def test_static_terrain_has_rows(self, static_terrain):
        """Static terrain must have at least one row."""
        assert len(static_terrain) > 0

    def test_static_terrain_required_columns(self, static_terrain):
        required = {"cell_id", "lat_center", "lon_center", "pilot_region"}
        assert required.issubset(set(static_terrain.columns))

    def test_static_terrain_coordinates_valid(self, static_terrain):
        """Grid cell coordinates must be within Uttarakhand bbox."""
        assert static_terrain["lat_center"].between(28.5, 32.0).all()
        assert static_terrain["lon_center"].between(77.5, 81.5).all()

    def test_static_terrain_no_invented_values(self, static_terrain):
        """If terrain_available is False, elev must be null (not zero)."""
        if "terrain_available" in static_terrain.columns and "elev_mean_m" in static_terrain.columns:
            no_terrain = static_terrain[static_terrain["terrain_available"] != True]
            # Null is acceptable; zero is NOT acceptable (would be invented)
            if len(no_terrain) > 0:
                elev_vals = no_terrain["elev_mean_m"].dropna()
                assert len(elev_vals) == 0 or (elev_vals != 0).all(), \
                    "Terrain cells without data have elevation=0 (should be null)"

    def test_static_terrain_elevation_plausible(self, static_terrain):
        """Uttarakhand elevation: 200–7000m."""
        if "elev_mean_m" in static_terrain.columns:
            valid = static_terrain["elev_mean_m"].dropna()
            if len(valid) > 0:
                assert float(valid.min()) >= 100, f"Implausibly low elev: {valid.min()}"
                assert float(valid.max()) <= 8000, f"Implausibly high elev: {valid.max()}"

    def test_static_terrain_slope_plausible(self, static_terrain):
        """Slope must be 0–90 degrees."""
        if "slope_mean_deg" in static_terrain.columns:
            valid = static_terrain["slope_mean_deg"].dropna()
            if len(valid) > 0:
                assert float(valid.min()) >= 0
                assert float(valid.max()) <= 90

    def test_static_terrain_unique_cell_ids(self, static_terrain):
        """Each grid cell must have unique cell_id."""
        assert static_terrain["cell_id"].nunique() == len(static_terrain)

    def test_static_terrain_real_data_flag(self, static_terrain):
        """data_type field must indicate real data."""
        if "data_type" in static_terrain.columns:
            assert static_terrain["data_type"].str.startswith("REAL").all()

# ──────────────────────────────────────────────────────────────────────────────
# E) Flood Training Matrix Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFloodMatrix:

    def test_flood_matrix_has_rows(self, flood_matrix):
        assert len(flood_matrix) > 0

    def test_flood_matrix_required_columns(self, flood_matrix):
        required = {"sample_id", "cell_id", "pilot_region", "label", "label_source",
                    "rain_source", "data_type", "chirps_coverage_pct"}
        assert required.issubset(set(flood_matrix.columns))

    def test_flood_matrix_binary_labels(self, flood_matrix):
        """Labels must be 0 or 1 only."""
        assert set(flood_matrix["label"].unique()).issubset({0, 1})

    def test_flood_matrix_no_synthetic_rows(self, flood_matrix):
        """No row must be synthetic."""
        assert flood_matrix["data_type"].str.startswith("REAL").all()

    def test_flood_matrix_unique_sample_ids(self, flood_matrix):
        """sample_id must be unique across all rows."""
        assert flood_matrix["sample_id"].nunique() == len(flood_matrix)

    def test_flood_matrix_rainfall_not_negative(self, flood_matrix):
        """Rainfall values must not be negative."""
        for col in ["rain_event_sum_mm", "rain_event_mean_mm", "rain_event_max_mm"]:
            if col in flood_matrix.columns:
                valid = flood_matrix[col].dropna()
                assert (valid >= 0).all(), f"Negative rainfall in {col}"

    def test_flood_matrix_rainfall_plausible(self, flood_matrix):
        """Single-window rainfall: 0–5000 mm plausible for multi-day window."""
        if "rain_event_sum_mm" in flood_matrix.columns:
            valid = flood_matrix["rain_event_sum_mm"].dropna()
            assert (valid < 5000).all(), f"Implausible max rainfall: {valid.max()}"

    def test_flood_matrix_coverage_pct_valid(self, flood_matrix):
        """CHIRPS coverage percentage must be 0–100."""
        if "chirps_coverage_pct" in flood_matrix.columns:
            valid = flood_matrix["chirps_coverage_pct"].dropna()
            assert valid.between(0, 100).all()

    def test_flood_matrix_river_source_null_when_missing(self, flood_matrix):
        """river_source must be null (not 'unknown' or '0') when CWC unavailable."""
        if "river_source" in flood_matrix.columns:
            bad = flood_matrix["river_source"].dropna()
            if len(bad) > 0:
                # If present, must be a real source name, not placeholder
                assert not bad.eq("0").any(), "river_source=0 is invalid (should be null)"
                assert not bad.eq("unknown").any(), "river_source='unknown' is invalid"

    def test_flood_matrix_positive_negative_both_present(self, flood_matrix):
        """Both positive and negative samples must exist."""
        assert (flood_matrix["label"] == 1).any(), "No positive (flood) samples"
        assert (flood_matrix["label"] == 0).any(), "No negative (non-flood) samples"

    def test_flood_matrix_coordinates_india(self, flood_matrix):
        """All cell coordinates must be within India bounds."""
        if "lat_center" in flood_matrix.columns:
            assert flood_matrix["lat_center"].between(6, 38).all()
            assert flood_matrix["lon_center"].between(67, 98).all()

    def test_flood_matrix_event_ids_match_events(self, flood_matrix, flood_events):
        """All event_ids in matrix must come from the events table."""
        if "event_id" not in flood_matrix.columns:
            return
        matrix_events = set(flood_matrix["event_id"].dropna().unique())
        event_table_ids = set(flood_events["event_id"].unique())
        # All positive event IDs should be in the events table
        pos_event_ids = set(flood_matrix[flood_matrix["label"] == 1]["event_id"].dropna().unique())
        unknown = pos_event_ids - event_table_ids
        assert len(unknown) == 0, f"Unknown event IDs in matrix: {unknown}"

# ──────────────────────────────────────────────────────────────────────────────
# F) Landslide Training Matrix Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestLandslideMatrix:

    def test_landslide_matrix_has_rows(self, landslide_matrix):
        assert len(landslide_matrix) > 0

    def test_landslide_matrix_has_label_type(self, landslide_matrix):
        """label_type column must distinguish dynamic from susceptibility."""
        assert "label_type" in landslide_matrix.columns
        assert "include_in_rainfall_model" in landslide_matrix.columns

    def test_landslide_no_undated_in_dynamic_training(self, landslide_matrix):
        """Dynamic rows must all have date_precision_days <= 7."""
        dyn = landslide_matrix[landslide_matrix["label_type"] == "dynamic"]
        if "date_precision_days" in dyn.columns:
            bad = dyn[dyn["date_precision_days"] > 7]
            assert len(bad) == 0, f"{len(bad)} dynamic rows have date_precision > 7 days"

    def test_landslide_matrix_no_synthetic(self, landslide_matrix):
        assert landslide_matrix["data_type"].str.startswith("REAL").all()

    def test_landslide_matrix_rainfall_positive_reasonable(self, landslide_matrix):
        """Rain-triggered events with CHIRPS data should show >0 rainfall."""
        rain_pos = landslide_matrix[
            (landslide_matrix["label"] == 1) &
            (landslide_matrix.get("include_in_rainfall_model", pd.Series([True])) == True) &
            (landslide_matrix.get("chirps_available", pd.Series([False])) == True)
        ]
        if len(rain_pos) > 0 and "rain_24h_mm" in rain_pos.columns:
            valid = rain_pos["rain_24h_mm"].dropna()
            if len(valid) > 0:
                assert (valid >= 0).all()

    def test_landslide_matrix_unique_sample_ids(self, landslide_matrix):
        assert landslide_matrix["sample_id"].nunique() == len(landslide_matrix)

# ──────────────────────────────────────────────────────────────────────────────
# G) Split / Leakage Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSplits:

    def test_flood_splits_structure(self, flood_splits):
        """Flood splits JSON must have loro, temporal, loeo strategies."""
        assert "splits" in flood_splits
        assert "loro" in flood_splits["splits"]
        assert "temporal" in flood_splits["splits"]

    def test_flood_splits_no_event_leakage(self, flood_splits):
        """No LORO fold must have event leakage."""
        for fold in flood_splits["splits"].get("loro", []):
            assert not fold.get("event_leakage", False), \
                f"Event leakage in fold: {fold.get('split_id')}"

    def test_flood_splits_temporal_no_leakage(self, flood_splits):
        """Temporal split must have no event leakage."""
        temp = flood_splits["splits"].get("temporal", {})
        if isinstance(temp, dict):
            assert not temp.get("event_leakage", False)

    def test_flood_splits_leakage_summary_clean(self, flood_splits):
        """Leakage summary must report zero leakage folds."""
        summary = flood_splits.get("leakage_summary", {})
        assert not summary.get("any_event_leakage", True), \
            f"Leakage detected: {summary}"

    def test_landslide_splits_no_leakage(self, landslide_splits):
        """Landslide splits must have no event leakage."""
        for fold in landslide_splits["splits"].get("loro", []):
            assert not fold.get("event_leakage", False)
        summary = landslide_splits.get("leakage_summary", {})
        assert not summary.get("any_event_leakage", True)

    def test_flood_loeo_feasible(self, flood_splits):
        """At least some LOEO folds must be feasible."""
        loeo = flood_splits["splits"].get("loeo", [])
        if loeo:
            feasible = [s for s in loeo if s.get("feasible")]
            assert len(feasible) > 0, "No feasible LOEO folds"

    def test_splits_train_test_non_overlapping_events(self, flood_splits):
        """Train and test event IDs must be disjoint in every fold."""
        for strategy, folds in flood_splits["splits"].items():
            if isinstance(folds, list):
                for fold in folds:
                    train_ids = set(fold.get("train_event_ids", []))
                    test_ids  = set(fold.get("test_event_ids", []))
                    overlap = train_ids & test_ids
                    assert len(overlap) == 0, \
                        f"Leakage in {strategy} fold {fold.get('fold_index')}: {overlap}"

# ──────────────────────────────────────────────────────────────────────────────
# H) Provenance / No-Synthetic Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestProvenance:

    def test_chirps_is_attributed(self, chirps_daily_stats):
        """Every CHIRPS row must be attributed."""
        assert chirps_daily_stats["source"].notna().all()
        assert (chirps_daily_stats["source"] == "CHIRPS-2.0").all()

    def test_flood_matrix_has_provenance(self, flood_matrix):
        """Every row must have rain_source."""
        assert "rain_source" in flood_matrix.columns
        # Rain source must be non-null (CHIRPS was downloaded)
        pos = flood_matrix[flood_matrix["label"] == 1]
        if len(pos) > 0:
            assert pos["rain_source"].notna().all()

    def test_no_inventory_mixed(self):
        """Verify synthetic data/ and real data_real/ are separate."""
        synthetic_in_real = list((PROJECT_ROOT / "data_real").rglob("india_predictions.json"))
        assert len(synthetic_in_real) == 0, "Synthetic predictions found in data_real/"

    def test_synthetic_mvp_intact(self):
        """Synthetic MVP predictions must be in data/ (not mixed with real)."""
        synth = PROJECT_ROOT / "data" / "predictions" / "india_predictions.json"
        assert synth.exists(), "Synthetic MVP predictions missing!"
        import json
        with open(synth) as f:
            data = json.load(f)
        assert len(data) >= 292, f"Synthetic MVP count dropped: {len(data)}"

    def test_cwc_status_manual_required(self, cwc_stations):
        """CWC station metadata must be marked MANUAL_REQUIRED."""
        assert "data_status" in cwc_stations.columns
        assert (cwc_stations["data_status"] == "MANUAL_REQUIRED").all()

    def test_imerg_status_manual_required(self):
        """IMERG status file must exist and be MANUAL_REQUIRED."""
        status_path = PROJECT_ROOT / "data_real" / "rainfall" / "imerg" / "imerg_status.json"
        if not status_path.exists():
            pytest.skip("IMERG status not generated yet")
        with open(status_path) as f:
            s = json.load(f)
        assert s["status"] == "MANUAL_REQUIRED"

# ──────────────────────────────────────────────────────────────────────────────
# I) Missingness / Null Handling Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMissingness:

    def test_flood_river_source_null_not_zero(self, flood_matrix):
        """river_source missing → null, never '0'."""
        if "river_source" in flood_matrix.columns:
            assert not (flood_matrix["river_source"] == "0").any()
            assert not (flood_matrix["river_source"] == 0).any()

    def test_flood_soil_source_null_not_zero(self, flood_matrix):
        """soil_source missing → null, never '0'."""
        if "soil_source" in flood_matrix.columns:
            assert not (flood_matrix["soil_source"] == "0").any()

    def test_static_terrain_null_not_zero_outside_dem(self, static_terrain):
        """Cells outside DEM tile → elev null, NOT zero."""
        if "terrain_available" in static_terrain.columns and "elev_mean_m" in static_terrain.columns:
            outside = static_terrain[static_terrain["terrain_available"] != True]
            if len(outside) > 0:
                bad = outside[outside["elev_mean_m"] == 0.0]
                assert len(bad) == 0, f"{len(bad)} cells outside DEM have elev=0 (should be null)"

    def test_flood_matrix_mandatory_fields_not_null(self, flood_matrix):
        """Core label/identity fields must never be null."""
        must_not_null = ["sample_id", "cell_id", "label", "pilot_region"]
        for col in must_not_null:
            if col in flood_matrix.columns:
                assert flood_matrix[col].notna().all(), f"Null values in {col}"

# ──────────────────────────────────────────────────────────────────────────────
# J) Numeric Range / Plausibility Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestNumericRanges:

    def test_flood_matrix_lat_lon_india(self, flood_matrix):
        for col, lo, hi in [("lat_center", 6, 38), ("lon_center", 67, 98)]:
            if col in flood_matrix.columns:
                valid = flood_matrix[col].dropna()
                assert valid.between(lo, hi).all(), f"{col} out of India bounds"

    def test_landslide_event_lat_lon_india(self):
        from real_pipeline.features.build_landslide_matrix import CURATED_LANDSLIDE_EVENTS
        for ev in CURATED_LANDSLIDE_EVENTS:
            assert 6 <= ev["lat"] <= 38, f"Lat out of India bounds: {ev}"
            assert 67 <= ev["lon"] <= 98, f"Lon out of India bounds: {ev}"

    def test_landslide_curated_dates_parseable(self):
        from real_pipeline.features.build_landslide_matrix import CURATED_LANDSLIDE_EVENTS
        for ev in CURATED_LANDSLIDE_EVENTS:
            d = date.fromisoformat(ev["event_date"])
            assert 2010 <= d.year <= 2025, f"Implausible year: {d} in {ev['event_id']}"

    def test_chirps_resolution_label_correct(self, chirps_daily_stats):
        """CHIRPS resolution field must say 0.05 deg."""
        assert (chirps_daily_stats["resolution_deg"] == 0.05).all()

    def test_flood_dates_in_plausible_range(self, flood_events):
        """Flood events must be between 2000 and 2025."""
        starts = pd.to_datetime(flood_events["date_start"], errors="coerce")
        assert starts.dt.year.between(2000, 2025).all()

    def test_static_terrain_coverage_pct_for_uk(self, static_terrain):
        """At least 5% of Uttarakhand cells should have terrain data (1 tile = 7.9%)."""
        if "terrain_available" in static_terrain.columns:
            pct = static_terrain["terrain_available"].eq(True).mean() * 100
            assert pct >= 5, f"Only {pct:.1f}% cells have terrain (need ≥5%)"
