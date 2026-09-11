"""
resqshield_ml.utils.config
===========================
YAML configuration loader for ResQShield experiments.

All pipeline components read their settings from a YAML file.
Nothing is hard-coded in source files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load a ResQShield YAML config file.

    Parameters
    ----------
    config_path : str or Path
        Path to a YAML configuration file (e.g., configs/resqshield_default.yaml).

    Returns
    -------
    dict
        Parsed configuration as a nested dictionary.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    yaml.YAMLError
        If the YAML is malformed.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    logger.info("Loaded config: %s (experiment: %s)",
                config_path, cfg.get("experiment", {}).get("name", "unnamed"))
    return cfg


def get_nested(cfg: dict, *keys: str, default: Any = None) -> Any:
    """Safely retrieve a nested config value.

    Parameters
    ----------
    cfg : dict
        The configuration dictionary.
    *keys : str
        Key path, e.g. get_nested(cfg, 'model', 'xgboost', 'n_estimators').
    default : Any
        Value to return if any key in the path is missing.

    Returns
    -------
    Any
        The value at the key path, or `default` if not found.

    Examples
    --------
    >>> n = get_nested(cfg, 'model', 'xgboost', 'n_estimators', default=500)
    """
    node = cfg
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node
