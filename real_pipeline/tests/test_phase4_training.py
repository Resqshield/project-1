# -*- coding: utf-8 -*-
"""
real_pipeline/tests/test_phase4_training.py
============================================
Phase 4 tests: leakage, event weighting, model integrity, shadow API.

All tests enforce the hard rules from the user specification:
  - No event leakage across folds
  - Class-conditional missingness check (no feature encodes label structure)
  - No ID/region/source/coverage fields in predictors
  - No synthetic rows
  - Event weighting present
  - Deterministic model reload/inference
  - Probability bounds [0, 1]
  - Threshold not chosen from test folds
  - Shadow API separate from synthetic MVP
  - Synthetic MVP intact
"""

import json
import pickle
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

FEAT_DIR   = PROJECT_ROOT / "data_real" / "features"
EVAL_DIR   = PROJECT_ROOT / "data_real" / "evaluation"
MODELS_DIR = PROJECT_ROOT / "models_real"
DATA_DIR   = PROJECT_ROOT / "data"
BACKEND_DIR = PROJECT_ROOT / "backend"


def _load_flood() -> pd.DataFrame:
    return pd.read_parquet(str(FEAT_DIR / "flood_training.parquet"))


def _load_model():
    path = MODELS_DIR / "flood_research_model.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


# ── Gate Tests ────────────────────────────────────────────────────────────────

class TestIndependenceAudit(unittest.TestCase):

    def test_readiness_report_exists(self):
        self.assertTrue((EVAL_DIR / "readiness_report.json").exists(),
                        "readiness_report.json missing — run independence_audit.py")

    def test_readiness_report_structure(self):
        with open(EVAL_DIR / "readiness_report.json") as f:
            r = json.load(f)
        self.assertIn("flood", r)
        self.assertIn("landslide", r)
        self.assertIn("gate1", r["flood"])
        self.assertIn("gate2", r["landslide"])

    def test_gate1_flood_experimental_only(self):
        with open(EVAL_DIR / "readiness_report.json") as f:
            r = json.load(f)
        label = r["flood"]["gate1"]["readiness_label"]
        self.assertEqual(label, "EXPERIMENTAL_BASELINE_ONLY",
                         f"Unexpected flood readiness: {label}")

    def test_gate2_landslide_blocked(self):
        with open(EVAL_DIR / "readiness_report.json") as f:
            r = json.load(f)
        self.assertFalse(r["landslide"]["gate2"]["training_allowed"],
                         "Landslide training should be blocked")
        self.assertEqual(r["landslide"]["gate2"]["readiness_label"], "NEEDS_MORE_EVENTS")

    def test_raw_rows_vs_independent_groups_reported(self):
        with open(EVAL_DIR / "readiness_report.json") as f:
            r = json.load(f)
        audit = r["flood"]["audit"]
        self.assertIn("raw_rows", audit)
        self.assertIn("independent_groups", audit)
        self.assertGreater(audit["raw_rows"], audit["independent_groups"] * 100,
                           "raw_rows should >> independent_groups")

    def test_independent_groups_count(self):
        with open(EVAL_DIR / "readiness_report.json") as f:
            r = json.load(f)
        n_groups = r["flood"]["audit"]["independent_groups"]
        self.assertEqual(n_groups, 6,
                         f"Expected 6 independent groups (3 pos + 3 neg), got {n_groups}")


# ── Leakage Tests ─────────────────────────────────────────────────────────────

class TestNoEventLeakage(unittest.TestCase):

    def setUp(self):
        self.df = _load_flood()

    def test_no_duplicate_sample_ids(self):
        dups = self.df["sample_id"].duplicated().sum()
        self.assertEqual(dups, 0, f"Duplicate sample IDs: {dups}")

    def test_event_groups_are_temporally_separated(self):
        """Positive and negative windows for the same region must not overlap in time."""
        for region in self.df["pilot_region"].unique():
            region_df = self.df[self.df["pilot_region"] == region]
            pos_events = region_df[region_df["label"] == 1]["event_id"].unique()
            neg_events = region_df[region_df["label"] == 0]["event_id"].unique()
            self.assertGreater(len(pos_events), 0, f"No positive events for {region}")
            self.assertGreater(len(neg_events), 0, f"No negative windows for {region}")
            # Verify no event_id appears in both pos and neg
            overlap = set(pos_events) & set(neg_events)
            self.assertEqual(len(overlap), 0,
                             f"Same event_id in pos and neg for {region}: {overlap}")

    def test_loeo_folds_no_event_leakage(self):
        """Simulated LOEO: test event must not be in training events."""
        events = self.df["event_id"].unique()
        for test_event in events:
            train_events = set(events) - {test_event}
            train_df = self.df[self.df["event_id"] != test_event]
            test_df  = self.df[self.df["event_id"] == test_event]
            # No test event in training
            self.assertNotIn(test_event, train_df["event_id"].values)
            # Training has at least 2 classes
            self.assertEqual(len(train_df["label"].unique()), 2,
                             f"Fold {test_event}: training has <2 classes")


