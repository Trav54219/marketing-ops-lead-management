# Marketing Ops: Lead Management Toolkit

A small, dependency-free Python project showing the marketing operations work that sits between a form fill and a sales conversation: scoring, lifecycle, matching, governance, attribution, mapping and data hygiene.

**All data is synthetic.** Leads, accounts, campaigns, domains (`.example`) and sales outcomes are generated from a seeded random generator (`mops/data.py`). Flaws such as bad emails, duplicates and badly named campaigns are injected on purpose so the audits have something to find. **Nothing here is connected to Marketo, HubSpot, Pardot or any other system**, and the numbers it prints describe the fake data, not real campaign performance.

## What is in it

| Module | What it does |
|---|---|
| `scoring.py` | Fit score (title, company size, industry, country) plus behavior score with exponential decay (30-day half-life, capped). |
| `lifecycle.py` | Lead / MQL / SQL / Recycled engine. MQL needs a score and a fit floor. 24h first-touch SLA with met / breached states. Recycle after 14 days without acceptance, recycle on rejection, 30-day cooldown before re-MQL. |
| `matching.py` | Lead-to-account match (domain, exact name, fuzzy name; free-mail aware) and email-based dedupe (case and `+tag` normalization, oldest record survives). |
| `governance.py` | UTM and campaign naming linter: `{year}q{n}_{region}_{objective}_{slug}`, source format, allowed mediums. |
| `attribution.py` | Per-campaign funnel (leads, MQLs, SQLs, cost per MQL, won revenue, ROI) and won revenue by channel under first-touch, last-touch and linear models. |
| `mapping.py` | Form-to-CRM field mapping validator: unmapped fields, unknown CRM fields, type mismatches, length overflow, picklist values, required fields with no source. |
| `hygiene.py` | Audit: missing-field rates, invalid emails, free mail, duplicate rate, leads with no account match. |
| `report.py` | Runs everything and writes `dashboard/index.html` (static, no JavaScript). |

## Run

```
python3 -m pytest -q      # tests, all local
python3 -m mops           # prints a summary, writes dashboard/index.html
```

Open `dashboard/index.html` in a browser. Python 3.9+; pytest is the only extra.

## Design notes

- Time is pinned (`mops.NOW`) so scoring decay and SLA timers are reproducible; the seed is 42.
- Thresholds and rules are constants at the top of each module, meant to be edited, not hard to find.
- The mapping validator checks config against a sample CRM schema; it never calls a CRM.
- Limits: the seeded sales behavior is random, so conversion and ROI figures carry no business meaning. The fuzzy match and dedupe are deliberately simple heuristics.
