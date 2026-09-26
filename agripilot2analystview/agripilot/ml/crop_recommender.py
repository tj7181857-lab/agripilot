"""
AgriPilot :: Crop Recommendation ML Engine.

Trains and evaluates multi-class crop recommendation models on the genuine
Indian Agricultural Crop Recommendation dataset (2,200 rows, 22 crops, 7 features):
  - Model 1: Decision Tree Classifier
  - Model 2: Random Forest Classifier (Primary production model)
  - Model 3: Gradient Boosting Classifier

Calculates genuine test-set metrics (Accuracy, Precision, Recall, F1, Confusion Matrix,
and Feature Importance) with no hard-coded values.
Saves trained model artifacts to outputs/crop_models/ and evaluation results to
outputs/crop_model_comparison.json.
Provides an explainable recommendation inference interface.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

# Ensure UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Resolve project base directory
HERE = os.path.dirname(os.path.abspath(__file__))
# Check if HERE is agripilot/ml or agripilot/agripilot/ml
if os.path.basename(HERE) == "ml":
    PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
else:
    PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))

DATA_PATH = os.path.join(PROJECT_ROOT, "data", "crop_recommendation.csv")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
MODELS_DIR = os.path.join(OUTPUT_DIR, "crop_models")

FEATURE_NAMES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]

FEATURE_LABELS = {
    "N": "Nitrogen (N)",
    "P": "Phosphorus (P)",
    "K": "Potassium (K)",
    "temperature": "Temperature (°C)",
    "humidity": "Relative Humidity (%)",
    "ph": "Soil pH",
    "rainfall": "Rainfall (mm)",
}


def load_dataset() -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Load and validate the genuine crop recommendation dataset."""
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Crop recommendation dataset not found at: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    assert all(c in df.columns for c in FEATURE_NAMES + ["label"]), (
        f"Dataset must contain {FEATURE_NAMES + ['label']}, found {list(df.columns)}"
    )
    X = df[FEATURE_NAMES]
    y = df["label"]
    return df, X, y


