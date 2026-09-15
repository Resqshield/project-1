# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
ResQ Shield - Phase 3: Landslide Risk Model Training
======================================================
Trains a RandomForestClassifier to predict landslide_risk (Low/Medium/High)
from terrain + environmental features in master_dataset.csv.

!! IMPORTANT DISCLAIMER !!
   - Training data is ENTIRELY SYNTHETIC / DEMO DATA.
   - landslide_risk labels were derived from a weighted formula on the same
     input features. The model learns to reproduce that synthetic rule,
     NOT real-world landslide dynamics.
   - Accuracy figures are "Synthetic Dataset Validation Accuracy".
     They do NOT represent validated real-world landslide-forecasting performance.
   - NOT suitable for operational early-warning or policy decisions.

Feature note:
   slope         = synthetic slope in degrees (0-45)
   elevation     = metres above sea level
   soil_moisture = synthetic ratio 0-1
   rainfall      = synthetic mm/month
   landslide_history = binary 0/1

Run:
    python ml/train_landslide.py

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
MODEL_PATH   = os.path.join(MODEL_DIR, "landslide_model.pkl")
META_PATH    = os.path.join(MODEL_DIR, "landslide_model_metadata.json")

# ── Features / target ─────────────────────────────────────────────────────────
FEATURES = ["rainfall", "soil_moisture", "slope", "elevation", "landslide_history"]
TARGET   = "landslide_risk"

# Explicitly excluded (must never be used as ML features)
EXCLUDED = ["district", "state", "latitude", "longitude",
            "flood_risk", "flood_history", "river_level"]

DIV  = "=" * 62
DIV2 = "-" * 62

def section(t): print(); print(DIV); print(f"  {t}"); print(DIV)

# ── 1. Load & validate ────────────────────────────────────────────────────────
def load_and_validate(path):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset not found: {path}\n"
            "Run: python ml/prepare_data.py  first."
        )
    df = pd.read_csv(path)
    section("DATA LOADING & VALIDATION")
    print(f"  Loaded : {path}")
    print(f"  Shape  : {df.shape[0]} rows x {df.shape[1]} columns")

    required = FEATURES + [TARGET]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Required columns missing from CSV: {missing_cols}")
    print("  Required columns check : PASSED")
    print(f"  Features used  : {FEATURES}")
    print(f"  Target         : {TARGET}")
    print(f"  Excluded cols  : {EXCLUDED}")

    mv = df[required].isnull().sum()
    mv_found = mv[mv > 0]
    if not mv_found.empty:
        print(f"\n  [WARNING] Missing values detected:")
        print(mv_found.to_string())
        df = df.dropna(subset=required)
        print(f"  Rows after dropping NaN: {len(df)}")
    else:
        print("  Missing values check   : NONE FOUND - OK")
    return df

# ── 2. Mountain terrain audit ─────────────────────────────────────────────────
TERRAIN_CHECKS = [
    # (district, min_slope, max_slope, min_elev, max_rainfall, note)
    ("Haridwar",      0,  12, 200,  400, "foothill town, should not have extreme slope/elevation"),
    ("Chamoli",      20,  45, 800,  400, "high Garhwal Himalaya, steep terrain expected"),
    ("Rudraprayag",  15,  45, 500,  400, "Garhwal confluence district, should be hilly"),
    ("Uttarkashi",   15,  45, 800,  400, "upper Garhwal, steep expected"),
    ("Pithoragarh",  15,  45, 1200, 400, "Kumaon Himalaya, steep terrain"),
    ("Leh",           5,  45, 3000,  80, "Ladakh, very high elevation, low rainfall"),
    ("Kargil",        5,  45, 2000,  80, "Ladakh, high elevation, arid"),
    ("Jaipur",        0,  10, 300,  300, "Rajasthan plains, very low slope"),
    ("Patna",         0,   5,  30,  400, "Bihar plains, almost flat"),
    ("Mumbai",        0,   8,   0,  600, "coastal low terrain"),
]