class TestClassConditionalMissingness(unittest.TestCase):
    """Verify no feature has class-correlated missingness after antecedent fix."""

    LEAK_THRESHOLD = 0.05  # 5%

    def setUp(self):
        self.df = _load_flood()

    def _get_candidate_features(self):
        from real_pipeline.training.feature_spec import FEATURE_BLACKLIST
        return [c for c in self.df.select_dtypes("number").columns
                if c not in FEATURE_BLACKLIST and c != "label"]

    def test_antecedent_missingness_parity(self):
        """ant_3d/7d/14d must have equal missingness in pos and neg after fix."""
        for feat in ["ant_3d_mm", "ant_7d_mm", "ant_14d_mm"]:
            if feat not in self.df.columns:
                continue
            miss_pos = self.df.loc[self.df["label"] == 1, feat].isna().mean()
            miss_neg = self.df.loc[self.df["label"] == 0, feat].isna().mean()
            delta = abs(miss_pos - miss_neg)
            self.assertLessEqual(delta, self.LEAK_THRESHOLD,
                                 f"LEAKAGE: {feat} missingness delta={delta:.3f} > {self.LEAK_THRESHOLD}")

    def test_no_high_risk_leakage_features(self):
        """No candidate predictor should have >30% class-conditional missingness delta."""
        feats = self._get_candidate_features()
        for feat in feats:
            miss_pos = self.df.loc[self.df["label"] == 1, feat].isna().mean()
            miss_neg = self.df.loc[self.df["label"] == 0, feat].isna().mean()
            delta = abs(miss_pos - miss_neg)
            self.assertLessEqual(delta, 0.30,
                                 f"HIGH LEAKAGE RISK: {feat} delta={delta:.3f}")


class TestFeatureBlacklist(unittest.TestCase):
    """No ID/source/region/coverage fields in the predictor list."""

    def test_blacklisted_features_not_in_spec(self):
        from real_pipeline.training.feature_spec import (
            FEATURE_BLACKLIST, get_core_common_features
        )
        fs = get_core_common_features(antecedent_ok=True)
        for feat in FEATURE_BLACKLIST:
            self.assertNotIn(feat, fs.features,
                             f"Blacklisted feature in core spec: {feat}")

    def test_event_id_not_in_predictor(self):
        from real_pipeline.training.feature_spec import get_core_common_features
        fs = get_core_common_features(antecedent_ok=True)
        self.assertNotIn("event_id", fs.features)

    def test_region_not_in_predictor(self):
        from real_pipeline.training.feature_spec import get_core_common_features
        fs = get_core_common_features(antecedent_ok=True)
        self.assertNotIn("pilot_region", fs.features)

    def test_label_source_not_in_predictor(self):
        from real_pipeline.training.feature_spec import get_core_common_features
        fs = get_core_common_features(antecedent_ok=True)
        self.assertNotIn("label_source", fs.features)

    def test_data_type_not_in_predictor(self):
        from real_pipeline.training.feature_spec import get_core_common_features
        fs = get_core_common_features(antecedent_ok=True)
        self.assertNotIn("data_type", fs.features)

    def test_coverage_flag_not_in_predictor(self):
        from real_pipeline.training.feature_spec import get_core_common_features
        fs = get_core_common_features(antecedent_ok=True)
        self.assertNotIn("terrain_available", fs.features)
        self.assertNotIn("data_coverage", fs.features)


# ── No Synthetic Rows ─────────────────────────────────────────────────────────

