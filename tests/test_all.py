from datetime import timedelta
import pytest
from mops import NOW
from mops.data import generate
from mops.scoring import fit_score, behavior_score, score_lead, decay
from mops.lifecycle import evaluate
from mops.matching import match_account, find_duplicates, email_key
from mops.governance import lint_campaign, lint_all
from mops.attribution import attribute_revenue
from mops.mapping import validate_form, validate_all, CRM_SCHEMA
from mops.hygiene import audit, valid_email
from mops.report import build, render


def lead(**kw):
    base = {"lead_id": "L1", "email": "a@x.example", "title": "VP Marketing", "employees": 300,
            "industry": "software", "country": "US", "created_at": NOW - timedelta(days=40), "events": [],
            "touches": [], "mql_at": None, "first_touch_at": None, "accepted_at": None, "rejected_at": None}
    base.update(kw)
    return base


def test_seed_is_deterministic():
    a, b = generate(7), generate(7)
    assert [l["email"] for l in a["leads"]] == [l["email"] for l in b["leads"]]
    assert generate(8)["leads"][0]["email"] != "" 


def test_decay_halves_at_half_life():
    assert decay(30) == pytest.approx(0.5)
    assert decay(0) == 1


def test_behavior_decays_with_age():
    fresh = lead(events=[{"type": "demo_request", "ts": NOW}])
    old = lead(events=[{"type": "demo_request", "ts": NOW - timedelta(days=60)}])
    assert behavior_score(fresh, NOW) == pytest.approx(40)
    assert behavior_score(old, NOW) == pytest.approx(10)


def test_fit_penalizes_students():
    assert fit_score(lead(title="Student")) < fit_score(lead(title="VP Marketing"))


def test_mql_requires_fit_floor():
    l = lead(title="Intern", employees=5, industry="retail", country="BR",
             events=[{"type": "demo_request", "ts": NOW}, {"type": "webinar_attend", "ts": NOW}])
    assert score_lead(l, NOW)["total"] >= 30
    assert evaluate(l, NOW)["stage"] == "Lead"


def test_mql_then_sla_and_recycle():
    ev = [{"type": "demo_request", "ts": NOW - timedelta(hours=30)}]
    l = lead(events=ev, mql_at=NOW - timedelta(hours=30))
    r = evaluate(l, NOW)
    assert (r["stage"], r["sla"]) == ("MQL", "breached_open")
    l["first_touch_at"] = l["mql_at"] + timedelta(hours=2)
    assert evaluate(l, NOW)["sla"] == "met"
    l["mql_at"] = NOW - timedelta(days=15)
    assert evaluate(l, NOW)["stage"] == "Recycled"


def test_sql_and_rejection_cooldown():
    assert evaluate(lead(accepted_at=NOW), NOW)["stage"] == "SQL"
    rej = lead(rejected_at=NOW - timedelta(days=5))
    assert evaluate(rej, NOW)["stage"] == "Recycled"
    rej2 = lead(rejected_at=NOW - timedelta(days=45), events=[{"type": "demo_request", "ts": NOW}])
    assert evaluate(rej2, NOW)["stage"] == "MQL"


ACCTS = [{"account_id": "A1", "name": "Delta Labs Inc", "domain": "deltalabs.example"}]


def test_match_by_domain_then_name_and_free_mail():
    assert match_account({"email": "q@deltalabs.example"}, ACCTS) == ("A1", "domain")
    assert match_account({"email": "q@gmail.com", "company": "delta labs, LLC"}, ACCTS) == ("A1", "name_exact")
    assert match_account({"email": "q@gmail.com", "company": "Deltalabz"}, ACCTS) == ("A1", "name_fuzzy")
    assert match_account({"email": "q@gmail.com", "company": ""}, ACCTS)[0] is None


