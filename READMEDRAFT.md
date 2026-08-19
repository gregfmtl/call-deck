# Call Deck

A private, phone-first cold-calling web app. Full-screen swipeable lead cards, click-to-dial through Quo, per-lead notes, and a one-tap export that hands a session's results to Claude for CRM follow-through.

This document is the technical reference for the app itself: what data it needs, exactly what shape that data must be in, how to build and deploy it, and how to load a new calling list from scratch. It's written so a Claude session or engineer with **zero prior context on this project** can pick it up and reproduce every step below.

- **Live app** (private — the URL itself is the credential, treat it like a password): `https://gregfmtl.github.io/call-deck/#k=<key>`. The key is stored in `call-deck-config.json` in the owner's Google Drive "Claude work folder" — it is never checked into this repo.  
- **Code**: `github.com/gregfmtl/call-deck` (this repo — public, but the only thing public is the app shell \+ AES-encrypted lead data; nothing here is readable without the key)  
- **Owner**: Greg ([greg@tryvelix.com](mailto:greg@tryvelix.com)), Velix

---

## 1\. Architecture at a glance

Call Deck is a static, single-page app — **no backend, no server, no database.** Everything lives in one HTML file plus one encrypted data blob, hosted on GitHub Pages.

```
site/ (= repo root when deployed)
├── index.html      built from src/template.html — the entire app (HTML+CSS+JS in one file)
├── leads.enc       AES-256-GCM ciphertext: 12-byte random IV + encrypted leads.json
├── icon-*.png      home-screen icons (iOS "Add to Home Screen")
└── robots.txt      Disallow: / (keeps it out of search indexes)
```

On load, the app reads a decryption key from the URL fragment (`#k=...`), fetches `leads.enc`, decrypts it client-side with the Web Crypto API, and renders the deck. The key is never sent to any server — it lives only in the URL and, after first successful load, in the phone's `localStorage` (`calldeck:key`) so it doesn't need to be re-entered. **Anyone with the URL fragment can read the data — there is no server-side access control.** That's the entire security model; it's adequate for "don't show up in a Google search" but not for anything more sensitive.

Nothing is written back to any CRM automatically. The app's only two outputs are (a) local device state (which leads are marked called, and free-text notes — both in `localStorage`, per device, per list) and (b) an **export**: a button that packages the session and hands it to a Claude conversation, which then does CRM work under human confirmation. See §6.

## 2\. Repository layout

```
├── index.html, leads.enc, icon-*.png, robots.txt   ← the deployed site (repo root)
└── src/
    ├── template.html    the app source (edit this, never index.html directly)
    ├── build.py         renders template.html → site/ (encrypts leads.json)
    ├── extract.py       LEGACY one-time importer — parses the original demo mockup HTML.
    │                    Not part of the ongoing workflow; kept for history. New lists come
    │                    from spreadsheets (§4), not mockups.
    ├── merge_sheet.py   merges an uploaded spreadsheet into leads.json (§5)
    ├── transform.py     one-off schema upgrade + manual enrichment script from the initial
    │                    build (§5.4). Treat as a worked example, not a reusable tool as-is.
    └── README.md        short pointer back to this file
```

The actual working copy these scripts run against lives outside the repo, in the build environment's `callapp/` directory — `leads.json` (plaintext, never committed) is the single source of truth that `build.py` encrypts into `leads.enc`. If you're a fresh agent starting from scratch, recreate that directory locally: it just needs `leads.json`, `template.html`, and the four Python scripts side by side.

## 3\. The `leads.json` data model

This is the canonical schema the app renders from. Every field below is what `template.html` actually reads (verified against source, not assumed).

```json
{
  "listId": "ecommerce-second-list-2026-08",
  "listName": "Ecommerce — Second List",
  "updated": "2026-08-07",
  "schema": 2,
  "quoFrom": "+15555550100",
  "leads": [ { ...one object per lead, shape below... } ]
}
```

(`quoFrom` shown here as a placeholder — the real number is only in `call-deck-config.json` in Drive, never committed to this public repo.)

| Top-level field | Required | Notes |
| :---- | :---- | :---- |
| `listId` | yes | Slug, unique per list. Used as the `localStorage` namespace (`calldeck:<listId>:*`) — **changing it resets a device's called/notes progress for that list.** Convention so far: `kebab-case-name-YYYY-MM`. |
| `listName` | yes | Shown verbatim as the card header on every card. Convention: the source spreadsheet's tab name, unedited. |
| `updated` | yes | ISO date, informational only — not read by the app UI. |
| `schema` | yes | Currently `2`. Bump if the lead shape changes incompatibly. |
| `quoFrom` | yes | E.164 number of the Quo inbox to dial *from* (the "Sales" inbox). Real value lives only in `call-deck-config.json` in Drive — not committed here. |
| `leads` | yes | Array, order \= card order. |

