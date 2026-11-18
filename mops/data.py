"""Seeded synthetic data generator. Nothing here is real: names, domains
(.example), companies and numbers are all random. Flaws are injected on
purpose so the audit modules have something to find."""
import random
from datetime import timedelta
from . import NOW

INDUSTRIES = ["software", "manufacturing", "healthcare", "financial services", "retail", "education", "logistics"]
TITLES = ["VP Marketing", "Director of Demand Gen", "Marketing Manager", "CMO", "Operations Analyst",
          "Founder", "Sales Director", "Student", "Intern", "Consultant", "Head of RevOps", "Coordinator"]
COUNTRIES = ["US", "US", "US", "CA", "GB", "DE", "FR", "IN", "BR"]
CHANNELS = ["paid_search", "paid_social", "email", "webinar", "organic", "partner", "content_syndication"]
WORDS_A = ["north", "blue", "iron", "bright", "summit", "delta", "open", "prime", "cedar", "lumen", "atlas", "quartz"]
WORDS_B = ["works", "labs", "systems", "group", "freight", "health", "dynamics", "supply", "partners", "tech"]
SUFFIX = ["", " Inc", " LLC", " Ltd", " Corp"]
FREE_MAIL = ["gmail.com", "yahoo.com", "outlook.com"]
EVENT_TYPES = ["email_open", "email_click", "page_view", "pricing_view", "webinar_attend", "demo_request", "form_fill"]
REGIONS = ["na", "emea", "apac", "latam"]


def make_accounts(rng, n):
    accounts, seen = [], set()
    while len(accounts) < n:
        a, b = rng.choice(WORDS_A), rng.choice(WORDS_B)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        accounts.append({
            "account_id": f"A{len(accounts)+1:04d}",
            "name": f"{a.title()}{b.title()}{rng.choice(SUFFIX)}",
            "domain": f"{a}{b}.example",
            "employees": rng.choice([8, 25, 60, 120, 300, 800, 2500, 9000]),
            "industry": rng.choice(INDUSTRIES),
        })
    return accounts


def make_campaigns(rng, count=14):
    camps = []
    for i in range(count):
        ch = CHANNELS[i % len(CHANNELS)]
        slug = rng.choice(["ops", "growth", "benchmark", "toolkit", "roadshow", "playbook"])
        good = rng.random() > 0.3
        if good:
            name = f"2025q{rng.choice([1, 2])}_{rng.choice(REGIONS)}_{rng.choice(['demand', 'nurture', 'brand'])}_{slug}"
            medium = {"paid_search": "cpc", "paid_social": "paid-social", "email": "email", "webinar": "webinar",
                      "organic": "organic", "partner": "partner", "content_syndication": "syndication"}[ch]
            source = {"paid_search": "google", "paid_social": "linkedin", "email": "newsletter", "webinar": "livestorm",
                      "organic": "google", "partner": "partnerco", "content_syndication": "syndicator"}[ch]
        else:  # seeded governance violations
            name = rng.choice([f"Spring Promo {slug}", f"Q2-{slug}-FINAL", f"2025q2_NA_demand_{slug}", f"test campaign {i}"])
            medium = rng.choice(["Email", "social", "CPC "])
            source = rng.choice(["Google", "li", "NewsLetter"])
        camps.append({
            "campaign_id": f"C{i+1:03d}", "name": name, "channel": ch, "utm_source": source,
            "utm_medium": medium, "spend": rng.choice([1500, 3200, 5000, 8000, 12000, 20000]),
        })
    return camps


