"""
AgriPilot :: Farm Advisory Fusion Engine (Step 4).

Combines farm records, soil/weather measurements, the trained crop recommender,
optional disease-classifier output, and the verified multilingual knowledge base.

Predictions are only used when a real model result is supplied or loaded from
saved Step-2 / Step-3 artifacts. Chemical product rates are never invented;
extension text is quoted from the knowledge base and labelled as non-prescription.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ML_DIR = os.path.join(HERE, "ml")
if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)

from paths import KB_PATH
import db as store

_KB = None
_CROP_ENGINE = None


def load_knowledge() -> Dict[str, Any]:
    global _KB
    if _KB is None:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            _KB = json.load(f)
    return _KB


def get_crop_engine():
    """Load the saved Step-2 production bundle (no retraining)."""
    global _CROP_ENGINE
    if _CROP_ENGINE is None:
        from crop_recommender import CropRecommender
        _CROP_ENGINE = CropRecommender()
    return _CROP_ENGINE


def _lang(value: Any, lang: str, fallback: str = "en") -> Any:
    if isinstance(value, dict):
        if lang in value:
            return value[lang]
        if fallback in value:
            return value[fallback]
    return value


def agronomy_for(crop: Optional[str]) -> Optional[Dict[str, Any]]:
    if not crop:
        return None
    kb = load_knowledge()
    crops = kb.get("crops_agronomy", {})
    key = crop.strip().lower()
    aliases = {
        "grape": "grapes", "paddy": "rice", "dhaan": "rice",
        "chana": "chickpea", "gram": "chickpea", "kapas": "cotton",
        "tamatar": "tomato", "pyaz": "onion", "kanda": "onion",
    }
    key = aliases.get(key, key)
    if key in crops:
        return crops[key]
    for k, v in crops.items():
        names = " ".join(
            str(v.get(f"name_{lg}", "")).lower() for lg in ("en", "hi", "mr")
        )
        if key in k or key in names:
            return v
    return None


def disease_entry(class_name: Optional[str], crop: Optional[str] = None, disease: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    kb = load_knowledge()
    diseases = kb.get("diseases", {})
    if class_name and class_name in diseases:
        return class_name, diseases[class_name]
    if crop and disease:
        crop_l = crop.lower()
        dis_l = disease.lower()
        for k, v in diseases.items():
            if crop_l in str(v.get("crop_en", "")).lower() and dis_l in str(v.get("disease_en", "")).lower():
                return k, v
    return None


def run_crop_recommendation(
    n: float, p: float, k: float, temperature: float, humidity: float, ph: float, rainfall: float
) -> Dict[str, Any]:
    engine = get_crop_engine()
    return engine.predict(
        n=n, p=p, k=k, temperature=temperature, humidity=humidity, ph=ph, rainfall=rainfall
    )


def _parse_range(text: Optional[str]) -> Optional[Tuple[float, float]]:
    if not text:
        return None
    cleaned = (
        text.replace("°C", "").replace("%", "").replace("mm", "")
        .replace("–", "-").replace("—", "-")
    )
    parts = cleaned.split("-")
    try:
        nums = [float(p.strip()) for p in parts if p.strip()]
        if len(nums) >= 2:
            return nums[0], nums[1]
    except ValueError:
        return None
    return None


def _in_range(value: Optional[float], rng: Optional[Tuple[float, float]]) -> Optional[bool]:
    if value is None or rng is None:
        return None
    return rng[0] <= value <= rng[1]


def irrigation_decision(measurement: Dict[str, Any], crop: Optional[str], disease: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    moisture = measurement.get("soil_moisture")
    # `rainfall` in this project is the same seasonal feature used by the crop model,
    # not necessarily today's storm total. Daily rain is optional (`recent_rain_mm`).
    seasonal_rain = measurement.get("rainfall")
    recent_rain = measurement.get("recent_rain_mm")
    humidity = measurement.get("humidity")
    rec = "monitor"
    reasons: List[str] = []

    if recent_rain is not None and recent_rain >= 20:
        rec = "skip"
        reasons.append(
            f"Recorded recent rain is {recent_rain:.1f} mm, so extra irrigation is usually unnecessary."
        )
    elif moisture is not None:
        if moisture < 25:
            rec = "irrigate"
            reasons.append(
                f"Root-zone soil moisture is {moisture:.1f}%, below a conservative 25% comfort band for most field crops."
            )
        elif moisture < 40:
            rec = "light_irrigation"
            reasons.append(
                f"Soil moisture is {moisture:.1f}%; a light irrigation is justified unless the field still feels wet."
            )
        else:
            rec = "skip"
            reasons.append(
                f"Soil moisture is {moisture:.1f}%, so irrigation can be skipped today."
            )
    else:
        rec = "monitor"
        reasons.append("Soil moisture was not recorded; irrigate only after checking the field or probe.")

    if seasonal_rain is not None:
        reasons.append(
            f"Seasonal rainfall feature used by the crop model is {seasonal_rain:.1f} mm (not treated as today's rainfall)."
        )

    agro = agronomy_for(crop)
    if agro:
        reasons.append(f"Crop-specific water note ({agro.get('name_en', crop)}): {agro.get('care_en')}")

    if disease and not disease.get("is_healthy"):
        if humidity and humidity >= 80:
            reasons.append(
                "Leaf disease is present and humidity is high; keep foliage dry (avoid overhead sprinklers)."
            )
        rec_note = "Avoid wetting leaves if a foliar disease is active."
        reasons.append(rec_note)

    labels = {
        "irrigate": "Irrigate today (drip/furrow preferred)",
        "light_irrigation": "Apply a light irrigation",
        "skip": "Skip irrigation today",
        "monitor": "Check the field before irrigating",
    }
    return {
        "recommendation": rec,
        "label": labels.get(rec, rec),
        "reasons": reasons,
        "soil_moisture": moisture,
        "rainfall": seasonal_rain,
        "recent_rain_mm": recent_rain,
    }


def nutrition_notes(measurement: Dict[str, Any], crop: Optional[str]) -> List[Dict[str, str]]:
    notes: List[Dict[str, str]] = []
    agro = agronomy_for(crop)
    if agro:
        notes.append({
            "factor": "Extension NPK guide",
            "status": "Reference",
            "detail": (
                f"{agro.get('name_en', crop)} typical fertilizer schedule in the knowledge base is "
                f"{agro.get('npk_ratio')} (ICAR/MPKV reference, not a custom dose)."
            ),
        })
        ph_rng = _parse_range(agro.get("ph_range"))
        if measurement.get("ph") is not None and ph_rng:
            ok = _in_range(measurement["ph"], ph_rng)
            notes.append({
                "factor": "Soil pH",
                "status": "Aligned" if ok else "Check",
                "detail": (
                    f"Measured pH {measurement['ph']} vs documented range {agro.get('ph_range')}."
                ),
            })
    for key, label in (("n", "Nitrogen (N)"), ("p", "Phosphorus (P)"), ("k", "Potassium (K)")):
        val = measurement.get(key)
        if val is None:
            continue
        notes.append({
            "factor": label,
            "status": "Observed",
            "detail": f"Latest farm measurement: {val}",
        })
    return notes


def _crop_fit_reasons(planted: Optional[str], crop_pred: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    if not crop_pred:
        return []
    recommended = crop_pred.get("recommended_crop")
    conf = crop_pred.get("confidence_pct", crop_pred.get("confidence"))
    reasons = [{
        "factor": "Crop recommendation model",
        "status": "Model",
        "detail": (
            f"Saved Random Forest / production crop model recommends {recommended} "
            f"(confidence {conf}). This is the genuine Step-2 inference, not a hardcoded label."
        ),
    }]
    if planted and recommended and planted.lower() not in recommended.lower() and recommended.lower() not in planted.lower():
        reasons.append({
            "factor": "Planted vs recommended",
            "status": "Mismatch",
            "detail": (
                f"This farm's active crop is {planted}, while the soil/weather profile scores highest for {recommended}. "
                "Treat this as a planning signal for the next season, not as an order to uproot the standing crop."
            ),
        })
    else:
        reasons.append({
            "factor": "Planted vs recommended",
            "status": "Aligned",
            "detail": f"Standing crop {planted or recommended} is consistent with the model recommendation.",
        })
    for r in crop_pred.get("reasons") or []:
        if isinstance(r, dict):
            reasons.append(r)
    return reasons


def _disease_reasons(disease_pred: Optional[Dict[str, Any]], lang: str) -> List[Dict[str, str]]:
    if not disease_pred:
        return [{
            "factor": "Disease classifier",
            "status": "Unavailable",
            "detail": "No leaf-image diagnosis is stored for this farm yet. Advisory does not invent a disease label.",
        }]
    healthy = bool(disease_pred.get("is_healthy"))
    name = disease_pred.get("disease") or disease_pred.get("class_name")
    conf = disease_pred.get("confidence_pct", disease_pred.get("confidence"))
    reasons = [{
        "factor": "Disease classifier",
        "status": "Healthy" if healthy else "Detected",
        "detail": (
            f"Step-3 MobileNetV2 model predicted {disease_pred.get('crop')} — {name} "
            f"(confidence {conf}%)."
        ),
    }]
    found = disease_entry(disease_pred.get("class_name"), disease_pred.get("crop"), disease_pred.get("disease"))
    if found:
        _, entry = found
        symptoms = _lang(entry.get("symptoms"), lang) or []
        if isinstance(symptoms, list) and symptoms:
            reasons.append({
                "factor": "Documented symptoms",
                "status": "Knowledge base",
                "detail": symptoms[0],
            })
        precautions = _lang(entry.get("precautions"), lang) or []
        if isinstance(precautions, list) and precautions:
            reasons.append({
                "factor": "Documented precaution",
                "status": "Knowledge base",
                "detail": precautions[0],
            })
        organic = (entry.get("treatment") or {}).get("organic_biological_management")
        organic_txt = _lang(organic, lang) if organic else None
        if organic_txt:
            reasons.append({
                "factor": "Biological / organic management",
                "status": "Knowledge base",
                "detail": str(organic_txt),
            })
        chemical = (entry.get("treatment") or {}).get("chemical_management")
        chemical_txt = _lang(chemical, lang) if chemical else None
        if chemical_txt and not healthy:
            reasons.append({
                "factor": "Chemical reference (not a prescription)",
                "status": "Extension quote",
                "detail": (
                    "Quoted from ICAR/MPKV knowledge base. Confirm locally with KVK / agriculture officer "
                    f"before any spray: {chemical_txt}"
                ),
            })
    return reasons


def localize_summary(lang: str, crop: str, irr: Dict[str, Any], disease_pred: Optional[Dict[str, Any]]) -> Dict[str, str]:
    irr_en = irr["label"]
    dis = "no leaf diagnosis on file"
    if disease_pred:
        dis = (
            "leaf appears healthy"
            if disease_pred.get("is_healthy")
            else f"leaf diagnosis: {disease_pred.get('disease')} ({disease_pred.get('confidence_pct', disease_pred.get('confidence'))})"
        )
    en = f"For {crop}: {irr_en}. {dis}."
    hi_map = {
        "Irrigate today (drip/furrow preferred)": "आज ड्रिप/कुंड से सिंचाई करें",
        "Apply a light irrigation": "हल्की सिंचाई करें",
        "Skip irrigation today": "आज सिंचाई न करें",
        "Check the field before irrigating": "सिंचाई से पहले खेत देखें",
    }
    mr_map = {
        "Irrigate today (drip/furrow preferred)": "आज ठिबक/सारणीने पाणी द्या",
        "Apply a light irrigation": "हलके पाणी द्या",
        "Skip irrigation today": "आज पाणी देऊ नका",
        "Check the field before irrigating": "पाणी देण्यापूर्वी शेत तपासा",
    }
    hi = f"{crop} पिकासाठी: {hi_map.get(irr_en, irr_en)}। पान निदान: {dis}।"
    mr = f"{crop} पिकासाठी: {mr_map.get(irr_en, irr_en)}. पान निदान: {dis}."
    return {"en": en, "hi": hi, "mr": mr}


def build_advisory(
    farm_id: int,
    language: str = "en",
    crop_prediction: Optional[Dict[str, Any]] = None,
    disease_prediction: Optional[Dict[str, Any]] = None,
    run_crop_model: bool = True,
    persist: bool = True,
    db_path: Optional[str] = None,
    exclude_demo: bool = False,
) -> Dict[str, Any]:
    ctx = store.farm_context(farm_id, db_path, exclude_demo=exclude_demo)
    farm = ctx["farm"]
    measurement = ctx["measurement"] or {}
    planted = (ctx["active_crop"] or {}).get("crop")
    language = (language or "en").lower()
    if language not in ("en", "hi", "mr"):
        language = "en"

    needed = ("n", "p", "k", "temperature", "humidity", "ph", "rainfall")
    can_run = all(measurement.get(k) is not None for k in needed)
    if crop_prediction is None and ctx.get("crop_prediction") and not run_crop_model:
        crop_prediction = ctx["crop_prediction"]
        if crop_prediction.get("reasons_json") and not crop_prediction.get("reasons"):
            try:
                crop_prediction["reasons"] = json.loads(crop_prediction["reasons_json"])
            except Exception:
                pass
    if crop_prediction is None and run_crop_model and can_run:
        crop_prediction = run_crop_recommendation(
            n=measurement["n"], p=measurement["p"], k=measurement["k"],
            temperature=measurement["temperature"], humidity=measurement["humidity"],
            ph=measurement["ph"], rainfall=measurement["rainfall"],
        )

    crop_pred_id = None
    if persist and crop_prediction and crop_prediction.get("recommended_crop"):
        crop_pred_id = store.insert("crop_predictions", {
            "farm_id": farm_id,
            "measurement_id": measurement.get("id"),
            "recommended_crop": crop_prediction["recommended_crop"],
            "confidence": crop_prediction.get("confidence"),
            "alternatives_json": json.dumps(crop_prediction.get("alternatives", []), ensure_ascii=False),
            "reasons_json": json.dumps(crop_prediction.get("reasons", []), ensure_ascii=False),
            "input_json": json.dumps(crop_prediction.get("input_values", {}), ensure_ascii=False),
            "model_name": crop_prediction.get("model_used", "Random Forest"),
            "model_version": "step2-production-bundle",
            "created_at": store.now(),
        }, db_path)

    if disease_prediction is None:
        disease_prediction = ctx.get("disease_prediction")

    irr = irrigation_decision(measurement, planted, disease_prediction)
    reasons: List[Dict[str, Any]] = []
    reasons.append({
        "factor": "Farm context",
        "status": "Observed",
        "detail": (
            f"{farm.get('name')} in {farm.get('district') or farm.get('location')}, "
            f"soil={farm.get('soil_type')}, irrigation={farm.get('irrigation_system')}, "
            f"standing crop={planted}."
        ),
    })
    if measurement:
        reasons.append({
            "factor": "Latest measurements",
            "status": "Observed",
            "detail": (
                f"N={measurement.get('n')}, P={measurement.get('p')}, K={measurement.get('k')}, "
                f"pH={measurement.get('ph')}, T={measurement.get('temperature')}°C, "
                f"RH={measurement.get('humidity')}%, rain={measurement.get('rainfall')} mm, "
                f"soil moisture={measurement.get('soil_moisture')}%."
            ),
        })
    reasons.extend(_crop_fit_reasons(planted, crop_prediction))
    reasons.extend(nutrition_notes(measurement, planted))
    reasons.extend(_disease_reasons(disease_prediction, language))
    for r in irr["reasons"]:
        reasons.append({"factor": "Irrigation", "status": irr["recommendation"], "detail": r})

    if ctx.get("last_advisory"):
        reasons.append({
            "factor": "Previous advisory",
            "status": "History",
            "detail": ctx["last_advisory"].get("summary") or ctx["last_advisory"].get("title"),
        })

    actions = [
        {"type": "irrigation", "text": irr["label"]},
    ]
    agro = agronomy_for(planted)
    if agro:
        care = agro.get(f"care_{language}") or agro.get("care_en")
        actions.append({"type": "crop_care", "text": care})
    actions.append({
        "type": "safety",
        "text": "Do not apply unlabelled chemicals. Confirm any spray with a local KVK / agriculture officer.",
    })

    summaries = localize_summary(language, planted or (crop_prediction or {}).get("recommended_crop") or "crop", irr, disease_prediction)
    payload = {
        "farm_id": farm_id,
        "language": language,
        "farm": farm,
        "standing_crop": planted,
        "measurement": measurement,
        "crop_recommendation": crop_prediction,
        "disease_prediction": disease_prediction,
        "irrigation": irr,
        "reasons": reasons,
        "actions": actions,
        "summary": summaries.get(language, summaries["en"]),
        "summary_all_languages": summaries,
        "knowledge_source": "data/agri_knowledge_multilingual.json (ICAR / MPKV Rahuri)",
        "models_used": {
            "crop": crop_prediction.get("model_used") if crop_prediction else None,
            "disease": "MobileNetV2" if disease_prediction else None,
        },
    }

    advisory_id = None
    if persist:
        advisory_id = store.insert("advisories", {
            "farm_id": farm_id,
            "language": language,
            "title": f"Farm advisory — {farm.get('name')}",
            "summary": payload["summary"],
            "reasons_json": json.dumps(reasons, ensure_ascii=False),
            "actions_json": json.dumps(actions, ensure_ascii=False),
            "payload_json": json.dumps({
                "irrigation": irr,
                "models_used": payload["models_used"],
            }, ensure_ascii=False),
            "crop_prediction_id": crop_pred_id,
            "disease_prediction_id": (disease_prediction or {}).get("id"),
            "created_at": store.now(),
        }, db_path)
        store.insert("irrigation_advisories", {
            "farm_id": farm_id,
            "advisory_id": advisory_id,
            "recommendation": irr["recommendation"],
            "reason": " | ".join(irr["reasons"]),
            "soil_moisture": irr.get("soil_moisture"),
            "rainfall": irr.get("rainfall"),
            "created_at": store.now(),
        }, db_path)
        payload["id"] = advisory_id
        payload["crop_prediction_id"] = crop_pred_id
    return payload
