"""
AgriPilot HTTP API (Step 4).

Extends the existing Python project with farm advisory, multilingual assistant,
prediction history, and SQLite-backed records. Does not retrain Step-2/3 models.

Run from the project root:
    python server.py
"""
from __future__ import annotations

import json
import math
import os
import secrets
import sys
import csv
import re
from datetime import timedelta
from io import BytesIO
from typing import Any, Dict, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "agripilot")
ML = os.path.join(PKG, "ml")
for p in (PKG, ML, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from flask import Flask, g, jsonify, redirect, request, session
from PIL import Image, UnidentifiedImageError

import db as store
from advisory import build_advisory, run_crop_recommendation
from assistant import answer_question
from paths import CROP_CSV, DISEASE_MODEL, DISEASE_MAPPING, db_path
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(
    __name__,
    static_folder=os.path.join(ROOT, "app"),
    static_url_path="",
)
app.secret_key = os.environ.get("AGRIPILOT_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)


def current_user() -> Optional[Dict[str, Any]]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = store.get_by_id("users", int(user_id))
    if not user or not user.get("password_hash"):
        session.clear()
        return None
    return user


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {k: user.get(k) for k in ("id", "name", "username", "role", "language")}


def completed_farms(user_id: int) -> list[Dict[str, Any]]:
    """Return only this user's farms with the basic profile fields completed."""
    farms = store.list_rows(
        "farms", "user_id = ?", (user_id,), "id ASC", 500
    )
    result = []
    for farm in farms:
        crop = store.list_rows(
            "farm_crops", "farm_id = ? AND status = 'active'", (farm["id"],), "id DESC", 1
        )
        if (all(str(farm.get(field) or "").strip() for field in
                ("name", "location", "district", "state", "soil_type", "irrigation_system"))
                and farm.get("area_ha") is not None and float(farm["area_ha"]) > 0
                and crop and str(crop[0].get("crop") or "").strip()):
            result.append(farm)
    return result


def post_login_redirect(user: Dict[str, Any]) -> str:
    return "/analyst/dashboard" if user.get("role") == "analyst" else ("/dashboard" if completed_farms(user["id"]) else "/setup-farm")


ANALYST_ENDPOINTS = {"list_users", "create_user", "model_versions", "model_evaluation", "records", "analyst_overview"}
PUBLIC_API_ENDPOINTS = {"health", "auth_login", "auth_register"}


@app.before_request
def enforce_authentication():
    if request.endpoint == "static":
        filename = (request.view_args or {}).get("filename", "")
        if filename.lower().endswith(".html") and filename not in {"login.html", "register.html"}:
            if current_user() is None:
                return redirect("/")
        return None
    if not request.path.startswith("/api/") or request.method == "OPTIONS":
        return None
    if request.endpoint in PUBLIC_API_ENDPOINTS:
        return None
    user = current_user()
    if user is None:
        return jsonify({"error": "authentication required"}), 401
    g.current_user = user
    if request.endpoint in ANALYST_ENDPOINTS and user.get("role") != "analyst":
        return jsonify({"error": "analyst role required"}), 403
    return None


@app.get("/")
def farmer_dashboard():
    user = current_user()
    if not user:
        return app.send_static_file("login.html")
    return redirect(post_login_redirect(user))


@app.get("/login")
def login_page():
    user = current_user()
    return redirect(post_login_redirect(user)) if user else app.send_static_file("login.html")


@app.get("/register")
def registration_page():
    user = current_user()
    return redirect(post_login_redirect(user)) if user else app.send_static_file("register.html")


@app.get("/analyst/login")
def analyst_login_page():
    user = current_user()
    if user:
        return redirect("/analyst/dashboard" if user.get("role") == "analyst" else post_login_redirect(user))
    return app.send_static_file("analyst-login.html")


@app.get("/analyst/dashboard")
def analyst_dashboard_page():
    user = current_user()
    if not user:
        return redirect("/analyst/login")
    if user.get("role") != "analyst":
        return redirect(post_login_redirect(user))
    return app.send_static_file("analyst.html")


@app.get("/setup-farm")
def setup_farm_page():
    user = current_user()
    if not user:
        return redirect("/")
    if user.get("role") == "analyst" or completed_farms(user["id"]):
        return redirect("/dashboard")
    return app.send_static_file("setup-farm.html")


@app.get("/dashboard")
def dashboard_page():
    user = current_user()
    if user is None:
        return redirect("/")
    if user.get("role") == "analyst":
        return redirect("/analyst/dashboard")
    if user.get("role") == "farmer" and not completed_farms(user["id"]):
        return redirect("/setup-farm")
    return app.send_static_file("index.html")

_DISEASE = None
_CROP_INPUT_BOUNDS = None


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,OPTIONS"
    return resp


def _json() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def parse_optional_id(value: Any) -> Optional[int]:
    if value is None or not str(value).strip():
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError("farm_id must be a positive integer")
    if result <= 0:
        raise ValueError("farm_id must be a positive integer")
    return result


def crop_input_bounds() -> Dict[str, tuple[float, float]]:
    """Read allowed marginal ranges from the exact Step-2 training CSV once."""
    global _CROP_INPUT_BOUNDS
    if _CROP_INPUT_BOUNDS is not None:
        return _CROP_INPUT_BOUNDS
    fields = {"n": "N", "p": "P", "k": "K", "temperature": "temperature",
              "humidity": "humidity", "ph": "ph", "rainfall": "rainfall"}
    values = {field: [] for field in fields.values()}
    with open(CROP_CSV, "r", encoding="utf-8-sig", newline="") as dataset:
        reader = csv.DictReader(dataset)
        if not reader.fieldnames or not set(values).issubset(reader.fieldnames):
            raise ValueError("crop training data does not contain expected feature columns")
        for row in reader:
            for field in values:
                number = float(row[field])
                if not math.isfinite(number):
                    raise ValueError("crop training data contains non-finite feature values")
                values[field].append(number)
    if not values or any(not column for column in values.values()):
        raise ValueError("crop training data is empty")
    _CROP_INPUT_BOUNDS = {
        api_field: (min(values[data_field]), max(values[data_field]))
        for api_field, data_field in fields.items()
    }
    return _CROP_INPUT_BOUNDS


def get_disease_engine():
    global _DISEASE
    if _DISEASE is None:
        if not os.path.exists(DISEASE_MODEL) or not os.path.exists(DISEASE_MAPPING):
            raise FileNotFoundError("Step-3 disease model artifacts are missing")
        from disease_classifier import DiseaseClassifier
        _DISEASE = DiseaseClassifier(model_path=DISEASE_MODEL, mapping_path=DISEASE_MAPPING)
    return _DISEASE


def disease_mapping_data() -> Dict[str, Any]:
    with open(DISEASE_MAPPING, "r", encoding="utf-8") as mapping_file:
        mapping = json.load(mapping_file)
    if not isinstance(mapping, dict):
        raise ValueError("Disease class mapping is invalid")
    return mapping


def can_access_farm(farm_id: int) -> bool:
    user = getattr(g, "current_user", None) or current_user()
    if not user:
        return False
    if user.get("role") == "analyst":
        return True
    farm = store.get_by_id("farms", int(farm_id))
    return bool(farm and farm.get("user_id") == user["id"])


def farm_access_error(farm_id: int):
    if not can_access_farm(farm_id):
        return jsonify({"error": "farm not found or access denied"}), 404
    return None


def open_meteo_json(url: str) -> Dict[str, Any]:
    """Fetch one bounded JSON response from Open-Meteo without a new dependency."""
    from urllib.request import Request, urlopen
    req = Request(url, headers={"User-Agent": "AgriPilot/1.0 (farm weather lookup)"})
    with urlopen(req, timeout=8) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("weather provider response was too large")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("weather provider returned invalid data")
    return payload


def _normal_location(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def live_weather_for_farm(farm: Dict[str, Any]) -> Dict[str, Any]:
    from urllib.parse import urlencode
    location = str(farm.get("location") or "").strip()
    state = str(farm.get("state") or "").strip()
    if not location or not state or state.casefold() == "other":
        return {"available": False, "message": "Weather data is currently unavailable because this farm needs a specific location and state."}
    query = urlencode({"name": f"{location}, {state}", "count": 10, "language": "en", "format": "json", "countryCode": "IN"})
    geocoded = open_meteo_json("https://geocoding-api.open-meteo.com/v1/search?" + query)
    matches = geocoded.get("results") or []
    match = next((item for item in matches if _normal_location(item.get("admin1")) == _normal_location(state)), None)
    if not match:
        return {"available": False, "message": "Weather data is currently unavailable because the farm location could not be matched to the saved state."}
    forecast_query = urlencode({
        "latitude": match["latitude"], "longitude": match["longitude"],
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": 3, "timezone": "auto",
    })
    forecast = open_meteo_json("https://api.open-meteo.com/v1/forecast?" + forecast_query)
    current = forecast.get("current") or {}
    daily = forecast.get("daily") or {}
    if not current.get("time") or not daily.get("time"):
        return {"available": False, "message": "Weather data is currently unavailable from the weather provider."}
    return {
        "available": True, "source": "Open-Meteo", "location": {
            "name": match.get("name"), "district": match.get("admin2"),
            "state": match.get("admin1"), "country": match.get("country"),
            "latitude": match.get("latitude"), "longitude": match.get("longitude"),
        },
        "timezone": forecast.get("timezone"), "current": current, "daily": daily,
    }


def history_response(table: str):
    user = g.current_user
    try:
        farm_id = parse_optional_id(request.args.get("farm_id"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if user.get("role") == "farmer" and farm_id is None:
        return jsonify({"error": "farm_id is required for farmer history"}), 400
    limit = min(max(request.args.get("limit", 50, type=int) or 50, 1), 500)
    if user.get("role") == "analyst":
        where, params = (("farm_id = ?", (farm_id,)) if farm_id else (None, None))
    elif farm_id:
        if not can_access_farm(farm_id):
            return jsonify({"error": "farm not found or access denied"}), 404
        where, params = "farm_id = ?", (farm_id,)
    elif table == "farmer_queries":
        where, params = "(farm_id IN (SELECT id FROM farms WHERE user_id = ?) OR user_id = ?)", (user["id"], user["id"])
    else:
        where, params = "farm_id IN (SELECT id FROM farms WHERE user_id = ?)", (user["id"],)
    if user.get("role") == "farmer":
        demo_measurements = "SELECT id FROM farm_measurements WHERE source IN ('demo_seed', 'simulation', 'pilot_simulation')"
        demo_predictions = f"SELECT id FROM crop_predictions WHERE measurement_id IN ({demo_measurements})"
        if table == "crop_predictions":
            where = f"({where}) AND (measurement_id IS NULL OR measurement_id NOT IN ({demo_measurements}))"
        elif table == "advisories":
            where = f"({where}) AND (crop_prediction_id IS NULL OR crop_prediction_id NOT IN ({demo_predictions}))"
        elif table == "irrigation_advisories":
            where = (f"({where}) AND (advisory_id IS NULL OR advisory_id NOT IN "
                     f"(SELECT id FROM advisories WHERE crop_prediction_id IN ({demo_predictions})))")
    return jsonify(store.list_rows(table, where, params, limit=limit))


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "AgriPilot Step 4 API",
        "database": db_path(),
        "steps": {"1": "datasets", "2": "crop_recommender", "3": "disease_classifier", "4": "advisory+assistant+sqlite"},
    })


@app.post("/api/auth/register")
def auth_register():
    body = _json()
    name = str(body.get("name") or "").strip()
    username = str(body.get("username") or body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not name or not username:
        return jsonify({"error": "name and username/email are required"}), 400
    if len(username) > 120 or any(ch.isspace() for ch in username):
        return jsonify({"error": "enter a valid username or email"}), 400
    if not isinstance(password, str) or len(password) < 10:
        return jsonify({"error": "password must be at least 10 characters"}), 400
    if store.user_by_username(username):
        return jsonify({"error": "that username/email is already registered"}), 409
    language = str(body.get("language") or "en").lower()
    if language not in {"en", "hi", "mr"}:
        language = "en"
    try:
        user_id = store.create_account(
            name=name, username=username, password_hash=generate_password_hash(password),
            phone=(body.get("phone") or "").strip() or None,
            language=language, role="farmer", farm=None,
        )
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            return jsonify({"error": "that username/email is already registered"}), 409
        raise
    user = store.get_by_id("users", user_id)
    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    return jsonify({"user": public_user(user), "redirect": "/setup-farm"}), 201


@app.post("/api/auth/login")
def auth_login():
    body = _json()
    username = str(body.get("username") or body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    user = store.user_by_username(username) if username else None
    if not user or not user.get("password_hash") or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username/email or password"}), 401
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"user": public_user(user), "redirect": post_login_redirect(user)})


@app.post("/api/farm-setup")
def save_initial_farm():
    user = g.current_user
    if user.get("role") != "farmer":
        return jsonify({"error": "farmer role required"}), 403
    if completed_farms(user["id"]):
        return jsonify({"error": "farm profile is already complete"}), 409
    body = _json()
    required = ("name", "location", "district", "state", "area_acres", "crop", "soil_type", "irrigation_system")
    missing = [key for key in required if not str(body.get(key) or "").strip()]
    if missing:
        return jsonify({"error": "complete all farm profile fields", "fields": missing}), 400
    try:
        area_acres = float(body["area_acres"])
        if not 0 < area_acres <= 1000000:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "farm area must be a positive number of acres"}), 400
    farm_fields = {
        "name": str(body["name"]).strip(), "location": str(body["location"]).strip(),
        "district": str(body["district"]).strip(), "state": str(body["state"]).strip(),
        "area_ha": area_acres * 0.40468564224,
        "soil_type": str(body["soil_type"]).strip(),
        "irrigation_system": str(body["irrigation_system"]).strip(),
    }
    crop_fields = {"crop": str(body["crop"]).strip().lower()}
    owned = store.list_rows("farms", "user_id = ?", (user["id"],), "id ASC", 500)
    if owned:
        farm_id = owned[0]["id"]
        store.update_farm_profile(farm_id, farm_fields, crop_fields)
    else:
        farm_id = store.create_farm_profile(user["id"], farm_fields, crop_fields)
    return jsonify({"farm": store.get_by_id("farms", farm_id), "redirect": "/dashboard"}), 201


@app.get("/api/auth/session")
def auth_session():
    return jsonify({"user": public_user(g.current_user)})


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify({"ok": True, "redirect": "/"})


@app.post("/api/users")
def create_user():
    body = _json()
    uid = store.insert("users", {
        "name": body.get("name") or "Farmer",
        "phone": body.get("phone"),
        "language": body.get("language") or "en",
        "created_at": store.now(),
    })
    return jsonify(public_user(store.get_by_id("users", uid))), 201


@app.get("/api/users")
def list_users():
    return jsonify([public_user(u) for u in store.list_rows("users", order_by="id ASC", limit=100)])


@app.post("/api/farms")
def create_farm():
    body = _json()
    if g.current_user["role"] == "farmer":
        return jsonify({"error": "complete the authenticated farm setup to create your farm"}), 403
    owner_id = g.current_user["id"] if g.current_user["role"] == "farmer" else body.get("user_id")
    fid = store.insert("farms", {
        "user_id": owner_id,
        "name": body.get("name") or "Farm",
        "location": body.get("location"),
        "district": body.get("district"),
        "state": body.get("state") or "Maharashtra",
        "soil_type": body.get("soil_type"),
        "irrigation_system": body.get("irrigation_system"),
        "area_ha": body.get("area_ha"),
        "created_at": store.now(),
    })
    return jsonify(store.get_by_id("farms", fid)), 201


@app.get("/api/farms")
def list_farms():
    if g.current_user["role"] == "analyst":
        rows = store.list_rows("farms", order_by="id ASC", limit=500)
    else:
        rows = store.list_rows("farms", "user_id = ?", (g.current_user["id"],), "id ASC", 500)
    return jsonify(rows)


@app.get("/api/farms/<int:farm_id>")
def get_farm(farm_id: int):
    denied = farm_access_error(farm_id)
    if denied:
        return denied
    try:
        context = store.farm_context(farm_id, exclude_demo=g.current_user.get("role") == "farmer")
        if context.get("user"):
            context["user"] = public_user(context["user"])
        return jsonify(context)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404


@app.put("/api/farms/<int:farm_id>")
def update_farm(farm_id: int):
    denied = farm_access_error(farm_id)
    if denied:
        return denied
    body = _json()
    allowed = {k: body[k] for k in (
        "name", "location", "district", "state", "soil_type", "irrigation_system", "area_ha"
    ) if k in body}
    if "name" in allowed and not str(allowed["name"] or "").strip():
        return jsonify({"error": "farm name is required"}), 400
    if "area_ha" in allowed and allowed["area_ha"] is not None:
        try:
            allowed["area_ha"] = float(allowed["area_ha"])
            if allowed["area_ha"] < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "area_ha must be a non-negative number"}), 400
    crop_fields = {k: body[k] for k in ("crop", "variety", "season", "sowing_date") if k in body}
    if "crop" in crop_fields:
        if not str(crop_fields["crop"] or "").strip():
            crop_fields.pop("crop")
        else:
            crop_fields["crop"] = str(crop_fields["crop"]).strip().lower()
    if "name" in allowed:
        allowed["name"] = str(allowed["name"]).strip()
    store.update_farm_profile(farm_id, allowed, crop_fields)
    return jsonify(store.get_by_id("farms", farm_id))


