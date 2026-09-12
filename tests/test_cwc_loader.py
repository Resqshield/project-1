"""
Tests for resqshield_ml.data.cwc_loader (T09).

CWC/NWDP telemetry schema normalizer and data loader.
"""

import io
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from resqshield_ml.data.cwc_loader import (
    COL_RAINFALL,
    COL_STATION_CODE,
    COL_STATION_NAME,
    COL_WATER_LEVEL,
    COL_WARNING_LEVEL,
    COL_DANGER_LEVEL,
    COLUMN_MAP,
    CWCJoinError,
    CWCSchemaError,
    inspect_cwc_dataframe,
    join_cwc_data,
    normalize_cwc_columns,
    parse_cwc_timestamp,
    validate_cwc_join,
)


# ══════════════════════════════════════════════════════════════════════════════
# SYNTHETIC TEST FIXTURES — NOT REAL CWC DATA
#
# The data used in these tests is entirely synthetic.
# It does NOT represent real measurements from any CWC station.
# These fixtures exist only to test schema normalization, timestamp parsing,
# and join validation logic.
#
# Real CWC/NWDP data is subject to the Hydro-Meteorological Data
# Dissemination Policy (2018) and requires a formal data request.
# ══════════════════════════════════════════════════════════════════════════════

def _make_synthetic_rainfall_df(
    n_hours: int = 48,
    station_code: str = "TEST_STATION",
    start: str = "2023-06-01 00:00",
) -> pd.DataFrame:
    """Synthetic hourly rainfall DataFrame with raw CWC column names.

    NOTE: SYNTHETIC TEST DATA — NOT REAL CWC TELEMETRY.
    """
    idx = pd.date_range(start=start, periods=n_hours, freq="1h")
    return pd.DataFrame({
        "Station_Code": [station_code] * n_hours,
        "Station_Name": ["Synthetic Test Station"] * n_hours,
        "River": ["Test River"] * n_hours,
        "Basin": ["Test Basin"] * n_hours,
        "State": ["Test State"] * n_hours,
        "Observation_DateTime": idx.strftime("%Y-%m-%d %H:%M:%S"),
        "Rainfall_mm": [float(i % 10) for i in range(n_hours)],
    })


def _make_synthetic_waterlevel_df(
    n_hours: int = 48,
    station_code: str = "TEST_STATION",
    start: str = "2023-06-01 00:00",
) -> pd.DataFrame:
    """Synthetic hourly water-level DataFrame with raw CWC column names.

    NOTE: SYNTHETIC TEST DATA — NOT REAL CWC TELEMETRY.
    """
    idx = pd.date_range(start=start, periods=n_hours, freq="1h")
    return pd.DataFrame({
        "Station_Code": [station_code] * n_hours,
        "Observation_DateTime": idx.strftime("%Y-%m-%d %H:%M:%S"),
        "Water_Level_m": [3.0 + 0.1 * (i % 20) for i in range(n_hours)],
        "Warning_Level_m": [5.0] * n_hours,
        "Danger_Level_m": [7.0] * n_hours,
    })


