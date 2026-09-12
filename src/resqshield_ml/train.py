"""
resqshield_ml.train
====================
Training CLI for the ResQShield flood prediction pipeline.

Usage
-----
    python -m resqshield_ml.train --config configs/flood_baseline.yaml

The module:
1. Parses --config
2. Loads the YAML configuration
3. Sets the configured random seed globally
4. Validates data.input_path (exits gracefully if not configured)
5. Validates timestamp_col and target_col presence in the CSV header
6. Loads the CSV
7. Runs configured feature engineering
8. Chronological split (NEVER random shuffle)
9. Builds the configured GradientBoosting or XGBoost model
10. Trains the model
11. Evaluates on the test split
12. Saves model artifact  → artifacts/models/<experiment>.joblib
13. Saves metrics JSON    → artifacts/metrics/<experiment>_metrics.json
14. Saves config snapshot → artifacts/configs/<experiment>_config.yaml

No synthetic data is generated here.
No data is downloaded here.

Upstream reference (MIT License):
    ECMWFCode4Earth/ml_flood — MATEHIW, ESoWC 2019
    Authors: @lkugler, @seblehner
    URL: https://github.com/ECMWFCode4Earth/ml_flood
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

logger = logging.getLogger(__name__)


# ─── Seed Helper ──────────────────────────────────────────────────────────────

def _set_global_seed(seed: int) -> None:
    """Set random seed globally for NumPy and Python random."""
    random.seed(seed)
    np.random.seed(seed)
    logger.info("Global random seed set to %d.", seed)


# ─── Dataset Validation ───────────────────────────────────────────────────────

_NO_DATASET_SENTINEL = (None, "", "null", "none", "N/A", "n/a")


def _validate_dataset_config(cfg: dict[str, Any]) -> Path:
    """Validate the data section of the config.

    Returns
    -------
    Path
        Absolute path to the input CSV, if valid.

    Raises
    ------
    SystemExit
        With a clear ERROR message if no approved dataset is configured
        or the file does not exist.
    """
    data_cfg = cfg.get("data", {})
    input_path = data_cfg.get("input_path")

    # Guard: no approved dataset configured
    if input_path in _NO_DATASET_SENTINEL:
        print(
            "ERROR: No approved dataset configured. "
            "Set data.input_path in configs/flood_baseline.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)

    csv_path = Path(input_path)
    if not csv_path.exists():
        print(
            f"ERROR: Dataset file not found: {csv_path}\n"
            "Set data.input_path in the config to an existing approved CSV.",
            file=sys.stderr,
        )
        sys.exit(1)

    return csv_path


def _validate_csv_columns(
    csv_path: Path,
    timestamp_col: str,
    target_col: str,
) -> None:
    """Check that required columns exist in the CSV header without loading it.

    Raises
    ------
    SystemExit
        If a required column is absent.
    """
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])

    missing = []
    if timestamp_col not in header:
        missing.append(f"timestamp_col='{timestamp_col}'")
    if target_col not in header:
        missing.append(f"target_col='{target_col}'")

    if missing:
        print(
            f"ERROR: Required column(s) not found in {csv_path}: {', '.join(missing)}\n"
            f"CSV header: {header}",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── Artifact Helpers ─────────────────────────────────────────────────────────

def _save_metrics_json(
    metrics: dict[str, Any],
    output_dir: Path,
    experiment_name: str,
) -> Path:
    """Save metrics dict as JSON with metadata envelope."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{experiment_name}_metrics.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    logger.info("Metrics saved → %s", out_path)
    return out_path


