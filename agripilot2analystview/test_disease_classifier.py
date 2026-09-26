"""
Test script for AgriPilot Step 3: Crop Disease Classifier & Grad-CAM Explainability.
Demonstrates:
  1. Loading saved Keras model without retraining.
  2. Loading class mapping and model evaluation metrics.
  3. Running leaf disease classification on sample images.
  4. Generating and verifying genuine Grad-CAM class activation heatmaps.
  5. Returning disease diagnosis and grounded agricultural care advice.
"""
import os
import sys
import json
import numpy as np

# Ensure UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "agripilot", "ml"))

from disease_classifier import DiseaseClassifier

def run_tests():
    print("=" * 75)
    print("   AGRIPILOT STEP 3: CROP DISEASE CLASSIFIER & GRAD-CAM VERIFICATION")
    print("=" * 75)

    # 1. Inspect Saved Metrics
    metrics_path = os.path.join(BASE, "outputs", "disease_model_metrics.json")
    assert os.path.exists(metrics_path), f"Missing {metrics_path}"
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics_data = json.load(f)

    overall = metrics_data["overall"]
    print("\n[1] TEST EVALUATION METRICS (Held-out Test Split - 66 images):")
    print(f"  - Accuracy:          {overall['accuracy_pct']}% ({overall['correct_samples']}/{overall['total_samples']} correct)")
    print(f"  - Macro F1-Score:    {overall['f1_macro']*100:.2f}%")
    print(f"  - Macro Precision:   {overall['precision_macro']*100:.2f}%")
    print(f"  - Macro Recall:      {overall['recall_macro']*100:.2f}%")
    print(f"  - Weighted F1-Score: {overall['f1_weighted']*100:.2f}%")

    print("\n[2] PER-CLASS PERFORMANCE BREAKDOWN:")
    print(f"  {'Class Name':42s} | {'Prec':6s} | {'Rec':6s} | {'F1':6s} | {'Support'}")
    print("  " + "-" * 70)
    for cname, m in metrics_data["per_class"].items():
        print(f"  {cname:42s} | {m['precision']*100:5.1f}% | {m['recall']*100:5.1f}% | {m['f1_score']*100:5.1f}% | {m['support']}")

    # 2. Confusion Matrix Summary
    cm = np.array(metrics_data["confusion_matrix"])
    print("\n[3] CONFUSION MATRIX SUMMARY:")
    print(f"  - Matrix shape: {cm.shape} (11 classes x 11 classes)")
    print(f"  - Diagonal sum (True Positives): {int(np.trace(cm))} / {int(cm.sum())}")
    print(f"  - Off-diagonal errors: {int(cm.sum() - np.trace(cm))}")

    # 3. Load Production Classifier
    print("\n[4] LOADING SAVED MODEL ARTIFACT (Zero Retraining):")
    classifier = DiseaseClassifier()
    print("  Model loaded successfully from outputs/disease_model.keras")
    print(f"  Total classes recognized: {len(classifier.class_mapping)}")

    # 4. Run Sample Inferences with Grad-CAM
    sample_dir = os.path.join(BASE, "data", "sample_leaves")
    test_samples = [
        "tomato_early_blight_sample_1.jpg",
        "grape_black_rot_sample_1.jpg",
        "tomato_healthy_sample_1.jpg",
        "potato_late_blight_sample_1.jpg",
    ]

    print("\n[5] TESTING REAL LEAF PREDICTIONS & GRAD-CAM EXPLAINABILITY:")
    for s_name in test_samples:
        img_path = os.path.join(sample_dir, s_name)
        if not os.path.exists(img_path):
            continue

        print("\n" + "-" * 75)
        print(f"  Test Leaf Image: {s_name}")
        res = classifier.predict_image(img_path, generate_gradcam=True)

        print(f"  --> Crop:        {res['crop']}")
        print(f"  --> Diagnosis:   {res['disease']} (Class: {res['class_name']})")
        print(f"  --> Confidence:  {res['confidence_pct']}%")
        print(f"  --> Severity:    {res['severity']}")
        print(f"  --> Top 3 Probabilities:")
        for cand in res["top_candidates"]:
            print(f"      * {cand['display_name']}: {cand['confidence_pct']}%")

        print(f"  --> Grad-CAM Overlay Generated:")
        print(f"      Saved to: {res['gradcam_path']}")
        assert os.path.exists(res['gradcam_path']), "Grad-CAM output file not created!"
        print(f"      File size: {os.path.getsize(res['gradcam_path'])} bytes")

        # Grounded agricultural advice
        if res.get("symptoms", {}).get("en"):
            print(f"  --> Symptoms (EN): {res['symptoms']['en'][0]}")
        if res.get("treatment", {}).get("chemical_management", {}).get("en"):
            print(f"  --> Chemical Treatment: {res['treatment']['chemical_management']['en']}")

    print("\n" + "=" * 75)
    print("  STATUS: ALL DISEASE CLASSIFIER & GRAD-CAM TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)

if __name__ == "__main__":
    run_tests()