def _to_utc_indexed(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize + parse to UTC DatetimeIndex."""
    df = normalize_cwc_columns(raw_df)
    df = parse_cwc_timestamp(df)
    return df


# ─── COLUMN_MAP Coverage ──────────────────────────────────────────────────────

class TestColumnMap:
    """Verify COLUMN_MAP correctness."""

    def test_all_values_are_canonical(self):
        """All map values should be non-empty strings."""
        for raw, canonical in COLUMN_MAP.items():
            assert isinstance(canonical, str)
            assert len(canonical) > 0

    def test_rainfall_column_mapped(self):
        """'Rainfall_mm' should map to canonical rainfall column."""
        assert COLUMN_MAP.get("Rainfall_mm") == COL_RAINFALL

    def test_waterlevel_column_mapped(self):
        assert COLUMN_MAP.get("Water_Level_m") == COL_WATER_LEVEL

    def test_station_code_mapped(self):
        assert COLUMN_MAP.get("Station_Code") == COL_STATION_CODE

    def test_warning_level_mapped(self):
        assert COLUMN_MAP.get("Warning_Level_m") == COL_WARNING_LEVEL

    def test_danger_level_mapped(self):
        assert COLUMN_MAP.get("Danger_Level_m") == COL_DANGER_LEVEL


# ─── Column Normalization ─────────────────────────────────────────────────────

class TestNormalizeCwcColumns:
    """Test column name normalization."""

    def test_renames_known_columns(self):
        raw = _make_synthetic_rainfall_df(n_hours=5)
        normed = normalize_cwc_columns(raw)
        assert COL_RAINFALL in normed.columns
        assert COL_STATION_CODE in normed.columns
        assert "Rainfall_mm" not in normed.columns

    def test_unknown_columns_preserved(self):
        raw = pd.DataFrame({"Rainfall_mm": [1.0], "UnknownCol": [99]})
        normed = normalize_cwc_columns(raw)
        assert "UnknownCol" in normed.columns
        assert COL_RAINFALL in normed.columns

    def test_empty_dataframe(self):
        normed = normalize_cwc_columns(pd.DataFrame())
        assert list(normed.columns) == []


# ─── Timestamp Parsing ────────────────────────────────────────────────────────

class TestParseCwcTimestamp:
    """Test IST→UTC timestamp parsing and index setting."""

    def test_datetime_index_is_utc(self):
        raw = _make_synthetic_rainfall_df(n_hours=10)
        df = normalize_cwc_columns(raw)
        df = parse_cwc_timestamp(df)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert str(df.index.tz) == "UTC"

    def test_chronologically_sorted(self):
        raw = _make_synthetic_rainfall_df(n_hours=24)
        df = normalize_cwc_columns(raw)
        df = parse_cwc_timestamp(df)
        assert df.index.is_monotonic_increasing

    def test_ist_offset(self):
        """IST is UTC+5:30; midnight IST → 18:30 previous day UTC."""
        raw = pd.DataFrame({
            "Observation_DateTime": ["2023-06-01 00:00:00"],
            "Rainfall_mm": [0.0],
        })
        df = normalize_cwc_columns(raw)
        df = parse_cwc_timestamp(df)
        assert df.index[0].hour == 18
        assert df.index[0].minute == 30

    def test_missing_timestamp_col_raises(self):
        df = pd.DataFrame({"Rainfall_mm": [1.0]})
        with pytest.raises(CWCSchemaError, match="Timestamp column"):
            parse_cwc_timestamp(df)


# ─── Data Quality Inspector ───────────────────────────────────────────────────

class TestInspectCwcDataframe:
    """Test QC report generation."""

    def _get_indexed_df(self):
        raw = _make_synthetic_rainfall_df(n_hours=48)
        return _to_utc_indexed(raw)

    def test_report_has_expected_keys(self):
        df = self._get_indexed_df()
        report = inspect_cwc_dataframe(df, name="test_rain")
        for key in ["name", "n_rows", "columns", "timestamp_min",
                    "timestamp_max", "missing_values"]:
            assert key in report

    def test_n_rows_correct(self):
        df = self._get_indexed_df()
        report = inspect_cwc_dataframe(df)
        assert report["n_rows"] == 48

    def test_missing_values_report(self):
        df = self._get_indexed_df()
        df.iloc[0, df.columns.get_loc(COL_RAINFALL)] = float("nan")
        report = inspect_cwc_dataframe(df)
        assert report["missing_values"][COL_RAINFALL]["n_missing"] == 1

    def test_no_duplicates_in_synthetic(self):
        df = self._get_indexed_df()
        report = inspect_cwc_dataframe(df)
        assert report["duplicate_timestamps"] == 0

    def test_station_codes_reported(self):
        df = self._get_indexed_df()
        report = inspect_cwc_dataframe(df)
        assert "station_codes" in report
        assert "TEST_STATION" in report["station_codes"]


# ─── Join Validation ──────────────────────────────────────────────────────────

class TestValidateCwcJoin:
    """Test defensible-join validation."""

    def test_valid_join_passes(self):
        rain_df = _to_utc_indexed(_make_synthetic_rainfall_df(n_hours=1000))
        wl_df = _to_utc_indexed(_make_synthetic_waterlevel_df(n_hours=1000))
        # Should not raise
        validate_cwc_join(rain_df, wl_df, min_overlap_hours=720)

    def test_no_overlap_raises(self):
        rain_df = _to_utc_indexed(
            _make_synthetic_rainfall_df(n_hours=48, start="2023-01-01")
        )
        wl_df = _to_utc_indexed(
            _make_synthetic_waterlevel_df(n_hours=48, start="2024-06-01")
        )
        with pytest.raises(CWCJoinError, match="overlap"):
            validate_cwc_join(rain_df, wl_df, min_overlap_hours=720)

    def test_insufficient_overlap_raises(self):
        rain_df = _to_utc_indexed(
            _make_synthetic_rainfall_df(n_hours=48, start="2023-06-01")
        )
        wl_df = _to_utc_indexed(
            _make_synthetic_waterlevel_df(n_hours=48, start="2023-06-01")
        )
        # 48h overlap < 720h minimum
        with pytest.raises(CWCJoinError, match="overlap"):
            validate_cwc_join(rain_df, wl_df, min_overlap_hours=720)

    def test_no_common_stations_raises(self):
        rain_df = _to_utc_indexed(
            _make_synthetic_rainfall_df(
                n_hours=1000, station_code="STATION_A", start="2023-01-01"
            )
        )
        wl_df = _to_utc_indexed(
            _make_synthetic_waterlevel_df(
                n_hours=1000, station_code="STATION_B", start="2023-01-01"
            )
        )
        with pytest.raises(CWCJoinError, match="station"):
            validate_cwc_join(rain_df, wl_df, min_overlap_hours=720)

    def test_non_datetime_index_raises(self):
        rain_df = pd.DataFrame({"rainfall_mm_hr": [1.0, 2.0]})
        wl_df = _to_utc_indexed(_make_synthetic_waterlevel_df(n_hours=100))
        with pytest.raises(CWCJoinError, match="DatetimeIndex"):
            validate_cwc_join(rain_df, wl_df)


# ─── Join Pipeline ────────────────────────────────────────────────────────────

class TestJoinCwcData:
    """Test the full join pipeline with synthetic fixtures."""

    def _rain_wl_dfs(self, n_hours: int = 1000):
        rain_raw = _make_synthetic_rainfall_df(n_hours=n_hours)
        wl_raw = _make_synthetic_waterlevel_df(n_hours=n_hours)
        rain_df = _to_utc_indexed(rain_raw)
        wl_df = _to_utc_indexed(wl_raw)
        return rain_df, wl_df

    def test_joined_has_both_columns(self):
        rain_df, wl_df = self._rain_wl_dfs()
        joined = join_cwc_data(rain_df, wl_df, min_overlap_hours=720)
        assert COL_RAINFALL in joined.columns
        assert COL_WATER_LEVEL in joined.columns

    def test_joined_index_is_datetime(self):
        rain_df, wl_df = self._rain_wl_dfs()
        joined = join_cwc_data(rain_df, wl_df, min_overlap_hours=720)
        assert isinstance(joined.index, pd.DatetimeIndex)

    def test_joined_is_sorted(self):
        rain_df, wl_df = self._rain_wl_dfs()
        joined = join_cwc_data(rain_df, wl_df, min_overlap_hours=720)
        assert joined.index.is_monotonic_increasing

    def test_join_fails_on_insufficient_overlap(self):
        rain_df = _to_utc_indexed(_make_synthetic_rainfall_df(n_hours=24))
        wl_df = _to_utc_indexed(_make_synthetic_waterlevel_df(n_hours=24))
        with pytest.raises(CWCJoinError):
            join_cwc_data(rain_df, wl_df, min_overlap_hours=720)


# ─── File Not Found ───────────────────────────────────────────────────────────

class TestFileNotFound:
    """Verify helpful errors when CWC files are absent."""

    def test_load_rainfall_missing_raises(self, tmp_path):
        from resqshield_ml.data.cwc_loader import load_cwc_rainfall
        with pytest.raises(FileNotFoundError, match="CWC rainfall"):
            load_cwc_rainfall(tmp_path / "nonexistent_rainfall.csv")

    def test_load_waterlevel_missing_raises(self, tmp_path):
        from resqshield_ml.data.cwc_loader import load_cwc_waterlevel
        with pytest.raises(FileNotFoundError, match="CWC water-level"):
            load_cwc_waterlevel(tmp_path / "nonexistent_wl.csv")