@app.post("/api/farms/<int:farm_id>/crops")
def add_crop(farm_id: int):
    denied = farm_access_error(farm_id)
    if denied:
        return denied
    body = _json()
    cid = store.insert("farm_crops", {
        "farm_id": farm_id,
        "crop": (body.get("crop") or "").lower(),
        "variety": body.get("variety"),
        "season": body.get("season"),
        "sowing_date": body.get("sowing_date"),
        "status": body.get("status") or "active",
        "created_at": store.now(),
    })
    return jsonify(store.get_by_id("farm_crops", cid)), 201


@app.post("/api/farms/<int:farm_id>/measurements")
def add_measurement(farm_id: int):
    denied = farm_access_error(farm_id)
    if denied:
        return denied
    body = _json()
    mid = store.insert("farm_measurements", {
        "farm_id": farm_id,
        "n": body.get("n"),
        "p": body.get("p"),
        "k": body.get("k"),
        "ph": body.get("ph"),
        "temperature": body.get("temperature"),
        "humidity": body.get("humidity"),
        "rainfall": body.get("rainfall"),
        "soil_moisture": body.get("soil_moisture"),
        "weather_notes": body.get("weather_notes"),
        "source": body.get("source") or "api",
        "recorded_at": body.get("recorded_at") or store.now(),
    })
    return jsonify(store.get_by_id("farm_measurements", mid)), 201


