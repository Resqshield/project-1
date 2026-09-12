"""
resqshield_ml.data.loader
==========================
Sensor data loader for the ResQShield pipeline.

This module replaces the ERA5/NetCDF/GloFAS data loader from
ECMWFCode4Earth/ml_flood with a ResQShield-specific loader
that reads time-series sensor data from CSV files.

Design decisions vs. ml_flood:
- ml_flood uses xarray DataArrays loaded from NetCDF
- ResQShield uses pandas DataFrames loaded from CSV (sensor streams)
- Chronological train/val/test split is preserved from ml_flood's approach
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Schema Validation ────────────────────────────────────────────────────────

REQUIRED_COLUMNS = {"timestamp", "water_level_m", "rainfall_mm_hr"}


def validate_schema(df: pd.DataFrame, required_cols: set[str] | None = None) -> None:
    """Check that the loaded DataFrame has the expected columns.

    Parameters
    ----------
    df : pd.DataFrame
        The loaded sensor DataFrame.
    required_cols : set of str, optional
        Columns that must be present. Defaults to REQUIRED_COLUMNS.

    Raises
    ------
    ValueError
        If any required column is missing.
    """
    if required_cols is None:
        required_cols = REQUIRED_COLUMNS

    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in sensor data: {sorted(missing)}\n"
            f"Available columns: {sorted(df.columns)}"
        )


# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_sensor_csv(
    path: str | Path,
    timestamp_col: str = "timestamp",
    drop_cols: list[str] | None = None,
    resample_freq: str | None = None,
) -> pd.DataFrame:
    """Load raw sensor data from a CSV file.

    Expected CSV format (minimum):
        timestamp,water_level_m,rainfall_mm_hr,...
        2024-01-01 00:00:00,1.23,0.5,...

    Parameters
    ----------
    path : str or Path
        Path to the CSV file.
    timestamp_col : str
        Name of the timestamp column.
    drop_cols : list of str, optional
        Additional columns to drop (e.g. metadata like 'notes').
    resample_freq : str, optional
        If set, resample to this frequency (e.g. '1H' for hourly).
        Missing values after resampling are forward-filled then
        backward-filled.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by timestamp, sorted chronologically.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Sensor data CSV not found: {path}")

    logger.info("Loading sensor data from: %s", path)
    df = pd.read_csv(path)

    # Parse timestamp
    if timestamp_col not in df.columns:
        raise ValueError(
            f"Timestamp column '{timestamp_col}' not found in CSV. "
            f"Available: {list(df.columns)}"
        )
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df = df.set_index(timestamp_col).sort_index()

    # Drop unwanted metadata columns
    if drop_cols:
        to_drop = [c for c in drop_cols if c in df.columns]
        df = df.drop(columns=to_drop)
        if to_drop:
            logger.debug("Dropped columns: %s", to_drop)

    # Resample if requested
    if resample_freq:
        original_len = len(df)
        df = df.resample(resample_freq).mean()
        df = df.ffill().bfill()
        logger.info(
            "Resampled to %s: %d → %d rows (ffill+bfill applied)",
            resample_freq, original_len, len(df)
        )

    # Basic type coercion — all numeric columns should be float
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            except Exception:
                pass

    logger.info(
        "Loaded %d rows, %d columns. Date range: %s → %s",
        len(df), len(df.columns),
        df.index.min(), df.index.max()
    )
    return df


# ─── Train / Val / Test Split ─────────────────────────────────────────────────
# Chronological split — following the same principle as ml_flood
# (train on historical, test on future — NEVER shuffle time-series)

