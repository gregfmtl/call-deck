#!/usr/bin/env python3
"""Build the deployable app: inject leads into template, generate manifest + icons."""
import json, os

D = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(D, "site")
os.makedirs(SITE, exist_ok=True)

with open(os.path.join(D, "leads.json")) as f:
    data = json.load(f)
with open(os.path.join(D, "template.html")) as f:
    tpl = f.read()

# --- preview build: single file, leads embedded (for direct sharing/testing) ---
PREV = os.path.join(D, "preview")
os.makedirs(PREV, exist_ok=True)
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
with open(os.path.join(PREV, "call-deck-preview.html"), "w") as f:
    f.write(tpl.replace("__LEADS_JSON__", payload))

# --- deploy build: leads encrypted (AES-256-GCM), key kept OUT of site/ ---
import base64, secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

keyfile = os.path.join(D, "deck.key")  # base64url raw key — never goes in site/
if os.path.exists(keyfile):
    key = base64.urlsafe_b64decode(open(keyfile).read().strip() + "==")
else:
    key = AESGCM.generate_key(bit_length=256)
    with open(keyfile, "w") as f:
        f.write(base64.urlsafe_b64encode(key).decode().rstrip("="))

iv = secrets.token_bytes(12)
ct = AESGCM(key).encrypt(iv, json.dumps(data, ensure_ascii=False).encode(), None)
with open(os.path.join(SITE, "leads.enc"), "wb") as f:
    f.write(iv + ct)

with open(os.path.join(SITE, "index.html"), "w") as f:
    f.write(tpl.replace("__LEADS_JSON__", "null"))

print("key (URL fragment): #k=" + open(keyfile).read().strip())

with open(os.path.join(SITE, "robots.txt"), "w") as f:
    f.write("User-agent: *\nDisallow: /\n")

# icons: dark rounded tile, green phone glyph
from PIL import Image, ImageDraw, ImageFont
def icon(size, path):
    img = Image.new("RGB", (size, size), "#0f1115")
    d = ImageDraw.Draw(img)
    m = size * 0.10
    d.rounded_rectangle([m, m, size - m, size - m], radius=size * 0.16, fill="#2ecc71")
    glyph = "☎"  # telephone
    fs = int(size * 0.52)
    font = None
    for fp in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, fs)
            break
    if font:
        bb = d.textbbox((0, 0), glyph, font=font)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        d.text(((size - w) / 2 - bb[0], (size - h) / 2 - bb[1]), glyph, font=font, fill="#06220f")
    img.save(path)

for s in (180, 192, 512):
    icon(s, os.path.join(SITE, f"icon-{s}.png"))

print("built:", sorted(os.listdir(SITE)))
print("index.html bytes:", os.path.getsize(os.path.join(SITE, "index.html")))