@app.get("/api/farms/<int:farm_id>/measurements")
def list_measurements(farm_id: int):
    denied = farm_access_error(farm_id)
    if denied:
        return denied
    if g.current_user.get("role") == "farmer":
        return jsonify(store.list_rows(
            "farm_measurements",
            "farm_id = ? AND source NOT IN ('demo_seed', 'simulation', 'pilot_simulation')",
            (farm_id,), limit=100,
        ))
    return jsonify(store.list_rows("farm_measurements", "farm_id = ?", (farm_id,), limit=100))


@app.get("/api/farms/<int:farm_id>/weather")
def farm_weather(farm_id: int):
    denied = farm_access_error(farm_id)
    if denied:
        return denied
    farm = store.get_by_id("farms", farm_id)
    try:
        return jsonify(live_weather_for_farm(farm))
    except Exception:
        app.logger.exception("Live weather lookup failed for farm %s", farm_id)
        return jsonify({"available": False, "message": "Weather data is currently unavailable."})


@app.get("/api/disease-model-info")
def disease_model_info():
    try:
        mapping = disease_mapping_data()
        classes = [mapping[key] for key in sorted(mapping, key=lambda key: int(key))]
        crops = sorted({str(item.get("crop", "")).strip() for item in classes
                        if isinstance(item, dict) and str(item.get("crop", "")).strip()},
                       key=str.casefold)
        if not crops:
            raise ValueError("Disease mapping has no crop labels")
        return jsonify({"supported_crops": crops, "classes": classes})
    except (OSError, json.JSONDecodeError, ValueError, KeyError):
        return jsonify({"error": "disease model class metadata is unavailable"}), 503


