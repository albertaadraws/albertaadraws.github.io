#!/usr/bin/env python3
"""Sanity checks before deploy: every internal link/asset starts with BASE_PATH, canonicals use SITE_URL+BASE_PATH,
there are no affiliate links unless config/partners.json is enabled, and each plan has a source + date."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public")
SITE = os.environ.get("SITE_URL", "https://albertaadraws.github.io").rstrip("/")
BASE = os.environ.get("BASE_PATH", "/alberta-power").rstrip("/")
bad = []
for d, _, fs in os.walk(OUT):
    for f in fs:
        if not f.endswith(".html"): continue
        p = os.path.join(d, f); t = open(p).read()
        for m in re.finditer(r'(?:href|src)="(/[^"]*)"', t):
            if BASE and not m.group(1).startswith(BASE + "/"): bad.append(f"{p}: root-relative link {m.group(1)}")
        for m in re.finditer(r'rel="canonical" href="([^"]+)"', t):
            if not m.group(1).startswith(SITE + BASE + "/"): bad.append(f"{p}: canonical {m.group(1)}")
        if 'rel="sponsored' in t and not json.load(open(os.path.join(ROOT, "config", "partners.json"))).get("enabled"):
            bad.append(f"{p}: partner link present while partners disabled")
for pl in json.load(open(os.path.join(ROOT, "data", "plans.json")))["plans"]:
    if not pl.get("source_url") or not pl.get("last_checked"): bad.append(f"plan {pl['id']} missing source/date")

def need_source(row, label):
    if not isinstance(row, dict):
        return
    if row.get("source_url") and row.get("last_checked"):
        return
    bad.append(f"{label} missing source/date")

water_path = os.path.join(ROOT, "data", "water.json")
if os.path.exists(water_path):
    water = json.load(open(water_path))
    for key in ("edmonton", "calgary", "edmonton_waste", "tips"):
        if water.get(key):
            need_source(water[key], "water " + key)
    ed = water.get("edmonton") or {}
    for tier in ed.get("water_tiers_m3") or []:
        if not (0 < tier.get("rate", 0) < 20):
            bad.append(f"edmonton water tier out of range: {tier}")
    cal = water.get("calgary") or {}
    if cal and not (0 < cal.get("water_per_m3", 0) < 20):
        bad.append("calgary water rate out of range")

solar_path = os.path.join(ROOT, "data", "solar.json")
if os.path.exists(solar_path):
    solar = json.load(open(solar_path))
    for pl in solar.get("plans") or []:
        if not pl.get("source_url") or not pl.get("last_checked"):
            bad.append(f"solar {pl.get('id')} missing source/date")
        for fld in ("export_rate", "import_rate"):
            v = pl.get(fld)
            if v is not None and not (0 < v <= 100):
                bad.append(f"solar {pl.get('id')} {fld} out of range: {v}")
        if pl.get("admin_monthly") is not None and not (0 <= pl["admin_monthly"] <= 80):
            bad.append(f"solar {pl.get('id')} admin out of range")
    for row in solar.get("production") or []:
        need_source(row, "pv " + str(row.get("city")))
        if not (800 <= row.get("kwh_per_kw", 0) <= 2000):
            bad.append(f"pv potential out of range: {row}")
    for row in solar.get("programs") or []:
        need_source(row, "program " + str(row.get("id")))
    cost = solar.get("installed_cost") or {}
    if cost:
        need_source(cost, "installed cost")

# SEO titles the owner asked for, after a build.
wanted = {
    "water/index.html": "Edmonton water rates",
    "solar/index.html": "Solar panels Edmonton cost",
    "solar/rates/index.html": "Alberta solar club rates",
}
for rel, phrase in wanted.items():
    p = os.path.join(OUT, rel)
    if not os.path.exists(p):
        bad.append(f"missing page {rel}")
        continue
    html = open(p).read()
    if phrase not in html.split("</title>", 1)[0]:
        bad.append(f"{rel} title missing {phrase!r}")
print("\n".join(bad) or "check_site: OK")
sys.exit(1 if bad else 0)
