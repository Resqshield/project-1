# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
ResQ Shield - Phase 2: Flood Risk Model Training
=================================================
Trains a RandomForestClassifier to predict flood_risk (Low/Medium/High).

!! IMPORTANT DISCLAIMER !!
   - Training data is ENTIRELY SYNTHETIC / DEMO DATA.
   - flood_risk labels were derived from a weighted formula on the same
     input features. The model learns to reproduce that synthetic rule,
     NOT real-world flood dynamics.
   - Accuracy figures are "Synthetic Dataset Validation Accuracy".
     They do NOT represent validated real-world disaster-forecasting.
   - NOT suitable for operational early-warning or policy decisions.

river_level note:
   river_level is a SYNTHETIC NORMALIZED RIVER LEVEL INDEX (0-10 scale).
   It is NOT a measurement in metres or any official gauge reading.

Run:
    python ml/train_flood.py

Dependencies:
    pip install pandas numpy scikit-learn joblib
"""

import os, json, warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_PATH    = os.path.join(PROJECT_ROOT, "data", "processed", "master_dataset.csv")
MODEL_DIR    = os.path.join(PROJECT_ROOT, "models")
MODEL_PATH   = os.path.join(MODEL_DIR, "flood_model.pkl")
META_PATH    = os.path.join(MODEL_DIR, "flood_model_metadata.json")

# ── Feature / target ──────────────────────────────────────────────────────────
FEATURES = ["rainfall", "river_level", "soil_moisture", "elevation", "flood_history"]
TARGET   = "flood_risk"

DIV  = "=" * 62
DIV2 = "-" * 62

def section(t): print(); print(DIV); print(f"  {t}"); print(DIV)

# ── 1. Load & validate ────────────────────────────────────────────────────────
def load_and_validate(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}\nRun: python ml/prepare_data.py")
    df = pd.read_csv(path)
    section("DATA LOADING & VALIDATION")
    print(f"  Loaded : {path}")
    print(f"  Shape  : {df.shape[0]} rows x {df.shape[1]} columns")
    missing_cols = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Required columns missing: {missing_cols}")
    print("  Required columns check : PASSED")
    mv = df[FEATURES + [TARGET]].isnull().sum()
    mv = mv[mv > 0]
    if not mv.empty:
        print(f"  [WARNING] Missing values found:\n{mv.to_string()}")
        df = df.dropna(subset=FEATURES + [TARGET])
        print(f"  Rows after dropping NaN: {len(df)}")
    else:
        print("  Missing values check   : NONE FOUND - OK")
    return df

# ── 2. Class distribution ─────────────────────────────────────────────────────
def print_class_dist(y):
    section("CLASS DISTRIBUTION  (flood_risk)")
    counts = y.value_counts(); total = len(y)
    for cls in ["Low", "Medium", "High"]:
        n = counts.get(cls, 0); pct = 100.0*n/total
        print(f"  {cls:<8}: {n:>3}  ({pct:5.1f}%)  {'#'*int(pct/2)}")
    print()
    print("  NOTE: Dataset is small/synthetic. class_weight='balanced' compensates.")

# ── 3. Train/test split ───────────────────────────────────────────────────────
def split_data(X, y):
    section("TRAIN / TEST SPLIT")
    min_cls = y.value_counts().min()
    strat = y if min_cls >= 2 else None
    if strat is None:
        print(f"  [WARNING] Smallest class={min_cls} sample(s). Stratification skipped.")
    else:
        print("  Stratified split used (all classes >= 2 samples).")
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.20,
                                               random_state=42, stratify=strat)
    print(f"  Training samples : {len(X_tr)}")
    print(f"  Test samples     : {len(X_te)}")
    return X_tr, X_te, y_tr, y_te

# ── 4. Train ──────────────────────────────────────────────────────────────────
def train_model(X_tr, y_tr):
    section("TRAINING  RandomForestClassifier")
    print("  n_estimators=200  random_state=42  class_weight='balanced'")
    m = RandomForestClassifier(n_estimators=200, random_state=42,
                               class_weight="balanced", n_jobs=-1)
    m.fit(X_tr, y_tr)
    print("  Training complete.")
    return m

# ── 5. Evaluate ───────────────────────────────────────────────────────────────
def evaluate(model, X_te, y_te):
    section("SYNTHETIC DATASET VALIDATION")
    print("  [!] These metrics reflect reproduction of SYNTHETIC rules,")
    print("      NOT real-world flood prediction performance.")
    print()
    y_pred = model.predict(X_te)
    acc = accuracy_score(y_te, y_pred)
    print(f"  Synthetic Dataset Validation Accuracy : {acc*100:.1f}%")
    print()
    print("  Classification Report (Synthetic Data Only):")
    print(DIV2)
    print(classification_report(y_te, y_pred, labels=["Low","Medium","High"], zero_division=0))
    cm = confusion_matrix(y_te, y_pred, labels=["Low","Medium","High"])
    print("  Confusion Matrix  [rows=Actual | cols=Predicted]")
    print(f"  {'':12}  {'Low':>6}  {'Medium':>8}  {'High':>6}")
    print(DIV2)
    for i, lbl in enumerate(["Low","Medium","High"]):
        vals = "  ".join(f"{v:>6}" for v in cm[i])
        print(f"  {lbl:<12}  {vals}")
    print(DIV2)
    return acc

# ── 6. Feature importance ─────────────────────────────────────────────────────
def print_importance(model, features):
    section("FLOOD MODEL - FEATURE IMPORTANCE")
    print("  (Mean impurity decrease — reflects SYNTHETIC data patterns)")
    print()
    pairs = sorted(zip(features, model.feature_importances_), key=lambda x: x[1], reverse=True)
    for f, imp in pairs:
        print(f"  {f:<18}  {imp:.4f}  {'#'*int(imp*60)}")

# ── 7. Predict single row ─────────────────────────────────────────────────────
def predict_row(model, row, features):
    X_row = row[features].values.reshape(1, -1)
    pred  = model.predict(X_row)[0]
    proba = model.predict_proba(X_row)[0]
    return pred, {cls: p for cls, p in zip(model.classes_, proba)}

# ── 8. General sanity checks ──────────────────────────────────────────────────
def general_sanity(model, df):
    section("GENERAL GEOGRAPHIC SANITY CHECK")
    for loc in ["Delhi", "Guwahati", "Mumbai", "Jaipur", "Leh"]:
        rows = df[df["district"]==loc]
        if rows.empty: print(f"  {loc}: NOT IN DATASET - skipped"); continue
        row = rows.iloc[0]
        pred, probs = predict_row(model, row, FEATURES)
        match = "[OK]" if pred == row[TARGET] else "[DIFF]"
        print(f"  {row['district']}, {row['state']}")
        print(f"  Actual: {row[TARGET]}  Predicted: {pred}  {match}")
        print("  Probs: " + " | ".join(f"{c}: {probs.get(c,0)*100:.1f}%" for c in ["Low","Medium","High"]))
        print()

# ── 9. Mountain validation ────────────────────────────────────────────────────
MOUNTAIN_GROUPS = {
    "UTTARAKHAND": ["Dehradun","Haridwar","Rishikesh","Nainital","Almora",
                    "Pithoragarh","Chamoli","Rudraprayag","Uttarkashi","Tehri Garhwal"],
    "HIMACHAL PRADESH": ["Shimla","Manali","Kullu","Mandi","Dharamsala","Chamba","Kinnaur"],
    "JAMMU & KASHMIR / LADAKH": ["Srinagar","Jammu","Anantnag","Baramulla","Leh","Kargil"],
    "NORTH-EASTERN HILLS": ["Gangtok","Itanagar","Tawang","Darjeeling","Kalimpong","Shillong","Aizawl","Kohima"],
}

def mountain_validation(model, df):
    section("HIMALAYAN / MOUNTAIN REGION VALIDATION")
    print("  [!] All values SYNTHETIC/DEMO. river_level = Normalized Index 0-10, NOT metres.")
    all_req  = [l for ls in MOUNTAIN_GROUPS.values() for l in ls]
    in_data  = [l for l in all_req if l in df["district"].values]
    missing  = [l for l in all_req if l not in df["district"].values]
    print(f"  Requested: {len(all_req)}  |  Found: {len(in_data)}  |  Missing: {len(missing)}")
    if missing: print(f"  Missing locations: {missing}")
    print()
    for grp, locs in MOUNTAIN_GROUPS.items():
        print(DIV2); print(f"  {grp}"); print(DIV2)
        for loc in locs:
            rows = df[df["district"]==loc]
            if rows.empty: print(f"    {loc:<22}: [NOT IN DATASET]"); continue
            row = rows.iloc[0]
            pred, probs = predict_row(model, row, FEATURES)
            match = "[OK]" if pred == row[TARGET] else "[DIFF]"
            print(f"    Location : {row['district']}, {row['state']}")
            print(f"      Rainfall         : {row['rainfall']:.1f} mm/month")
            print(f"      River Level Index: {row['river_level']:.2f} / 10")
            print(f"      Soil Moisture    : {row['soil_moisture']*100:.1f}%")
            print(f"      Elevation        : {row['elevation']:.0f} m")
            print(f"      Flood History    : {int(row['flood_history'])}")
            print(f"      Actual Demo Label: {row[TARGET]}")
            print(f"      Predicted        : {pred}  {match}")
            for cls in ["Low","Medium","High"]:
                p = probs.get(cls,0)
                print(f"      {cls:<8}: {p*100:5.1f}%  {'*'*int(p*30)}")
            print()
        print()

# ── 10. Save ──────────────────────────────────────────────────────────────────
def save_model(model, acc, y_tr, y_te):
    os.makedirs(MODEL_DIR, exist_ok=True)
    bundle = {"model": model, "features": FEATURES, "target": TARGET,
              "data_type": "synthetic_demo",
              "disclaimer": ("Trained on synthetic/demo data. Metrics verify the ML pipeline "
                             "only; NOT validated real-world disaster-forecasting performance.")}
    joblib.dump(bundle, MODEL_PATH)
    meta = {"model_type": "RandomForestClassifier", "features": FEATURES,
            "target": TARGET, "classes": list(model.classes_),
            "n_estimators": 200, "random_state": 42, "class_weight": "balanced",
            "n_train_samples": int(len(y_tr)), "n_test_samples": int(len(y_te)),
            "synthetic_validation_accuracy": round(float(acc), 4),
            "data_type": "synthetic_demo",
            "river_level_note": "river_level is a SYNTHETIC NORMALIZED INDEX (0-10), not real gauge metres.",
            "disclaimer": ("The current model is trained on synthetic labels generated from "
                           "environmental features. Evaluation metrics verify the ML pipeline "
                           "is functioning; they do not represent validated real-world disaster "
                           "forecasting performance.")}
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    section("MODEL SAVED")
    print(f"  Bundle  : {MODEL_PATH}")
    print(f"  Metadata: {META_PATH}")

# ── 11. Reload check ──────────────────────────────────────────────────────────
def verify_reload(df):
    section("MODEL RELOAD VERIFICATION")
    bundle = joblib.load(MODEL_PATH)
    m2, feats2 = bundle["model"], bundle["features"]
    row = df[df["district"]=="Guwahati"]
    row = row.iloc[0] if not row.empty else df.iloc[0]
    pred2, probs2 = predict_row(m2, row, feats2)
    print(f"  Test location : {row['district']}, {row['state']}")
    print(f"  Predicted     : {pred2}")
    for cls in ["Low","Medium","High"]:
        print(f"    {cls:<8}: {probs2.get(cls,0)*100:5.1f}%")
    print("  [OK] Reload successful - saved model works correctly.")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(); print(DIV)
    print("  ResQ Shield - Phase 2: Flood Model Training")
    print(DIV)
    print("  [!] SYNTHETIC/DEMO DATA PIPELINE - NOT a real early-warning system.")
    df = load_and_validate(DATA_PATH)
    X = df[FEATURES].copy(); y = df[TARGET].copy()
    print_class_dist(y)
    X_tr, X_te, y_tr, y_te = split_data(X, y)
    model = train_model(X_tr, y_tr)
    acc = evaluate(model, X_te, y_te)
    print_importance(model, FEATURES)
    general_sanity(model, df)
    mountain_validation(model, df)
    save_model(model, acc, y_tr, y_te)
    verify_reload(df)
    print(); print(DIV)
    print("  Phase 2 complete. Next: python ml/train_landslide.py")
    print(DIV); print()

if __name__ == "__main__":
    main()