@app.post("/api/crop-recommend")
def crop_recommend():
    body = _json()
    required = ("n", "p", "k", "temperature", "humidity", "ph", "rainfall")
    missing = [k for k in required if body.get(k) is None]
    if missing:
        return jsonify({"error": "missing fields", "fields": missing}), 400
    if g.current_user.get("role") == "farmer" and body.get("soil_data_confirmed") is not True:
        return jsonify({
            "error": "Precise soil-based crop recommendation requires soil information from a farmer-confirmed soil test report",
            "fields": ["soil_data_confirmed"],
        }), 400
    numeric_inputs = {}
    for key in required:
        try:
            numeric_inputs[key] = float(body[key])
        except (TypeError, ValueError):
            return jsonify({"error": "all model inputs must be numbers", "fields": [key]}), 400
        if not math.isfinite(numeric_inputs[key]):
            return jsonify({"error": "all model inputs must be finite numbers", "fields": [key]}), 400
    try:
        bounds = crop_input_bounds()
    except (OSError, ValueError, csv.Error, UnicodeError):
        return jsonify({"error": "crop training feature ranges are unavailable"}), 503
    outside = [key for key, value in numeric_inputs.items()
               if value < bounds[key][0] or value > bounds[key][1]]
    if outside:
        return jsonify({
            "error": "These values are outside the range covered by our trained model. Please verify the soil-test and weather values.",
            "fields": outside,
            "training_ranges": {key: list(bounds[key]) for key in outside},
        }), 422
    try:
        farm_id = parse_optional_id(body.get("farm_id"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if g.current_user.get("role") == "farmer":
        if not farm_id:
            farms = store.list_rows("farms", "user_id = ?", (g.current_user["id"],), "id ASC", 2)
            if len(farms) != 1:
                return jsonify({"error": "farm_id is required for an account without exactly one farm"}), 400
            farm_id = farms[0]["id"]
        denied = farm_access_error(int(farm_id))
        if denied:
            return denied
    elif farm_id:
        denied = farm_access_error(int(farm_id))
        if denied:
            return denied
    result = run_crop_recommendation(
        n=numeric_inputs["n"], p=numeric_inputs["p"], k=numeric_inputs["k"],
        temperature=numeric_inputs["temperature"], humidity=numeric_inputs["humidity"],
        ph=numeric_inputs["ph"], rainfall=numeric_inputs["rainfall"],
    )
    if farm_id:
        measurement_id = store.insert("farm_measurements", {
            "farm_id": farm_id,
            "n": numeric_inputs["n"], "p": numeric_inputs["p"], "k": numeric_inputs["k"],
            "ph": numeric_inputs["ph"], "temperature": numeric_inputs["temperature"],
            "humidity": numeric_inputs["humidity"], "rainfall": numeric_inputs["rainfall"],
            "source": "soil_test_report_farmer_entered",
            "weather_notes": ("Soil report: " + os.path.basename(str(body.get("soil_report_filename")))[:180]) if str(body.get("soil_report_filename") or "").strip() else "Farmer-confirmed values entered manually from a soil test.",
            "recorded_at": store.now(),
        })
        pid = store.insert("crop_predictions", {
            "farm_id": farm_id,
            "measurement_id": measurement_id,
            "recommended_crop": result["recommended_crop"],
            "confidence": result.get("confidence"),
            "alternatives_json": json.dumps(result.get("alternatives", []), ensure_ascii=False),
            "reasons_json": json.dumps(result.get("reasons", []), ensure_ascii=False),
            "input_json": json.dumps(result.get("input_values", {}), ensure_ascii=False),
            "model_name": result.get("model_used"),
            "model_version": "step2-production-bundle",
            "created_at": store.now(),
        })
        result["id"] = pid
        result["farm_id"] = farm_id
        result["measurement_id"] = measurement_id
    return jsonify(result)


@app.post("/api/soil-report/extract")
def soil_report_extract():
    """Best-effort local text/OCR extraction; the farmer must confirm every value."""
    if g.current_user.get("role") != "farmer":
        return jsonify({"error": "farmer role required"}), 403
    upload = request.files.get("report")
    if upload is None or not upload.filename:
        return jsonify({"error": "soil report file is required"}), 400
    filename = os.path.basename(upload.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".pdf", ".jpg", ".jpeg", ".png"}:
        return jsonify({"error": "upload a PDF, JPG, JPEG, or PNG soil report"}), 415
    data = upload.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        return jsonify({"error": "soil report must be 10 MB or smaller"}), 413
    text = ""
    method = None
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            method = "PDF embedded text"
        except ImportError:
            return jsonify({"status": "manual_entry_required", "filename": filename, "values": {}, "message": "PDF text extraction is unavailable in this installation. Enter values from the report manually; no values were inferred."}), 200
        except Exception:
            return jsonify({"error": "could not read this PDF report"}), 400
    else:
        try:
            image = Image.open(BytesIO(data)).convert("RGB")
            try:
                import pytesseract
                text = pytesseract.image_to_string(image)
                method = "Tesseract OCR"
            except Exception:
                return jsonify({"status": "manual_entry_required", "filename": filename, "values": {}, "message": "Image OCR is unavailable in this installation. Enter values from the report manually; no values were inferred."}), 200
        except (UnidentifiedImageError, OSError, ValueError):
            return jsonify({"error": "uploaded file is not a readable image"}), 400
    patterns = {
        "n": r"(?:nitrogen|\bN\b)\s*[:=\-]?\s*(-?\d+(?:\.\d+)?)",
        "p": r"(?:phosphorus|\bP\b)\s*[:=\-]?\s*(-?\d+(?:\.\d+)?)",
        "k": r"(?:potassium|\bK\b)\s*[:=\-]?\s*(-?\d+(?:\.\d+)?)",
        "ph": r"(?:soil\s*)?pH\s*[:=\-]?\s*(-?\d+(?:\.\d+)?)",
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                if math.isfinite(value):
                    values[key] = value
            except ValueError:
                pass
    return jsonify({"status": "extracted" if values else "no_values_found", "filename": filename, "method": method,
                    "values": values, "message": "Review and correct the extracted values against your report before confirming." if values else "No N, P, K, or pH values were recognized. Enter them manually from the report."})


@app.post("/api/disease-predict")
def disease_predict():
    try:
        farm_id = parse_optional_id(request.form.get("farm_id"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if g.current_user.get("role") == "farmer" and not farm_id:
        farms = store.list_rows("farms", "user_id = ?", (g.current_user["id"],), "id ASC", 2)
        if len(farms) != 1:
            return jsonify({"error": "farm_id is required for an account without exactly one farm"}), 400
        farm_id = farms[0]["id"]
    if farm_id:
        denied = farm_access_error(farm_id)
        if denied:
            return denied
    upload = request.files.get("image")
    if upload is None or not upload.filename:
        return jsonify({"error": "multipart field 'image' is required"}), 400
    expected_crop = str(request.form.get("crop") or "").strip()
    if not expected_crop:
        return jsonify({"error": "select or enter the crop shown in the image"}), 400
    try:
        mapping = disease_mapping_data()
    except (OSError, json.JSONDecodeError, ValueError):
        return jsonify({"error": "disease model class metadata is unavailable"}), 503
    supported_crops = sorted({
        str(item.get("crop", "")).strip() for item in mapping.values()
        if isinstance(item, dict) and str(item.get("crop", "")).strip()
    }, key=str.casefold)
    if expected_crop.casefold() not in {crop.casefold() for crop in supported_crops}:
        return jsonify({
            "status": "unsupported_crop",
            "error": "This crop is not currently supported by the disease model.",
            "supported_crops": supported_crops,
        }), 422
    image_bytes = upload.read()
    try:
        engine = get_disease_engine()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify({"error": "uploaded file is not a valid image"}), 400
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            if min(image.size) < 64:
                return jsonify({"status": "poor_quality", "error": "Image is too small for reliable leaf analysis. Upload an original, clear image at least 64 pixels wide and high."}), 422
    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify({"error": "uploaded file is not a valid image"}), 400
    result = engine.predict_image(
        image_bytes,
        generate_gradcam=bool(request.form.get("gradcam", "1") != "0"),
        expected_crop=expected_crop,
    )
    if not result.get("crop_matches_selection", True):
        return jsonify({
            "status": "unable_to_identify_reliably",
            "error": "The model's crop result did not match the crop selected for this image. No disease result was saved. Check the crop selection and upload a clear leaf image.",
        }), 422
    record = {
        "farm_id": farm_id,
        "crop": result.get("crop"),
        "disease": result.get("disease"),
        "class_name": result.get("class_name"),
        "is_healthy": 1 if result.get("is_healthy") else 0,
        "confidence": result.get("confidence"),
        "severity": result.get("severity"),
        "top_candidates_json": json.dumps(result.get("top_candidates", []), ensure_ascii=False),
        "image_name": upload.filename,
        "gradcam_path": result.get("gradcam_path"),
        "model_version": "step3-mobilenetv2",
        "created_at": store.now(),
    }
    pid = store.insert("disease_predictions", record)
    result["id"] = pid
    result["farm_id"] = farm_id
    # keep API JSON smaller
    if result.get("gradcam_base64") and request.form.get("include_gradcam_b64") != "1":
        result["gradcam_base64"] = None
        result["gradcam_omitted"] = True
    return jsonify(result)


@app.post("/api/advisory")
def farm_advisory():
    body = _json()
    try:
        farm_id = parse_optional_id(body.get("farm_id"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not farm_id:
        if g.current_user.get("role") == "farmer":
            farms = store.list_rows("farms", "user_id = ?", (g.current_user["id"],), "id ASC", 2)
            if len(farms) == 1:
                farm_id = farms[0]["id"]
        if not farm_id:
            return jsonify({"error": "farm_id is required"}), 400
    denied = farm_access_error(int(farm_id))
    if denied:
        return denied
    try:
        payload = build_advisory(
            int(farm_id),
            language=body.get("language") or "en",
            run_crop_model=body.get("run_crop_model", True),
            persist=body.get("persist", True),
            exclude_demo=g.current_user.get("role") == "farmer",
        )
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(payload)


@app.post("/api/assistant")
def assistant():
    body = _json()
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    try:
        farm_id = parse_optional_id(body.get("farm_id"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not farm_id and g.current_user.get("role") == "farmer":
        farms = store.list_rows("farms", "user_id = ?", (g.current_user["id"],), "id ASC", 2)
        if len(farms) == 1:
            farm_id = farms[0]["id"]
        else:
            return jsonify({"error": "farm_id is required for an account without exactly one farm"}), 400
    if farm_id and not can_access_farm(int(farm_id)):
        return jsonify({"error": "farm not found or access denied"}), 404
    payload = answer_question(
        question,
        farm_id=farm_id,
        language=body.get("language"),
        persist=body.get("persist", True),
        exclude_demo=g.current_user.get("role") == "farmer",
    )
    return jsonify(payload)


@app.get("/api/history/crop-predictions")
def hist_crops():
    return history_response("crop_predictions")


@app.get("/api/history/disease-predictions")
def hist_disease():
    return history_response("disease_predictions")


@app.get("/api/history/queries")
def hist_queries():
    return history_response("farmer_queries")


@app.get("/api/history/advisories")
def hist_advisories():
    return history_response("advisories")


@app.get("/api/history/irrigation")
def hist_irrigation():
    return history_response("irrigation_advisories")


@app.get("/api/model-versions")
def model_versions():
    return jsonify(store.list_rows("model_versions", order_by="id ASC", limit=20))


# Step 5: read-only access to the evaluation artifacts generated by Steps 2 and 3.
@app.get("/api/model-evaluation")
def model_evaluation():
    """Return saved evaluation artifacts; never trains or rewrites a model."""
    from paths import CROP_COMPARISON, DISEASE_METRICS

    def read_json(path):
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    return jsonify({
        "crop": read_json(CROP_COMPARISON),
        "disease": read_json(DISEASE_METRICS),
    })


@app.get("/api/analyst/overview")
def analyst_overview():
    """Return database-backed aggregates and recent activity without personal identifiers."""
    tables = {
        "users": "users", "farms": "farms", "farm_crops": "farm_crops",
        "farm_measurements": "farm_measurements", "crop_predictions": "crop_predictions",
        "disease_predictions": "disease_predictions", "farmer_queries": "farmer_queries",
        "advisories": "advisories",
    }
    rows = {key: store.list_rows(table, order_by="id DESC", limit=100000)
            for key, table in tables.items()}
    farms = rows["farms"]
    def distribution(items, field):
        out = {}
        for item in items:
            label = str(item.get(field) or "Unspecified")
            out[label] = out.get(label, 0) + 1
        return out
    activities = []
    for kind, key, field in (("Crop recommendation", "crop_predictions", "recommended_crop"),
                             ("Disease scan", "disease_predictions", "disease"),
                             ("Advisory", "advisories", "title"),
                             ("Assistant query", "farmer_queries", None),
                             ("Soil/weather measurement", "farm_measurements", "source")):
        for row in rows[key][:20]:
            activities.append({"type": kind, "label": row.get(field) if field else None, "created_at": row.get("created_at") or row.get("recorded_at")})
    activities.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    active_farm_ids = {int(c["farm_id"]) for c in rows["farm_crops"] if c.get("status") == "active" and c.get("farm_id") is not None}
    complete_farms = sum(1 for f in farms if f.get("name") and f.get("location") and f.get("district") and f.get("state") and f.get("soil_type") and f.get("irrigation_system") and f.get("area_ha") and int(f["id"]) in active_farm_ids)
    return jsonify({
        "counts": {"farmers": sum(1 for u in rows["users"] if u.get("role") == "farmer"),
                   "farms": len(farms), "crop_recommendations": len(rows["crop_predictions"]),
                   "disease_scans": len(rows["disease_predictions"]),
                   "assistant_queries": len(rows["farmer_queries"]), "advisories": len(rows["advisories"]),
                   "soil_measurements": sum(1 for m in rows["farm_measurements"] if m.get("n") is not None or m.get("p") is not None or m.get("k") is not None or m.get("ph") is not None),
                   "soil_report_measurements": sum(1 for m in rows["farm_measurements"] if m.get("source") == "soil_test_report_farmer_entered"),
                   "complete_farm_profiles": complete_farms,
                   "incomplete_farm_profiles": max(0, len(farms) - complete_farms)},
        "farms_by_state": distribution(farms, "state"),
        "farms_by_district": distribution(farms, "district"),
        "current_crops": distribution([c for c in rows["farm_crops"] if c.get("status") == "active"], "crop"),
        "recommendations_by_crop": distribution(rows["crop_predictions"], "recommended_crop"),
        "disease_by_class": distribution(rows["disease_predictions"], "class_name"),
        "disease_by_crop": distribution(rows["disease_predictions"], "crop"),
        "recent_activity": activities[:30],
    })


@app.get("/api/records/<table>")
def records(table: str):
    allowed = {
        "users", "farms", "farm_crops", "farm_measurements", "crop_predictions",
        "disease_predictions", "farmer_queries", "advisories", "irrigation_advisories",
        "model_versions",
    }
    if table not in allowed:
        return jsonify({"error": "unknown table"}), 404
    limit = min(max(request.args.get("limit", 50, type=int) or 50, 1), 1000)
    rows = store.list_rows(table, order_by="id DESC", limit=limit)
    if table == "users":
        rows = [public_user(user) for user in rows]
    return jsonify(rows)


def create_app() -> Flask:
    store.init_db()
    return app


if __name__ == "__main__":
    store.init_db()
    print(f"AgriPilot API  db={db_path()}")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
