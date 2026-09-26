"""
AgriPilot HTTP API (Step 4).

Extends the existing Python project with farm advisory, multilingual assistant,
prediction history, and SQLite-backed records. Does not retrain Step-2/3 models.

Run from the project root:
    python server.py
"""
from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from typing import Any, Dict, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "agripilot")
ML = os.path.join(PKG, "ml")
for p in (PKG, ML, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from flask import Flask, jsonify, request
from PIL import Image, UnidentifiedImageError

import db as store
from advisory import build_advisory, run_crop_recommendation
from assistant import answer_question
from paths import DISEASE_MODEL, DISEASE_MAPPING, db_path

app = Flask(
    __name__,
    static_folder=os.path.join(ROOT, "app"),
    static_url_path="",
)


@app.get("/")
def farmer_dashboard():
    return app.send_static_file("index.html")

_DISEASE = None


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,OPTIONS"
    return resp


def _json() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def get_disease_engine():
    global _DISEASE
    if _DISEASE is None:
        if not os.path.exists(DISEASE_MODEL) or not os.path.exists(DISEASE_MAPPING):
            raise FileNotFoundError("Step-3 disease model artifacts are missing")
        from disease_classifier import DiseaseClassifier
        _DISEASE = DiseaseClassifier(model_path=DISEASE_MODEL, mapping_path=DISEASE_MAPPING)
    return _DISEASE


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "AgriPilot Step 4 API",
        "database": db_path(),
        "steps": {"1": "datasets", "2": "crop_recommender", "3": "disease_classifier", "4": "advisory+assistant+sqlite"},
    })


@app.post("/api/users")
def create_user():
    body = _json()
    uid = store.insert("users", {
        "name": body.get("name") or "Farmer",
        "phone": body.get("phone"),
        "language": body.get("language") or "en",
        "created_at": store.now(),
    })
    return jsonify(store.get_by_id("users", uid)), 201


@app.get("/api/users")
def list_users():
    return jsonify(store.list_rows("users", order_by="id ASC", limit=100))


@app.post("/api/farms")
def create_farm():
    body = _json()
    fid = store.insert("farms", {
        "user_id": body.get("user_id"),
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
    return jsonify(store.list_rows("farms", order_by="id ASC", limit=100))


@app.get("/api/farms/<int:farm_id>")
def get_farm(farm_id: int):
    try:
        return jsonify(store.farm_context(farm_id))
    except KeyError as e:
        return jsonify({"error": str(e)}), 404


@app.put("/api/farms/<int:farm_id>")
def update_farm(farm_id: int):
    body = _json()
    allowed = {k: body[k] for k in (
        "name", "location", "district", "state", "soil_type", "irrigation_system", "area_ha", "user_id"
    ) if k in body}
    store.update("farms", farm_id, allowed)
    return jsonify(store.get_by_id("farms", farm_id))


@app.post("/api/farms/<int:farm_id>/crops")
def add_crop(farm_id: int):
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
    return jsonify(store.list_rows("farm_measurements", "farm_id = ?", (farm_id,), limit=100))


@app.post("/api/crop-recommend")
def crop_recommend():
    body = _json()
    required = ("n", "p", "k", "temperature", "humidity", "ph", "rainfall")
    missing = [k for k in required if body.get(k) is None]
    if missing:
        return jsonify({"error": "missing fields", "fields": missing}), 400
    result = run_crop_recommendation(
        n=body["n"], p=body["p"], k=body["k"],
        temperature=body["temperature"], humidity=body["humidity"],
        ph=body["ph"], rainfall=body["rainfall"],
    )
    farm_id = body.get("farm_id")
    if farm_id:
        pid = store.insert("crop_predictions", {
            "farm_id": farm_id,
            "measurement_id": body.get("measurement_id"),
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
    return jsonify(result)


@app.post("/api/disease-predict")
def disease_predict():
    farm_id = request.form.get("farm_id", type=int)
    upload = request.files.get("image")
    if upload is None or not upload.filename:
        return jsonify({"error": "multipart field 'image' is required"}), 400
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
    result = engine.predict_image(image_bytes, generate_gradcam=bool(request.form.get("gradcam", "1") != "0"))
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
    farm_id = body.get("farm_id")
    if not farm_id:
        return jsonify({"error": "farm_id is required"}), 400
    try:
        payload = build_advisory(
            int(farm_id),
            language=body.get("language") or "en",
            run_crop_model=body.get("run_crop_model", True),
            persist=body.get("persist", True),
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
    payload = answer_question(
        question,
        farm_id=body.get("farm_id"),
        language=body.get("language"),
        persist=body.get("persist", True),
    )
    return jsonify(payload)


@app.get("/api/history/crop-predictions")
def hist_crops():
    farm_id = request.args.get("farm_id", type=int)
    where, params = (None, None)
    if farm_id:
        where, params = "farm_id = ?", (farm_id,)
    return jsonify(store.list_rows("crop_predictions", where, params, limit=int(request.args.get("limit", 50))))


@app.get("/api/history/disease-predictions")
def hist_disease():
    farm_id = request.args.get("farm_id", type=int)
    where, params = (None, None)
    if farm_id:
        where, params = "farm_id = ?", (farm_id,)
    return jsonify(store.list_rows("disease_predictions", where, params, limit=int(request.args.get("limit", 50))))


@app.get("/api/history/queries")
def hist_queries():
    farm_id = request.args.get("farm_id", type=int)
    where, params = (None, None)
    if farm_id:
        where, params = "farm_id = ?", (farm_id,)
    return jsonify(store.list_rows("farmer_queries", where, params, limit=int(request.args.get("limit", 50))))


@app.get("/api/history/advisories")
def hist_advisories():
    farm_id = request.args.get("farm_id", type=int)
    where, params = (None, None)
    if farm_id:
        where, params = "farm_id = ?", (farm_id,)
    return jsonify(store.list_rows("advisories", where, params, limit=int(request.args.get("limit", 50))))


@app.get("/api/history/irrigation")
def hist_irrigation():
    farm_id = request.args.get("farm_id", type=int)
    where, params = (None, None)
    if farm_id:
        where, params = "farm_id = ?", (farm_id,)
    return jsonify(store.list_rows("irrigation_advisories", where, params, limit=int(request.args.get("limit", 50))))


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


@app.get("/api/records/<table>")
def records(table: str):
    allowed = {
        "users", "farms", "farm_crops", "farm_measurements", "crop_predictions",
        "disease_predictions", "farmer_queries", "advisories", "irrigation_advisories",
        "model_versions",
    }
    if table not in allowed:
        return jsonify({"error": "unknown table"}), 404
    return jsonify(store.list_rows(table, order_by="id DESC", limit=int(request.args.get("limit", 50))))


def create_app() -> Flask:
    store.init_db()
    return app


if __name__ == "__main__":
    store.init_db()
    print(f"AgriPilot API  db={db_path()}")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
