#!/usr/bin/env python3
"""Generate this week's 'Draws this week' newsletter draft (Markdown + HTML) from data/*.json.

  python3 scripts/newsletter.py                      # week ending today
  python3 scripts/newsletter.py --week-ending 2026-10-07
Writes newsletter/draws-this-week-YYYY-MM-DD.md and .html. Nothing is sent.
"""
import argparse, datetime as dt, html, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from aaip import SOURCE_URL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_URL = os.environ.get("SITE_URL", "https://albertaadraws.github.io").rstrip("/")


def fd(iso):
    return dt.date.fromisoformat(iso).strftime("%a %b %-d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-ending", default=dt.date.today().isoformat())
    a = ap.parse_args()
    end = dt.date.fromisoformat(a.week_ending)
    start = end - dt.timedelta(days=6)
    D = json.load(open(os.path.join(ROOT, "data/draws.json")))
    P = json.load(open(os.path.join(ROOT, "data/pools.json")))
    draws = D["draws"]
    week = [d for d in draws if start.isoformat() <= d["date"] <= end.isoformat()]
    week.sort(key=lambda d: d["date"])
    health = [d for d in week if d["sector"] == "health-care"]

    def prev_min(d):
        prev = [x for x in draws if x["category"] == d["category"] and x["date"] < d["date"] and x["min_score"] is not None]
        return prev[0]["min_score"] if prev else None

    md = [f"# Draws this week: {start.strftime('%b %-d')} – {end.strftime('%b %-d, %Y')}", ""]
    tot = sum(d["invitations"] or 0 for d in week)
    lt = sum(1 for d in week if d["invitations_lt10"])
    if week:
        md.append(f"Alberta held **{len(week)} draw{'s' if len(week) != 1 else ''}** this week, inviting **{tot:,}{'+' if lt else ''}** candidates.")
    else:
        last = draws[0]
        md.append(f"**No new AAIP draws were published this week.** The most recent draw on record is {dt.date.fromisoformat(last['date']).strftime('%B %-d, %Y')} "
                  f"({last['stream_raw']}, minimum score {last['min_score']}, {last['invitations_text']} invitations). "
                  f"The official page was last updated {dt.date.fromisoformat(D['page_last_updated']).strftime('%B %-d, %Y')}.")
    md.append("")
    if week:
        md += ["## This week's draws", "", "| Date | Stream / pathway | Min score | Change | Invitations |", "|---|---|---:|---:|---:|"]
        for d in week:
            pm = prev_min(d)
            ch = "" if pm is None or d["min_score"] is None else f"{d['min_score'] - pm:+d} vs last"
            md.append(f"| {fd(d['date'])} | {d['stream_raw']} | {d['min_score_text']} | {ch} | {d['invitations_text']} |")
        md.append("")
    md += ["## 🩺 Health & care workers", ""]
    if health:
        for d in health:
            md.append(f"- **{fd(d['date'])}**: {d['stream_raw']}: minimum **{d['min_score']}**, {d['invitations_text']} invitations")
    else:
        hs = [d for d in draws if d["sector"] == "health-care"][:3]
        md.append("No health care draws this week. The most recent ones:")
        for d in hs:
            md.append(f"- {dt.date.fromisoformat(d['date']).strftime('%b %-d')}: {d['stream_raw']}: min {d['min_score']}, {d['invitations_text']} invited")
    md.append("")
    snaps = P["snapshots"]
    md += ["## Who's waiting (EOI pool)", ""]
    cur = snaps[-1]
    prev = next((s for s in reversed(snaps[:-1]) if s["page_last_updated"] and s["page_last_updated"] <= start.isoformat()), None)
    prevmap = {p["full_name"]: p["count"] for p in prev["pools"]} if prev else {}
    for p in cur["pools"]:
        ch = ""
        if p["full_name"] in prevmap and p["count"] is not None and prevmap[p["full_name"]] is not None:
            ch = f" ({p['count'] - prevmap[p['full_name']]:+,})"
        md.append(f"- {p['full_name']}: **{p['count_text']}**{ch}")
    md.append(f"- **Total: {cur['total']:,}**" + ("" if prev else " (week-over-week changes appear once we have a prior snapshot)"))
    md += ["", f"[Check where your score stands →]({SITE_URL}/score-checker/)", "",
           "---", "",
           "**Sponsor:** _[SPONSOR SLOT: TODO]_", "",
           "**Prepping for your language test?** _[AFFILIATE PLACEHOLDER: TODO add PracticeCLB / CELPIP Simulator affiliate links]_", "",
           "---", "",
           f"_Source: [AAIP processing information]({SOURCE_URL}), Government of Alberta. This newsletter is informational only. It is not immigration advice and is not affiliated with the Government of Alberta. Talk to a licensed RCIC or lawyer before you make decisions._"]
    text = "\n".join(md) + "\n"
    os.makedirs(os.path.join(ROOT, "newsletter"), exist_ok=True)
    base = os.path.join(ROOT, "newsletter", f"draws-this-week-{end.isoformat()}")
    open(base + ".md", "w").write(text)
    open(base + ".html", "w").write(md_to_html(text))
    print(f"[newsletter] {len(week)} draws in week {start}..{end} -> {base}.md / .html")


def md_to_html(text):
    try:
        import markdown
        body = markdown.markdown(text, extensions=["tables"])
    except ImportError:  # minimal fallback
        import re
        out, in_table, in_ul = [], False, False
        for line in text.splitlines():
            inl = lambda s: re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', re.sub(r"_([^_]+)_", r"<em>\1</em>", re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", html.escape(s, quote=False))))
            if line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if set("".join(cells)) <= set("-:"):
                    continue
                if not in_table:
                    out.append("<table>"); in_table = True
                    out.append("<tr>" + "".join(f"<th>{inl(c)}</th>" for c in cells) + "</tr>"); continue
                out.append("<tr>" + "".join(f"<td>{inl(c)}</td>" for c in cells) + "</tr>"); continue
            if in_table:
                out.append("</table>"); in_table = False
            if line.startswith("- "):
                if not in_ul:
                    out.append("<ul>"); in_ul = True
                out.append(f"<li>{inl(line[2:])}</li>"); continue
            if in_ul:
                out.append("</ul>"); in_ul = False
            if line.startswith("## "):
                out.append(f"<h2>{inl(line[3:])}</h2>")
            elif line.startswith("# "):
                out.append(f"<h1>{inl(line[2:])}</h1>")
            elif line.strip() == "---":
                out.append("<hr>")
            elif line.strip():
                out.append(f"<p>{inl(line)}</p>")
        body = "\n".join(out)
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Draws this week</title>
<style>body{{font-family:system-ui,Arial,sans-serif;max-width:640px;margin:24px auto;padding:0 16px;color:#16202e;line-height:1.5}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border-bottom:1px solid #e3e7ee;padding:6px;text-align:left}}h1{{font-size:24px}}h2{{font-size:18px;margin-top:24px}}a{{color:#0b4f8a}}hr{{border:0;border-top:1px solid #e3e7ee}}</style></head><body>{body}</body></html>"""


if __name__ == "__main__":
    main()
