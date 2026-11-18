"""Data hygiene audit: missing fields, invalid emails/domains, duplicates, orphans."""
import re
from .matching import find_duplicates, match_account, email_domain
from .data import FREE_MAIL

REQUIRED = ["email", "company", "title", "country", "industry"]
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
BAD_TLDS = {"invalid", "test", "localhost"}


def valid_email(e):
    if not e or not EMAIL_RE.match(e):
        return False
    return e.rsplit(".", 1)[1].lower() not in BAD_TLDS


def audit(leads, accounts):
    n = len(leads)
    missing = {f: sum(1 for l in leads if not (l.get(f) or "")) for f in REQUIRED}
    invalid = [l["lead_id"] for l in leads if not valid_email(l.get("email"))]
    free = sum(1 for l in leads if email_domain(l.get("email", "")) in FREE_MAIL)
    dups = find_duplicates(leads)
    dup_records = sum(len(d["merged"]) for d in dups)
    orphans = sum(1 for l in leads if match_account(l, accounts)[0] is None)
    return {
        "records": n,
        "missing_by_field": missing,
        "missing_rate_by_field": {f: round(c / n, 3) for f, c in missing.items()},
        "invalid_emails": len(invalid), "invalid_email_rate": round(len(invalid) / n, 3),
        "free_mail": free,
        "duplicate_groups": len(dups), "duplicate_records": dup_records,
        "duplicate_rate": round(dup_records / n, 3),
        "unmatched_to_account": orphans, "unmatched_rate": round(orphans / n, 3),
    }