def terrain_audit(df):
    section("MOUNTAIN TERRAIN DATA QUALITY AUDIT")
    print("  Checking geographically sensible ranges for key locations.")
    print("  [!] All values are SYNTHETIC/DEMO - audit checks plausibility only.")
    print()

    issues = []
    for (dist, min_sl, max_sl, min_el, max_rf, note) in TERRAIN_CHECKS:
        row = df[df["district"] == dist]
        if row.empty:
            print(f"  {dist:<20}: NOT IN DATASET")
            continue
        r = row.iloc[0]
        sl  = r["slope"]
        el  = r["elevation"]
        rf  = r["rainfall"]
        sm  = r["soil_moisture"]
        flags = []
        if not (min_sl <= sl <= max_sl):
            flags.append(f"slope={sl:.1f} expected [{min_sl},{max_sl}]")
        if el < min_el:
            flags.append(f"elevation={el:.0f}m expected >={min_el}m")
        if dist in ("Leh","Kargil") and rf > max_rf:
            flags.append(f"rainfall={rf:.1f} seems HIGH for arid Ladakh (expected <={max_rf})")

        status = "[SUSPICIOUS]" if flags else "[OK]"
        print(f"  {dist:<20}: slope={sl:5.1f}deg  elev={el:6.0f}m  "
              f"rain={rf:5.1f}mm  sm={sm:.2f}  {status}")
        if flags:
            for f in flags: print(f"    >> {f}")
            issues.append((dist, flags, note))

    print()
    if issues:
        print(f"  [!] {len(issues)} suspicious rows found:")
        for dist, flags, note in issues:
            print(f"    {dist}: {note}")
        print("  These will be documented. Terrain values will be corrected")
        print("  in prepare_data.py only if clearly unrealistic.")
    else:
        print("  All checked locations appear geographically plausible.")
        print("  No corrections to prepare_data.py required.")
    return issues

# ── 3. Class distribution ─────────────────────────────────────────────────────
def print_class_dist(y):
    section("LANDSLIDE RISK CLASS DISTRIBUTION")
    counts = y.value_counts(); total = len(y)
    for cls in ["Low", "Medium", "High"]:
        n = counts.get(cls, 0); pct = 100.0 * n / total
        bar = "#" * int(pct / 2)
        print(f"  {cls:<8}: {n:>3}  ({pct:5.1f}%)  {bar}")
    print()
    min_cls = counts.min()
    if min_cls < 5:
        print(f"  [WARNING] Smallest class has only {min_cls} sample(s).")
        print("  Model may underperform on minority class. class_weight='balanced' helps.")
    else:
        print(f"  class_weight='balanced' will compensate for imbalance.")

# ── 4. Train/test split ───────────────────────────────────────────────────────
def split_data(X, y):
    section("TRAIN / TEST SPLIT")
    min_cls = y.value_counts().min()
    strat   = y if min_cls >= 2 else None
    if strat is None:
        print(f"  [WARNING] Smallest class has {min_cls} sample. Stratification skipped.")
    else:
        print("  Stratified split used (all classes >= 2 samples).")
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=strat
    )
    print(f"  Training samples : {len(X_tr)}")
    print(f"  Test samples     : {len(X_te)}")
    return X_tr, X_te, y_tr, y_te

# ── 5. Train ──────────────────────────────────────────────────────────────────
def train_model(X_tr, y_tr):
    section("TRAINING  RandomForestClassifier")
    print("  n_estimators=200  random_state=42  class_weight='balanced'  n_jobs=-1")
    m = RandomForestClassifier(
        n_estimators=200, random_state=42,
        class_weight="balanced", n_jobs=-1
    )
    m.fit(X_tr, y_tr)
    print("  Training complete.")
    return m

