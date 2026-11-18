"""Lead-to-account matching and lead dedupe."""
import re
from difflib import SequenceMatcher
from .data import FREE_MAIL

_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$")
_SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|co|company)\b\.?", re.I)


def email_domain(email):
    return email.rsplit("@", 1)[1].strip().lower() if "@" in (email or "") else ""


def norm_company(name):
    return re.sub(r"[^a-z0-9]", "", _SUFFIX.sub("", (name or "").lower()))


def match_account(lead, accounts):
    """Return (account_id|None, method). Domain first, then exact normalized name, then fuzzy name."""
    dom = email_domain(lead.get("email", ""))
    if dom and dom not in FREE_MAIL:
        for a in accounts:
            if a["domain"] == dom:
                return a["account_id"], "domain"
    key = norm_company(lead.get("company"))
    if key:
        for a in accounts:
            if norm_company(a["name"]) == key:
                return a["account_id"], "name_exact"
        best = max(accounts, key=lambda a: SequenceMatcher(None, key, norm_company(a["name"])).ratio())
        if SequenceMatcher(None, key, norm_company(best["name"])).ratio() >= 0.85:
            return best["account_id"], "name_fuzzy"
    return None, "unmatched"


def email_key(email):
    e = (email or "").strip().lower()
    if not _EMAIL.match(e):
        return ""
    local, dom = e.rsplit("@", 1)
    return local.split("+", 1)[0] + "@" + dom


def find_duplicates(leads):
    """Group leads sharing a normalized email. Survivor = oldest record."""
    groups = {}
    for l in leads:
        k = email_key(l.get("email"))
        if k:
            groups.setdefault(k, []).append(l)
    out = []
    for k, g in groups.items():
        if len(g) > 1:
            g = sorted(g, key=lambda l: l["created_at"])
            out.append({"key": k, "survivor": g[0]["lead_id"], "merged": [l["lead_id"] for l in g[1:]]})
    return out
