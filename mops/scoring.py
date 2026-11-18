"""Lead scoring: fit (who they are) + behavior (what they did, with exponential decay)."""
import math

MQL_THRESHOLD = 60
HALF_LIFE_DAYS = 30.0
BEHAVIOR_CAP = 60

FIT_TITLE = [("cmo", 25), ("vp", 22), ("head", 20), ("director", 18), ("founder", 18), ("manager", 10),
             ("analyst", 6), ("coordinator", 3)]
FIT_NEGATIVE_TITLES = ("student", "intern")
TARGET_INDUSTRIES = {"software", "financial services", "healthcare"}
TARGET_COUNTRIES = {"US", "CA", "GB"}
EVENT_POINTS = {"email_open": 1, "email_click": 4, "page_view": 2, "pricing_view": 12,
                "webinar_attend": 15, "demo_request": 40, "form_fill": 8}


def fit_score(lead):
    t = (lead.get("title") or "").lower()
    pts = 0
    if any(n in t for n in FIT_NEGATIVE_TITLES):
        pts -= 20
    else:
        pts += next((p for k, p in FIT_TITLE if k in t), 0)
    emp = lead.get("employees") or 0
    pts += 20 if 100 <= emp <= 5000 else 10 if emp >= 25 else 0
    pts += 10 if lead.get("industry") in TARGET_INDUSTRIES else 0
    pts += 5 if lead.get("country") in TARGET_COUNTRIES else 0
    return pts


def decay(age_days, half_life=HALF_LIFE_DAYS):
    return 0.5 ** (max(age_days, 0) / half_life)


def behavior_score(lead, now):
    raw = sum(EVENT_POINTS.get(e["type"], 0) * decay((now - e["ts"]).total_seconds() / 86400)
              for e in lead.get("events", []))
    return min(raw, BEHAVIOR_CAP)


def score_lead(lead, now):
    fit, beh = fit_score(lead), behavior_score(lead, now)
    return {"fit": fit, "behavior": round(beh, 1), "total": round(max(fit + beh, 0), 1)}
