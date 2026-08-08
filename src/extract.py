#!/usr/bin/env python3
"""Extract lead cards from the mockup HTML into leads.json."""
import json, re
from bs4 import BeautifulSoup

SRC = "/root/.claude/uploads/246e3e1f-46db-55bd-8210-180d67a399df/5925a7f7-coldcalllistcombined.html"

with open(SRC) as f:
    soup = BeautifulSoup(f.read(), "html.parser")

leads = []
for sec in soup.select("section.lead"):
    card = sec.select_one(".card")
    def txt(sel):
        el = card.select_one(sel)
        return el.get_text(" ", strip=True) if el else None

    lead = {
        "brand": txt(".brand"),
        "name": txt(".name"),
        "title": txt(".ptitle"),
        "company": txt(".co"),
    }
    # location: "City, State — TZ"
    loc_el = card.select_one(".loc")
    if loc_el:
        tz_el = loc_el.select_one("b")
        lead["tz"] = tz_el.get_text(strip=True) if tz_el else None
        full = loc_el.get_text(" ", strip=True)
        lead["location"] = re.sub(r"\s*—\s*" + re.escape(lead["tz"] or "") + r"\s*$", "", full).strip() if lead["tz"] else full

    # stats
    for stat in card.select(".stat"):
        k = stat.select_one(".k").get_text(strip=True).lower()
        v = stat.select_one(".v").get_text(strip=True)
        if "revenue" in k: lead["revenue"] = v
        elif "employee" in k: lead["employees"] = v

    # dial
    dial = card.select_one("a.dial")
    if dial:
        small = dial.select_one("small")
        phone_type = None
        if small:
            phone_type = small.get_text(strip=True).replace("— TAP TO CALL", "").replace("— TAP TO CALL", "").strip()
            phone_type = re.sub(r"\s*—\s*TAP TO CALL\s*$", "", small.get_text(strip=True)).strip()
            small.extract()
        num_text = dial.get_text(" ", strip=True)
        num_text = re.sub(r"^\D*?(?=\+)", "", num_text)  # strip phone emoji
        lead["dial"] = {"display": num_text, "tel": dial.get("href", "").replace("tel:", ""), "type": phone_type}
    else:
        lead["dial"] = None  # "No number listed"

    # backups
    backups = []
    bwrap = card.select_one(".backups")
    if bwrap:
        for a in bwrap.select("a.bnum"):
            btype_el = a.find_next_sibling("span", class_="btype")
            btype = btype_el.get_text(strip=True).strip("()") if btype_el else None
            backups.append({"display": a.get_text(" ", strip=True), "tel": a.get("href", "").replace("tel:", ""), "type": btype})
    lead["backups"] = backups

    # links
    links = []
    for a in card.select("a.lnk"):
        links.append({"label": a.get_text(strip=True), "href": a.get("href")})
    lead["links"] = links

    ind = txt(".ind")
    lead["industry"] = re.sub(r"^Industry:\s*", "", ind) if ind else None
    lead["about"] = txt(".about")
    lead["note"] = txt(".note")
    leads.append(lead)

data = {
    "listId": "ecommerce-second-list-2026-08",
    "listName": "Ecommerce — Second List",
    "updated": "2026-08-07",
    "leads": leads,
}
with open("/home/claude/callapp/leads.json", "w") as f:
    json.dump(data, f, indent=1, ensure_ascii=False)

print(f"{len(leads)} leads extracted")
for i, l in enumerate(leads, 1):
    d = l["dial"]["display"] if l["dial"] else "NO NUMBER"
    print(f"{i:2d}. {l['name']:<22} {l['company']:<32} {d:<20} bk:{len(l['backups'])} note:{'Y' if l['note'] else '-'} tz:{l.get('tz')}")
