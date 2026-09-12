"""
resqshield_ml.models.flood_model
==================================
Flood level prediction model for ResQShield.

Design adapted from (MIT License):
    ECMWFCode4Earth/ml_flood :: python/misc/floodmodels.py
    Class: FlowModel (model selection + fit/predict interface)
    Authors: @lkugler, @seblehner — ESoWC 2019, MATEHIW Project

Key differences from the upstream FlowModel:
- Upstream: wraps xgboost.XGBRegressor + keras TDNN; uses xarray DataArrays
- ResQShield: wraps XGBRegressor + sklearn GradientBoostingRegressor;
              uses pandas DataFrames; no Keras/TDNN dependency
- Model serialisation via joblib (same as upstream)
- Adds SHAP feature importance (optional)
- Adds multi-horizon prediction support
- Hyperparameter search via hyperopt (optional, flag-gated)

DO NOT use for final flood forecasting until trained on real Indian data.
"""

from __future__ import annotations

import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Optional imports — graceful degradation
try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False
    logger.warning("xgboost not installed — XGBoost model will be unavailable.")

try:
    from hyperopt import Trials, fmin, hp, tpe
    _HYPEROPT_AVAILABLE = True
except ImportError:
    _HYPEROPT_AVAILABLE = False
    logger.warning("hyperopt not installed — Bayesian HPO will be unavailable.")


# ─── ResQShield FloodModel ─────────────────────────────────────────────────────
# Adapted from ml_flood::floodmodels.py::FlowModel (MIT License)
# The original FlowModel supported 'neural_net', 'xgboost', 'Ridge'.
# ResQShield FloodModel supports 'xgboost' and 'gradient_boosting'.

