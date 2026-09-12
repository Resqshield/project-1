"""
resqshield_ml.features.engineer
================================
Feature engineering for the ResQShield flood early warning pipeline.

Algorithmic approach adapted from (MIT License):
    ECMWFCode4Earth/ml_flood :: python/misc/utils_floodmodel.py
    Functions: shift_and_aggregate(), add_shifted_variables()
    Authors: @lkugler, @seblehner — ESoWC 2019, MATEHIW Project

Key differences from the upstream implementation:
- Upstream works on xarray DataArrays (NetCDF grid data)
- This module works on pandas DataFrames (tabular sensor streams)
- Basin-specific spatial aggregation is replaced by station-level aggregation
- Adds ResQShield-specific features: rate-of-rise, antecedent precipitation index
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Core Temporal Feature Engineering ────────────────────────────────────────
# Adapted from ml_flood::utils_floodmodel.py::add_shifted_variables()
# and shift_and_aggregate() — reimplemented for pandas DataFrame

def add_lag_features(
    df: pd.DataFrame,
    columns: list[str],
    lag_steps: list[int],
) -> pd.DataFrame:
    """Add lagged (shifted) copies of specified columns.

    This is the pandas-DataFrame equivalent of ml_flood's
    `add_shifted_variables(ds, shifts, variables)` which operated on
    xarray Datasets.

    Naming convention: `{column}_lag_{N}` where N is the lag in timesteps.
    For hourly data, lag=3 means the value 3 hours ago.

    Adapted from:
        ECMWFCode4Earth/ml_flood :: utils_floodmodel.py (MIT License)
        Original: ds[var].shift(time=i) on xarray Dataset

    Parameters
    ----------
    df : pd.DataFrame
        Time-indexed sensor data.
    columns : list of str
        Columns to create lag features for.
    lag_steps : list of int
        Lag values in timesteps (e.g. [1, 2, 3, 6, 12, 24]).

    Returns
    -------
    pd.DataFrame
        Original DataFrame with lag columns appended.
    """
    df = df.copy()
    existing_cols = set(df.columns)
    added = []

    for col in columns:
        if col not in df.columns:
            logger.warning("Column '%s' not found — skipping lag features.", col)
            continue
        for lag in lag_steps:
            if lag == 0:
                continue  # zero-lag is the original column itself
            new_col = f"{col}_lag_{lag}"
            if new_col not in existing_cols:
                df[new_col] = df[col].shift(lag)
                added.append(new_col)

    logger.debug("Added %d lag feature columns.", len(added))
    return df


def add_rolling_features(
    df: pd.DataFrame,
    columns: list[str],
    window_steps: list[int],
    func: str = "sum",
) -> pd.DataFrame:
    """Add rolling window aggregation features.

    This is the pandas equivalent of ml_flood's `shift_and_aggregate()`
    which computed rolling sums/means on xarray time coordinates.

    Naming convention: `{column}_rolling_{func}_{N}`
    Example: `rainfall_mm_hr_rolling_sum_6` = cumulative rainfall past 6 hours.

    Adapted from:
        ECMWFCode4Earth/ml_flood :: utils_floodmodel.py (MIT License)
        Original: df.shift(time=shift).rolling(time=aggregate).sum()

    Parameters
    ----------
    df : pd.DataFrame
        Time-indexed sensor data.
    columns : list of str
        Columns to aggregate.
    window_steps : list of int
        Window sizes in timesteps.
    func : str
        Aggregation function: 'sum', 'mean', 'max', 'min'.

    Returns
    -------
    pd.DataFrame
        Original DataFrame with rolling feature columns appended.
    """
    valid_funcs = {"sum", "mean", "max", "min"}
    if func not in valid_funcs:
        raise ValueError(f"Invalid aggregation function '{func}'. Choose from {valid_funcs}.")

    df = df.copy()
    added = []

    for col in columns:
        if col not in df.columns:
            logger.warning("Column '%s' not found — skipping rolling features.", col)
            continue
        roller = df[col].rolling(window=max(window_steps), min_periods=1)
        # We compute per window individually for correct naming
        for window in window_steps:
            new_col = f"{col}_rolling_{func}_{window}"
            if new_col not in df.columns:
                rolled = df[col].rolling(window=window, min_periods=1)
                df[new_col] = getattr(rolled, func)()
                added.append(new_col)

    logger.debug("Added %d rolling feature columns (func=%s).", len(added), func)
    return df


# ─── ResQShield-Specific Features ─────────────────────────────────────────────
# Not in ml_flood — added for real-time early warning requirements

def add_rate_of_rise(
    df: pd.DataFrame,
    level_col: str = "water_level_m",
    delta_windows: list[int] | None = None,
) -> pd.DataFrame:
    """Add water-level rate-of-rise features.

    The rate of water-level rise (dH/dt) is one of the most important
    indicators for flash flood early warning. A rapid rise (even from a
    low absolute level) signals imminent danger.

    Parameters
    ----------
    df : pd.DataFrame
        Time-indexed sensor data.
    level_col : str
        Column containing water level readings.
    delta_windows : list of int, optional
        Window sizes for delta computation. Default [1, 3, 6].
        delta_window=3 means: current_level - level_3_steps_ago

    Returns
    -------
    pd.DataFrame
        Original DataFrame with rate-of-rise columns appended.
    """
    if delta_windows is None:
        delta_windows = [1, 3, 6]

    df = df.copy()
    if level_col not in df.columns:
        logger.warning("Level column '%s' not found — skipping rate-of-rise.", level_col)
        return df

    for window in delta_windows:
        col_name = f"{level_col}_delta_{window}"
        df[col_name] = df[level_col] - df[level_col].shift(window)

    logger.debug("Added rate-of-rise features for '%s': windows=%s", level_col, delta_windows)
    return df


def add_antecedent_precipitation_index(
    df: pd.DataFrame,
    rainfall_col: str = "rainfall_mm_hr",
    decay_factor: float = 0.9,
    new_col: str = "antecedent_precipitation_index",
) -> pd.DataFrame:
    """Add the Antecedent Precipitation Index (API).

    API is a soil moisture proxy computed as an exponentially weighted
    moving sum of past rainfall. It captures long-term soil saturation
    which determines how much additional rainfall is needed to trigger
    surface runoff or flooding.

    API(t) = decay_factor * API(t-1) + rainfall(t)

    Parameters
    ----------
    df : pd.DataFrame
        Time-indexed sensor data.
    rainfall_col : str
        Column containing rainfall readings.
    decay_factor : float
        Daily decay factor (0 < k < 1). Typical values: 0.85–0.95.
        Higher k = slower soil drainage (clay soils).
    new_col : str
        Name for the new API column.

    Returns
    -------
    pd.DataFrame
        DataFrame with API column appended.
    """
    df = df.copy()
    if rainfall_col not in df.columns:
        logger.warning("Rainfall column '%s' not found — skipping API.", rainfall_col)
        return df

    rainfall = df[rainfall_col].values
    api = np.zeros(len(rainfall))
    api[0] = rainfall[0]
    for t in range(1, len(rainfall)):
        api[t] = decay_factor * api[t - 1] + rainfall[t]

    df[new_col] = api
    logger.debug("Added Antecedent Precipitation Index (decay=%.2f).", decay_factor)
    return df


# ─── Full Feature Engineering Pipeline ────────────────────────────────────────

def build_features(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Run the complete ResQShield feature engineering pipeline.

    This is the single entry point for feature engineering.
    All parameters are read from the experiment config.

    Steps (in order):
    1. Add lag features for sensor columns
    2. Add rolling sum features for rainfall
    3. Add water-level rate-of-rise
    4. Add antecedent precipitation index
    5. Drop columns listed in config

    Parameters
    ----------
    df : pd.DataFrame
        Raw (or resampled) sensor DataFrame from data.loader.
    cfg : dict
        Full experiment config from configs/resqshield_default.yaml.

    Returns
    -------
    pd.DataFrame
        Feature-engineered DataFrame ready for model training.
        Note: rows with NaN from lag warmup are NOT dropped here —
        that is handled by data.loader.extract_Xy().
    """
    feat_cfg = cfg.get("features", {})

    # Step 1: Lag features
    lag_hours = feat_cfg.get("lag_hours", [1, 3, 6, 12, 24])
    dynamic_cols = feat_cfg.get("dynamic_sensor_cols", [])
    available_cols = [c for c in dynamic_cols if c in df.columns]

    if available_cols:
        logger.info("Building lag features for: %s (lags: %s)", available_cols, lag_hours)
        df = add_lag_features(df, columns=available_cols, lag_steps=lag_hours)
    else:
        logger.warning("No dynamic sensor columns found in DataFrame. Skipping lag features.")

    # Step 2: Rolling sum features for rainfall
    rolling_windows = feat_cfg.get("rolling_sum_windows", [3, 6, 12, 24])
    rainfall_cols = [c for c in ["rainfall_mm_hr", "upstream_rainfall_mm_hr"] if c in df.columns]
    if rainfall_cols:
        logger.info("Building rolling sum features for: %s", rainfall_cols)
        df = add_rolling_features(df, columns=rainfall_cols, window_steps=rolling_windows, func="sum")

    # Step 3: Rate-of-rise features
    target_col = cfg.get("data", {}).get("target_col", "water_level_m")
    delta_cfg = feat_cfg.get("delta_features", [])
    for delta_spec in delta_cfg:
        col = delta_spec.get("col", target_col)
        windows = delta_spec.get("windows", [1, 3, 6])
        if col in df.columns:
            logger.info("Building rate-of-rise for '%s', windows=%s", col, windows)
            df = add_rate_of_rise(df, level_col=col, delta_windows=windows)

    # Step 4: Antecedent Precipitation Index
    if "rainfall_mm_hr" in df.columns:
        logger.info("Computing Antecedent Precipitation Index.")
        df = add_antecedent_precipitation_index(df, rainfall_col="rainfall_mm_hr")

    # Step 5: Drop metadata columns
    drop_cols = feat_cfg.get("drop_cols", [])
    to_drop = [c for c in drop_cols if c in df.columns]
    if to_drop:
        df = df.drop(columns=to_drop)
        logger.info("Dropped metadata columns: %s", to_drop)

    logger.info(
        "Feature engineering complete: %d columns total (%d rows).",
        len(df.columns), len(df)
    )
    return df