def test_dedupe_plus_tag_and_case():
    a = lead(lead_id="L1", email="Bob@x.example", created_at=NOW - timedelta(days=90))
    b = lead(lead_id="L2", email="bob+promo@X.example")
    assert email_key(b["email"]) == "bob@x.example"
    d = find_duplicates([b, a])
    assert d == [{"key": "bob@x.example", "survivor": "L1", "merged": ["L2"]}]


def test_governance_good_and_bad():
    good = {"name": "2025q2_na_demand_playbook", "utm_source": "google", "utm_medium": "cpc"}
    assert lint_campaign(good) == []
    codes = {c for c, _ in lint_campaign({"name": "Spring Promo", "utm_source": "Google", "utm_medium": "Email"})}
    assert {"NAME_PATTERN", "NAME_CASE", "NAME_WHITESPACE", "SOURCE_FORMAT", "MEDIUM_NOT_ALLOWED"} <= codes
    assert "NAME_REGION" in {c for c, _ in lint_campaign({"name": "2025q2_zz_demand_x", "utm_source": "a", "utm_medium": "cpc"})}


def test_attribution_models_sum_to_same_revenue():
    ls = [lead(touches=[{"channel": "email"}, {"channel": "webinar"}, {"channel": "paid_search"}],
               opportunity={"amount": 9000, "status": "won"}),
          lead(touches=[{"channel": "email"}], opportunity={"amount": 5000, "status": "lost"})]
    f, l, lin = (attribute_revenue(ls, m) for m in ("first", "last", "linear"))
    assert f == {"email": 9000} and l == {"paid_search": 9000}
    assert sum(lin.values()) == pytest.approx(9000)
    with pytest.raises(ValueError):
        attribute_revenue(ls, "bogus")


def test_mapping_catches_each_issue_type():
    codes = {i["code"] for i in validate_all()}
    assert {"UNMAPPED", "UNKNOWN_CRM_FIELD", "TYPE_MISMATCH", "LENGTH_OVERFLOW", "PICKLIST_VALUE",
            "REQUIRED_NOT_MAPPED"} <= codes


def test_mapping_clean_form_passes():
    form = {"email": {"crm": "Email", "type": "email", "max": 80}, "company": {"crm": "Company", "type": "string"},
            "src": {"crm": "LeadSource", "type": "picklist", "options": ["web"]},
            "c": {"crm": "Consent", "type": "boolean"}}
    assert validate_form("ok", form) == []


def test_email_validation():
    assert valid_email("a@b.example")
    for bad in ["", "x", "a@@b.com", "a@nodot", "a@b.invalid"]:
        assert not valid_email(bad)


def test_hygiene_counts_match_injected_flaws():
    d = generate(42)
    h = audit(d["leads"], d["accounts"])
    assert h["records"] == len(d["leads"])
    assert h["invalid_emails"] >= 1 and h["duplicate_records"] >= 1
    assert 0 < h["duplicate_rate"] < 0.2
    assert h["missing_by_field"]["email"] >= 1


def test_full_report_builds_and_renders_escaped_html():
    r = build(42)
    html = render(r)
    assert "synthetic" in html.lower() and "Marketo" in html
    assert r["lifecycle"]["stages"] and r["governance"]["campaigns_failing"] >= 1
    assert "<script" not in html


def test_no_real_domains_in_generated_data():
    d = generate(42)
    free = {"gmail.com", "yahoo.com", "outlook.com"}
    for a in d["accounts"]:
        assert a["domain"].endswith(".example")
    for l in d["leads"]:
        if "@" in l["email"] and l["email"].count("@") == 1:
            dom = l["email"].rsplit("@", 1)[1].lower()
            assert dom.endswith((".example", ".invalid")) or dom in free or "." not in dom


def test_invalid_emails_never_form_duplicate_groups():
    ls = [lead(lead_id="L1", email="user@@broken.example"), lead(lead_id="L2", email="user@@broken.example")]
    assert find_duplicates(ls) == []