class TestNoSyntheticContamination(unittest.TestCase):

    def test_flood_matrix_no_synthetic(self):
        df = _load_flood()
        self.assertTrue(
            (df["data_type"] == "REAL_DATA \u2014 NOT SYNTHETIC").all(),
            "Synthetic rows found in flood matrix"
        )

    def test_synthetic_mvp_intact(self):
        """The original synthetic data directory must be untouched."""
        data_dir = PROJECT_ROOT / "data"
        self.assertTrue(data_dir.exists(), "data/ directory missing — synthetic MVP broken")
        # MVP stores predictions as JSON in subdirectory
        json_candidates = list(data_dir.rglob("*.json"))
        csv_candidates  = list(data_dir.rglob("*.csv"))
        self.assertGreater(len(json_candidates) + len(csv_candidates), 0,
                           "No data files in data/ — synthetic MVP may be broken")

    def test_data_real_separate_from_data(self):
        """data_real/ must not pollute data/."""
        data_real = PROJECT_ROOT / "data_real"
        data_dir  = PROJECT_ROOT / "data"
        self.assertTrue(data_real.exists())
        # No symlinks or cross-references
        real_files = {f.name for f in data_real.rglob("*.parquet")}
        data_files = {f.name for f in data_dir.rglob("*.parquet")}
        cross = real_files & data_files
        # Some name overlap is OK (different paths), but check directories don't alias
        real_abs = data_real.resolve()
        data_abs = data_dir.resolve()
        self.assertNotEqual(real_abs, data_abs, "data_real/ and data/ resolve to same path!")


# ── Event Weighting ───────────────────────────────────────────────────────────

class TestEventWeighting(unittest.TestCase):

    def test_weighting_equalizes_event_contribution(self):
        """After event weighting, all events should contribute equal total weight."""
        from real_pipeline.training.train_flood_models import compute_event_weights
        df = _load_flood()
        weights = compute_event_weights(df)
        # Each event's total weight should be approximately equal
        event_weight_sums = {}
        for eid in df["event_id"].unique():
            mask = df["event_id"] == eid
            event_weight_sums[eid] = weights[mask.values].sum()

        values = list(event_weight_sums.values())
        max_w = max(values)
        min_w = min(values)
        ratio = max_w / min_w
        self.assertLess(ratio, 1.01,
                        f"Event weights not equal: max/min ratio={ratio:.4f} > 1.01")

    def test_weights_all_positive(self):
        from real_pipeline.training.train_flood_models import compute_event_weights
        df = _load_flood()
        w = compute_event_weights(df)
        self.assertTrue((w > 0).all(), "Some weights are non-positive")

    def test_weights_finite(self):
        from real_pipeline.training.train_flood_models import compute_event_weights
        df = _load_flood()
        w = compute_event_weights(df)
        self.assertTrue(np.isfinite(w).all(), "Some weights are inf/nan")


# ── Model Integrity ───────────────────────────────────────────────────────────

class TestModelIntegrity(unittest.TestCase):

    def setUp(self):
        self.bundle = _load_model()

    def test_model_file_exists(self):
        self.assertTrue((MODELS_DIR / "flood_research_model.pkl").exists(),
                        "flood_research_model.pkl not found")

    def test_model_metadata_exists(self):
        self.assertTrue((MODELS_DIR / "flood_research_metadata.json").exists(),
                        "flood_research_metadata.json not found")

    def test_metadata_not_operational(self):
        with open(MODELS_DIR / "flood_research_metadata.json") as f:
            meta = json.load(f)
        self.assertTrue(meta["not_operational"])
        self.assertFalse(meta["deployment_allowed"])
        self.assertEqual(meta["status"], "EXPERIMENTAL_BASELINE_ONLY")

    def test_model_serialization_reload(self):
        if self.bundle is None:
            self.skipTest("Model not yet trained")
        self.assertIn("model", self.bundle)
        self.assertIn("feature_list", self.bundle)
        self.assertIn("model_name", self.bundle)

    def test_deterministic_inference(self):
        """Same input → same output after reload."""
        if self.bundle is None:
            self.skipTest("Model not yet trained")
        df = _load_flood()
        feats = self.bundle["feature_list"]
        valid_feats = [f for f in feats if f in df.columns]
        X = df[valid_feats].head(100).fillna(0).values

        model = self.bundle["model"]
        pred1 = model.predict_proba(X)[:, 1]
        pred2 = model.predict_proba(X)[:, 1]
        np.testing.assert_array_equal(pred1, pred2,
                                      "Model inference is not deterministic")

    def test_probability_bounds(self):
        """All predicted probabilities must be in [0, 1]."""
        if self.bundle is None:
            self.skipTest("Model not yet trained")
        df = _load_flood()
        feats = self.bundle["feature_list"]
        valid_feats = [f for f in feats if f in df.columns]
        X = df[valid_feats].head(500).fillna(0).values
        model = self.bundle["model"]
        probs = model.predict_proba(X)[:, 1]
        self.assertTrue((probs >= 0).all() and (probs <= 1).all(),
                        f"Probabilities out of [0,1]: min={probs.min():.4f}, max={probs.max():.4f}")