def train_and_evaluate(
    test_size: float = 0.20,
    random_state: int = 42,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Train Decision Tree, Random Forest, and Gradient Boosting models
    on stratified train/test split and calculate authentic metrics.
    """
    df, X, y = load_dataset()
    classes = sorted(y.unique().tolist())

    # Stratified train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    if verbose:
        print(f"Dataset: {len(df)} samples, {len(FEATURE_NAMES)} features, {len(classes)} classes")
        print(f"Split: {len(X_train)} train samples, {len(X_test)} test samples ({int(test_size*100)}%)")

    models = {
        "decision_tree": {
            "name": "Decision Tree",
            "estimator": DecisionTreeClassifier(
                criterion="gini",
                max_depth=12,
                min_samples_split=4,
                min_samples_leaf=2,
                random_state=random_state,
            )
        },
        "random_forest": {
            "name": "Random Forest",
            "estimator": RandomForestClassifier(
                n_estimators=150,
                max_depth=15,
                min_samples_split=3,
                min_samples_leaf=1,
                random_state=random_state,
                n_jobs=-1,
            )
        },
        "gradient_boosting": {
            "name": "Gradient Boosting",
            "estimator": GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=4,
                subsample=0.85,
                random_state=random_state,
            )
        },
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    results = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dataset_file": "data/crop_recommendation.csv",
            "total_samples": len(df),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "test_size": test_size,
            "random_state": random_state,
            "features": FEATURE_NAMES,
            "classes": classes,
            "num_classes": len(classes),
        },
        "comparison": {},
        "per_class": {},
        "confusion_matrices": {},
        "feature_importance": {},
    }

    best_model_key = None
    best_f1 = -1.0

    # Calculate crop baseline centroids for agronomic explainability
    crop_profiles = {}
    for crop in classes:
        crop_data = df[df["label"] == crop][FEATURE_NAMES]
        crop_profiles[crop] = {
            "means": {feat: round(float(crop_data[feat].mean()), 2) for feat in FEATURE_NAMES},
            "mins": {feat: round(float(crop_data[feat].min()), 2) for feat in FEATURE_NAMES},
            "maxs": {feat: round(float(crop_data[feat].max()), 2) for feat in FEATURE_NAMES},
            "stds": {feat: round(float(crop_data[feat].std()), 2) for feat in FEATURE_NAMES},
        }

    for key, item in models.items():
        name = item["name"]
        clf = item["estimator"]

        t0 = time.time()
        clf.fit(X_train, y_train)
        train_time = round(time.time() - t0, 3)

        t0 = time.time()
        y_pred = clf.predict(X_test)
        pred_time = round(time.time() - t0, 4)

        # Genuine metrics calculation
        acc = float(accuracy_score(y_test, y_pred))
        prec_macro = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
        prec_weighted = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
        rec_macro = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
        rec_weighted = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
        f1_m = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        f1_w = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

        cm = confusion_matrix(y_test, y_pred, labels=classes).tolist()
        report = classification_report(y_test, y_pred, labels=classes, output_dict=True, zero_division=0)

        # Feature importances
        if hasattr(clf, "feature_importances_"):
            importances = clf.feature_importances_.tolist()
            feat_imp = [
                {"feature": f, "importance": round(float(imp), 4), "label": FEATURE_LABELS[f]}
                for f, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
            ]
        else:
            feat_imp = []

        # Model evaluation payload
        results["comparison"][key] = {
            "model_name": name,
            "accuracy": round(acc, 4),
            "precision_macro": round(prec_macro, 4),
            "precision_weighted": round(prec_weighted, 4),
            "recall_macro": round(rec_macro, 4),
            "recall_weighted": round(rec_weighted, 4),
            "f1_macro": round(f1_m, 4),
            "f1_weighted": round(f1_w, 4),
            "training_time_sec": train_time,
            "inference_time_sec": pred_time,
            "top_feature": feat_imp[0]["feature"] if feat_imp else None,
        }

        results["confusion_matrices"][key] = cm
        results["feature_importance"][key] = feat_imp
        results["per_class"][key] = {
            cls: {
                "precision": round(float(report[cls]["precision"]), 4),
                "recall": round(float(report[cls]["recall"]), 4),
                "f1_score": round(float(report[cls]["f1-score"]), 4),
                "support": int(report[cls]["support"]),
            }
            for cls in classes if cls in report
        }

        # Save individual model artifact
        model_artifact_path = os.path.join(MODELS_DIR, f"{key}.joblib")
        joblib.dump(clf, model_artifact_path)

        if f1_m > best_f1:
            best_f1 = f1_m
            best_model_key = key

        if verbose:
            print(f"[{name}] Acc: {acc*100:.2f}% | F1-Macro: {f1_m*100:.2f}% | Prec: {prec_macro*100:.2f}% | Rec: {rec_macro*100:.2f}% (Trained in {train_time}s)")

    # Save production bundle with the best performing model
    best_clf = models[best_model_key]["estimator"]
    production_bundle = {
        "model_key": best_model_key,
        "model_name": models[best_model_key]["name"],
        "model": best_clf,
        "features": FEATURE_NAMES,
        "classes": classes,
        "metrics": results["comparison"][best_model_key],
        "crop_profiles": crop_profiles,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    bundle_path = os.path.join(MODELS_DIR, "crop_recommender_bundle.joblib")
    joblib.dump(production_bundle, bundle_path)

    # Save crop_profiles in comparison results for explainability
    results["crop_profiles"] = crop_profiles
    results["best_model"] = best_model_key

    # Save structured JSON for Analyst Dashboard
    comparison_json_path = os.path.join(OUTPUT_DIR, "crop_model_comparison.json")
    with open(comparison_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"\nSaved models to: {MODELS_DIR}/")
        print(f"Saved comparison JSON to: {comparison_json_path}")
        print(f"Best Model Selected: {models[best_model_key]['name']} (F1: {best_f1*100:.2f}%)")

    return results


class CropRecommender:
    """
    Production inference engine for Crop Recommendation.
    Loads saved model artifacts without retraining.
    """

    def __init__(self, bundle_path: Optional[str] = None):
        if bundle_path is None:
            bundle_path = os.path.join(MODELS_DIR, "crop_recommender_bundle.joblib")

        if not os.path.exists(bundle_path):
            # If not yet trained, run training once
            train_and_evaluate(verbose=False)

        self.bundle = joblib.load(bundle_path)
        self.model = self.bundle["model"]
        self.features = self.bundle["features"]
        self.classes = self.bundle["classes"]
        self.metrics = self.bundle["metrics"]
        self.crop_profiles = self.bundle["crop_profiles"]
        self.model_name = self.bundle["model_name"]

    def predict(
        self,
        n: float,
        p: float,
        k: float,
        temperature: float,
        humidity: float,
        ph: float,
        rainfall: float,
        top_k: int = 4
    ) -> Dict[str, Any]:
        """
        Predict recommended crop and alternative candidates with probability scores,
        along with domain-grounded agronomic rationale.
        """
        input_data = pd.DataFrame([{
            "N": float(n),
            "P": float(p),
            "K": float(k),
            "temperature": float(temperature),
            "humidity": float(humidity),
            "ph": float(ph),
            "rainfall": float(rainfall),
        }])[self.features]

        # Probability distribution across all 22 crops
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(input_data)[0]
            top_indices = np.argsort(probs)[::-1][:top_k]
            top_crops = [self.classes[i] for i in top_indices]
            top_probs = [float(probs[i]) for i in top_indices]
        else:
            pred = self.model.predict(input_data)[0]
            top_crops = [pred]
            top_probs = [1.0]

        primary_crop = top_crops[0]
        confidence = top_probs[0]

        alternatives = [
            {"crop": c, "probability": round(p, 4), "confidence_pct": round(p * 100, 1)}
            for c, p in zip(top_crops[1:], top_probs[1:]) if p > 0.005
        ]

        # Explainability: Compare input features with optimal crop profile
        reasons = self._generate_reasons(primary_crop, input_data.iloc[0])

        return {
            "recommended_crop": primary_crop,
            "confidence": round(confidence, 4),
            "confidence_pct": round(confidence * 100, 1),
            "model_used": self.model_name,
            "alternatives": alternatives,
            "input_values": input_data.iloc[0].to_dict(),
            "reasons": reasons,
            "optimal_profile": self.crop_profiles.get(primary_crop, {}).get("means", {}),
        }

    def _generate_reasons(self, crop: str, inputs: pd.Series) -> List[Dict[str, Any]]:
        """Explain why the crop was recommended based on optimal parameters."""
        profile = self.crop_profiles.get(crop, {})
        if not profile:
            return ["Optimal agronomic parameters match this crop."]

        means = profile.get("means", {})
        mins = profile.get("mins", {})
        maxs = profile.get("maxs", {})

        reasons = []

        # Soil Nutrients (NPK) evaluation
        n_val = inputs["N"]
        p_val = inputs["P"]
        k_val = inputs["K"]
        if mins.get("N", 0) <= n_val <= maxs.get("N", 140):
            reasons.append({
                "factor": "Soil Nitrogen (N)",
                "status": "Optimal",
                "detail": f"Soil Nitrogen level ({n_val:.0f} kg/ha) matches {crop}'s ideal requirement (avg {means.get('N', 0):.0f} kg/ha)."
            })
        elif n_val < mins.get("N", 0):
            reasons.append({
                "factor": "Soil Nitrogen (N)",
                "status": "Moderate",
                "detail": f"Soil Nitrogen ({n_val:.0f} kg/ha) is slightly below average ({means.get('N', 0):.0f} kg/ha); supplementary urea recommended."
            })
        else:
            reasons.append({
                "factor": "Soil Nitrogen (N)",
                "status": "High",
                "detail": f"Ample soil Nitrogen available for vegetative growth."
            })

        # Moisture & Rainfall
        rf = inputs["rainfall"]
        if mins.get("rainfall", 0) <= rf <= maxs.get("rainfall", 300):
            reasons.append({
                "factor": "Rainfall Suitability",
                "status": "Optimal",
                "detail": f"Rainfall level ({rf:.1f} mm) is well-suited for {crop} (typical range: {mins.get('rainfall', 0):.0f}-{maxs.get('rainfall', 0):.0f} mm)."
            })
        else:
            reasons.append({
                "factor": "Rainfall Suitability",
                "status": "Managed",
                "detail": f"Rainfall ({rf:.1f} mm) deviates from natural range; requires controlled irrigation management."
            })

        # Temperature
        temp = inputs["temperature"]
        if mins.get("temperature", 10) <= temp <= maxs.get("temperature", 45):
            reasons.append({
                "factor": "Thermal Comfort",
                "status": "Optimal",
                "detail": f"Ambient temperature ({temp:.1f}°C) is within the favorable vegetative threshold ({mins.get('temperature', 0):.1f}-{maxs.get('temperature', 0):.1f}°C)."
            })

        # Soil pH
        ph = inputs["ph"]
        if mins.get("ph", 4.0) <= ph <= maxs.get("ph", 9.0):
            reasons.append({
                "factor": "Soil pH",
                "status": "Optimal",
                "detail": f"Soil pH ({ph:.2f}) falls within optimal nutrient uptake window for {crop}."
            })

        # Relative Humidity
        hum = inputs["humidity"]
        if mins.get("humidity", 10) <= hum <= maxs.get("humidity", 100):
            reasons.append({
                "factor": "Atmospheric Humidity",
                "status": "Optimal",
                "detail": f"Relative humidity ({hum:.1f}%) supports healthy transpiration without excessive disease pressure."
            })

        return reasons


def main():
    print("=" * 70)
    print("      AGRIPILOT: CROP RECOMMENDATION MODEL TRAINING & EVALUATION")
    print("=" * 70)
    res = train_and_evaluate(test_size=0.20, random_state=42, verbose=True)
    print("\nSummary Comparison Table:")
    comp_df = pd.DataFrame(res["comparison"]).T
    print(comp_df[["model_name", "accuracy", "f1_macro", "precision_macro", "recall_macro", "training_time_sec"]])
    print("=" * 70)


if __name__ == "__main__":
    main()
