"""Lifecycle stage engine: Lead -> MQL -> SQL, with SLA timers and recycle rules.

Rules (all constants below):
- MQL when total score >= threshold and fit >= MIN_FIT (behavior alone is not enough).
- Sales must make first touch within SLA_FIRST_TOUCH_HOURS of MQL, else SLA breach.
- SQL = sales accepted. Rejected -> Recycled.
- MQL untouched or unaccepted for RECYCLE_AFTER_DAYS -> Recycled (back to nurture).
- Recycled leads become MQL again only after COOLDOWN_DAYS and a fresh qualifying score.
"""
from datetime import timedelta
from .scoring import score_lead, MQL_THRESHOLD

MIN_FIT = 20
SLA_FIRST_TOUCH_HOURS = 24
RECYCLE_AFTER_DAYS = 14
COOLDOWN_DAYS = 30


def evaluate(lead, now):
    s = score_lead(lead, now)
    out = {"lead_id": lead["lead_id"], "score": s["total"], "stage": "Lead", "sla": None, "reason": ""}
    mql_at = lead.get("mql_at")
    qualifies = s["total"] >= MQL_THRESHOLD and s["fit"] >= MIN_FIT
    if lead.get("accepted_at"):
        out.update(stage="SQL", reason="accepted by sales")
        return out
    if lead.get("rejected_at"):
        cooled = (now - lead["rejected_at"]) >= timedelta(days=COOLDOWN_DAYS)
        if cooled and qualifies:
            out.update(stage="MQL", reason="re-qualified after cooldown")
        else:
            out.update(stage="Recycled", reason="rejected by sales")
        return out
    if not mql_at:
        if qualifies:
            out.update(stage="MQL", reason="score crossed threshold")
        return out
    # was an MQL; apply SLA + recycle
    first = lead.get("first_touch_at")
    deadline = mql_at + timedelta(hours=SLA_FIRST_TOUCH_HOURS)
    if first:
        out["sla"] = "met" if first <= deadline else "breached_late"
    else:
        out["sla"] = "breached_open" if now > deadline else "running"
    if now - mql_at >= timedelta(days=RECYCLE_AFTER_DAYS):
        out.update(stage="Recycled", reason=f"no acceptance within {RECYCLE_AFTER_DAYS}d")
    else:
        out.update(stage="MQL", reason="awaiting sales")
    return out


def summarize(results):
    counts, sla = {}, {}
    for r in results:
        counts[r["stage"]] = counts.get(r["stage"], 0) + 1
        if r["sla"]:
            sla[r["sla"]] = sla.get(r["sla"], 0) + 1
    judged = sla.get("met", 0) + sla.get("breached_late", 0) + sla.get("breached_open", 0)
    return {"stages": counts, "sla": sla, "sla_met_rate": round(sla.get("met", 0) / judged, 3) if judged else None}
