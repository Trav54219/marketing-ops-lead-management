"""Run every module over the seeded data and render a static HTML dashboard."""
import json
from html import escape
from . import NOW
from .data import generate
from .scoring import score_lead
from .lifecycle import evaluate, summarize
from .matching import match_account, find_duplicates
from .governance import lint_all
from .attribution import attribute_revenue, campaign_performance
from .mapping import validate_all
from .hygiene import audit


def build(seed=42):
    d = generate(seed)
    leads, accounts, camps = d["leads"], d["accounts"], d["campaigns"]
    results = [evaluate(l, NOW) for l in leads]
    stage = {r["lead_id"]: r["stage"] for r in results}
    methods = {}
    for l in leads:
        m = match_account(l, accounts)[1]
        methods[m] = methods.get(m, 0) + 1
    return {
        "seed": seed, "now": NOW.isoformat(),
        "lifecycle": summarize(results),
        "match_methods": methods,
        "duplicates": find_duplicates(leads),
        "governance": lint_all(camps),
        "attribution": {m: attribute_revenue(leads, m) for m in ("first", "last", "linear")},
        "campaigns": campaign_performance(camps, leads, stage),
        "mapping_issues": validate_all(),
        "hygiene": audit(leads, accounts),
        "score_buckets": _buckets([score_lead(l, NOW)["total"] for l in leads]),
    }


def _buckets(scores):
    edges = [0, 20, 40, 60, 80, 1000]
    labels = ["0-19", "20-39", "40-59", "60-79", "80+"]
    return {lab: sum(1 for s in scores if lo <= s < hi) for lab, lo, hi in zip(labels, edges, edges[1:])}


def _table(headers, rows):
    h = "".join(f"<th>{escape(str(x))}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


def _bars(data):
    mx = max(data.values()) or 1
    return "".join(f'<div class="bar"><span>{escape(str(k))}</span><i style="width:{v/mx*100:.0f}%"></i><b>{v}</b></div>'
                   for k, v in data.items())


def render(r):
    hy, lc = r["hygiene"], r["lifecycle"]
    cards = [("Records", hy["records"]), ("Duplicate rate", f'{hy["duplicate_rate"]:.1%}'),
             ("Invalid email rate", f'{hy["invalid_email_rate"]:.1%}'),
             ("SLA met", "n/a" if lc["sla_met_rate"] is None else f'{lc["sla_met_rate"]:.1%}'),
             ("Naming pass rate", f'{r["governance"]["pass_rate"]:.1%}')]
    card_html = "".join(f'<div class="card"><small>{k}</small><strong>{v}</strong></div>' for k, v in cards)
    camp_rows = [(c["campaign_id"], c["name"], c["channel"], c["spend"], c["leads"], c["mqls"], c["sqls"],
                  c["cost_per_mql"], c["revenue"], c["roi"]) for c in r["campaigns"]]
    attr = sorted({ch for m in r["attribution"].values() for ch in m})
    attr_rows = [(ch, *(r["attribution"][m].get(ch, 0) for m in ("first", "last", "linear"))) for ch in attr]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marketing Ops Dashboard (synthetic data)</title><style>
body{{font:14px/1.5 system-ui,sans-serif;margin:0;background:#f6f7f9;color:#1c2330}}main{{max-width:1000px;margin:auto;padding:24px 16px}}
h1{{margin:0 0 4px}}h2{{margin-top:32px;border-bottom:1px solid #d5d9e0;padding-bottom:4px}}.note{{background:#fff4d6;padding:8px 12px;border-radius:6px}}
.cards{{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}}.card{{background:#fff;padding:12px 16px;border-radius:8px;min-width:140px}}
.card small{{display:block;color:#566}}.card strong{{font-size:22px}}table{{border-collapse:collapse;width:100%;background:#fff;font-size:13px}}
td,th{{padding:6px 8px;border-bottom:1px solid #e6e9ee;text-align:left}}.wrap{{overflow-x:auto}}
.bar{{display:flex;align-items:center;gap:8px;margin:3px 0}}.bar span{{width:80px}}.bar i{{display:block;height:14px;background:#3b6fd4;border-radius:3px}}
</style></head><body><main>
<h1>Marketing Ops Dashboard</h1>
<p class="note">All data is synthetic (seed {r["seed"]}, as-of {escape(r["now"])}). Nothing is connected to Marketo, HubSpot, Pardot or any real system.</p>
<div class="cards">{card_html}</div>
<h2>Lead score distribution</h2>{_bars(r["score_buckets"])}
<h2>Lifecycle stages</h2>{_bars(lc["stages"])}<p>SLA outcomes: {escape(json.dumps(lc["sla"]))}</p>
<h2>Campaign performance</h2><div class="wrap">{_table(["ID","Name","Channel","Spend","Leads","MQLs","SQLs","$/MQL","Won revenue","ROI"], camp_rows)}</div>
<h2>Won revenue by channel and attribution model</h2><div class="wrap">{_table(["Channel","First touch","Last touch","Linear"], attr_rows)}</div>
<h2>Naming governance ({r["governance"]["campaigns_failing"]} of {r["governance"]["campaigns_checked"]} campaigns failing)</h2>
<div class="wrap">{_table(["Campaign","Name","Code","Message"], [(v["campaign_id"],v["name"],v["code"],v["message"]) for v in r["governance"]["violations"]])}</div>
<h2>Form to CRM mapping issues</h2><div class="wrap">{_table(["Form","Field","Code","Message"], [(i["form"],i["field"],i["code"],i["message"]) for i in r["mapping_issues"]])}</div>
<h2>Data hygiene</h2><div class="wrap">{_table(["Metric","Value"], [("Missing by field", json.dumps(hy["missing_by_field"])),("Invalid emails", hy["invalid_emails"]),("Free-mail addresses", hy["free_mail"]),("Duplicate groups", hy["duplicate_groups"]),("Duplicate records", hy["duplicate_records"]),("Unmatched to account", f'{hy["unmatched_to_account"]} ({hy["unmatched_rate"]:.1%})'),("Account match methods", json.dumps(r["match_methods"]))])}</div>
</main></body></html>"""


def main(out="dashboard/index.html", seed=42):
    r = build(seed)
    with open(out, "w") as f:
        f.write(render(r))
    print(json.dumps({k: r[k] for k in ("lifecycle", "hygiene")}, indent=2, default=str))
    print("wrote", out)


if __name__ == "__main__":
    main()