def _save_config_snapshot(
    cfg: dict[str, Any],
    output_dir: Path,
    experiment_name: str,
) -> Path:
    """Save an exact copy of the config used for this run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{experiment_name}_config.yaml"
    with open(out_path, "w", encoding="utf-8") as fh:
        yaml.dump(cfg, fh, default_flow_style=False, allow_unicode=True)
    logger.info("Config snapshot saved → %s", out_path)
    return out_path


def _build_artifact_metadata(
    cfg: dict[str, Any],
    model: Any,  # FloodModel
    n_train: int,
    n_val: int,
    n_test: int,
) -> dict[str, Any]:
    """Build the metadata envelope stored with model artifacts."""
    exp_cfg = cfg.get("experiment", {})
    return {
        "experiment_name": exp_cfg.get("name", "unnamed"),
        "seed": exp_cfg.get("seed", 42),
        "model_type": model.kind,
        "feature_names": model.feature_names_ or [],
        "n_train_rows": n_train,
        "n_val_rows": n_val,
        "n_test_rows": n_test,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Main Training Function ───────────────────────────────────────────────────

def run_training(config_path: str | Path) -> None:
    """Execute the full training pipeline from a config file.

    This function is the single source of truth for the training workflow.
    It is called by both the CLI entry point and can be imported for
    programmatic use in tests or notebooks.

    Parameters
    ----------
    config_path : str or Path
        Path to a ResQShield YAML config file.
    """
    # ── Imports (deferred so the module can be imported cheaply) ──────────────
    from resqshield_ml.data.loader import (
        chronological_split,
        extract_Xy,
        load_sensor_csv,
    )
    from resqshield_ml.evaluation.metrics import evaluate, save_metrics
    from resqshield_ml.features.engineer import build_features
    from resqshield_ml.models.flood_model import build_model_from_config
    from resqshield_ml.utils.config import load_config

    # ── 1. Load config ────────────────────────────────────────────────────────
    cfg = load_config(config_path)

    exp_cfg = cfg.get("experiment", {})
    experiment_name = exp_cfg.get("name", "unnamed")
    seed = int(exp_cfg.get("seed", 42))

    logger.info("=== ResQShield Training Pipeline ===")
    logger.info("Experiment : %s", experiment_name)
    logger.info("Config     : %s", config_path)

    # ── 2. Set global seed ────────────────────────────────────────────────────
    _set_global_seed(seed)

    # ── 3. Validate dataset path — exit gracefully if not configured ──────────
    csv_path = _validate_dataset_config(cfg)

    # ── 4. Validate timestamp / target columns ────────────────────────────────
    data_cfg = cfg.get("data", {})
    timestamp_col = data_cfg.get("timestamp_col", "timestamp")
    target_col = data_cfg.get("target_col", "water_level_m")
    _validate_csv_columns(csv_path, timestamp_col, target_col)

    # ── 5. Load CSV ───────────────────────────────────────────────────────────
    drop_cols = cfg.get("features", {}).get("drop_cols", [])
    df_raw = load_sensor_csv(
        csv_path,
        timestamp_col=timestamp_col,
        drop_cols=drop_cols,
    )

    # ── 6. Feature engineering ────────────────────────────────────────────────
    df_feat = build_features(df_raw, cfg=cfg)

    # ── 7. Chronological split — NEVER shuffle ────────────────────────────────
    split_cfg = cfg.get("split", {})
    train_df, val_df, test_df = chronological_split(
        df_feat,
        train_end=split_cfg.get("train_end", "2023-12-31"),
        val_end=split_cfg.get("val_end"),
    )

    X_train, y_train = extract_Xy(train_df, target_col=target_col)
    X_val, y_val = (
        extract_Xy(val_df, target_col=target_col) if len(val_df) > 0
        else (None, None)
    )
    X_test, y_test = extract_Xy(test_df, target_col=target_col)

    logger.info(
        "Split → train: %d | val: %d | test: %d rows",
        len(X_train), len(X_val) if X_val is not None else 0, len(X_test),
    )

    # ── 8. Build model ────────────────────────────────────────────────────────
    model = build_model_from_config(cfg)

    # ── 9. Train ──────────────────────────────────────────────────────────────
    model.fit(X_train, y_train, X_val=X_val, y_val=y_val)

    # ── 10. Evaluate ──────────────────────────────────────────────────────────
    artifact_dirs = cfg.get("artifacts", {})
    model_dir = Path(artifact_dirs.get("model_dir", "artifacts/models"))
    metrics_dir = Path(artifact_dirs.get("metrics_dir", "artifacts/metrics"))
    configs_dir = Path(artifact_dirs.get("configs_dir", "artifacts/configs"))

    metrics: dict[str, Any] = {}
    if len(X_test) > 0:
        y_pred = model.predict(X_test)
        metrics = evaluate(y_pred, y_test.values, cfg=cfg, split_name="test")
    else:
        logger.warning("Test set is empty — skipping evaluation.")
        metrics = {"warning": "test set was empty"}

    # ── 11. Attach artifact metadata ──────────────────────────────────────────
    metadata = _build_artifact_metadata(
        cfg, model,
        n_train=len(X_train),
        n_val=len(X_val) if X_val is not None else 0,
        n_test=len(X_test),
    )
    metrics["metadata"] = metadata

    # ── 12. Save model artifact ───────────────────────────────────────────────
    model_path = model.save(model_dir, name=experiment_name)

    # ── 13. Save metrics JSON ─────────────────────────────────────────────────
    _save_metrics_json(metrics, metrics_dir, experiment_name)

    # ── 14. Save config snapshot ──────────────────────────────────────────────
    _save_config_snapshot(cfg, configs_dir, experiment_name)

    logger.info("=== Training complete ===")
    logger.info("Model    → %s", model_path)
    logger.info("Metrics  → %s", metrics_dir / f"{experiment_name}_metrics.json")
    logger.info("Config   → %s", configs_dir / f"{experiment_name}_config.yaml")


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m resqshield_ml.train",
        description=(
            "ResQShield Training CLI\n"
            "Trains a flood prediction model from a YAML config.\n\n"
            "Example:\n"
            "  python -m resqshield_ml.train --config configs/flood_baseline.yaml"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        required=True,
        metavar="PATH",
        help="Path to a ResQShield YAML config file (e.g. configs/flood_baseline.yaml)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Top-level entry point called by ``python -m resqshield_ml.train``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    args = _parse_args(argv)
    run_training(args.config)


if __name__ == "__main__":
    main()
