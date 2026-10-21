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
print("\n".join(bad) or "check_site: OK")
sys.exit(1 if bad else 0)
