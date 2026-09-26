"""
AgriPilot :: explanation generator.

Recommendations are useless if a farmer will not act on them, and the adoption
literature is consistent that *reason-giving* and *quantified consequence* are
what move behaviour.  Each explanation therefore states: what to do, when, why
now (the driving evidence), what happens if it is skipped, and how sure the
agent is.  Strings are kept short because they are delivered over SMS/USSD as
well as in-app.
"""
from __future__ import annotations

TEMPLATES = {
    "en": {
        "irrigate": ("Irrigate {depth} mm today ({hours}). Soil moisture is at "
                     "{pct}% of the safe range and {rain_txt}. Skipping it risks "
                     "about {loss}% of this crop's yield."),
        "skip_irrigation": ("No irrigation needed today. {rain_txt} and the root "
                            "zone still holds {days} more days of water. This saves "
                            "roughly {saved} mm ({rupees} rupees)."),
        "fertilise": ("Apply {n} kg N/ha ({product_kg} kg {product}) with the next "
                      "irrigation. The crop takes up most nitrogen over the coming "
                      "{window} days and the soil pool is short by {gap} kg."),
        "defer_fertiliser": ("Hold the fertiliser for now: {rain_p}% chance of heavy "
                             "rain in 48 hours would wash away about {loss} kg of N."),
        "spray": ("Spray {method} for {pest} within {window} hours. Pest pressure is "
                  "{level} and rising; untreated this costs about {rupees} rupees, "
                  "the spray costs {cost}."),
        "no_spray": ("No spray needed. {pest} pressure is below the economic "
                     "threshold; a calendar spray now would cost {cost} rupees for "
                     "no gain."),
        "harvest": "Crop is at maturity. Plan harvest in the next {days} days.",
    },
    "mr": {
        "irrigate": ("आज {depth} मिमी पाणी द्या ({hours}). जमिनीतील ओलावा सुरक्षित "
                     "पातळीच्या {pct}% आहे आणि {rain_txt}. पाणी न दिल्यास सुमारे "
                     "{loss}% उत्पादन घटू शकते."),
        "skip_irrigation": ("आज पाणी देण्याची गरज नाही. {rain_txt} आणि मुळांच्या "
                            "भागात {days} दिवस पुरेल एवढा ओलावा आहे. यामुळे {saved} "
                            "मिमी पाणी ({rupees} रुपये) वाचते."),
        "fertilise": ("पुढील पाण्याबरोबर {n} किलो नत्र/हेक्टर ({product_kg} किलो "
                      "{product}) द्या. पुढील {window} दिवसांत पिकाला सर्वाधिक नत्र "
                      "लागते; जमिनीत {gap} किलोची कमतरता आहे."),
        "defer_fertiliser": ("खत सध्या थांबवा: ४८ तासांत जोरदार पावसाची {rain_p}% "
                             "शक्यता असून सुमारे {loss} किलो नत्र वाहून जाईल."),
        "spray": ("{window} तासांत {pest} साठी {method} फवारणी करा. किडीचा दाब {level} "
                  "असून वाढत आहे; फवारणी न केल्यास सुमारे {rupees} रुपयांचे नुकसान, "
                  "फवारणीचा खर्च {cost} रुपये."),
        "no_spray": ("फवारणीची गरज नाही. {pest} चा दाब आर्थिक मर्यादेखाली आहे; आत्ता "
                     "फवारणी केल्यास {cost} रुपये विनाकारण खर्च होतील."),
        "harvest": "पीक काढणीस तयार आहे. पुढील {days} दिवसांत काढणीचे नियोजन करा.",
    },
}

ICONS = {"irrigate": "💧", "skip_irrigation": "🚫💧", "fertilise": "🌱",
         "defer_fertiliser": "⏸️", "spray": "🐛", "no_spray": "✅", "harvest": "🌾"}


def render(kind: str, lang: str = "en", **kw) -> str:
    tpl = TEMPLATES.get(lang, TEMPLATES["en"]).get(kind)
    if tpl is None:
        tpl = TEMPLATES["en"][kind]
    return tpl.format(**kw)


def confidence_phrase(conf: float, lang: str = "en") -> str:
    if lang == "mr":
        return "खात्री: " + ("जास्त" if conf > 0.75 else "मध्यम" if conf > 0.5 else "कमी")
    return "confidence: " + ("high" if conf > 0.75 else "medium" if conf > 0.5 else "low")


def sms_pack(text: str, icon: str, limit: int = 160) -> str:
    """Low-bandwidth channel: one icon + truncated text, <=160 bytes."""
    body = f"{icon} {text}"
    return body if len(body.encode()) <= limit else body[:limit - 3] + "..."