# ── 6. Evaluate ───────────────────────────────────────────────────────────────
def evaluate(model, X_te, y_te):
    section("SYNTHETIC DATASET VALIDATION")
    print("  [!] The current landslide model is trained on synthetic labels generated")
    print("      from environmental features. Evaluation metrics verify that the ML")
    print("      pipeline is functioning; they do NOT represent validated real-world")
    print("      landslide forecasting performance.")
    print()
    y_pred = model.predict(X_te)
    acc    = accuracy_score(y_te, y_pred)
    print(f"  Synthetic Dataset Validation Accuracy : {acc*100:.1f}%")
    print()
    print("  Classification Report (Synthetic Data Only):")
    print(DIV2)
    print(classification_report(y_te, y_pred,
                                labels=["Low","Medium","High"], zero_division=0))
    cm = confusion_matrix(y_te, y_pred, labels=["Low","Medium","High"])
    print("  Confusion Matrix  [rows=Actual | cols=Predicted]")
    print(f"  {'':12}  {'Low':>6}  {'Medium':>8}  {'High':>6}")
    print(DIV2)
    for i, lbl in enumerate(["Low","Medium","High"]):
        vals = "  ".join(f"{v:>6}" for v in cm[i])
        print(f"  {lbl:<12}  {vals}")
    print(DIV2)
    return acc

# ── 7. Feature importance ─────────────────────────────────────────────────────
def print_importance(model):
    section("LANDSLIDE MODEL - FEATURE IMPORTANCE")
    print("  (Mean impurity decrease across all trees)")
    print("  NOTE: Reflects SYNTHETIC data patterns, not proven causal links.")
    print()
    pairs = sorted(zip(FEATURES, model.feature_importances_),
                   key=lambda x: x[1], reverse=True)
    for feat, imp in pairs:
        bar = "#" * int(imp * 60)
        print(f"  {feat:<22}  {imp:.4f}  {bar}")

# ── 8. Predict single row helper ──────────────────────────────────────────────
def predict_row(model, row):
    X_row = row[FEATURES].values.reshape(1, -1)
    pred  = model.predict(X_row)[0]
    proba = model.predict_proba(X_row)[0]
    probs = {cls: p for cls, p in zip(model.classes_, proba)}
    return pred, probs

# ── 9. Mountain validation ────────────────────────────────────────────────────
MOUNTAIN_GROUPS = {
    "UTTARAKHAND": [
        "Dehradun","Haridwar","Rishikesh","Nainital","Almora",
        "Pithoragarh","Chamoli","Rudraprayag","Uttarkashi","Tehri Garhwal",
    ],
    "HIMACHAL PRADESH": [
        "Shimla","Manali","Kullu","Mandi","Dharamsala","Chamba","Kinnaur",
    ],
    "JAMMU & KASHMIR / LADAKH": [
        "Srinagar","Jammu","Anantnag","Baramulla","Leh","Kargil",
    ],
    "SIKKIM / ARUNACHAL PRADESH": [
        "Gangtok","Itanagar","Tawang",
    ],
    "NORTH-EASTERN HILLS": [
        "Darjeeling","Kalimpong","Shillong","Aizawl","Kohima",
    ],
}

def mountain_validation(model, df):
    section("HIMALAYAN / MOUNTAIN LANDSLIDE VALIDATION")
    print("  [!] All values SYNTHETIC/DEMO. Not real sensor readings.")
    print()
    all_req = [l for ls in MOUNTAIN_GROUPS.values() for l in ls]
    found   = [l for l in all_req if l in df["district"].values]
    missing = [l for l in all_req if l not in df["district"].values]
    print(f"  Requested mountain locations : {len(all_req)}")
    print(f"  Found in dataset             : {len(found)}")
    print(f"  Missing (not in dataset)     : {len(missing)}")
    if missing:
        print(f"  Missing list: {missing}")
    print()

    for grp, locs in MOUNTAIN_GROUPS.items():
        print(DIV2)
        print(f"  {grp}")
        print(DIV2)
        for loc in locs:
            rows = df[df["district"] == loc]
            if rows.empty:
                print(f"    {loc:<22}: [NOT IN DATASET]")
                continue
            row = rows.iloc[0]
            pred, probs = predict_row(model, row)
            actual = row[TARGET]
            match  = "[OK]" if pred == actual else "[DIFF]"
            print(f"    Location : {row['district']}, {row['state']}")
            print(f"      Rainfall         : {row['rainfall']:.1f} mm/month")
            print(f"      Soil Moisture    : {row['soil_moisture']*100:.1f}%")
            print(f"      Slope            : {row['slope']:.1f} degrees")
            print(f"      Elevation        : {row['elevation']:.0f} m")
            print(f"      Landslide History: {int(row['landslide_history'])}")
            print(f"      Actual Demo Label   : {actual}")
            print(f"      Predicted Risk      : {pred}  {match}")
            for cls in ["Low","Medium","High"]:
                p = probs.get(cls, 0.0)
                bar = "*" * int(p * 30)
                print(f"      {cls:<8}: {p*100:5.1f}%  {bar}")
            print()
        print()