Each entry in `leads[]`:

| Field | Required | Type | Notes |
| :---- | :---- | :---- | :---- |
| `name` | yes | string | Full name, as displayed. |
| `title` | yes | string | Job title. Use `""` if unknown — not `null` (rendered directly, `null` would print as text). |
| `company` | yes | string | Company name. |
| `brand` | yes | string | Segment/list-tag, **not shown on the card** (the card header now shows `listName` uniformly instead — this was a deliberate UX change). Still carried through to the export as `segment`, so keep it meaningful. Default: same value as `listName` unless the source data distinguishes sub-segments (see §5.5, open question). |
| `location` | no | string | e.g. `"Fullerton, California"`. |
| `tz` | no | string | Short code shown next to location, e.g. `PT`, `ET`, `CT`, `MT`, `AT`, `Other`. |
| `revenue` | no | string | Free text, e.g. `"$98.2M"` or `"not listed"`. Rendered as-is; `—` shown if absent. |
| `employees` | no | string | Free text, e.g. `"510"`. `—` shown if absent. |
| `industry` | no | string | Free text. |
| `about` | no | string | One-liner company description. |
| `note` | no | string or `null` | **Research note** — shown in a highlighted box on the card. This is *not* Greg's own call notes (those are a separate, always-starts-blank textarea in the app, saved to `localStorage` only, never pre-filled from here). See §5.5 for the current gap in how this field gets populated from a sheet. |
| `email` | no | string | If present, rendered as tap-to-copy. |
| `numbers` | yes (may be `[]`) | array of number objects, shape below | If empty or all-DNC, the app renders a Google-search fallback link instead of a dial button (see §3.1). |
| `links` | no | array of `{label, href}` | Rendered as pill buttons. Recognized labels the app treats specially: `"Website"` (also makes the company name itself a clickable link). Other labels (`"LinkedIn"`, `"Co. LinkedIn"`, etc.) just render as-is — any label works. |

### 3.1 The `numbers[]` model (read this before writing an importer)

```json
{ "display": "+1 555-010-1234", "tel": "+15550101234", "type": "Other", "dnc": false, "primary": true }
```

(fake example number — 555 exchange, not a real lead)