def make_leads(rng, accounts, campaigns, n):
    leads = []
    for i in range(n):
        acct = rng.choice(accounts)
        camp = rng.choice(campaigns)
        created = NOW - timedelta(days=rng.randint(1, 120), hours=rng.randint(0, 23))
        free = rng.random() < 0.08
        domain = rng.choice(FREE_MAIL) if free else acct["domain"]
        email = f"user{i+1:04d}@{domain}"
        lead = {
            "lead_id": f"L{i+1:05d}", "email": email, "company": acct["name"] if not free else rng.choice([acct["name"], ""]),
            "title": rng.choice(TITLES), "employees": acct["employees"], "industry": acct["industry"],
            "country": rng.choice(COUNTRIES), "created_at": created,
            "source_campaign": camp["campaign_id"], "channel": camp["channel"],
            "utm_source": camp["utm_source"], "utm_medium": camp["utm_medium"], "utm_campaign": camp["name"],
        }
        # behavior events within lifetime of the lead
        events = []
        for _ in range(rng.choice([0, 1, 2, 3, 5, 8, 12])):
            ts = created + timedelta(days=rng.random() * (NOW - created).days, hours=rng.randint(0, 20))
            events.append({"type": rng.choice(EVENT_TYPES), "ts": min(ts, NOW)})
        lead["events"] = sorted(events, key=lambda e: e["ts"])
        # extra touches for multi-touch attribution
        touches = [{"ts": created, "campaign_id": camp["campaign_id"], "channel": camp["channel"]}]
        for _ in range(rng.choice([0, 0, 1, 2])):
            c2 = rng.choice(campaigns)
            touches.append({"ts": created + timedelta(days=rng.randint(1, 30)), "campaign_id": c2["campaign_id"], "channel": c2["channel"]})
        lead["touches"] = sorted(touches, key=lambda t: t["ts"])
        # sales actions
        lead["first_touch_at"] = None
        lead["accepted_at"] = None
        lead["rejected_at"] = None
        lead["opportunity"] = None
        leads.append(lead)

    # seeded flaws
    for lead in rng.sample(leads, int(n * 0.04)):
        lead["email"] = rng.choice(["not-an-email", "user@@broken.example", "name@nodot", "x@tempmail.invalid", ""])
    for lead in rng.sample(leads, int(n * 0.08)):
        lead[rng.choice(["title", "company", "country", "industry"])] = ""
    for lead in rng.sample(leads, int(n * 0.06)):  # duplicates: same person, messy email
        dup = dict(lead)
        dup["lead_id"] = f"L{len(leads)+1:05d}"
        dup["email"] = lead["email"].upper().replace("@", "+promo@", 1) if rng.random() < 0.5 else lead["email"].upper()
        dup["created_at"] = lead["created_at"] + timedelta(days=rng.randint(1, 20))
        dup["events"], dup["touches"] = [], list(lead["touches"][:1])
        leads.append(dup)
    return leads


def apply_sales_actions(rng, leads, scorer, mql_threshold):
    """Seed sales behavior for leads that crossed the MQL line: some touched fast,
    some slow, some never, some accepted/rejected, a share turn into opportunities."""
    for lead in leads:
        score = scorer(lead)
        if score < mql_threshold:
            continue
        mql_at = lead["events"][-1]["ts"] if lead["events"] else lead["created_at"]
        lead["mql_at"] = mql_at
        r = rng.random()
        if r < 0.55:
            lead["first_touch_at"] = mql_at + timedelta(hours=rng.choice([1, 3, 6, 12, 20, 30, 50]))
        if lead["first_touch_at"]:
            r2 = rng.random()
            if r2 < 0.45:
                lead["accepted_at"] = lead["first_touch_at"] + timedelta(days=rng.randint(0, 5))
            elif r2 < 0.6:
                lead["rejected_at"] = lead["first_touch_at"] + timedelta(days=rng.randint(1, 6))
        if lead["accepted_at"] and rng.random() < 0.6:
            lead["opportunity"] = {"amount": rng.choice([8000, 15000, 24000, 40000, 75000]),
                                   "status": rng.choice(["won", "lost", "open"])}
    return leads


def generate(seed=42, n_accounts=60, n_leads=400):
    from .scoring import score_lead, MQL_THRESHOLD
    rng = random.Random(seed)
    accounts = make_accounts(rng, n_accounts)
    campaigns = make_campaigns(rng)
    leads = make_leads(rng, accounts, campaigns, n_leads)
    for l in leads:
        l.setdefault("mql_at", None)
    apply_sales_actions(rng, leads, lambda l: score_lead(l, NOW)["total"], MQL_THRESHOLD)
    return {"accounts": accounts, "campaigns": campaigns, "leads": leads}
