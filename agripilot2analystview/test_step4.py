"""
AgriPilot Step 4 tests:
  SQLite CRUD, farm advisory fusion, multilingual assistant,
  crop/disease model integration, history, API, and Step 1–3 sanity.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "agripilot")
ML = os.path.join(PKG, "ml")
for p in (PKG, ML, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["AGRIPILOT_DB"] = os.path.join(tempfile.gettempdir(), "agripilot_step4_test.db")
if os.path.exists(os.environ["AGRIPILOT_DB"]):
    os.remove(os.environ["AGRIPILOT_DB"])

import db as store
from advisory import build_advisory, run_crop_recommendation
from assistant import answer_question, detect_language
from paths import CROP_BUNDLE, CROP_CSV, DISEASE_DATA_DIR, DISEASE_MODEL, KB_PATH
import server


class Step4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.init_db()
        cls.farm_id = store.list_rows("farms", order_by="id ASC", limit=1)[0]["id"]
        cls.client = server.app.test_client()

    def test_01_sqlite_created_and_seeded(self):
        self.assertTrue(os.path.exists(os.environ["AGRIPILOT_DB"]))
        users = store.list_rows("users", order_by="id ASC")
        farms = store.list_rows("farms", order_by="id ASC")
        versions = store.list_rows("model_versions", order_by="id ASC")
        self.assertGreaterEqual(len(users), 1)
        self.assertGreaterEqual(len(farms), 1)
        self.assertGreaterEqual(len(versions), 2)
        types = {v["model_type"] for v in versions}
        self.assertIn("crop_recommendation", types)
        self.assertIn("disease_classification", types)

    def test_02_crud_insert_read_update(self):
        uid = store.insert("users", {
            "name": "CRUD Farmer", "phone": "9999999999", "language": "hi", "created_at": store.now()
        })
        row = store.get_by_id("users", uid)
        self.assertEqual(row["name"], "CRUD Farmer")
        n = store.update("users", uid, {"language": "mr"})
        self.assertEqual(n, 1)
        self.assertEqual(store.get_by_id("users", uid)["language"], "mr")

        fid = store.insert("farms", {
            "user_id": uid, "name": "CRUD Farm", "location": "Pune", "district": "Pune",
            "state": "Maharashtra", "soil_type": "black cotton", "irrigation_system": "furrow",
            "area_ha": 1.2, "created_at": store.now(),
        })
        store.insert("farm_crops", {
            "farm_id": fid, "crop": "cotton", "status": "active", "created_at": store.now()
        })
        store.insert("farm_measurements", {
            "farm_id": fid, "n": 118, "p": 48, "k": 22, "ph": 6.8,
            "temperature": 24.8, "humidity": 80, "rainfall": 85, "soil_moisture": 28,
            "source": "test", "recorded_at": store.now(),
        })
        ctx = store.farm_context(fid)
        self.assertEqual(ctx["active_crop"]["crop"], "cotton")
        self.assertEqual(ctx["measurement"]["n"], 118)

    def test_03_crop_recommendation_integration(self):
        self.assertTrue(os.path.exists(CROP_BUNDLE), "Step-2 model bundle missing")
        result = run_crop_recommendation(90, 42, 43, 23.5, 82.0, 6.5, 220.0)
        self.assertIn("recommended_crop", result)
        self.assertGreater(result["confidence"], 0)
        self.assertEqual(result["model_used"], "Random Forest")
        self.assertTrue(result["reasons"])

    def test_04_farm_advisory_fusion(self):
        payload = build_advisory(self.farm_id, language="en", run_crop_model=True, persist=True)
        self.assertIn("irrigation", payload)
        self.assertIn("reasons", payload)
        self.assertTrue(any(r["factor"] == "Crop recommendation model" for r in payload["reasons"]))
        self.assertTrue(payload["crop_recommendation"])
        self.assertIn(payload["irrigation"]["recommendation"], {"irrigate", "light_irrigation", "skip", "monitor"})
        hist = store.list_rows("advisories", "farm_id = ?", (self.farm_id,))
        self.assertGreaterEqual(len(hist), 1)
        irr = store.list_rows("irrigation_advisories", "farm_id = ?", (self.farm_id,))
        self.assertGreaterEqual(len(irr), 1)
        crops = store.list_rows("crop_predictions", "farm_id = ?", (self.farm_id,))
        self.assertGreaterEqual(len(crops), 1)

    def test_05_assistant_english(self):
        out = answer_question(
            "Should I irrigate my tomato crop today given the soil moisture?",
            farm_id=self.farm_id, language="en", persist=True,
        )
        self.assertEqual(out["language"], "en")
        self.assertIn("Irrigation", out["answer"])
        self.assertIn("knowledge", out["answer"].lower())
        self.assertTrue(out.get("id"))

    def test_06_assistant_hindi(self):
        q = "मेरी टमाटर फसल को पानी दूँ या नहीं? मिट्टी की नमी कैसी है?"
        self.assertEqual(detect_language(q), "hi")
        out = answer_question(q, farm_id=self.farm_id, persist=True)
        self.assertEqual(out["detected_language"], "hi")
        self.assertIn("फार्म संदर्भ", out["answer"])
        self.assertIn("कीटनाशक", out["answer"])

    def test_07_assistant_marathi(self):
        q = "माझ्या टोमॅटो पिकाला आज पाणी द्यावे का? शेतातील ओलावा कसा आहे?"
        self.assertEqual(detect_language(q), "mr")
        out = answer_question(q, farm_id=self.farm_id, persist=True)
        self.assertEqual(out["detected_language"], "mr")
        self.assertIn("शेत संदर्भ", out["answer"])
        self.assertIn("कीटकनाशक", out["answer"])

    def test_08_disease_prediction_integration_and_history(self):
        self.assertTrue(os.path.exists(DISEASE_MODEL), "Step-3 keras model missing")
        cls_dir = os.path.join(DISEASE_DATA_DIR, "Tomato___Early_blight")
        images = [f for f in os.listdir(cls_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        self.assertTrue(images)
        img_path = os.path.join(cls_dir, images[0])
        from disease_classifier import DiseaseClassifier
        clf = DiseaseClassifier()
        pred = clf.predict_image(img_path, generate_gradcam=False)
        self.assertEqual(pred["crop"], "Tomato")
        self.assertIn("confidence", pred)
        pid = store.insert("disease_predictions", {
            "farm_id": self.farm_id,
            "crop": pred["crop"],
            "disease": pred["disease"],
            "class_name": pred["class_name"],
            "is_healthy": 1 if pred["is_healthy"] else 0,
            "confidence": pred["confidence"],
            "severity": pred.get("severity"),
            "top_candidates_json": json.dumps(pred.get("top_candidates", [])),
            "image_name": os.path.basename(img_path),
            "gradcam_path": None,
            "model_version": "step3-mobilenetv2",
            "created_at": store.now(),
        })
        stored = store.get_by_id("disease_predictions", pid)
        self.assertEqual(stored["crop"], "Tomato")
        # advisory should now cite the stored diagnosis
        adv = build_advisory(self.farm_id, language="en", run_crop_model=False, persist=True)
        self.assertTrue(any("Disease classifier" in r["factor"] for r in adv["reasons"]))
        self.assertFalse(any("invent" in r["detail"].lower() and r["status"] == "fake" for r in adv["reasons"]))

    def test_09_api_health_advisory_assistant_history(self):
        h = self.client.get("/api/health")
        self.assertEqual(h.status_code, 200)
        self.assertTrue(h.get_json()["ok"])

        rec = self.client.post("/api/crop-recommend", json={
            "farm_id": self.farm_id,
            "n": 25, "p": 128, "k": 200, "temperature": 28.5,
            "humidity": 81, "ph": 6.2, "rainfall": 68,
        })
        self.assertEqual(rec.status_code, 200)
        body = rec.get_json()
        self.assertEqual(body["recommended_crop"], "grapes")

        adv = self.client.post("/api/advisory", json={"farm_id": self.farm_id, "language": "en"})
        self.assertEqual(adv.status_code, 200)
        self.assertIn("summary", adv.get_json())

        en = self.client.post("/api/assistant", json={
            "farm_id": self.farm_id, "language": "en",
            "question": "What fertilizer schedule is documented for tomato?",
        })
        self.assertEqual(en.status_code, 200)
        self.assertIn("150:75:75", en.get_json()["answer"])

        hist = self.client.get(f"/api/history/queries?farm_id={self.farm_id}")
        self.assertEqual(hist.status_code, 200)
        self.assertGreaterEqual(len(hist.get_json()), 1)

        hist2 = self.client.get(f"/api/history/crop-predictions?farm_id={self.farm_id}")
        self.assertGreaterEqual(len(hist2.get_json()), 1)

        recs = self.client.get("/api/records/advisories")
        self.assertEqual(recs.status_code, 200)

    def test_10_api_disease_upload(self):
        from io import BytesIO
        cls_dir = os.path.join(DISEASE_DATA_DIR, "Grape___Black_rot")
        images = [f for f in os.listdir(cls_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        path = os.path.join(cls_dir, images[0])
        with open(path, "rb") as f:
            data = f.read()
        resp = self.client.post(
            "/api/disease-predict",
            data={"farm_id": str(self.farm_id), "gradcam": "0", "image": (BytesIO(data), "leaf.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True)[:500])
        js = resp.get_json()
        self.assertIn("disease", js)
        self.assertEqual(js.get("crop"), "Grape")
        hist = self.client.get(f"/api/history/disease-predictions?farm_id={self.farm_id}")
        self.assertGreaterEqual(len(hist.get_json()), 1)

    def test_11_step1_datasets_still_present(self):
        self.assertTrue(os.path.exists(CROP_CSV))
        self.assertTrue(os.path.exists(KB_PATH))
        self.assertTrue(os.path.isdir(DISEASE_DATA_DIR))
        import pandas as pd
        df = pd.read_csv(CROP_CSV)
        self.assertEqual(len(df), 2200)
        with open(KB_PATH, "r", encoding="utf-8") as f:
            kb = json.load(f)
        self.assertIn("diseases", kb)
        self.assertIn("crops_agronomy", kb)

    def test_12_step2_and_step3_modules_importable(self):
        from crop_recommender import CropRecommender, FEATURE_NAMES
        from disease_classifier import IMAGE_SIZE, MODEL_PATH
        self.assertEqual(FEATURE_NAMES[0], "N")
        self.assertTrue(os.path.exists(MODEL_PATH))
        r = CropRecommender()
        self.assertEqual(r.model_name, "Random Forest")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    unittest.main(verbosity=2)