def chronological_split(
    df: pd.DataFrame,
    train_end: str,
    val_end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split a time-indexed DataFrame chronologically into train/val/test.

    This preserves temporal ordering, which is critical for time-series
    models to avoid data leakage from future to past.

    Approach adapted from ECMWFCode4Earth/ml_flood (MIT License):
    - Training period: 1981–2000
    - Test period: 2001–2017
    ResQShield uses the same philosophy with configurable dates.

    Parameters
    ----------
    df : pd.DataFrame
        Time-indexed DataFrame (index must be DatetimeIndex).
    train_end : str
        Last date of the training period (inclusive), e.g. "2023-12-31".
    val_end : str, optional
        Last date of the validation period (inclusive), e.g. "2024-06-30".
        If None, no validation split is made and val = empty DataFrame.

    Returns
    -------
    (train, val, test) : tuple of pd.DataFrames
        - train: data up to and including train_end
        - val: data from train_end+1 to val_end (empty if val_end is None)
        - test: data after val_end (or after train_end if val_end is None)
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame must have a DatetimeIndex for chronological split.")

    train_end_dt = pd.Timestamp(train_end)

    train = df[df.index <= train_end_dt]

    if val_end is not None:
        val_end_dt = pd.Timestamp(val_end)
        val = df[(df.index > train_end_dt) & (df.index <= val_end_dt)]
        test = df[df.index > val_end_dt]
    else:
        val = pd.DataFrame(columns=df.columns)
        test = df[df.index > train_end_dt]

    logger.info(
        "Chronological split — train: %d rows (%s to %s) | val: %d rows | test: %d rows",
        len(train),
        train.index.min() if len(train) else "N/A",
        train.index.max() if len(train) else "N/A",
        len(val),
        len(test),
    )

    if len(train) == 0:
        logger.warning("Training set is EMPTY — check train_end date and data range.")
    if len(test) == 0:
        logger.warning("Test set is EMPTY — check val_end date and data range.")

    return train, val, test


# ─── X / y Extraction ─────────────────────────────────────────────────────────

def extract_Xy(
    df: pd.DataFrame,
    target_col: str,
    forecast_horizon: int = 1,
    drop_na: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Extract feature matrix X and target vector y from the DataFrame.

    The target y is shifted forward by `forecast_horizon` steps so the
    model learns to predict N steps into the future.

    Parameters
    ----------
    df : pd.DataFrame
        Feature-engineered DataFrame (all lag columns already added).
    target_col : str
        Name of the target column (e.g., "water_level_m").
    forecast_horizon : int
        How many time steps ahead to predict. 1 = next timestep.
        For hourly data, horizon=3 means 3-hour ahead forecast.
    drop_na : bool
        If True, drop rows where X or y contains NaN (from lag features).

    Returns
    -------
    (X, y) : (pd.DataFrame, pd.Series)
        X has shape (n_samples, n_features).
        y has shape (n_samples,).
    """
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in DataFrame.")

    y = df[target_col].shift(-forecast_horizon)  # future value
    X = df.drop(columns=[target_col])

    if drop_na:
        valid_idx = (~X.isna().any(axis=1)) & (~y.isna())
        n_dropped = (~valid_idx).sum()
        if n_dropped > 0:
            logger.debug("Dropped %d rows with NaN (lag warmup + horizon shift)", n_dropped)
        X, y = X[valid_idx], y[valid_idx]

    return X, y


# ─── Synthetic Data Generator (for smoke tests when no real data exists) ──────

def generate_synthetic_sensor_data(
    n_hours: int = 8760,
    start: str = "2023-01-01",
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a synthetic sensor dataset for pipeline testing.

    This is ONLY for pipeline smoke tests — not for training or evaluation.
    Values are statistically plausible but NOT real data.

    Parameters
    ----------
    n_hours : int
        Number of hourly timesteps to generate (default 8760 = 1 year).
    start : str
        Start datetime string.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Synthetic hourly sensor data with required columns.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start=start, periods=n_hours, freq="h")

    # Synthetic rainfall: mostly zero, occasional events
    rain_base = rng.exponential(scale=0.2, size=n_hours)
    rain_event = (rng.random(n_hours) < 0.05) * rng.exponential(scale=8.0, size=n_hours)
    rainfall = np.clip(rain_base + rain_event, 0, 200)

    # Synthetic water level: mean-reverting with rainfall influence
    water_level = np.zeros(n_hours)
    water_level[0] = 1.5
    for t in range(1, n_hours):
        water_level[t] = (
            0.92 * water_level[t - 1]        # mean reversion
            + 0.04 * rainfall[t - 1]          # rainfall lag
            + 0.3                              # base flow
            + rng.normal(0, 0.05)             # noise
        )
    water_level = np.clip(water_level, 0.0, 20.0)

    df = pd.DataFrame(
        {
            "timestamp": idx,
            "rainfall_mm_hr": np.round(rainfall, 3),
            "soil_moisture_pct": np.clip(
                30 + 20 * np.sin(np.linspace(0, 4 * np.pi, n_hours)) + rng.normal(0, 3, n_hours),
                0, 100,
            ).round(1),
            "water_level_m": np.round(water_level, 3),
            "upstream_rainfall_mm_hr": np.round(
                np.roll(rainfall, shift=3) * 0.8, 3
            ),  # upstream = lagged downstream
        }
    )
    df = df.set_index("timestamp")
    logger.info("Generated %d rows of synthetic sensor data (seed=%d)", n_hours, seed)
    return df
