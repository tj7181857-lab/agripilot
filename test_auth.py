"""Authentication, authorization, and user-to-farm isolation checks."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "agripilot")
for item in (ROOT, PKG, os.path.join(PKG, "ml")):
    if item not in sys.path:
        sys.path.insert(0, item)

TEST_DIR = tempfile.mkdtemp(prefix="agripilot_auth_")
os.environ["AGRIPILOT_DB"] = os.path.join(TEST_DIR, "auth-test.db")

import db as store
import server
from werkzeug.security import check_password_hash, generate_password_hash


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store.init_db()
        demo = store.list_rows("users", order_by="id ASC", limit=1)[0]
        store.set_user_login(demo["id"], "demo@agripilot.test", generate_password_hash("DemoFarmer!234"))
        cls.demo_id = demo["id"]
        cls.demo_farm = store.list_rows("farms", "user_id = ?", (cls.demo_id,), limit=1)[0]["id"]
        cls.app = server.app
        cls.app.config.update(TESTING=True)

    def test_01_unauthenticated_redirects_and_api_denied(self):
        client = self.app.test_client()
        response = client.get("/")
        self.assertIn("Sign in to your account", response.get_data(as_text=True))
        response.close()
        self.assertEqual(client.get("/dashboard").status_code, 302)
        self.assertEqual(client.get("/index.html").status_code, 302)
        self.assertEqual(client.get("/api/farms").status_code, 401)
        self.assertEqual(client.get("/api/health").status_code, 200)
        analyst_login_page = client.get("/analyst/login")
        self.assertEqual(analyst_login_page.status_code, 200)
        analyst_login_page.close()
        self.assertEqual(client.get("/analyst/dashboard").status_code, 302)
        self.assertEqual(client.get("/api/analyst/overview").status_code, 401)

    def test_02_registration_routes_new_farmer_through_owned_farm_setup(self):
        client = self.app.test_client()
        response = client.post("/api/auth/register", json={
            "name": "Test Farmer", "username": "newfarmer@agripilot.test",
            "password": "SecureFarmer!234", "role": "analyst",
            "language": "mr",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["redirect"], "/setup-farm")
        user = response.get_json()["user"]
        self.assertEqual(user["role"], "farmer")
        row = store.get_by_id("users", user["id"])
        self.assertNotEqual(row["password_hash"], "SecureFarmer!234")
        self.assertTrue(check_password_hash(row["password_hash"], "SecureFarmer!234"))
        self.assertEqual(store.list_rows("farms", "user_id = ?", (user["id"],), limit=5), [])
        self.assertEqual(client.get("/dashboard").headers["Location"], "/setup-farm")
        response = client.get("/setup-farm")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Set up your farm", response.get_data(as_text=True))
        response.close()
        payload = {
            "name": "New Test Farm", "location": "Test Village", "district": "Nashik",
            "state": "Maharashtra", "area_acres": 2.0, "crop": "tomato",
            "soil_type": "loam", "irrigation_system": "drip",
        }
        self.assertEqual(client.post("/api/farm-setup", json={"name": "incomplete"}).status_code, 400)
        saved = client.post("/api/farm-setup", json=payload)
        self.assertEqual(saved.status_code, 201)
        farm = saved.get_json()["farm"]
        self.assertEqual(farm["user_id"], user["id"])
        self.assertAlmostEqual(farm["area_ha"], 0.80937128448)
        dashboard = client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        dashboard.close()
        self.assertEqual(client.get("/setup-farm").status_code, 302)

    def test_03_login_failure_success_and_logout(self):
        client = self.app.test_client()
        self.assertEqual(client.post("/api/auth/login", json={
            "username": "demo@agripilot.test", "password": "wrong-password"
        }).status_code, 401)
        self.assertEqual(client.post("/api/auth/login", json={
            "username": "demo@agripilot.test", "password": "DemoFarmer!234"
        }).status_code, 200)
        self.assertEqual(client.post("/api/auth/login", json={
            "username": "demo@agripilot.test", "password": "DemoFarmer!234"
        }).get_json()["redirect"], "/dashboard")
        self.assertEqual(client.get("/api/auth/session").get_json()["user"]["role"], "farmer")
        seeded_measurement = store.latest_for_farm("farm_measurements", self.demo_farm)
        seeded_prediction = store.insert("crop_predictions", {
            "farm_id": self.demo_farm, "measurement_id": seeded_measurement["id"],
            "recommended_crop": "must-not-leak", "created_at": store.now(),
        })
        seeded_advisory = store.insert("advisories", {
            "farm_id": self.demo_farm, "crop_prediction_id": seeded_prediction,
            "language": "en", "title": "seeded advisory", "created_at": store.now(),
        })
        store.insert("irrigation_advisories", {
            "farm_id": self.demo_farm, "advisory_id": seeded_advisory,
            "recommendation": "skip", "created_at": store.now(),
        })
        farms = client.get("/api/farms").get_json()
        self.assertEqual([f["id"] for f in farms], [self.demo_farm])
        context = client.get(f"/api/farms/{self.demo_farm}").get_json()
        self.assertNotIn("password_hash", context["user"])
        self.assertIsNone(context["measurement"], "seeded measurement must not be farmer context")
        self.assertEqual(client.get(f"/api/farms/{self.demo_farm}/measurements").get_json(), [])
        self.assertEqual(client.get(f"/api/history/crop-predictions?farm_id={self.demo_farm}").get_json(), [])
        self.assertEqual(client.get("/api/history/crop-predictions").status_code, 400)
        self.assertEqual(client.get("/api/history/crop-predictions?farm_id=not-an-id").status_code, 400)
        self.assertEqual(client.get("/api/history/crop-predictions?farm_id=0").status_code, 400)
        self.assertEqual(client.get(f"/api/history/advisories?farm_id={self.demo_farm}").get_json(), [])
        self.assertEqual(client.get(f"/api/history/irrigation?farm_id={self.demo_farm}").get_json(), [])
        self.assertEqual(client.post("/api/farms", json={"name": "Unexpected"}).status_code, 403)
        self.assertEqual(client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(client.get("/api/farms").status_code, 401)
        self.assertEqual(client.get("/dashboard").status_code, 302)
        response = client.get("/")
        self.assertIn("Sign in to your account", response.get_data(as_text=True))
        response.close()

    def test_06_farmer_dashboard_explains_soil_report_requirement(self):
        client = self.app.test_client()
        self.assertEqual(client.post("/api/auth/login", json={
            "username": "demo@agripilot.test", "password": "DemoFarmer!234"
        }).status_code, 200)
        response = client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Do you have a soil test report?", page)
        self.assertIn('id="app-language"', page)
        self.assertIn('src="i18n.js"', page)
        self.assertIn('data-i18n="Crop health scanner"', page)
        response.close()
        translations = client.get("/i18n.js")
        self.assertEqual(translations.status_code, 200)
        self.assertIn("मेरा खेत".encode("utf-8"), translations.data)
        translations.close()
        assets = client.get("/live_api.js")
        self.assertEqual(assets.status_code, 200)
        self.assertIn(b"Seed/demo readings are not prefilled.", assets.data)
        assets.close()

    def test_04_farmer_ownership_and_analyst_authorization(self):
        farmer = self.app.test_client()
        farmer.post("/api/auth/login", json={"username": "demo@agripilot.test", "password": "DemoFarmer!234"})
        new_user_id = store.create_account(
            name="Other Farmer", username="other@agripilot.test",
            password_hash=generate_password_hash("OtherFarmer!234"), role="farmer",
            farm={"name": "Other Farm"},
        )
        other_farm = store.list_rows("farms", "user_id = ?", (new_user_id,), limit=1)[0]["id"]
        self.assertEqual(farmer.get(f"/api/farms/{other_farm}").status_code, 404)
        self.assertEqual(farmer.put(f"/api/farms/{other_farm}", json={"name": "Hijack"}).status_code, 404)
        self.assertEqual(farmer.post(f"/api/farms/{other_farm}/crops", json={"crop": "tomato"}).status_code, 404)
        self.assertEqual(farmer.post(f"/api/farms/{other_farm}/measurements", json={"temperature": 20}).status_code, 404)
        self.assertEqual(farmer.get(f"/api/farms/{other_farm}/measurements").status_code, 404)
        self.assertEqual(farmer.get(f"/api/farms/{other_farm}/weather").status_code, 404)
        self.assertEqual(farmer.post("/api/crop-recommend", json={
            "farm_id": other_farm, "soil_data_confirmed": True,
            "n": 90, "p": 42, "k": 43, "temperature": 20.9,
            "humidity": 82, "ph": 6.5, "rainfall": 220,
        }).status_code, 404)
        self.assertEqual(farmer.post("/api/disease-predict", data={"farm_id": str(other_farm)}).status_code, 404)
        self.assertEqual(farmer.post("/api/advisory", json={"farm_id": other_farm}).status_code, 404)
        self.assertEqual(farmer.post("/api/assistant", json={
            "farm_id": other_farm, "question": "What should I do?"
        }).status_code, 404)
        self.assertEqual(farmer.get("/api/records/farms").status_code, 403)
        self.assertEqual(farmer.get("/api/model-evaluation").status_code, 403)

        store.create_account(
            name="Test Analyst", username="analyst@agripilot.test",
            password_hash=generate_password_hash("AnalystAccess!234"), role="analyst",
        )
        analyst = self.app.test_client()
        self.assertEqual(analyst.post("/api/auth/login", json={
            "username": "analyst@agripilot.test", "password": "AnalystAccess!234"
        }).status_code, 200)
        self.assertEqual(analyst.post("/api/auth/login", json={
            "username": "analyst@agripilot.test", "password": "AnalystAccess!234"
        }).get_json()["redirect"], "/analyst/dashboard")
        analyst_page = analyst.get("/analyst/dashboard")
        self.assertEqual(analyst_page.status_code, 200)
        self.assertIn("Analyst Overview", analyst_page.get_data(as_text=True))
        analyst_page.close()
        self.assertEqual(analyst.get("/api/analyst/overview").status_code, 200)
        self.assertEqual(farmer.get("/api/analyst/overview").status_code, 403)
        self.assertEqual(farmer.get("/analyst/dashboard").headers["Location"], "/dashboard")
        self.assertEqual(farmer.get("/analyst/login").headers["Location"], "/dashboard")
        self.assertEqual(analyst.get("/api/records/farms").status_code, 200)
        self.assertEqual(analyst.get("/api/model-evaluation").status_code, 200)
        self.assertGreaterEqual(len(analyst.get("/api/farms").get_json()), 2)
        analyst_users = analyst.get("/api/records/users").get_json()
        self.assertTrue(analyst_users)
        self.assertTrue(all("password_hash" not in row for row in analyst_users))
        self.assertTrue(any(row["recommended_crop"] == "must-not-leak"
                            for row in analyst.get("/api/records/crop_predictions").get_json()))

    def test_05_existing_demo_user_and_farm_relationship_preserved(self):
        user = store.get_by_id("users", self.demo_id)
        farm = store.get_by_id("farms", self.demo_farm)
        self.assertEqual(user["name"], "Demo Farmer")
        self.assertEqual(farm["user_id"], self.demo_id)
        self.assertEqual(user["role"], "farmer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
