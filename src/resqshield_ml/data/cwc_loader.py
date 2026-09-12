"""
resqshield_ml.data.cwc_loader
==============================
CWC / NWDP telemetry data loader for ResQShield (T09).

Data source
-----------
India's Central Water Commission (CWC) / National Water Data Portal (NWDP)
publishes hourly rainfall telemetry, river water-level telemetry, and
discharge telemetry.  Access to raw historical CSVs is governed by the
Hydro-Meteorological Data Dissemination Policy (2018) and requires a formal
data request.

This module provides:
  1. CWC CSV schema constants and a normalizer for the canonical column names
     used once data files are obtained.
  2. A data quality inspector that reports timestamp coverage, missing rates,
     duplicates, and whether rainfall + water-level records can be joined.
  3. A join validator that STOPS and raises CWCJoinError rather than
     producing a silent bad join.
  4. A convenience loader that combines normalise → inspect → join.

Status (as of 2026-09-12)
--------------------------
CWC/NWDP raw historical hourly CSVs are NOT freely available for download.
The portals accessible without a formal request are real-time dashboards only:
  - ffs.india-water.gov.in  (real-time water level, map view)
  - aff.india-water.gov.in  (7-day forecast table)
  - inf.cwc.gov.in          (3-day inundation map)
  - rsms.cwc.gov.in         (reservoir storage)

Formal data access procedure:
  Submit a Data Request Form + Secrecy Undertaking to the concerned
  CWC Field Chief Engineer (Hydro-Meteorological Data Dissemination
  Policy, 2018).  Contact: fmdte@nic.in.

Known CWC schema (from AFF portal metadata, ffs.india-water.gov.in)
---------------------------------------------------------------------
Rainfall / Water Level telemetry CSVs typically contain:

  Column (raw CWC)          Canonical column          Unit
  ─────────────────────     ──────────────────────    ─────────────
  Station_Code              station_code              —
  Station_Name              station_name              —
  River                     river                     —
  Basin                     basin                     —
  State                     state                     —
  District                  district                  —
  Observation_DateTime      timestamp                 IST (UTC+5:30)
  Rainfall_mm               rainfall_mm_hr            mm (per hour if hourly)
  Water_Level_m             water_level_m             m MSL
  Discharge_cumecs          discharge_cumecs          m³/s
  Warning_Level_m           warning_level_m           m MSL (station metadata)
  Danger_Level_m            danger_level_m            m MSL (station metadata)
  HFL_m                     hfl_m                     m MSL (historical max)

Column names in actual CWC CSVs may differ by region, report type, and year.
The COLUMN_MAP below is a best-effort normalizer; update it when real CSVs
are obtained.

References
----------
  CWC Flood Forecasting & Hydrological Observation page:
    https://cwc.gov.in/en/flood-forecasting-hydrological-observation
  AFF portal (tabular view of Warning / Danger levels per station):
    https://aff.india-water.gov.in/table.php
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── CWC Data Access Status ────────────────────────────────────────────────────

CWC_DATA_STATUS = (
    "CWC/NWDP raw historical hourly telemetry CSVs require a formal "
    "Data Request Form and Secrecy Undertaking under the "
    "Hydro-Meteorological Data Dissemination Policy (2018). "
    "Contact: fmdte@nic.in. "
    "No programmatic download is available without formal approval."
)


# ─── Schema Constants ──────────────────────────────────────────────────────────

# Canonical column names used throughout ResQShield
COL_STATION_CODE = "station_code"
COL_STATION_NAME = "station_name"
COL_RIVER = "river"
COL_BASIN = "basin"
COL_STATE = "state"
COL_DISTRICT = "district"
COL_TIMESTAMP = "timestamp"
COL_RAINFALL = "rainfall_mm_hr"
COL_WATER_LEVEL = "water_level_m"
COL_DISCHARGE = "discharge_cumecs"
COL_WARNING_LEVEL = "warning_level_m"
COL_DANGER_LEVEL = "danger_level_m"
COL_HFL = "hfl_m"

# Canonical minimum columns for a valid joined dataset
REQUIRED_JOINED_COLS = {COL_TIMESTAMP, COL_RAINFALL, COL_WATER_LEVEL}

# Best-effort mapping from raw CWC column names to canonical names.
# Update this dict when actual CWC CSVs are obtained and column names confirmed.
COLUMN_MAP: dict[str, str] = {
    # Rainfall files
    "Station_Code": COL_STATION_CODE,
    "Station_Name": COL_STATION_NAME,
    "Station Name": COL_STATION_NAME,
    "StationCode": COL_STATION_CODE,
    "StationName": COL_STATION_NAME,
    "STATION_CODE": COL_STATION_CODE,
    "STATION_NAME": COL_STATION_NAME,
    "River": COL_RIVER,
    "RIVER": COL_RIVER,
    "Basin": COL_BASIN,
    "BASIN": COL_BASIN,
    "State": COL_STATE,
    "STATE": COL_STATE,
    "District": COL_DISTRICT,
    "DISTRICT": COL_DISTRICT,
    "Observation_DateTime": COL_TIMESTAMP,
    "Date_Time": COL_TIMESTAMP,
    "DateTime": COL_TIMESTAMP,
    "Datetime": COL_TIMESTAMP,
    "date_time": COL_TIMESTAMP,
    "ObsDateTime": COL_TIMESTAMP,
    "OBS_DATETIME": COL_TIMESTAMP,
    "Rainfall_mm": COL_RAINFALL,
    "Rainfall_Mm": COL_RAINFALL,
    "Rainfall(mm)": COL_RAINFALL,
    "RAINFALL_MM": COL_RAINFALL,
    "rainfall_mm": COL_RAINFALL,
    # Water level files
    "Water_Level_m": COL_WATER_LEVEL,
    "Water_Level(m)": COL_WATER_LEVEL,
    "WaterLevel_m": COL_WATER_LEVEL,
    "WATER_LEVEL_M": COL_WATER_LEVEL,
    "water_level_mMSL": COL_WATER_LEVEL,
    "WL_m": COL_WATER_LEVEL,
    # Discharge files
    "Discharge_cumecs": COL_DISCHARGE,
    "Discharge(cumecs)": COL_DISCHARGE,
    "DISCHARGE_CUMECS": COL_DISCHARGE,
    "discharge_m3s": COL_DISCHARGE,
    # Threshold metadata
    "Warning_Level_m": COL_WARNING_LEVEL,
    "Warning_Level(m)": COL_WARNING_LEVEL,
    "WL_Threshold_m": COL_WARNING_LEVEL,
    "Danger_Level_m": COL_DANGER_LEVEL,
    "Danger_Level(m)": COL_DANGER_LEVEL,
    "DL_Threshold_m": COL_DANGER_LEVEL,
    "HFL_m": COL_HFL,
    "HFL(m)": COL_HFL,
    "Highest_Flood_Level_m": COL_HFL,
}


# ─── Errors ────────────────────────────────────────────────────────────────────

class CWCJoinError(Exception):
    """Raised when rainfall and water-level records cannot be defensibly joined.

    Per T09 data-first rule: if the rainfall and water-level data cannot be
    joined defensibly, STOP and report the issue rather than fabricating a join.
    """


class CWCSchemaError(Exception):
    """Raised when a CWC CSV is missing required columns after normalization."""


# ─── Schema Normalizer ─────────────────────────────────────────────────────────

def normalize_cwc_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename raw CWC CSV columns to canonical ResQShield column names.

    Applies COLUMN_MAP. Unrecognised columns are left as-is with a warning.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame as loaded from a CWC CSV.

    Returns
    -------
    pd.DataFrame
        DataFrame with renamed columns.
    """
    rename = {col: COLUMN_MAP[col] for col in df.columns if col in COLUMN_MAP}
    unrecognised = [col for col in df.columns if col not in COLUMN_MAP]

    if unrecognised:
        logger.warning(
            "Unrecognised CWC columns (not in COLUMN_MAP) — left as-is: %s",
            unrecognised,
        )

    df = df.rename(columns=rename)
    logger.debug("Normalised %d column(s): %s", len(rename), list(rename.values()))
    return df


