"""Campaign performance and source attribution (first-touch, last-touch, linear)."""
from collections import defaultdict


def _won(l):
    o = l.get("opportunity")
    return o["amount"] if o and o["status"] == "won" else 0


def attribute_revenue(leads, model):
    """Distribute each won deal across touches' channels. Returns {channel: revenue}."""
    rev = defaultdict(float)
    for l in leads:
        amt = _won(l)
        touches = l.get("touches") or []
        if not amt or not touches:
            continue
        if model == "first":
            rev[touches[0]["channel"]] += amt
        elif model == "last":
            rev[touches[-1]["channel"]] += amt
        elif model == "linear":
            for t in touches:
                rev[t["channel"]] += amt / len(touches)
        else:
            raise ValueError(model)
    return {k: round(v, 2) for k, v in rev.items()}


def campaign_performance(campaigns, leads, stage_by_lead):
    """Per-campaign funnel using each lead's sourcing campaign (first touch)."""
    rows = {c["campaign_id"]: {**c, "leads": 0, "mqls": 0, "sqls": 0, "won": 0, "revenue": 0} for c in campaigns}
    for l in leads:
        r = rows.get(l["source_campaign"])
        if not r:
            continue
        r["leads"] += 1
        st = stage_by_lead.get(l["lead_id"], "Lead")
        if st in ("MQL", "SQL") or l.get("mql_at"):
            r["mqls"] += 1
        if st == "SQL":
            r["sqls"] += 1
        w = _won(l)
        if w:
            r["won"] += 1
            r["revenue"] += w
    for r in rows.values():
        r["cost_per_lead"] = round(r["spend"] / r["leads"], 2) if r["leads"] else None
        r["cost_per_mql"] = round(r["spend"] / r["mqls"], 2) if r["mqls"] else None
        r["mql_rate"] = round(r["mqls"] / r["leads"], 3) if r["leads"] else None
        r["roi"] = round((r["revenue"] - r["spend"]) / r["spend"], 2) if r["spend"] else None
    return sorted(rows.values(), key=lambda r: r["campaign_id"])
