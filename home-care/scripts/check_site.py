#!/usr/bin/env python3
"""Fail the build if the home care finder drifts from its rules.

Listings stay alphabetical, the ownership disclosure is on every page, Alberta Care
Staffing stays unpublished, internal links stay under BASE_PATH, and the contact
email stays albertacarestaffing@gmail.com.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public")
SITE = os.environ.get("SITE_URL", "https://albertaadraws.github.io").rstrip("/")
BASE = os.environ.get("BASE_PATH", "/home-care").rstrip("/")
EMAIL = "albertacarestaffing@gmail.com"
bad = []

cfg = json.load(open(os.path.join(ROOT, "config", "site.json")))
if cfg.get("contact_email") != EMAIL:
    bad.append(f"config contact_email is {cfg.get('contact_email')!r}")
if cfg.get("paid_listings"):
    bad.append("paid_listings is enabled")
if cfg.get("owner_agency") != "Alberta Care Staffing":
    bad.append("owner_agency changed")

src = json.load(open(os.path.join(ROOT, "data", "agencies.json")))
owners = [a for a in src["agencies"] if a.get("name") == "Alberta Care Staffing"]
if len(owners) != 1 or owners[0].get("publish") or not owners[0].get("owner"):
    bad.append("Alberta Care Staffing listing is not the unpublished owner placeholder")

htmls = []
for d, _, fs in os.walk(OUT):
    for f in fs:
        if f.endswith(".html"):
            htmls.append(os.path.join(d, f))
if not htmls:
    bad.append("no HTML was built")

for p in htmls:
    t = open(p, encoding="utf-8").read()
    if "Ownership disclosure:" not in t:
        bad.append(f"{p}: missing ownership disclosure")
    if "<h3>Alberta Care Staffing" in t:
        bad.append(f"{p}: unpublished agency is listed")
    for m in re.finditer(r'(?:href|src)="(/[^"]*)"', t):
        if not m.group(1).startswith(BASE + "/"):
            bad.append(f"{p}: root-relative link {m.group(1)}")
    for m in re.finditer(r'rel="canonical" href="([^"]+)"', t):
        if not m.group(1).startswith(SITE + BASE + "/"):
            bad.append(f"{p}: canonical {m.group(1)}")

pub = json.load(open(os.path.join(OUT, "data", "agencies.json")))
names = [a["name"] for a in pub["agencies"]]
if "Alberta Care Staffing" in names:
    bad.append("published data includes Alberta Care Staffing")
if names != sorted(names, key=lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower())):
    bad.append("published agencies are not alphabetical")
listed = open(os.path.join(OUT, "get-listed", "index.html"), encoding="utf-8").read()
if EMAIL not in listed:
    bad.append("get-listed page is missing the contact email")

print("\n".join(bad) or "check_site: OK")
sys.exit(1 if bad else 0)
