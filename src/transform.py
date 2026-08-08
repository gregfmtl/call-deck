#!/usr/bin/env python3
"""Upgrade leads.json to the v2 numbers[] model and merge sheet-sourced
numbers + DNC flags (from Ecommerce_call_lists_normalized + Velix_LI_Untapped_CallList)."""
import json, re

with open("leads.json") as f:
    data = json.load(f)

def digits(tel):
    # full-string digits (incl. extension) so 'x ext 212' dedupes separately from the bare line
    return re.sub(r"[^\d]", "", tel or "")

# Sheet-sourced additions/overrides, keyed by 1-based card number.
# dnc=True => number is on a Do-Not-Call list (or contact-level DNC) -> locked in UI.
ENRICH = {
    5:  [{"display": "+1 555-555-0105", "tel": "+15555550105", "type": "Mobile", "dnc": True}],   # Huertas (contact DNC=true)
    17: [{"display": "+1 555-555-0117", "tel": "+15555550117", "type": "Mobile", "dnc": True}],   # Sevimli (contact DNC=true)
    21: [{"display": "+1 555-555-0121", "tel": "+15555550121", "type": "Mobile", "dnc": True}],   # Varriale (contact DNC=true)
    22: [{"display": "+1 555-555-0122", "tel": "+15555550122", "type": "Mobile", "dnc": True}],   # Goettlicher (contact DNC=true)
    23: [{"display": "+1 555-555-0123", "tel": "+15555550123", "type": "Mobile", "dnc": True}],   # Lines (contact DNC=true)
    26: [{"display": "+1 555-555-0126", "tel": "+15555550126", "type": "Mobile", "dnc": True}],   # Furmanski (mobile DNC FLAGGED)
    34: [{"display": "+1 555-555-0134 ext 212", "tel": "+15555550134,,212", "type": "Work Direct", "dnc": True}],  # Tillman (direct line DNC-flagged)
}

for i, lead in enumerate(data["leads"], 1):
    numbers = []
    if lead.get("dial"):
        d = lead.pop("dial")
        numbers.append({"display": d["display"], "tel": d["tel"],
                        "type": (d.get("type") or "Phone").title(), "dnc": False, "primary": True})
    else:
        lead.pop("dial", None)
    for b in lead.pop("backups", []):
        numbers.append({"display": b["display"], "tel": b["tel"],
                        "type": (b.get("type") or "Phone").title(), "dnc": False, "primary": False})
    seen = {digits(n["tel"]) for n in numbers}
    for extra in ENRICH.get(i, []):
        if digits(extra["tel"]) not in seen:
            numbers.append({**extra, "primary": False})
    lead["numbers"] = numbers

# Emails for the LI-list cards (from Velix_LI_Untapped_CallList sheet)
EMAILS = {
    24: "contact24@example.com", 25: "contact25@example.com",
    26: "contact26@example.com", 27: "contact27@example.com",
    28: "contact28@example.com", 30: "contact30@example.com",
    32: "contact32@example.com", 33: "contact33@example.com",
    34: "contact34@example.com",
}
for i, lead in enumerate(data["leads"], 1):
    if i in EMAILS:
        lead["email"] = EMAILS[i]

data["quoFrom"] = "+15555550199"  # Quo "Sales" inbox (Gregory Frank)
data["schema"] = 2

with open("leads.json", "w") as f:
    json.dump(data, f, indent=1, ensure_ascii=False)

for i, l in enumerate(data["leads"], 1):
    ns = " | ".join(("DNC🔒" if n["dnc"] else "ok") + " " + n["type"] + " " + n["display"] for n in l["numbers"]) or "none"
    print(f"{i:2d}. {l['name']:<22} {ns}")
