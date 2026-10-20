#!/usr/bin/env python3
"""Fail if the built site does not use the GitHub Pages user-site URL at the domain root."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SITE = "https://albertaadraws.github.io"

index = (PUBLIC / "index.html").read_text(encoding="utf-8")
checks = {
    "canonical": f'rel="canonical" href="{SITE}/"',
    "stylesheet": 'href="/assets/style.css"',
    "script": 'src="/assets/app.js"',
}
missing = [name for name, needle in checks.items() if needle not in index]
# Open-data links live on the about page, not the home page.
about = (PUBLIC / "about" / "index.html").read_text(encoding="utf-8")
for needle in ('href="/data/draws.json"', 'href="/data/pools.json"', 'href="/data/occupations.json"', 'href="/feed.xml"', 'href="/feed.json"'):
    if needle not in about:
        missing.append(f"about {needle}")

sitemap = (PUBLIC / "sitemap.xml").read_text(encoding="utf-8")
feed = (PUBLIC / "feed.xml").read_text(encoding="utf-8")
feed_json = (PUBLIC / "feed.json").read_text(encoding="utf-8")
robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
if f"<loc>{SITE}/</loc>" not in sitemap:
    missing.append("sitemap home")
if f"<link>{SITE}/</link>" not in feed or f"{SITE}/feed.xml" not in feed:
    missing.append("rss")
if f'"home_page_url": "{SITE}/"' not in feed_json:
    missing.append("json feed")
if f"Sitemap: {SITE}/sitemap.xml" not in robots:
    missing.append("robots")

bad_domain = []
for path in PUBLIC.rglob("*"):
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="replace").replace("you@example.com", "")
    if "example.com" in text or "albertadraws.ca" in text:
        bad_domain.append(str(path.relative_to(ROOT)))

# Disclaimer must survive the build.
disclaimer = (PUBLIC / "disclaimer" / "index.html").read_text(encoding="utf-8")
for phrase in ("not immigration advice", "not affiliated with, endorsed by"):
    if phrase not in disclaimer.lower():
        missing.append(f"disclaimer:{phrase}")

if missing or bad_domain:
    if missing:
        print("missing checks:", ", ".join(missing), file=sys.stderr)
    if bad_domain:
        print("unexpected domain in:", ", ".join(bad_domain), file=sys.stderr)
    sys.exit(1)

pages = sorted(p.relative_to(PUBLIC).as_posix() for p in PUBLIC.rglob("index.html"))
print(f"[check] {len(pages)} pages, feeds use {SITE}, assets are root-relative")