# ── 10. Plains/coastal comparison ─────────────────────────────────────────────
PLAINS_LOCS = ["Delhi", "Jaipur", "Patna", "Mumbai", "Chennai"]

def plains_comparison(model, df):
    section("PLAINS / COASTAL COMPARISON")
    print("  Verifying that high rainfall alone does not drive High landslide risk")
    print("  when slope is low. This is the key flood-vs-landslide distinction.")
    print()
    print(f"  {'Location':<16} {'State':<20} {'Slope':>6} {'Rain':>6} {'Elev':>6} "
          f"{'Actual':<8} {'Predicted':<10} {'Low%':>6} {'Med%':>6} {'High%':>6}")
    print(DIV2)
    for loc in PLAINS_LOCS:
        rows = df[df["district"] == loc]
        if rows.empty:
            print(f"  {loc:<16}: NOT IN DATASET")
            continue
        row = rows.iloc[0]
        pred, probs = predict_row(model, row)
        actual = row[TARGET]
        lp = probs.get("Low",0)*100; mp = probs.get("Medium",0)*100; hp = probs.get("High",0)*100
        print(f"  {row['district']:<16} {row['state']:<20} {row['slope']:>5.1f} "
              f"{row['rainfall']:>5.0f} {row['elevation']:>5.0f} "
              f"{actual:<8} {pred:<10} {lp:>5.1f} {mp:>5.1f} {hp:>5.1f}")
    print()
    print("  Key insight: Low-slope plains (Patna, Delhi) should stay Low/Medium")
    print("  even with moderate rainfall — slope is the dominant landslide driver.")

# ── 11. Flood vs Landslide conceptual sanity table ────────────────────────────
def sanity_table():
    section("FLOOD vs LANDSLIDE CONCEPTUAL DISTINCTION (Explanatory Only)")
    print("  This table explains expected risk patterns. It does NOT alter model output.")
    print()
    rows = [
        ("Haridwar",    "Uttarakhand",  "Foothill / river plain",  "Flood risk relevant; low landslide slope"),
        ("Chamoli",     "Uttarakhand",  "High Himalayan mountain", "Landslide risk dominant; steep terrain"),
        ("Leh",         "Ladakh",       "High dry mountain",       "High elevation but arid; not monsoon-driven"),
        ("Mumbai",      "Maharashtra",  "Low coastal terrain",     "Heavy rain = flood risk, not mountain landslide"),
        ("Itanagar",    "Arunachal",    "Hill district NE India",  "High rain + slope = both risks possible"),
        ("Jaipur",      "Rajasthan",    "Dry plains",              "Low rain + low slope = generally Low both"),
    ]
    print(f"  {'Location':<14} {'State':<15} {'Terrain Type':<28} {'Expected Distinction'}")
    print(DIV2)
    for loc, st, terrain, distinction in rows:
        print(f"  {loc:<14} {st:<15} {terrain:<28} {distinction}")