def parse_cwc_timestamp(
    df: pd.DataFrame,
    timestamp_col: str = COL_TIMESTAMP,
    tz: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """Parse the CWC timestamp column to UTC-aware DatetimeIndex.

    CWC observations are in IST (UTC+5:30).  This function:
    1. Parses the timestamp column.
    2. Localises to IST if not already timezone-aware.
    3. Converts to UTC.
    4. Sets the result as the DataFrame index.

    Parameters
    ----------
    df : pd.DataFrame
        Normalised CWC DataFrame (timestamp column must be present).
    timestamp_col : str
        Name of the timestamp column.
    tz : str
        Source timezone string. Default 'Asia/Kolkata' (IST = UTC+5:30).

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by UTC DatetimeIndex, sorted ascending.
    """
    if timestamp_col not in df.columns:
        raise CWCSchemaError(
            f"Timestamp column '{timestamp_col}' not found after normalisation. "
            f"Available: {list(df.columns)}"
        )

    ts = pd.to_datetime(df[timestamp_col], errors="coerce")
    n_invalid = ts.isna().sum()
    if n_invalid > 0:
        logger.warning("Could not parse %d timestamp value(s) — they will be NaT.", n_invalid)

    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
    ts = ts.dt.tz_convert("UTC")

    df = df.drop(columns=[timestamp_col])
    df.index = ts
    df.index.name = "timestamp_utc"
    df = df.sort_index()

    logger.info(
        "Timestamp parsed: %d rows, %s → %s (UTC)",
        len(df),
        df.index.min(),
        df.index.max(),
    )
    return df


# ─── Data Quality Inspector ────────────────────────────────────────────────────

def inspect_cwc_dataframe(df: pd.DataFrame, name: str = "dataset") -> dict[str, Any]:
    """Inspect a CWC DataFrame and return a data quality report.

    Reports
    -------
    - Row count
    - Column names
    - Timestamp coverage (min, max, frequency, gaps)
    - Missing-value rates per column
    - Duplicate timestamp count
    - Station identifiers (unique values)
    - Unit conversion notes

    Parameters
    ----------
    df : pd.DataFrame
        Normalised, timestamp-indexed CWC DataFrame.
    name : str
        Human-readable name for logging.

    Returns
    -------
    dict
        Data quality report.
    """
    report: dict[str, Any] = {
        "name": name,
        "n_rows": len(df),
        "columns": list(df.columns),
    }

    # Timestamp coverage
    if isinstance(df.index, pd.DatetimeIndex):
        report["timestamp_min"] = str(df.index.min())
        report["timestamp_max"] = str(df.index.max())
        report["timestamp_span_days"] = (df.index.max() - df.index.min()).days
        inferred_freq = pd.infer_freq(df.index)
        report["inferred_frequency"] = inferred_freq
        n_dupes = df.index.duplicated().sum()
        report["duplicate_timestamps"] = int(n_dupes)
        if n_dupes > 0:
            logger.warning("[%s] %d duplicate timestamps detected.", name, n_dupes)
    else:
        report["timestamp_min"] = "N/A — no DatetimeIndex"
        report["timestamp_max"] = "N/A"

    # Missing value rates
    missing = {}
    for col in df.columns:
        n_missing = int(df[col].isna().sum())
        pct = round(100 * n_missing / max(len(df), 1), 2)
        missing[col] = {"n_missing": n_missing, "pct_missing": pct}
    report["missing_values"] = missing

    # Station identifiers
    if COL_STATION_CODE in df.columns:
        report["station_codes"] = df[COL_STATION_CODE].unique().tolist()
    if COL_STATION_NAME in df.columns:
        report["station_names"] = df[COL_STATION_NAME].unique().tolist()
    if COL_RIVER in df.columns:
        report["rivers"] = df[COL_RIVER].unique().tolist()
    if COL_BASIN in df.columns:
        report["basins"] = df[COL_BASIN].unique().tolist()

    # Warning / danger thresholds
    for col in [COL_WARNING_LEVEL, COL_DANGER_LEVEL, COL_HFL]:
        if col in df.columns:
            vals = df[col].dropna().unique()
            if len(vals) > 0:
                report[f"{col}_values"] = vals.tolist()

    # Unit conversion notes
    report["unit_notes"] = (
        "Rainfall column is expected as mm/hr for hourly data. "
        "If CWC provides cumulative daily rainfall in mm, divide by 24. "
        "Water level is in m MSL; no conversion required. "
        "Discharge is in cumecs (m³/s); no conversion required."
    )

    logger.info("[%s] QC report: %d rows, %d cols, %s → %s",
                name, len(df), len(df.columns),
                report.get("timestamp_min"), report.get("timestamp_max"))
    return report


# ─── Join Validator ────────────────────────────────────────────────────────────

def validate_cwc_join(
    rainfall_df: pd.DataFrame,
    waterlevel_df: pd.DataFrame,
    min_overlap_hours: int = 720,
    station_col: str = COL_STATION_CODE,
) -> None:
    """Validate that rainfall and water-level records can be defensibly joined.

    Raises CWCJoinError if:
    - Neither DataFrame has a DatetimeIndex.
    - There is insufficient temporal overlap.
    - There are no common station identifiers (when station column is present).

    Parameters
    ----------
    rainfall_df : pd.DataFrame
        Normalised rainfall DataFrame (DatetimeIndex).
    waterlevel_df : pd.DataFrame
        Normalised water-level DataFrame (DatetimeIndex).
    min_overlap_hours : int
        Minimum required overlap in hours (default 720 = ~30 days).
    station_col : str
        Column name to use for station matching.

    Raises
    ------
    CWCJoinError
        If the join is not defensible.
    """
    for name, df in [("rainfall", rainfall_df), ("water_level", waterlevel_df)]:
        if not isinstance(df.index, pd.DatetimeIndex):
            raise CWCJoinError(
                f"Cannot join: {name} DataFrame does not have a DatetimeIndex. "
                "Call parse_cwc_timestamp() first."
            )

    overlap_start = max(rainfall_df.index.min(), waterlevel_df.index.min())
    overlap_end = min(rainfall_df.index.max(), waterlevel_df.index.max())

    if overlap_start >= overlap_end:
        raise CWCJoinError(
            f"Cannot join: no temporal overlap between rainfall "
            f"({rainfall_df.index.min()} → {rainfall_df.index.max()}) "
            f"and water level "
            f"({waterlevel_df.index.min()} → {waterlevel_df.index.max()})."
        )

    overlap_hours = (overlap_end - overlap_start).total_seconds() / 3600
    if overlap_hours < min_overlap_hours:
        raise CWCJoinError(
            f"Cannot join: temporal overlap is only {overlap_hours:.0f} hours, "
            f"which is less than the required {min_overlap_hours} hours. "
            "Select a longer date range or a different station."
        )

    # Station matching (if station column present in both)
    if (
        station_col in rainfall_df.columns
        and station_col in waterlevel_df.columns
    ):
        rain_stations = set(rainfall_df[station_col].dropna().unique())
        wl_stations = set(waterlevel_df[station_col].dropna().unique())
        common = rain_stations & wl_stations
        if not common:
            raise CWCJoinError(
                f"Cannot join: no common station codes between rainfall "
                f"{sorted(rain_stations)} and water level {sorted(wl_stations)}."
            )
        logger.info("Common stations for join: %s", sorted(common))
    else:
        logger.warning(
            "Station column '%s' not found in one or both DataFrames. "
            "Join will be by timestamp only — ensure files are from the same station.",
            station_col,
        )

    logger.info(
        "Join validated: %.0f-hour overlap (%s → %s).",
        overlap_hours, overlap_start, overlap_end,
    )


# ─── Full Load + Join Pipeline ─────────────────────────────────────────────────

def load_cwc_rainfall(path: str | Path) -> pd.DataFrame:
    """Load, normalize, and timestamp-parse a CWC rainfall telemetry CSV.

    Parameters
    ----------
    path : str or Path
        Path to the CWC rainfall CSV file.

    Returns
    -------
    pd.DataFrame
        Normalised, UTC-indexed DataFrame with at least `rainfall_mm_hr`.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    CWCSchemaError
        If `rainfall_mm_hr` is missing after normalisation.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"CWC rainfall file not found: {path}\n{CWC_DATA_STATUS}"
        )
    logger.info("Loading CWC rainfall file: %s", path)
    df = pd.read_csv(path)
    df = normalize_cwc_columns(df)
    df = parse_cwc_timestamp(df)

    if COL_RAINFALL not in df.columns:
        raise CWCSchemaError(
            f"No rainfall column found after normalisation. "
            f"Available: {list(df.columns)}. "
            f"Update COLUMN_MAP for this file's column names."
        )
    # Coerce to numeric
    df[COL_RAINFALL] = pd.to_numeric(df[COL_RAINFALL], errors="coerce")
    return df


def load_cwc_waterlevel(path: str | Path) -> pd.DataFrame:
    """Load, normalize, and timestamp-parse a CWC water-level telemetry CSV.

    Parameters
    ----------
    path : str or Path
        Path to the CWC water-level CSV file.

    Returns
    -------
    pd.DataFrame
        Normalised, UTC-indexed DataFrame with at least `water_level_m`.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    CWCSchemaError
        If `water_level_m` is missing after normalisation.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"CWC water-level file not found: {path}\n{CWC_DATA_STATUS}"
        )
    logger.info("Loading CWC water-level file: %s", path)
    df = pd.read_csv(path)
    df = normalize_cwc_columns(df)
    df = parse_cwc_timestamp(df)

    if COL_WATER_LEVEL not in df.columns:
        raise CWCSchemaError(
            f"No water level column found after normalisation. "
            f"Available: {list(df.columns)}. "
            f"Update COLUMN_MAP for this file's column names."
        )
    df[COL_WATER_LEVEL] = pd.to_numeric(df[COL_WATER_LEVEL], errors="coerce")
    return df