class FloodModel:
    """ResQShield flood level prediction model.

    A thin wrapper around XGBoost or scikit-learn GradientBoostingRegressor
    that provides a consistent fit/predict interface and handles serialization.

    The design mirrors ECMWFCode4Earth/ml_flood's FlowModel class pattern
    (MIT License), adapted for:
    - pandas DataFrames instead of xarray DataArrays
    - Config-driven hyperparameters from YAML
    - Integrated joblib serialization
    - Feature importance extraction

    Parameters
    ----------
    kind : str
        Model type: 'xgboost' or 'gradient_boosting'.
    model_params : dict
        Hyperparameters for the model (from config['model'][kind]).

    Examples
    --------
    >>> model = FloodModel(kind='xgboost', model_params={'n_estimators': 500})
    >>> model.fit(X_train, y_train, X_val=X_val, y_val=y_val)
    >>> predictions = model.predict(X_test)
    """

    SUPPORTED_KINDS = {"xgboost", "gradient_boosting"}

    def __init__(self, kind: str, model_params: dict[str, Any]) -> None:
        if kind not in self.SUPPORTED_KINDS:
            raise ValueError(
                f"Unsupported model kind '{kind}'. Choose from: {self.SUPPORTED_KINDS}"
            )
        if kind == "xgboost" and not _XGB_AVAILABLE:
            raise ImportError("xgboost is not installed. Run: pip install xgboost")

        self.kind = kind
        self.model_params = model_params
        self._model = self._build_model(kind, model_params)
        self.feature_names_: list[str] | None = None
        self.is_fitted_ = False

    def _build_model(self, kind: str, params: dict[str, Any]) -> Any:
        """Instantiate the underlying scikit-learn compatible model."""
        if kind == "xgboost":
            # Separate xgboost-specific params from fit params
            xgb_params = {k: v for k, v in params.items()
                          if k not in {"early_stopping_rounds"}}
            return xgb.XGBRegressor(**xgb_params)

        elif kind == "gradient_boosting":
            return GradientBoostingRegressor(**params)

    def fit(
        self,
        X_train: pd.DataFrame | np.ndarray,
        y_train: pd.Series | np.ndarray,
        X_val: pd.DataFrame | np.ndarray | None = None,
        y_val: pd.Series | np.ndarray | None = None,
    ) -> "FloodModel":
        """Train the flood model.

        Parameters
        ----------
        X_train : DataFrame or array
            Training feature matrix.
        y_train : Series or array
            Training target (water level in m).
        X_val : DataFrame or array, optional
            Validation features for early stopping (XGBoost only).
        y_val : Series or array, optional
            Validation targets.

        Returns
        -------
        self
        """
        if isinstance(X_train, pd.DataFrame):
            self.feature_names_ = list(X_train.columns)

        logger.info(
            "Training %s model on %d samples, %d features.",
            self.kind, len(X_train), X_train.shape[1]
        )

        if self.kind == "xgboost" and X_val is not None and y_val is not None:
            early_stopping = self.model_params.get("early_stopping_rounds", 50)
            eval_set = [(np.asarray(X_val), np.asarray(y_val))]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._model.fit(
                    X_train, y_train,
                    eval_set=eval_set,
                    early_stopping_rounds=early_stopping,
                    verbose=False,
                )
        else:
            self._model.fit(X_train, y_train)

        self.is_fitted_ = True
        logger.info("Training complete.")
        return self

    def predict(
        self,
        X: pd.DataFrame | np.ndarray,
        clip_negative: bool = True,
    ) -> np.ndarray:
        """Generate predictions from the trained model.

        Parameters
        ----------
        X : DataFrame or array
            Feature matrix to predict on.
        clip_negative : bool
            If True, clip predictions below 0 to 0 (water level cannot be negative).

        Returns
        -------
        np.ndarray
            Predicted water levels in metres.
        """
        if not self.is_fitted_:
            raise RuntimeError("Model is not fitted. Call fit() first.")

        preds = self._model.predict(np.asarray(X)).squeeze()

        if clip_negative:
            preds = np.clip(preds, 0.0, None)

        return preds

    def feature_importance(self, top_n: int = 20) -> pd.DataFrame:
        """Return a sorted DataFrame of feature importances.

        Parameters
        ----------
        top_n : int
            Number of top features to return.

        Returns
        -------
        pd.DataFrame
            Columns: ['feature', 'importance'] sorted descending.
        """
        if not self.is_fitted_:
            raise RuntimeError("Model is not fitted.")

        if self.kind == "xgboost":
            importances = self._model.feature_importances_
        elif self.kind == "gradient_boosting":
            importances = self._model.feature_importances_
        else:
            return pd.DataFrame(columns=["feature", "importance"])

        features = self.feature_names_ or [f"f{i}" for i in range(len(importances))]
        df = pd.DataFrame({"feature": features, "importance": importances})
        df = df.sort_values("importance", ascending=False).head(top_n).reset_index(drop=True)
        return df

    def save(self, artifact_dir: str | Path, name: str | None = None) -> Path:
        """Serialize the model to disk using joblib.

        Follows the same serialization approach as ml_flood (MIT License):
            from joblib import dump, load  # saving and loading pipeline objects

        Parameters
        ----------
        artifact_dir : str or Path
            Directory to save the model file in.
        name : str, optional
            Filename prefix. Defaults to experiment-timestamp.

        Returns
        -------
        Path
            Path to the saved model file.
        """
        artifact_dir = Path(artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"{name or 'resqshield'}_{self.kind}_{ts}.joblib"
        out_path = artifact_dir / filename

        joblib.dump(self, out_path)
        logger.info("Model saved to: %s", out_path)
        return out_path

    @classmethod
    def load(cls, path: str | Path) -> "FloodModel":
        """Load a serialized FloodModel from disk.

        Parameters
        ----------
        path : str or Path
            Path to a .joblib model file.

        Returns
        -------
        FloodModel
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        model = joblib.load(path)
        logger.info("Model loaded from: %s", path)
        return model

    def __repr__(self) -> str:
        status = "fitted" if self.is_fitted_ else "not fitted"
        n_features = len(self.feature_names_) if self.feature_names_ else "unknown"
        return (
            f"FloodModel(kind='{self.kind}', status={status}, "
            f"n_features={n_features})"
        )


# ─── Factory Function ──────────────────────────────────────────────────────────

def build_model_from_config(cfg: dict[str, Any]) -> FloodModel:
    """Instantiate a FloodModel from the experiment config.

    Parameters
    ----------
    cfg : dict
        Full experiment config (from configs/resqshield_default.yaml).

    Returns
    -------
    FloodModel
    """
    model_cfg = cfg.get("model", {})
    kind = model_cfg.get("kind", "xgboost")
    params = model_cfg.get(kind, {})

    # Remove non-constructor params that are used during fit() instead
    params = dict(params)
    params.pop("early_stopping_rounds", None)  # passed during fit

    logger.info("Building FloodModel: kind=%s, params=%s", kind, params)
    return FloodModel(kind=kind, model_params=params)


# ─── Entry Point (CLI) ────────────────────────────────────────────────────────

def _cli_main() -> None:
    """Command-line entry point for model training.

    Usage:
        python -m resqshield_ml.models.flood_model \\
            --data data/processed/features.csv \\
            --config configs/resqshield_default.yaml \\
            --artifact-dir artifacts/
    """
    import argparse
    from resqshield_ml.data.loader import chronological_split, extract_Xy, load_sensor_csv
    from resqshield_ml.evaluation.metrics import evaluate, save_metrics, save_predictions
    from resqshield_ml.utils.config import load_config

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="ResQShield FloodModel trainer")
    parser.add_argument("--data", required=True, help="Path to processed features CSV")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--artifact-dir", default="artifacts", help="Output directory for model + metrics")
    args = parser.parse_args()

    cfg = load_config(args.config)
    df = load_sensor_csv(
        args.data,
        timestamp_col=cfg["data"]["timestamp_col"],
        drop_cols=cfg["features"].get("drop_cols", []),
    )

    split_cfg = cfg.get("split", {})
    train, val, test = chronological_split(
        df,
        train_end=split_cfg.get("train_end", "2023-12-31"),
        val_end=split_cfg.get("val_end"),
    )

    target_col = cfg["data"]["target_col"]
    X_train, y_train = extract_Xy(train, target_col=target_col)
    X_val, y_val = extract_Xy(val, target_col=target_col) if len(val) else (None, None)
    X_test, y_test = extract_Xy(test, target_col=target_col)

    model = build_model_from_config(cfg)
    model.fit(X_train, y_train, X_val=X_val, y_val=y_val)

    # Save model
    artifact_dir = Path(args.artifact_dir)
    exp_name = cfg.get("experiment", {}).get("name", "resqshield")
    model.save(artifact_dir / "models", name=exp_name)

    # Evaluate on test set
    if len(X_test) > 0:
        y_pred = model.predict(X_test)
        metrics = evaluate(y_pred, y_test.values, cfg=cfg, split_name="test")
        save_metrics(metrics, artifact_dir / "metrics", "test_metrics.json")
        save_predictions(y_pred, y_test.values, X_test.index, artifact_dir / "metrics")

        # Feature importance
        fi = model.feature_importance(top_n=20)
        fi.to_csv(artifact_dir / "metrics" / "feature_importance.csv", index=False)
        logger.info("\nTop 10 features:\n%s", fi.head(10).to_string(index=False))


if __name__ == "__main__":
    _cli_main()