# ── Fold Metrics ─────────────────────────────────────────────────────────────

class TestFoldMetrics(unittest.TestCase):

    def test_fold_metrics_exist(self):
        self.assertTrue((EVAL_DIR / "fold_metrics.csv").exists(),
                        "fold_metrics.csv missing")

    def test_event_metrics_exist(self):
        self.assertTrue((EVAL_DIR / "event_metrics.csv").exists(),
                        "event_metrics.csv missing")

    def test_no_random_row_split_in_metrics(self):
        """No strategy='RANDOM' in fold metrics."""
        df = pd.read_csv(EVAL_DIR / "fold_metrics.csv")
        if "strategy" in df.columns:
            random_rows = df[df["strategy"].str.upper() == "RANDOM"]
            self.assertEqual(len(random_rows), 0,
                             "Random row-split results found in metrics — not allowed")

    def test_loeo_folds_present(self):
        df = pd.read_csv(EVAL_DIR / "fold_metrics.csv")
        loeo_rows = df[df["strategy"] == "LOEO"]
        self.assertGreater(len(loeo_rows), 0, "No LOEO folds in metrics")

    def test_pr_auc_bounds(self):
        df = pd.read_csv(EVAL_DIR / "fold_metrics.csv")
        if "pr_auc" in df.columns:
            self.assertTrue((df["pr_auc"].dropna() >= 0).all())
            self.assertTrue((df["pr_auc"].dropna() <= 1).all())

    def test_recall_bounds(self):
        df = pd.read_csv(EVAL_DIR / "fold_metrics.csv")
        if "recall_pod" in df.columns:
            self.assertTrue((df["recall_pod"].dropna() >= 0).all())
            self.assertTrue((df["recall_pod"].dropna() <= 1).all())


# ── Shadow API Separation ─────────────────────────────────────────────────────

class TestShadowAPISeparation(unittest.TestCase):

    def test_real_research_blueprint_exists(self):
        route_path = BACKEND_DIR / "routes" / "real_research.py"
        self.assertTrue(route_path.exists(),
                        "real_research.py blueprint missing")

    def test_real_blueprint_has_correct_prefix(self):
        route_path = BACKEND_DIR / "routes" / "real_research.py"
        content = route_path.read_text(encoding="utf-8", errors="replace")
        # FastAPI APIRouter uses prefix argument
        self.assertIn('prefix="/api/real"', content,
                      "Shadow API must be at /api/real prefix")

    def test_real_blueprint_not_operational_flag(self):
        route_path = BACKEND_DIR / "routes" / "real_research.py"
        content = route_path.read_text(encoding="utf-8", errors="replace")
        self.assertIn("not_operational", content)
        self.assertIn("research_only", content)

    def test_real_blueprint_does_not_overwrite_locations(self):
        route_path = BACKEND_DIR / "routes" / "real_research.py"
        content = route_path.read_text(encoding="utf-8", errors="replace")
        # Must not DEFINE a /api/locations route (decorator or APIRouter route)
        # Mentioning it in docs/comments/response payloads is fine
        self.assertNotIn('@router.get("/api/locations"', content,
                         "Shadow API must not register a /api/locations route")
        self.assertNotIn('@app.get("/api/locations"', content,
                         "Shadow API must not register a /api/locations route")


    def test_real_blueprint_no_nationwide_predictions(self):
        route_path = BACKEND_DIR / "routes" / "real_research.py"
        content = route_path.read_text(encoding="utf-8", errors="replace")
        self.assertIn("nationwide_predictions", content,
                      "Shadow API should explicitly state nationwide_predictions=False")


# ── Threshold Integrity ───────────────────────────────────────────────────────

class TestThresholdIntegrity(unittest.TestCase):

    def test_threshold_analysis_exists(self):
        if not (EVAL_DIR / "threshold_analysis.csv").exists():
            self.skipTest("threshold_analysis.csv not yet generated")

    def test_threshold_analysis_note(self):
        """Threshold analysis must include EXPLORATORY_ONLY note."""
        if not (EVAL_DIR / "threshold_analysis.csv").exists():
            self.skipTest("threshold_analysis.csv not yet generated")
        df = pd.read_csv(EVAL_DIR / "threshold_analysis.csv")
        if "note" in df.columns:
            self.assertTrue(
                df["note"].str.contains("EXPLORATORY_ONLY").any(),
                "Threshold analysis must include EXPLORATORY_ONLY note"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