# ── 12. Save model ────────────────────────────────────────────────────────────
def save_model(model, acc, y_tr, y_te):
    os.makedirs(MODEL_DIR, exist_ok=True)
    bundle = {
        "model":     model,
        "features":  FEATURES,
        "target":    TARGET,
        "data_type": "synthetic_demo",
        "disclaimer": (
            "The current landslide model is trained on synthetic labels generated "
            "from environmental features. Evaluation metrics verify that the ML "
            "pipeline is functioning; they do not represent validated real-world "
            "landslide forecasting performance."
        ),
    }
    joblib.dump(bundle, MODEL_PATH)
    meta = {
        "model_type":   "RandomForestClassifier",
        "features":     FEATURES,
        "target":       TARGET,
        "classes":      list(model.classes_),
        "n_estimators": 200,
        "random_state": 42,
        "class_weight": "balanced",
        "n_train_samples": int(len(y_tr)),
        "n_test_samples":  int(len(y_te)),
        "synthetic_validation_accuracy": round(float(acc), 4),
        "data_type":    "synthetic_demo",
        "feature_notes": {
            "slope":            "Synthetic slope in degrees (0-45); key landslide driver",
            "elevation":        "Metres above sea level",
            "soil_moisture":    "Synthetic ratio 0-1",
            "rainfall":         "Synthetic monthly rainfall mm",
            "landslide_history":"Binary 0/1 historical occurrence",
        },
        "disclaimer": (
            "The current landslide model is trained on synthetic labels generated "
            "from environmental features. Evaluation metrics verify that the ML "
            "pipeline is functioning; they do not represent validated real-world "
            "landslide forecasting performance."
        ),
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    section("MODEL SAVED")
    print(f"  Bundle  : {MODEL_PATH}")
    print(f"  Metadata: {META_PATH}")
    print()
    print("  Bundle keys: 'model', 'features', 'target', 'data_type', 'disclaimer'")

# ── 13. Reload verification ───────────────────────────────────────────────────
def verify_reload(df):
    section("MODEL RELOAD VERIFICATION")
    print("  Reloading landslide_model.pkl and testing on a mountain location...")
    bundle2 = joblib.load(MODEL_PATH)
    m2, feats2 = bundle2["model"], bundle2["features"]
    for test_loc in ["Chamoli", "Rudraprayag", "Shimla"]:
        rows = df[df["district"] == test_loc]
        if not rows.empty:
            row = rows.iloc[0]; break
    else:
        row = df.iloc[0]
    pred2, probs2 = predict_row(m2, row)
    print(f"  Test location : {row['district']}, {row['state']}")
    print(f"  Slope={row['slope']:.1f}deg  Elev={row['elevation']:.0f}m  "
          f"Rain={row['rainfall']:.1f}mm")
    print(f"  Predicted Landslide Risk : {pred2}")
    print("  Probabilities (reloaded model):")
    for cls in ["Low","Medium","High"]:
        print(f"    {cls:<8}: {probs2.get(cls,0)*100:5.1f}%")
    print()
    print("  [OK] Reload successful - saved model works correctly.")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(); print(DIV)
    print("  ResQ Shield - Phase 3: Landslide Model Training")
    print(DIV)
    print("  [!] SYNTHETIC/DEMO DATA PIPELINE - NOT a real early-warning system.")
    print("  [!] Flood model (flood_model.pkl) is NOT modified or used here.")

    df = load_and_validate(DATA_PATH)
    terrain_audit(df)

    X = df[FEATURES].copy()
    y = df[TARGET].copy()

    print_class_dist(y)
    X_tr, X_te, y_tr, y_te = split_data(X, y)
    model = train_model(X_tr, y_tr)
    acc   = evaluate(model, X_te, y_te)
    print_importance(model)
    mountain_validation(model, df)
    plains_comparison(model, df)
    sanity_table()
    save_model(model, acc, y_tr, y_te)
    verify_reload(df)

    print(); print(DIV)
    print("  Phase 3 complete.")
    print("  Next: Phase 4 - python ml/generate_predictions.py")
    print(DIV); print()

if __name__ == "__main__":
    main()