def join_cwc_data(
    rainfall_df: pd.DataFrame,
    waterlevel_df: pd.DataFrame,
    resample_freq: str = "1h",
    min_overlap_hours: int = 720,
    station_filter: str | None = None,
) -> pd.DataFrame:
    """Join CWC rainfall and water-level DataFrames into a single aligned dataset.

    Steps
    -----
    1. Validate join defensibility (calls validate_cwc_join).
    2. Optionally filter to a single station.
    3. Resample both to a common frequency (default hourly).
    4. Outer-join on timestamp index.
    5. Drop rows with NaN in both rainfall and water level.
    6. Log data quality summary.

    Parameters
    ----------
    rainfall_df : pd.DataFrame
        UTC-indexed rainfall DataFrame (from load_cwc_rainfall).
    waterlevel_df : pd.DataFrame
        UTC-indexed water-level DataFrame (from load_cwc_waterlevel).
    resample_freq : str
        Pandas resample frequency (default '1h').
    min_overlap_hours : int
        Minimum required overlap hours.
    station_filter : str, optional
        If provided and a station_code column exists, filter to this station
        before joining.

    Returns
    -------
    pd.DataFrame
        Joined, resampled dataset with at least `rainfall_mm_hr` and
        `water_level_m` columns, indexed by UTC timestamp.

    Raises
    ------
    CWCJoinError
        If the join is not defensible.
    """
    # Station filter
    for name, df in [("rainfall", rainfall_df), ("water_level", waterlevel_df)]:
        if (
            station_filter is not None
            and COL_STATION_CODE in df.columns
        ):
            df = df[df[COL_STATION_CODE] == station_filter]
            if df.empty:
                raise CWCJoinError(
                    f"Station filter '{station_filter}' produced empty {name} DataFrame."
                )

    validate_cwc_join(rainfall_df, waterlevel_df, min_overlap_hours=min_overlap_hours)

    # Keep only numeric + station metadata columns before resampling
    rain_num = rainfall_df.select_dtypes(include=[np.number])
    wl_num = waterlevel_df.select_dtypes(include=[np.number])

    # Resample to common frequency
    rain_res = rain_num.resample(resample_freq).mean()
    wl_res = wl_num.resample(resample_freq).mean()

    # Outer join
    joined = rain_res.join(wl_res, how="outer", rsuffix="_wl")

    # Drop rows missing both rainfall and water level (uninformative)
    has_rain = joined[COL_RAINFALL].notna() if COL_RAINFALL in joined.columns else pd.Series(False, index=joined.index)
    has_wl = joined[COL_WATER_LEVEL].notna() if COL_WATER_LEVEL in joined.columns else pd.Series(False, index=joined.index)
    before = len(joined)
    joined = joined[has_rain | has_wl]
    dropped = before - len(joined)
    if dropped > 0:
        logger.info("Dropped %d rows missing both rainfall and water level.", dropped)

    missing_rain = joined[COL_RAINFALL].isna().sum() if COL_RAINFALL in joined.columns else len(joined)
    missing_wl = joined[COL_WATER_LEVEL].isna().sum() if COL_WATER_LEVEL in joined.columns else len(joined)
    logger.info(
        "Joined dataset: %d rows. Missing: rainfall=%d (%.1f%%), water_level=%d (%.1f%%)",
        len(joined),
        missing_rain, 100 * missing_rain / max(len(joined), 1),
        missing_wl, 100 * missing_wl / max(len(joined), 1),
    )
    return joined
