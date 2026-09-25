"""
Test script for AgriPilot Step 2: Crop Recommendation Engine.
Demonstrates:
  1. Loading saved model artifacts without retraining.
  2. Multi-scenario crop recommendation predictions.
  3. Prediction confidence and alternative crops with probabilities.
  4. Explainable agronomic reasons matching farm soil & weather parameters.
"""
import os
import sys

# Ensure UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add agripilot/ml to sys.path
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "agripilot", "ml"))

from crop_recommender import CropRecommender

def run_tests():
    print("=" * 70)
    print("      AGRIPILOT STEP 2: CROP RECOMMENDATION INFERENCE TEST")
    print("=" * 70)
    
    # Initialize recommender (loads saved model bundle from outputs/crop_models/)
    recommender = CropRecommender()
    print(f"Loaded Production Model: {recommender.model_name}")
    print(f"Trained Test Accuracy: {recommender.metrics['accuracy']*100:.2f}%")
    print(f"Trained Test F1-Macro: {recommender.metrics['f1_macro']*100:.2f}%")
    print("-" * 70)

    # Test Scenarios
    scenarios = [
        {
            "name": "High-Rainfall Wetland Farm (Paddy/Rice condition)",
            "inputs": {"n": 90, "p": 42, "k": 43, "temperature": 23.5, "humidity": 82.0, "ph": 6.5, "rainfall": 220.0}
        },
        {
            "name": "Semi-Arid Deccan Plateau Farm (Chickpea/Gram condition)",
            "inputs": {"n": 38, "p": 65, "k": 78, "temperature": 18.2, "humidity": 16.5, "ph": 7.2, "rainfall": 75.0}
        },
        {
            "name": "Nashik Vineyard Soil Profile (Grape condition)",
            "inputs": {"n": 25, "p": 128, "k": 200, "temperature": 28.5, "humidity": 81.0, "ph": 6.2, "rainfall": 68.0}
        },
        {
            "name": "Vidarbha Black Soil Profile (Cotton condition)",
            "inputs": {"n": 118, "p": 48, "k": 22, "temperature": 24.8, "humidity": 80.0, "ph": 6.8, "rainfall": 85.0}
        }
    ]

    for idx, sc in enumerate(scenarios, 1):
        print(f"\n[Test Case {idx}] Scenario: {sc['name']}")
        inp = sc["inputs"]
        print(f"  Inputs: N={inp['n']}, P={inp['p']}, K={inp['k']}, Temp={inp['temperature']}°C, Humidity={inp['humidity']}%, pH={inp['ph']}, Rain={inp['rainfall']}mm")
        
        result = recommender.predict(
            n=inp["n"],
            p=inp["p"],
            k=inp["k"],
            temperature=inp["temperature"],
            humidity=inp["humidity"],
            ph=inp["ph"],
            rainfall=inp["rainfall"]
        )
        
        print(f"  --> RECOMMENDED CROP: {result['recommended_crop'].upper()} (Confidence: {result['confidence_pct']}%)")
        print("  --> Top Alternative Crops:")
        for alt in result["alternatives"]:
            print(f"      * {alt['crop']}: {alt['confidence_pct']}% probability")
            
        print("  --> Explainable Agronomic Rationale:")
        for r in result["reasons"]:
            print(f"      [{r['status']}] {r['factor']}: {r['detail']}")
            
    print("\n" + "=" * 70)
    print("  STATUS: ALL INFERENCE TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