| Field | Notes |
| :---- | :---- |
| `display` | Human-readable, shown on the button. |
| `tel` | E.164-ish, used to build the dial link. **Extensions go after a comma**: `"+15550109999,,212"` (two commas \= a 2-second pause in most dialers' convention; the app itself just splits on the first comma when building the Quo link and dropping the extension — see below). |
| `type` | Free text label shown uppercased next to the number, e.g. `Mobile`, `Work Direct`, `Other`, `Company`. |
| `dnc` | **If `true`, this number is completely excluded from the DOM.** Not shown, not grayed out, not dialable — fully absent. This is a hard requirement, not a display preference: DNC numbers must never appear in the rendered HTML at all. |
| `primary` | Marks which number the big dial button uses. Exactly one number per lead should have `primary: true` and `dnc: false`; if none does, the app falls back to the first non-DNC number in the array (see `primaryOf()` in template.html). |

**Dialing logic:** the big dial button uses `openphone://dial?number=<tel, up to first comma>&from=<quoFrom>&action=call` (Quo's deep link scheme — opens Quo directly, no phone-settings changes needed). Tapping it also auto-marks the lead as "called" with a timestamp. All *other* non-DNC numbers render as smaller "backup" links using the same Quo scheme. If `numbers` is empty, or every entry has `dnc: true`, the app instead renders a link to `https://www.google.com/search?q="<company>" <location> contact phone number` — this one is intentionally **not** wired to the auto-mark-called behavior, since visiting a search page isn't the same as attempting a call.

**DNC is per-number, not per-lead.** A lead can have some callable numbers and some DNC numbers simultaneously (e.g., a DNC-flagged personal mobile plus a callable company switchboard line) — only the flagged ones disappear.

## 4\. Input spreadsheet format

New lists arrive as a spreadsheet, not a mockup. **Greg has one canonical column layout** for cold-call sheets — it's also used by his Google Sheets dialer rig, Attio import, and conditional formatting, so column *positions* are load-bearing elsewhere and must not be reordered even though Call Deck itself only reads a subset. This layout is documented in full (and should be treated as authoritative) in the `normalize-call-list` skill; summarized here for the fields Call Deck actually consumes:

| Column | Sheet header | → `leads.json` field |
| :---- | :---- | :---- |
| H, I | First Name, Last Name | `name` (`"First Last"`) |
| J | Title | `title` |
| G or AG | Company Name for Emails / Company Name | `company` — **which of these two to prefer is not yet settled; confirm with Greg per import** (see §5.5) |
| F, D, C | Company City, Company State, Company Country | `location` |
| E | Time zone | `tz` (values: `AT, ET, CT, MT, PT, Other`) |
| AD | Annual Revenue | `revenue` |
| O | \# Employees | `employees` |
| M | Industry | `industry` |
| N | Short Description | `about` |
| S | Mobile Phone | `numbers[]`, type `Mobile`, DNC-eligible |
| T | Work Direct Phone | `numbers[]`, type `Work Direct`, DNC-eligible |
| U | Other Phone | `numbers[]`, type `Other`, DNC-eligible |
| V | Company Phone | `numbers[]`, type `Company`, **not** DNC-eligible — see below |
| W | Do Not Call | drives `dnc: true` on the personal-line numbers above (Mobile/Work Direct/Other) when truthy |
| AE | Email | `email` |
| X | Website | `links` (label `Website`) |
| Y | Company Linkedin Url | `links` (label `Co. LinkedIn`) |
| Z | Person Linkedin Url | `links` (label `LinkedIn`) |
| A | Filed in Attio by Claude | currently read but **not wired into any output field** — see §5.5 |

**Why Company Phone is exempt from DNC:** the existing merge logic (`merge_sheet.py`) only applies the sheet's Do-Not-Call flag to *personal* lines (mobile/work-direct/other) and deliberately leaves the shared company switchboard number callable even when the contact themself is DNC-flagged, on the theory that a general company line isn't "calling the person" in the same sense. This is baked into the current script — flagging it here so it's a documented decision, not a silent assumption, since it affects who's technically reachable when a contact is marked DNC.

**Phone number formatting the importer expects:**

- Raw values like `'+1 555-010-8452 ext 2101` (note the leading apostrophe some spreadsheet tools add to force text formatting; fake example number) — the importer strips the apostrophe and converts to `tel:`\-style: `+15550108452,,2101`.  
- `Do Not Call` is read as a string and matched case-insensitively against `"true"`, `"1"`, `"yes"`; per the canonical sheet spec it should actually be a real boolean — both are handled.  
- Blank/formula cells (values starting with `=`) are skipped, not treated as phone numbers.

**Matching rows to existing leads:** the merge is keyed on `(first name, last name)`, lowercased. If your source list has duplicate names across companies, this will misattribute — dedupe or pre-flag ambiguous names before merging.

## 5\. Full pipeline — building a list from scratch

Run from the `callapp/` working directory described in §2.

### 5.1 Starting a brand-new list (the normal path going forward)

1. Get the spreadsheet from Greg in the canonical layout (§4). If it's a raw export (Apollo/ZoomInfo/LinkedIn scrape) that hasn't been normalized yet, that's the `normalize-call-list` skill's job, not this pipeline's — normalize first, then hand the result here.  
2. Build a fresh `leads.json` directly from the sheet: **there is currently no generic "sheet → leads.json from scratch" script** — `merge_sheet.py` as it exists today only *merges additions* into an already-existing `leads.json` (see §5.5, this is the biggest reproducibility gap in the current tooling). Until that's built, the fastest correct path is to write the row → lead mapping from §4 directly (a short script, or by hand for small lists), producing:

```json
{ "listId": "<slug>-YYYY-MM", "listName": "<exact tab name>", "updated": "YYYY-MM-DD",
  "schema": 2, "quoFrom": "<real number from call-deck-config.json, not this repo>", "leads": [ ... ] }
```

3. Run the build:

```shell
python3 build.py
```

   This produces `preview/call-deck-preview.html` (plaintext, for local testing — open directly in a browser, no key needed) and `site/{index.html, leads.enc, icon-*.png, robots.txt}` (the deployable, encrypted bundle). It reuses the existing `deck.key` if present (so the same URL/key keeps working across list updates) or generates a new one if `deck.key` is missing.

   

4. **Test the preview first.** Open `preview/call-deck-preview.html`, click through several cards, confirm: no DNC numbers appear anywhere in the DOM, the dial button opens the expected Quo link, numbers/company/location render correctly, cards with no callable number show the Google-search fallback.  
5. Deploy (§5.3).  
6. Refresh `call-deck-leads-index.json` in Drive (§6.2) — every new list needs this regenerated, it's how a future export gets resolved back to real names.  
7. Remind Greg to **export the previous list first** if he hasn't — progress (`called`/notes) is stored per `listId` in `localStorage`; loading a new list doesn't erase the old one, but he can't get back to the old deck's progress without navigating to its own URL (same key, but the deployed `leads.enc` will have been overwritten — so the old list's cards are genuinely gone once redeployed unless you kept a copy).

### 5.2 The legacy scripts (for history / reference only)

- `extract.py` parses one specific static HTML mockup (`coldcalllistcombined.html`) that was the very first input to this project, before spreadsheets were the norm. It is hardcoded to that file's path and structure. **Do not run this expecting it to work on anything else** — it's kept only so the original `leads.json` is reproducible.  
- `transform.py` was a one-time schema migration (old `dial`/`backups` shape → the current `numbers[]` model) plus a hardcoded `ENRICH` dict of specific DNC numbers and a hardcoded `EMAILS` dict, both keyed by card position number and sourced from that first batch's spreadsheets. **These dicts are specific to that one import and must not be reused or assumed to apply to a new list.** Treat this file as a worked example of the numbers\[\]-model shape, not a tool to re-run.  
- `merge_sheet.py` is closer to reusable but still has two hardcoded values that must be edited per run: the `XLSX` path at the top of the file, and the sheet tab name (`ws["Ecommerce - second list"]`). Update both before running against a new spreadsheet. It expects a header row matching the column names in §4 (subset of the canonical 84-column layout) and merges *additions* into whatever `leads.json` already has loaded — it does not create a list from nothing.

### 5.3 Build & deploy (encryption \+ GitHub Pages)

```shell
python3 build.py     # writes site/index.html, site/leads.enc, site/icon-*.png, site/robots.txt
```

Then push `site/*` to the repo root:

```shell
cp site/* /path/to/repo/ && cp src/template.html src/*.py /path/to/repo/src/
cd /path/to/repo
git add -A && git commit -m "describe the change"
git push origin main
```

**If pushing via the GitHub REST API is blocked** (some sandboxed environments proxy-block `api.github.com` account/repo endpoints with a 403/502 even though smart-HTTP `git push` works): authenticate the push directly with an explicit header instead of relying on a credential helper:

```shell
B=$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)
git -c http.extraHeader="Authorization: Basic $B" push https://github.com/gregfmtl/call-deck.git main
```

`$GITHUB_TOKEN` is stored in `call-deck-config.json` in Drive (`github.token`) — **never commit it, never print it into this repo.** It's a fine-grained/classic PAT scoped to this repo with `repo` (contents) permission; it expires periodically and Greg has to rotate it in GitHub settings when it does — if pushes start failing with "Permission denied," that's usually why.

GitHub Pages itself (Settings → Pages → branch `main`, root) has to be enabled once, by hand, by someone with access to the GitHub account — it cannot be turned on via the API from this environment (that endpoint is blocked the same way). If Pages isn't serving, that's the first thing to check, not the build.

### 5.4 The encryption key

`deck.key` (base64url, 256-bit, generated by `build.py` on first run) is the AES-GCM key. It must match `encryption.aesGcmKeyB64Url` in `call-deck-config.json` — that's what makes the private URL (`#k=...`) keep working across rebuilds. **Never regenerate this key casually**; doing so invalidates the live URL Greg has saved to his home screen, and he'd need to redo the "Add to Home Screen" step with a new link.

### 5.5 Known gaps — resolve or confirm before the next new-list import

Being explicit about these rather than quietly working around them, since they'll trip up anyone picking this up cold:

1. **No sheet-to-`leads.json` script exists for a genuinely new list.** `merge_sheet.py` only adds to an existing file. Building the "from scratch" script described in §5.1 step 2 (canonical-column-layout → full `leads.json`, replacing both `extract.py` and the enrichment half of `transform.py`) is the single highest-value fix to make this reproducible by someone other than the person who built it.  
2. **`company` field source is ambiguous**: the canonical sheet has both "Company Name for Emails" (G) and "Company Name" (AG), which may differ. Not yet confirmed which should win.  
3. **The research `note` field (§3, the yellow box) has no sheet-column source wired up.** "Filed in Attio by Claude" (column A) is read by `merge_sheet.py` into an unused variable and dropped. Either wire that column in, pick a different source column, or treat per-lead research notes as something added by hand after import — as it was for the first list, via the hardcoded `ENRICH`/manual-edit approach in `transform.py`.  
4. **Per-lead `brand`/segment has no defined sheet source** for new imports. In the original mockup-derived list it was a manually-set qualifier per lead (e.g. "ADDED TO LINKEDIN — MAYBE"). Since the card header now shows `listName` uniformly, `brand` only matters for the export's `segment` field — worth deciding whether new imports just set it equal to `listName` for every lead, or whether there's a real sheet column (e.g. Apollo's `Lists`) that should populate it per-row.

None of these block using the app with a list that's already built — they only matter when building the *next* list from a raw sheet.

## 6\. Export & the Google Drive "memory" files

The app has no backend, so it can't write to Attio or log anything server-side. Instead, tapping **Export to Claude** on the summary card:

1. Builds a JSON payload of every lead that was marked called or has a note: `{n, name, company, segment, called (ISO timestamp or null), note}` (`n` is 1-indexed position in the list, `segment` \= that lead's `brand` field).  
2. Copies a full text block to the clipboard containing that JSON plus written instructions for whichever Claude session receives it, and opens `https://claude.ai/new?q=<url-encoded text>` in a new tab — which prefills a new chat's composer. If the encoded text is too long for a URL (\~4000 char threshold), it instead prefills a short "check your clipboard" message and relies on the clipboard copy plus a manual paste.

That receiving Claude session — which will have **no memory of building this app** — needs three Drive files, all in the owner's "Claude work folder":

| File | Purpose |
| :---- | :---- |
| `call-deck-config.json` | Sensitive. Deploy token, encryption key, Quo number, build notes. |
| `call-deck-README.md` | The *protocol* document — standing rules (below) and the step-by-step export-handling checklist. This repository README covers the technical "how the app works" side; that Drive doc covers the "how to behave when handling Greg's data" side. Keep both in sync when either changes. |
| `call-deck-leads-index.json` | Maps export entry `n` back to full lead identity (name, company, title, segment, email, phone, LinkedIn) without needing to decrypt `leads.enc`. **Must be regenerated every time a new list is loaded** — it's built from whatever `leads.json` is currently live. |

### 6.1 Standing rules (do not relitigate these — Greg has stated them explicitly)

- **Chat is Greg's only interface.** He never opens the Drive folder or reads these files directly. Everything he needs to see or decide comes back to him as a chat message — never "see the file at `<path>`."  
- **The sheet is the sole source at import.** When loading a new list, normalize what's in the uploaded sheet and nothing else. Do not cross-reference Attio, Gmail, Quo, or any other connector to enrich lead data before or after loading — Greg has explicitly ruled this out as expensive and redundant. If richer context (touch history, angle-to-use) is wanted later, it arrives as a column in a future sheet, not a live lookup.  
- **Quo only, from the configured Sales inbox number** (see `call-deck-config.json`). Never route calls through Greg's personal cell.  
- **DNC numbers are never shown or dialed.** Not grayed out, not visible-but-locked — absent from the rendered page entirely.  
- **Nothing writes to Attio without Greg's explicit per-export confirmation.** Draft the payload, show it, wait.

### 6.2 Processing an export (checklist for the receiving session)

1. Match each entry's `n`/name against `call-deck-leads-index.json` (confirm `listId` matches the index you're reading — if it doesn't, the index is stale; ask Greg to point you at the latest `leads.json` and regenerate it before continuing).  
2. Append the session to `call-deck-log.md` (create it if missing).  
3. Draft an Attio call-note payload per called/noted lead — outcome, cleaned note, next step. Show Greg; do not write until he confirms.  
4. Recommend next touch \+ channel per lead (text / email / LinkedIn DM / follow-up call), reasoned from the note content and the lead's segment.  
5. Give a short, honest session-review: what the notes suggest went well, one or two concrete things to improve toward booking meetings.

## 7\. Reproducing this whole project from nothing

If every piece of prior context were lost — new agent, new session, only this repo and Drive folder to go on — the order of operations is:

1. Read this file end to end (you just did).  
2. Read `call-deck-config.json` and `call-deck-README.md` in Drive for secrets and the standing behavioral rules.  
3. Get the current spreadsheet from Greg (or use one already loaded, if just maintaining the existing list).  
4. Build `leads.json` per §4/§5 (writing the from-scratch script described in §5.5 item 1 if it doesn't exist yet — check the repo's `src/` first, it may have been added since this was written).  
5. `python3 build.py`, test the preview, deploy per §5.3.  
6. Regenerate `call-deck-leads-index.json`.  
7. Tell Greg the deck is ready and to force-quit/reopen the app on his phone (iOS caches the home-screen web app aggressively).

That's the complete loop.  
