#!/usr/bin/env python3
"""Merge the uploaded 'Ecommerce - second list' xlsx into leads.json v2:
adds missing numbers with types, applies contact-level DNC to personal numbers."""
import json, re, openpyxl

XLSX = "/root/.claude/uploads/246e3e1f-46db-55bd-8210-180d67a399df/9cd87743-Untitled_spreadsheet_5.xlsx"

def digits(tel):
    return re.sub(r"[^\d]", "", str(tel or ""))

def to_tel(display):
    """'+1 555-555-0100 ext 2101' -> '+15555550100,,2101'"""
    s = str(display).strip()
    m = re.match(r"^(.*?)(?:\s*(?:ext\.?|x)\s*(\d+))?$", s, re.I)
    base, ext = m.group(1), m.group(2)
    tel = "+" + re.sub(r"[^\d]", "", base)
    return tel + (",," + ext if ext else "")

wb = openpyxl.load_workbook(XLSX, read_only=True)
ws = wb["Ecommerce - second list"]
rows = ws.iter_rows(values_only=True)
header = [str(h) if h else "" for h in next(rows)]
idx = {h: i for i, h in enumerate(header)}

PHONE_COLS = [("Mobile Phone", "Mobile", True), ("Work Direct Phone", "Work Direct", True),
              ("Other Phone", "Other", True), ("Company Phone", "Company", False)]

sheet = {}
for r in rows:
    if not r or not r[idx["First Name"]]:
        continue
    def g(col):
        v = r[idx[col]] if col in idx else None
        return "" if v is None else str(v).strip()
    key = (g("First Name").lower(), g("Last Name").lower())
    dnc = g("Do Not Call").lower() in ("true", "1", "yes")
    nums = []
    for col, typ, personal in PHONE_COLS:
        v = g(col)
        if v and not v.startswith("="):
            nums.append({"display": v.replace("'", ""), "tel": to_tel(v.replace("'", "")),
                         "type": typ, "dnc": bool(dnc and personal)})
    sheet[key] = {"dnc": dnc, "numbers": nums, "email": g("Email"), "notes_col": g("Filed in Attio by Claude")[:60]}

print("sheet contacts:", len(sheet))

with open("leads.json") as f:
    data = json.load(f)

changed = 0
for i, lead in enumerate(data["leads"], 1):
    parts = lead["name"].split()
    key = (parts[0].lower(), parts[-1].lower())
    row = sheet.get(key)
    if not row:
        continue
    have = {digits(n["tel"]) for n in lead["numbers"]}
    added = []
    for n in row["numbers"]:
        if digits(n["tel"]) not in have:
            lead["numbers"].append({**n, "primary": False})
            added.append(("DNC🔒 " if n["dnc"] else "") + n["type"] + " " + n["display"])
            have.add(digits(n["tel"]))
    if row["email"] and "@" in row["email"] and not lead.get("email"):
        lead["email"] = row["email"]
        added.append("email " + row["email"])
    if added:
        changed += 1
        print(f"{i:2d}. {lead['name']:<22} + {', '.join(added)}")

with open("leads.json", "w") as f:
    json.dump(data, f, indent=1, ensure_ascii=False)
print("leads enriched:", changed)
