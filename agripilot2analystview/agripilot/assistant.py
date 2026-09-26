"""
AgriPilot :: Multilingual agricultural assistant (English, Hindi, Marathi).

Answers are assembled from:
  - verified knowledge base (diseases + crop agronomy)
  - farm / soil / weather records
  - genuine crop-recommendation and disease-classifier outputs when stored
  - previous advisories

No agricultural facts are invented. Chemical rates are only quoted from the
knowledge base and labelled as extension references, not prescriptions.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import db as store
from advisory import agronomy_for, build_advisory, load_knowledge, _lang

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
MARATHI_MARKERS = (
    "आहे", "नाही", "कसे", "काय", "पिक", "शेत", "पाणी", "फवारणी", "माती",
    "सिंचन", "द्राक्ष", "कांदा", "भात", "मका", "कापूस", "टोमॅटो", "खत",
    "पाने", "रोगाचा", "शेतकऱ", "किती",
)
HINDI_MARKERS = (
    "है", "नहीं", "कैसे", "क्या", "फसल", "खेत", "पानी", "छिड़काव", "मिट्टी",
    "सिंचाई", "धान", "गेहूं", "टमाटर", "प्याज", "कपास", "खाद", "पत्ति",
    "किसान", "कितना",
)


def detect_language(text: str) -> str:
    if not text or not DEVANAGARI.search(text):
        return "en"
    mr = sum(1 for m in MARATHI_MARKERS if m in text)
    hi = sum(1 for m in HINDI_MARKERS if m in text)
    if mr > hi:
        return "mr"
    if hi > mr:
        return "hi"
    # Default Devanagari without strong markers to Hindi (more common UI default)
    return "hi"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


INTENT_KEYWORDS = {
    "irrigation": (
        "irrigat", "water", "moisture", "drip", "पाणी", "सिंचन", "सिंचाई", "पानी", "ओलावा",
    ),
    "disease": (
        "disease", "blight", "rot", "spot", "leaf", "fungus", "healthy",
        "रोग", "झुलसा", "करपा", "पान", "पत्ती", "फफूंद", "दाग", "ठिपके",
    ),
    "nutrition": (
        "fertiliz", "nitrogen", "phosphorus", "potassium", "npk", "urea", "ph",
        "खत", "खाद", "नत्र", "यूरिया", "युरिया",
    ),
    "crop_choice": (
        "recommend", "which crop", "sow", "plant", "suitable",
        "कौन सी फसल", "कोणते पीक", "लावा", "पेरणी",
    ),
}


def detect_intent(question: str) -> str:
    q = _norm(question)
    scores = {k: sum(1 for w in words if w in q) for k, words in INTENT_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "general"


def retrieve_knowledge(question: str, crop: Optional[str], lang: str) -> List[Dict[str, str]]:
    kb = load_knowledge()
    q = _norm(question)
    hits: List[Tuple[int, Dict[str, str]]] = []

    agro = agronomy_for(crop) if crop else None
    if agro:
        hits.append((3, {
            "source": f"crops_agronomy:{crop}",
            "title": agro.get(f"name_{lang}") or agro.get("name_en"),
            "text": agro.get(f"care_{lang}") or agro.get("care_en"),
        }))
        hits.append((2, {
            "source": f"crops_agronomy:{crop}:npk",
            "title": "NPK reference",
            "text": f"Documented NPK guide: {agro.get('npk_ratio')}; pH {agro.get('ph_range')}; "
                    f"temp {agro.get('temp_range')}; rain {agro.get('rainfall_range')}.",
        }))

    for key, entry in kb.get("diseases", {}).items():
        blob = " ".join([
            key,
            str(entry.get("crop_en", "")),
            str(entry.get("disease_en", "")),
            str(entry.get("disease_hi", "")),
            str(entry.get("disease_mr", "")),
            str(entry.get("scientific_name", "")),
            " ".join(_lang(entry.get("symptoms"), "en") or []),
        ]).lower()
        score = 0
        tokens = [t for t in re.split(r"[^a-zA-Z\u0900-\u097F]+", q) if len(t) > 3]
        for t in tokens:
            if t in blob:
                score += 1
        if crop and crop.lower() in str(entry.get("crop_en", "")).lower():
            score += 1
        if score:
            symptoms = _lang(entry.get("symptoms"), lang) or []
            precautions = _lang(entry.get("precautions"), lang) or []
            prevention = _lang(entry.get("prevention"), lang) or []
            organic = _lang((entry.get("treatment") or {}).get("organic_biological_management"), lang)
            text_parts = []
            if symptoms:
                text_parts.append(symptoms[0] if isinstance(symptoms, list) else str(symptoms))
            if precautions:
                text_parts.append(precautions[0] if isinstance(precautions, list) else str(precautions))
            if prevention:
                text_parts.append(prevention[0] if isinstance(prevention, list) else str(prevention))
            if organic:
                text_parts.append(str(organic))
            hits.append((score, {
                "source": f"diseases:{key}",
                "title": entry.get(f"disease_{lang}") or entry.get("disease_en"),
                "text": " ".join(text_parts),
            }))

    hits.sort(key=lambda x: x[0], reverse=True)
    # unique sources, top 5
    seen = set()
    out = []
    for _, item in hits:
        if item["source"] in seen:
            continue
        seen.add(item["source"])
        out.append(item)
        if len(out) >= 5:
            break
    return out


def _fmt_ctx(ctx: Dict[str, Any], lang: str) -> str:
    farm = ctx.get("farm") or {}
    meas = ctx.get("measurement") or {}
    planted = (ctx.get("active_crop") or {}).get("crop")
    crop_pred = ctx.get("crop_prediction") or {}
    dis = ctx.get("disease_prediction") or {}
    bits_en = [
        f"Farm {farm.get('name')} ({farm.get('district') or farm.get('location')})",
        f"standing crop {planted}" if planted else "no standing crop recorded",
        f"soil {farm.get('soil_type')}, irrigation {farm.get('irrigation_system')}",
    ]
    if meas:
        bits_en.append(
            f"N={meas.get('n')} P={meas.get('p')} K={meas.get('k')} pH={meas.get('ph')} "
            f"T={meas.get('temperature')}°C RH={meas.get('humidity')}% rain={meas.get('rainfall')} mm "
            f"moisture={meas.get('soil_moisture')}%"
        )
    if crop_pred.get("recommended_crop"):
        bits_en.append(
            f"crop model recommends {crop_pred.get('recommended_crop')} "
            f"(conf {crop_pred.get('confidence')})"
        )
    if dis.get("disease"):
        bits_en.append(
            f"disease model: {dis.get('crop')} {dis.get('disease')} "
            f"(conf {dis.get('confidence')}, healthy={dis.get('is_healthy')})"
        )
    ctx_en = "; ".join(bits_en)
    if lang == "hi":
        return "फार्म संदर्भ: " + ctx_en
    if lang == "mr":
        return "शेत संदर्भ: " + ctx_en
    return "Farm context: " + ctx_en


TEMPLATES = {
    "preamble": {
        "en": "Answer based only on this farm's records and the verified AgriPilot knowledge base.",
        "hi": "यह उत्तर केवल इस खेत के रिकॉर्ड और सत्यापित कृषि ज्ञान आधार पर है।",
        "mr": "हे उत्तर फक्त या शेताच्या नोंदी आणि पडताळलेल्या ज्ञानकोशावर आधारित आहे.",
    },
    "no_fact": {
        "en": "The knowledge base does not contain a verified fact for that specific request, so no extra claim is added.",
        "hi": "ज्ञान आधार में इस विशिष्ट प्रश्न का सत्यापित तथ्य नहीं है, इसलिए कोई अतिरिक्त दावा नहीं जोड़ा गया।",
        "mr": "ज्ञानकोशात या विशिष्ट प्रश्नाची पडताळलेली माहिती नाही, म्हणून अतिरिक्त दावा जोडलेला नाही.",
    },
    "safety": {
        "en": "This is decision support, not a pesticide prescription. Confirm any chemical use with a local KVK / agriculture officer.",
        "hi": "यह निर्णय-सहायता है, कीटनाशक नुस्खा नहीं। कोई भी रसायन स्थानीय केवीके / कृषि अधिकारी से पुष्टि के बाद ही उपयोग करें।",
        "mr": "हे निर्णय-सहाय्य आहे, कीटकनाशक प्रिस्क्रिप्शन नाही. कोणतेही रसायन स्थानिक केव्हीके / कृषि अधिकाऱ्यांकडे खात्री करूनच वापरा.",
    },
}


def compose_answer(
    question: str,
    lang: str,
    intent: str,
    ctx: Dict[str, Any],
    snippets: List[Dict[str, str]],
    advisory: Optional[Dict[str, Any]] = None,
) -> str:
    parts = [TEMPLATES["preamble"][lang], _fmt_ctx(ctx, lang)]

    if intent == "irrigation" and advisory:
        irr = advisory.get("irrigation") or {}
        if lang == "hi":
            parts.append(f"सिंचाई सलाह: {irr.get('label')}.")
        elif lang == "mr":
            parts.append(f"सिंचन सल्ला: {irr.get('label')}.")
        else:
            parts.append(f"Irrigation advice: {irr.get('label')}.")
        for r in (irr.get("reasons") or [])[:3]:
            parts.append("- " + r)

    if intent == "crop_choice":
        pred = ctx.get("crop_prediction") or (advisory or {}).get("crop_recommendation") or {}
        if pred.get("recommended_crop"):
            msg = (
                f"The trained crop model recommends {pred.get('recommended_crop')} "
                f"with confidence {pred.get('confidence_pct', pred.get('confidence'))}."
            )
            if lang == "hi":
                msg = (
                    f"प्रशिक्षित फसल मॉडल {pred.get('recommended_crop')} सुझाता है "
                    f"(विश्वास {pred.get('confidence_pct', pred.get('confidence'))})."
                )
            elif lang == "mr":
                msg = (
                    f"प्रशिक्षित पीक मॉडेल {pred.get('recommended_crop')} सुचवते "
                    f"(विश्वास {pred.get('confidence_pct', pred.get('confidence'))})."
                )
            parts.append(msg)

    if intent == "disease":
        dis = ctx.get("disease_prediction")
        if dis:
            label = f"{dis.get('crop')} / {dis.get('disease')} ({dis.get('confidence')})"
            if lang == "hi":
                parts.append(f"पंजीकृत पत्ता-निदान: {label}.")
            elif lang == "mr":
                parts.append(f"नोंदवलेले पान-निदान: {label}.")
            else:
                parts.append(f"Stored leaf diagnosis: {label}.")
        else:
            if lang == "hi":
                parts.append("इस खेत के लिए अभी कोई पत्ता-चित्र निदान सहेजा नहीं गया है।")
            elif lang == "mr":
                parts.append("या शेतासाठी अजून पान-प्रतिमा निदान साठवलेले नाही.")
            else:
                parts.append("No leaf-image diagnosis is stored for this farm yet.")

    if snippets:
        if lang == "hi":
            parts.append("ज्ञान आधार से संबंधित बिंदु:")
        elif lang == "mr":
            parts.append("ज्ञानकोशातील संबंधित मुद्दे:")
        else:
            parts.append("Relevant verified knowledge:")
        for s in snippets:
            if s.get("text"):
                parts.append(f"- {s.get('title')}: {s['text']}")
    else:
        parts.append(TEMPLATES["no_fact"][lang])

    last = ctx.get("last_advisory")
    if last and last.get("summary"):
        if lang == "hi":
            parts.append(f"पिछली सलाह: {last.get('summary')}")
        elif lang == "mr":
            parts.append(f"मागील सल्ला: {last.get('summary')}")
        else:
            parts.append(f"Previous advisory: {last.get('summary')}")

    parts.append(TEMPLATES["safety"][lang])
    return "\n".join(p for p in parts if p)


def answer_question(
    question: str,
    farm_id: Optional[int] = None,
    language: Optional[str] = None,
    persist: bool = True,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    detected = detect_language(question)
    lang = (language or detected or "en").lower()
    if lang not in ("en", "hi", "mr"):
        lang = detected
    intent = detect_intent(question)

    ctx: Dict[str, Any] = {
        "farm": None, "user": None, "active_crop": None, "measurement": None,
        "crop_prediction": None, "disease_prediction": None, "last_advisory": None,
        "recent_queries": [],
    }
    if farm_id is not None:
        ctx = store.farm_context(farm_id, db_path)

    planted = (ctx.get("active_crop") or {}).get("crop")
    snippets = retrieve_knowledge(question, planted, lang)

    advisory = None
    if farm_id is not None and intent in ("irrigation", "nutrition", "crop_choice", "general"):
        try:
            advisory = build_advisory(
                farm_id,
                language=lang,
                run_crop_model=bool(ctx.get("measurement")),
                persist=False,
                db_path=db_path,
            )
        except Exception:
            advisory = None

    text = compose_answer(question, lang, intent, ctx, snippets, advisory)
    payload = {
        "question": question,
        "language": lang,
        "detected_language": detected,
        "intent": intent,
        "answer": text,
        "sources": snippets,
        "farm_id": farm_id,
    }
    if persist and farm_id is not None:
        qid = store.insert("farmer_queries", {
            "farm_id": farm_id,
            "user_id": (ctx.get("user") or {}).get("id"),
            "language": lang,
            "detected_language": detected,
            "question": question,
            "answer": text,
            "sources_json": json.dumps(snippets, ensure_ascii=False),
            "created_at": store.now(),
        }, db_path)
        payload["id"] = qid
    return payload
