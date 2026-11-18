"""UTM and campaign naming governance linter.

Campaign name convention:  {year}q{1-4}_{region}_{objective}_{slug}
  e.g. 2025q2_na_demand_playbook   (all lowercase, slug = [a-z0-9-]+)
utm_source: lowercase [a-z0-9-]. utm_medium must come from an allowed list.
"""
import re

ALLOWED_MEDIUMS = {"cpc", "paid-social", "email", "webinar", "organic", "partner", "syndication"}
REGIONS = {"na", "emea", "apac", "latam"}
OBJECTIVES = {"demand", "nurture", "brand"}
NAME_RE = re.compile(r"^(20\d{2})q([1-4])_([a-z]+)_([a-z]+)_([a-z0-9-]+)$")
TOKEN_RE = re.compile(r"^[a-z0-9-]+$")


def lint_campaign(c):
    v = []
    name, src, med = c.get("name", ""), c.get("utm_source", ""), c.get("utm_medium", "")
    m = NAME_RE.match(name)
    if not m:
        if name != name.lower():
            v.append(("NAME_CASE", "campaign name must be lowercase"))
        if re.search(r"\s", name):
            v.append(("NAME_WHITESPACE", "campaign name contains spaces"))
        v.append(("NAME_PATTERN", "does not match {year}q{n}_{region}_{objective}_{slug}"))
    else:
        if m.group(3) not in REGIONS:
            v.append(("NAME_REGION", f"unknown region '{m.group(3)}'"))
        if m.group(4) not in OBJECTIVES:
            v.append(("NAME_OBJECTIVE", f"unknown objective '{m.group(4)}'"))
    if not TOKEN_RE.match(src):
        v.append(("SOURCE_FORMAT", f"utm_source '{src}' must be lowercase [a-z0-9-]"))
    if med not in ALLOWED_MEDIUMS:
        v.append(("MEDIUM_NOT_ALLOWED", f"utm_medium '{med}' not in allowed list"))
    return v


def lint_all(campaigns):
    report = []
    for c in campaigns:
        for code, msg in lint_campaign(c):
            report.append({"campaign_id": c["campaign_id"], "name": c["name"], "code": code, "message": msg})
    bad = {r["campaign_id"] for r in report}
    return {"violations": report, "campaigns_checked": len(campaigns),
            "campaigns_failing": len(bad), "pass_rate": round(1 - len(bad) / len(campaigns), 3) if campaigns else None}
