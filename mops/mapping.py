"""Form-to-CRM field mapping validator. Pure config checks; no CRM is contacted."""

CRM_SCHEMA = {
    "Email": {"type": "email", "required": True, "max": 80},
    "Company": {"type": "string", "required": True, "max": 60},
    "JobTitle": {"type": "string", "required": False, "max": 40},
    "Employees": {"type": "number", "required": False},
    "Country": {"type": "picklist", "required": False, "values": ["US", "CA", "GB", "DE", "FR"]},
    "LeadSource": {"type": "picklist", "required": True, "values": ["web", "event", "partner"]},
    "Consent": {"type": "boolean", "required": True},
}

# form field -> {"crm": field, "type": form type, "max": form max length, "options": [...]}
SAMPLE_FORMS = {
    "demo_request": {
        "email": {"crm": "Email", "type": "email", "max": 100},
        "company": {"crm": "Company", "type": "string", "max": 60},
        "title": {"crm": "JobTitle", "type": "string", "max": 40},
        "headcount": {"crm": "Employees", "type": "string"},
        "country": {"crm": "Country", "type": "picklist", "options": ["US", "CA", "GB", "IN"]},
        "referrer": {"crm": "LeadSource", "type": "picklist", "options": ["web", "event"]},
        "phone": {"crm": "Phone", "type": "string"},
        "newsletter_optin": {"crm": None, "type": "boolean"},
    },
    "webinar_signup": {
        "email": {"crm": "Email", "type": "email", "max": 80},
        "company": {"crm": "Company", "type": "string", "max": 60},
        "source": {"crm": "LeadSource", "type": "picklist", "options": ["web", "event", "partner"]},
        "consent": {"crm": "Consent", "type": "boolean"},
    },
}


def validate_form(form_name, fields, schema=CRM_SCHEMA):
    issues = []
    mapped = set()
    for fname, f in fields.items():
        crm = f.get("crm")
        if not crm:
            issues.append((form_name, fname, "UNMAPPED", "form field has no CRM target; data is dropped"))
            continue
        if crm not in schema:
            issues.append((form_name, fname, "UNKNOWN_CRM_FIELD", f"'{crm}' does not exist in CRM schema"))
            continue
        mapped.add(crm)
        s = schema[crm]
        if f.get("type") != s["type"]:
            issues.append((form_name, fname, "TYPE_MISMATCH", f"form {f.get('type')} -> CRM {s['type']}"))
        if s.get("max") and f.get("max") and f["max"] > s["max"]:
            issues.append((form_name, fname, "LENGTH_OVERFLOW", f"form max {f['max']} > CRM max {s['max']}"))
        if s["type"] == "picklist":
            bad = [o for o in f.get("options", []) if o not in s["values"]]
            if bad:
                issues.append((form_name, fname, "PICKLIST_VALUE", f"values not in CRM picklist: {bad}"))
    for crm, s in schema.items():
        if s["required"] and crm not in mapped:
            issues.append((form_name, "-", "REQUIRED_NOT_MAPPED", f"required CRM field '{crm}' has no form source"))
    return [dict(zip(("form", "field", "code", "message"), i)) for i in issues]


def validate_all(forms=SAMPLE_FORMS, schema=CRM_SCHEMA):
    out = []
    for name, fields in forms.items():
        out += validate_form(name, fields, schema)
    return out
