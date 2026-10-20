#!/usr/bin/env python3
"""Build the static site into public/ from data/*.json.

  python3 scripts/build.py
SITE_URL (default https://albertaadraws.github.io) is used for absolute URLs in the sitemap, RSS/JSON feeds and canonical tags.
BASE_PATH stays empty for this GitHub Pages user site so assets and links are served from the domain root.
Set BASE_PATH (e.g. /repo-name) only for a GitHub Pages project URL.
"""
import datetime as dt, html, json, os, shutil, statistics, sys
from collections import defaultdict
from email.utils import format_datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from aaip import STREAMS, SECTORS, SOURCE_URL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public")
SITE_URL = os.environ.get("SITE_URL", "https://albertaadraws.github.io").rstrip("/")
BASE = os.environ.get("BASE_PATH", "").rstrip("/")
SITE = "Alberta PR Draw Tracker"
TZ = ZoneInfo("America/Edmonton")
COLORS = {"alberta-opportunity-stream": "#2563eb", "dedicated-health-care-pathway": "#c2410c",
          "alberta-express-entry-stream": "#7c3aed", "rural-renewal-stream": "#059669",
          "tourism-and-hospitality-stream": "#d97706", "other": "#64748b"}
STREAM_ORDER = ["dedicated-health-care-pathway", "alberta-opportunity-stream", "alberta-express-entry-stream",
                "rural-renewal-stream", "tourism-and-hospitality-stream"]
OFFICIAL = {
    "alberta-opportunity-stream": "https://www.alberta.ca/aaip-alberta-opportunity-stream",
    "dedicated-health-care-pathway": "https://www.alberta.ca/dedicated-health-care-pathway",
    "alberta-express-entry-stream": "https://www.alberta.ca/aaip-alberta-express-entry-stream",
    "rural-renewal-stream": "https://www.alberta.ca/aaip-rural-renewal-stream",
    "tourism-and-hospitality-stream": "https://www.alberta.ca/aaip-tourism-and-hospitality-stream",
}
e = lambda s: html.escape(str(s if s is not None else ""), quote=True)
u = lambda p: BASE + p


def load(name):
    return json.load(open(os.path.join(ROOT, "data", name)))


DATA = load("draws.json")
DRAWS = [d for d in DATA["draws"]]
POOLS = load("pools.json")
OCC = load("occupations.json")
LATEST_POOL = POOLS["latest"]


def fdate(iso, short=False):
    d = dt.date.fromisoformat(iso[:10])
    return d.strftime("%b %-d, %Y" if short else "%B %-d, %Y")


def ftime(iso):
    t = dt.datetime.fromisoformat(iso).astimezone(TZ)
    return t.strftime("%b %-d, %Y, %-I:%M %p") + " MT"


def inv_sum(ds):
    tot = sum(d["invitations"] or 0 for d in ds)
    lt = sum(1 for d in ds if d["invitations_lt10"])
    return tot, lt


# ------------------------------------------------------------------ SVG chart
def svg_chart(draws, group="stream", height=280, title="Minimum score by draw"):
    pts = [d for d in draws if d["min_score"] is not None]
    if not pts:
        return "<p class='muted'>No scored draws yet.</p>"
    W, H, L, R, T, B = 900, height, 40, 14, 14, 30
    d0 = min(dt.date.fromisoformat(d["date"]) for d in pts)
    d1 = max(dt.date.fromisoformat(d["date"]) for d in pts)
    span = max((d1 - d0).days, 1)
    smin = min(d["min_score"] for d in pts); smax = max(d["min_score"] for d in pts)
    lo, hi = (smin // 5) * 5 - 5, ((smax + 4) // 5) * 5 + 5
    x = lambda d: L + (dt.date.fromisoformat(d).toordinal() - d0.toordinal()) / span * (W - L - R)
    y = lambda s: T + (hi - s) / (hi - lo) * (H - T - B)
    g = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{e(title)}"><title>{e(title)}</title>']
    for s in range(lo, hi + 1, 5):
        g.append(f'<line x1="{L}" x2="{W-R}" y1="{y(s):.1f}" y2="{y(s):.1f}" stroke="#e5e9f0"/><text x="{L-6}" y="{y(s)+4:.1f}" font-size="11" text-anchor="end" fill="#6b7280">{s}</text>')
    # month ticks
    m = dt.date(d0.year, d0.month, 1)
    step = 1 if span < 400 else 2
    while m <= d1:
        if m >= d0:
            xx = x(m.isoformat())
            g.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{T}" y2="{H-B}" stroke="#f1f4f8"/><text x="{xx:.1f}" y="{H-10}" font-size="11" text-anchor="middle" fill="#6b7280">{m.strftime("%b '%y")}</text>')
        mm = m.month - 1 + step
        m = dt.date(m.year + mm // 12, mm % 12 + 1, 1)
    series = defaultdict(list)
    for d in sorted(pts, key=lambda d: d["date"]):
        series[d[group]].append(d)
    for key, ds in series.items():
        col = COLORS.get(ds[0]["stream"], "#64748b") if group == "stream" else PALETTE[list(series).index(key) % len(PALETTE)]
        if len(ds) > 1 and group != "stream":
            path = " ".join(f'{"M" if i == 0 else "L"}{x(d["date"]):.1f},{y(d["min_score"]):.1f}' for i, d in enumerate(ds))
            g.append(f'<path d="{path}" fill="none" stroke="{col}" stroke-opacity=".35" stroke-width="1.5"/>')
        for d in ds:
            g.append(f'<circle cx="{x(d["date"]):.1f}" cy="{y(d["min_score"]):.1f}" r="4.2" fill="{col}"><title>{e(fdate(d["date"], True))} · {e(d["stream_raw"])} · min {d["min_score"]} · {e(d["invitations_text"])} invited</title></circle>')
    g.append("</svg>")
    legend = "".join(f'<span><i class="dot" style="background:{COLORS.get(ds[0]["stream"]) if group=="stream" else PALETTE[i % len(PALETTE)]}"></i>{e(STREAMS[k][0] if group=="stream" else ds[0]["category_label"])}</span>' for i, (k, ds) in enumerate(series.items()))
    return "".join(g) + f'<div class="legend">{legend}</div>'


PALETTE = ["#c2410c", "#2563eb", "#7c3aed", "#059669", "#d97706", "#0891b2", "#be185d", "#4d7c0f", "#64748b"]


# ------------------------------------------------------------------ layout
NAV = [("/", "Latest draws"), ("/health-care-workers/", "Health & care"), ("/streams/", "Streams"),
       ("/occupations/", "Occupations"), ("/score-checker/", "Score checker"), ("/newsletter/", "Newsletter"), ("/about/", "About")]


def page(path, title, desc, body, scripts=(), jsonld=None):
    full_title = f"{title} | {SITE}" if path != "/" else f"{SITE}: every Alberta (AAIP) immigration draw, tracked"
    nav = "".join(f'<a href="{u(p)}"{" class=active" if (p == path or (p != "/" and path.startswith(p))) else ""}>{e(t)}</a>' for p, t in NAV)
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    sc = "".join(f'<script src="{u("/assets/" + s)}" defer></script>' for s in ("app.js",) + tuple(scripts))
    doc = f"""<!doctype html><html lang="en-CA"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE_URL}{path}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{SITE}"><meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{SITE_URL}{path}"><meta name="twitter:card" content="summary">
<meta name="theme-color" content="#0b4f8a">
<link rel="alternate" type="application/rss+xml" title="{SITE} – draws" href="{u('/feed.xml')}">
<link rel="alternate" type="application/feed+json" title="{SITE} – draws" href="{u('/feed.json')}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230b4f8a'/%3E%3Ctext x='16' y='22' font-size='15' text-anchor='middle' fill='white' font-family='Arial' font-weight='bold'%3EPR%3C/text%3E%3C/svg%3E">
<link rel="stylesheet" href="{u('/assets/style.css')}">{ld}</head><body>
<header class="site"><div class="wrap"><a class="logo" href="{u('/')}"><span class="mark">PR</span>{SITE}</a>
<button class="menu-btn" aria-label="Menu">Menu</button><nav class="main">{nav}</nav></div></header>
<div class="notice"><div class="wrap">Independent tracker. <b>Not affiliated with the Government of Alberta.</b> Information only, not immigration advice. <a href="{u('/disclaimer/')}">Read the disclaimer</a>.</div></div>
<main><div class="wrap">{body}</div></main>
<footer class="site"><div class="wrap">
<div class="disc"><b>Disclaimer:</b> {SITE} is an independent, informational website. It is <b>not affiliated with, endorsed by, or connected to the Government of Alberta, the Alberta Advantage Immigration Program (AAIP), or IRCC</b>. Nothing here is immigration or legal advice. Data is copied from public Government of Alberta pages and may be incomplete, delayed or wrong. Always check <a href="{SOURCE_URL}" rel="noopener">the official AAIP page</a> and talk to a licensed Regulated Canadian Immigration Consultant (RCIC) or a lawyer before you make decisions.</div>
<nav class="small"><a href="{u('/draws/')}">All draws</a><a href="{u('/score-checker/')}">Score checker</a><a href="{u('/about/')}">About & sources</a><a href="{u('/disclaimer/')}">Disclaimer</a><a href="{u('/sponsor/')}">Sponsor this site</a><a href="{u('/feed.xml')}">RSS</a><a href="{u('/feed.json')}">JSON feed</a></nav>
<p class="small">Data last checked {ftime(DATA['last_refreshed'])} · Official page last updated {fdate(DATA['page_last_updated']) if DATA.get('page_last_updated') else 'unknown'} · © {dt.date.today().year} {SITE}</p>
</div></footer>{sc}</body></html>"""
    dest = os.path.join(OUT, path.strip("/"), "index.html") if path.endswith("/") else os.path.join(OUT, path.lstrip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "w", encoding="utf-8").write(doc)
    if path.endswith("/") and path != "/404/":
        PAGES.append(path)


PAGES = []


# ------------------------------------------------------------------ components
def draws_table(ds, show_sector=True, tid=None, data_attrs=False):
    rows = []
    for d in ds:
        hc = d["sector"] == "health-care"
        attrs = f' data-stream="{d["stream"]}" data-year="{d["year"]}" data-sector="{d["sector"]}"' if data_attrs else ""
        nocs = f' <span class="pill" title="Occupation codes listed in the official draw summary">{len(d["nocs"])} NOCs</span>' if d.get("nocs") else ""
        rows.append(f'<tr id="{d["id"]}"{attrs}><td class="date">{fdate(d["date"], True)}</td>'
                    f'<td><i class="dot" style="background:{COLORS.get(d["stream"])}"></i><a href="{u("/streams/" + d["stream"] + "/")}">{e(d["stream_raw"])}</a>{nocs}</td>'
                    + (f'<td class="sec"><span class="pill{" health" if hc else ""}">{e(d["sector_name"])}</span></td>' if show_sector else "")
                    + f'<td class="num"><b>{e(d["min_score_text"] if d["min_score"] is None else d["min_score"])}</b></td><td class="num">{e(d["invitations_text"])}</td></tr>')
    head = "<tr><th>Date</th><th>Stream / pathway</th>" + ('<th class="sec">Sector</th>' if show_sector else "") + '<th class="num">Min score</th><th class="num">Invitations</th></tr>'
    return f'<div class="table-wrap"><table{f" id={tid}" if tid else ""}><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def newsletter_box(compact=False):
    # TODO(newsletter): replace action="#" with the provider's embed form action (e.g. Buttondown:
    #   https://buttondown.com/api/emails/embed-subscribe/<username>) and remove data-newsletter.
    return f"""<div class="card" id="newsletter"><h3>📬 Draws this week, in your inbox</h3>
<p class="small muted" style="margin:0 0 10px">One short email every week: new AAIP draws, minimum scores and pool changes. Free. Unsubscribe any time.</p>
<!-- TODO: newsletter provider not connected yet. This form does not send data anywhere. -->
<form class="inline" action="#" method="post" data-newsletter data-todo="connect-newsletter-provider">
<input type="email" name="email" required placeholder="you@example.com" aria-label="Email address"><button class="btn" type="submit">Subscribe</button></form>
<p class="nl-msg small hidden" style="color:var(--warn);margin:8px 0 0"></p></div>"""


def affiliate_box():
    # TODO(affiliate): swap these plain links for tracked affiliate links once approved
    #   (PracticeCLB partners: https://practiceclb.com/partners ; CELPIP Simulator referral: https://www.celpipsimulator.com/referral-program)
    return f"""<div class="slot" data-slot="affiliate-english-test"><div class="tag">Affiliate placeholder · English test practice</div>
<h3 style="margin-top:6px">Boost your language score</h3>
<p class="small muted" style="margin:0 0 8px">Language test results are one of the biggest parts of most Alberta EOI scores. Practice tools:</p>
<ul class="small" style="margin:0;padding-left:18px">
<li><a href="https://practiceclb.com/" rel="sponsored noopener" target="_blank">PracticeCLB</a>: CELPIP & CLB practice <!-- TODO affiliate link --></li>
<li><a href="https://www.celpipsimulator.com/" rel="sponsored noopener" target="_blank">CELPIP Simulator</a>: full mock exams with AI scoring <!-- TODO affiliate link --></li></ul>
<p class="small muted" style="margin:8px 0 0">Disclosure: we may earn a commission from these links in future. It doesn't affect the data on this site.</p></div>"""


def sponsor_box():
    return f"""<div class="slot" data-slot="sponsor"><div class="tag">Sponsor slot · available</div>
<h3 style="margin-top:6px">Sponsor this site</h3>
<p class="small muted" style="margin:0 0 8px">Reach people actively tracking Alberta immigration draws. One sponsor at a time, clearly labelled.</p>
<a class="btn ghost" href="{u('/sponsor/')}">Sponsorship details</a></div>"""


def stream_stats(ds):
    sc = [d["min_score"] for d in ds if d["min_score"] is not None]
    yr = dt.date.today().year
    this = [d for d in ds if d["year"] == yr]
    tot, lt = inv_sum(this)
    return sc, this, tot, lt


def pools_block():
    rows = [p for p in LATEST_POOL["pools"] if p["count"] is not None]
    mx = max(p["count"] for p in rows)
    rows.sort(key=lambda p: (p["stream"] != "dedicated-health-care-pathway", -p["count"]))
    trs = "".join(f'<tr><td><i class="dot" style="background:{COLORS.get(p["stream"])}"></i>{e(p["full_name"])}</td><td class="num"><b>{p["count"]:,}</b></td><td style="width:38%"><div class="bar"><span style="width:{p["count"]/mx*100:.1f}%;background:{COLORS.get(p["stream"])}"></span></div></td></tr>' for p in rows)
    hist = POOLS["snapshots"]
    note = f"{len(hist)} snapshot{'s' if len(hist) != 1 else ''} stored so far. Pool history builds up as the daily refresh runs."
    return f"""<div class="table-wrap"><table><thead><tr><th>Stream / pathway</th><th class="num">EOIs in pool</th><th></th></tr></thead><tbody>{trs}
<tr><td><b>Total</b></td><td class="num"><b>{(LATEST_POOL.get('total') or 0):,}</b></td><td></td></tr></tbody></table></div>
<p class="meta">Source: <a href="{SOURCE_URL}">AAIP processing information</a>, Table 9 (as of {fdate(LATEST_POOL['page_last_updated'])}). {note}</p>"""


def nominations_block():
    rows = []
    for n in LATEST_POOL["nominations"]:
        v = n["values"]
        alloc = next((v[k] for k in v if "allocation" in k.lower()), "")
        issued = next((v[k] for k in v if "issued" in k.lower()), "")
        rem = next((v[k] for k in v if "remaining" in k.lower()), "")
        name = n["name"].split(" (")[0]
        rows.append(f"<tr><td>{e(name)}</td><td class='num'>{e(alloc)}</td><td class='num'>{e(issued)}</td><td class='num'><b>{e(rem)}</b></td></tr>")
    return f"""<div class="table-wrap"><table><thead><tr><th>Stream</th><th class="num">2026 allocation</th><th class="num">Issued</th><th class="num">Spaces left</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="meta">Source: <a href="{SOURCE_URL}">AAIP processing information</a>, Tables 1–8.</p>"""


# ------------------------------------------------------------------ pages
def build_home():
    latest = DRAWS[0]
    yr = dt.date.today().year
    this = [d for d in DRAWS if d["year"] == yr]
    tot, lt = inv_sum(this)
    health = [d for d in DRAWS if d["sector"] == "health-care"]
    h_this = [d for d in health if d["year"] == yr]
    htot, hlt = inv_sum(h_this)
    last30 = [d for d in DRAWS if (dt.date.today() - dt.date.fromisoformat(d["date"])).days <= 30]
    summary = next((n["values"] for n in LATEST_POOL["nominations"] if n["section"].startswith("All streams")), {})
    body = f"""
<div class="hero"><div><h1>Every Alberta immigration draw, in one place</h1>
<p class="lead">Minimum scores, invitation counts and pool sizes for every Alberta Advantage Immigration Program (AAIP) draw. Checked every day against the official Government of Alberta page.</p>
<p><a class="btn" href="{u('/score-checker/')}">Check where your score stands →</a> <a class="btn ghost" href="{u('/health-care-workers/')}">Health & care workers</a></p>
<p class="meta">Official page last updated <b>{fdate(DATA['page_last_updated'])}</b> · we last checked {ftime(DATA['last_refreshed'])}</p></div>
<div class="card latest"><div class="meta">Latest draw · {fdate(latest['date'])}</div>
<h3 style="margin:6px 0 10px">{e(latest['stream_raw'])}</h3>
<div class="grid g2" style="grid-template-columns:1fr 1fr"><div><div class="big">{latest['min_score']}</div><div class="meta">minimum score</div></div><div><div class="big">{e(latest['invitations_text'])}</div><div class="meta">invitations</div></div></div>
<p class="small" style="margin:12px 0 0"><a href="{u('/streams/' + latest['stream'] + '/')}">More {e(STREAMS[latest['stream']][0])} draws →</a></p></div></div>

<div class="grid g4" style="margin-top:18px">
<div class="card stat"><div class="n">{len(this)}</div><div class="l">draws in {yr}</div></div>
<div class="card stat"><div class="n">{tot:,}{'+' if lt else ''}</div><div class="l">invitations in {yr}{f' (+{lt} draws listed as "less than 10")' if lt else ''}</div></div>
<div class="card stat"><div class="n">{(LATEST_POOL.get('total') or 0):,}</div><div class="l">candidates in the EOI pool</div></div>
<div class="card stat"><div class="n">{e(summary.get('2026 nomination spaces remaining', '–'))}</div><div class="l">2026 nomination spaces left (of {e(summary.get('2026 nomination allocation', '–'))})</div></div></div>

<section class="card feature" style="margin-top:22px"><h2>🩺 Health & care workers</h2>
<p class="small" style="margin:0 0 12px">Alberta runs dedicated draws for nurses, physicians and other regulated health professionals, plus Express Entry "Priority Sectors (Health Care)" draws. <b>{len(h_this)}</b> health draws so far in {yr}, with <b>{htot:,}{'+' if hlt else ''}</b> invitations.</p>
{draws_table(health[:5], show_sector=False)}
<p class="small" style="margin:10px 0 0"><a href="{u('/health-care-workers/')}">All health & care draws, eligible professions and trends →</a></p></section>

<h2>Latest draws</h2>{draws_table(DRAWS[:12])}
<p class="small"><a href="{u('/draws/')}">See all {len(DRAWS)} draws since {fdate(DRAWS[-1]['date'])} →</a></p>

<h2>Minimum score trend</h2><div class="card">{svg_chart([d for d in DRAWS if d['year'] == yr], title=f'Minimum score of each AAIP draw in {yr}')}
<p class="meta">Each dot is one draw. Hover or tap a dot for details. Streams target different people, so compare like with like.</p></div>

<div class="grid g2" style="margin-top:8px"><div><h2>Who's waiting: EOI pool sizes</h2>{pools_block()}</div>
<div><h2>2026 nomination spaces</h2>{nominations_block()}</div></div>

<div class="grid g3" style="margin-top:26px">{newsletter_box()}{affiliate_box()}{sponsor_box()}</div>
"""
    jsonld = {"@context": "https://schema.org", "@type": "Dataset", "name": "Alberta AAIP draw history",
              "description": "Date, stream, minimum score and invitations for each Alberta Advantage Immigration Program draw.",
              "url": SITE_URL + "/", "isBasedOn": SOURCE_URL, "dateModified": DATA["last_refreshed"][:10],
              "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE_URL + "/data/draws.json"}]}
    page("/", SITE, f"Track every Alberta AAIP immigration draw: latest minimum scores, invitations and pool sizes. Latest: {fdate(latest['date'])}, {latest['stream_raw']}, min score {latest['min_score']}.", body, jsonld=jsonld)


def build_all_draws():
    years = sorted({d["year"] for d in DRAWS}, reverse=True)
    opt = lambda pairs: "".join(f'<option value="{k}">{e(v)}</option>' for k, v in pairs)
    body = f"""<h1>All Alberta (AAIP) draws</h1><p class="lead">Every draw we have on record: {len(DRAWS)} draws from {fdate(DRAWS[-1]['date'])} to {fdate(DRAWS[0]['date'])}. Filter by stream, sector or year.</p>
<div class="filters" data-filter-table="#all"><select name="stream"><option value="">All streams</option>{opt((k, STREAMS[k][0]) for k in STREAM_ORDER)}</select>
<select name="sector"><option value="">All sectors</option>{opt(SECTORS.items())}</select>
<select name="year"><option value="">All years</option>{opt((y, y) for y in years)}</select><input name="q" type="search" placeholder="Search…"></div>
<p class="meta">Showing <span data-count>{len(DRAWS)}</span> draws. 2026 draws come from the <a href="{SOURCE_URL}">AAIP processing information page</a>. 2025 draws come from the official <a href="https://www.alberta.ca/system/files/im-aaip-draw-history-summary.pdf">AAIP Draw Summary 2025 (PDF)</a>, which also lists the occupation (NOC) codes targeted by some draws.</p>
{draws_table(DRAWS, tid="all", data_attrs=True)}"""
    page("/draws/", "All AAIP draws", f"Complete list of {len(DRAWS)} Alberta Advantage Immigration Program draws with minimum scores and invitations. Filter by stream, sector and year.", body)


def build_streams():
    cards = []
    for s in STREAM_ORDER:
        ds = [d for d in DRAWS if d["stream"] == s]
        if not ds:
            continue
        name, short, desc = STREAMS[s]
        sc, this, tot, lt = stream_stats(ds)
        pool = [p for p in LATEST_POOL["pools"] if p["stream"] == s]
        pool_n = sum(p["count"] or 0 for p in pool)
        cats = sorted({(d["category"], d["category_label"]) for d in ds})
        last = ds[0]
        catlinks = " ".join(f'<a class="btn ghost small" style="padding:6px 10px;font-size:13px;margin:0 6px 6px 0" href="{u("/score-checker/?cat=" + c)}">Check score: {e(l)}</a>' for c, l in cats)
        nocs_draws = [d for d in ds if d.get("nocs")]
        body = f"""<p class="meta"><a href="{u('/streams/')}">Streams</a> / {e(short)}</p><h1>{e(name)} draws</h1><p class="lead">{e(desc)}</p>
<div class="grid g4"><div class="card stat"><div class="n">{last['min_score']}</div><div class="l">latest minimum ({fdate(last['date'], True)})</div></div>
<div class="card stat"><div class="n">{len(this)}</div><div class="l">draws in {dt.date.today().year}</div></div>
<div class="card stat"><div class="n">{tot:,}{'+' if lt else ''}</div><div class="l">invitations in {dt.date.today().year}</div></div>
<div class="card stat"><div class="n">{pool_n:,}</div><div class="l">EOIs in pool now</div></div></div>
<h2>Minimum score over time</h2><div class="card">{svg_chart(ds, group='category', title=name + ' minimum scores')}
<p class="meta">Range across all {len(sc)} draws: {min(sc)}–{max(sc)} (median {statistics.median(sc):g}).</p></div>
<h2>Where does my score stand?</h2><div class="chips">{catlinks}</div>
<h2>Draw history</h2>{draws_table(ds)}
{"<h2>Occupations named in draws</h2><p class='small'>These draws listed specific occupation (NOC) codes in the official 2025 Draw Summary:</p>" + "".join(f"<details class='card' style='margin-bottom:8px'><summary><b>{fdate(d['date'], True)}</b>: {e(d['stream_raw'])} ({len(d['nocs'])} NOC codes)</summary><ul class='small'>" + "".join(f"<li>{n['code']}: {e(n['title'])}</li>" for n in d['nocs']) + "</ul></details>" for d in nocs_draws) if nocs_draws else ""}
<p class="meta" style="margin-top:16px">Official stream info: <a href="{OFFICIAL.get(s, SOURCE_URL)}">{OFFICIAL.get(s, SOURCE_URL)}</a></p>
<div class="grid g2" style="margin-top:20px">{newsletter_box()}{affiliate_box()}</div>"""
        page(f"/streams/{s}/", f"{name} draws & minimum scores", f"All {name} ({short}) draws: latest minimum score {last['min_score']} on {fdate(last['date'])}, invitations, trends and pool size.", body)
        cards.append(f'<a class="card" style="text-decoration:none;color:inherit;border-left:4px solid {COLORS[s]}" href="{u("/streams/" + s + "/")}"><h3>{e(name)}</h3><p class="small muted" style="margin:0 0 8px">{e(desc)}</p><div class="small">Latest: <b>{fdate(last["date"], True)}</b>, min score <b>{last["min_score"]}</b> · {len(ds)} draws on record · pool {pool_n:,}</div></a>')
    page("/streams/", "AAIP streams", "Draw history, minimum scores and pool sizes for each Alberta Advantage Immigration Program worker stream.",
         f"<h1>Draws by stream</h1><p class='lead'>Each AAIP worker stream has its own draws and its own score range. Pick yours.</p><div class='grid g2'>{''.join(cards)}</div>")


def build_health():
    hs = [d for d in DRAWS if d["sector"] == "health-care"]
    by_cat = defaultdict(list)
    for d in hs:
        by_cat[d["category_label"]].append(d)
    yr = dt.date.today().year
    stat_cards = ""
    for lab, ds in by_cat.items():
        this = [d for d in ds if d["year"] == yr]
        tot, lt = inv_sum(this)
        stat_cards += f'<div class="card"><h3>{e(lab)}</h3><div class="small">Latest: <b>{fdate(ds[0]["date"], True)}</b>, min score <b>{ds[0]["min_score"]}</b>, {e(ds[0]["invitations_text"])} invited<br>{yr}: {len(this)} draws, {tot:,}{"+" if lt else ""} invitations<br><a href="{u("/score-checker/?cat=" + ds[0]["category"])}">Check my score →</a></div></div>'
    pool = next((p for p in LATEST_POOL["pools"] if p["stream"] == "dedicated-health-care-pathway"), None)
    nom = next((n["values"] for n in LATEST_POOL["nominations"] if n["section"].startswith("Dedicated Health")), {})
    body = f"""<h1>Alberta immigration draws for health & care workers</h1>
<p class="lead">Alberta invites health professionals in two ways: the <b>Dedicated Health Care Pathway</b> (Express Entry and non-Express Entry options) and <b>Alberta Express Entry Priority Sectors (Health Care)</b> draws. All of them are tracked here.</p>
<div class="grid g3">{stat_cards}</div>
<div class="grid g4" style="margin-top:14px"><div class="card stat"><div class="n">{pool['count'] if pool else '–':,}</div><div class="l">EOIs in the Dedicated Health Care pool</div></div>
<div class="card stat"><div class="n">{e(nom.get('2026 nomination allocation', '–'))}</div><div class="l">2026 health pathway allocation</div></div>
<div class="card stat"><div class="n">{e(nom.get('2026 nomination spaces remaining', '–'))}</div><div class="l">spaces remaining</div></div>
<div class="card stat"><div class="n">{e(nom.get('Currently assessing applications received on or before:', '–'))}</div><div class="l">now assessing applications received on or before</div></div></div>
<h2>Minimum score trend</h2><div class="card">{svg_chart(hs, group='category', title='Health care draw minimum scores')}</div>
<h2>Eligible professions (Dedicated Health Care Pathway)</h2>
<div class="card small"><p style="margin-top:0">According to <a href="https://www.alberta.ca/dedicated-health-care-pathway">alberta.ca</a>, you need an Alberta job offer and proof from the Alberta regulator that you can practise in one of these professions:</p>
<ul style="columns:2;margin:0">{''.join(f'<li>{p}</li>' for p in ['Physicians (CPSA)','Registered Nurses (CRNA)','Licensed Practical Nurses (CLPNA)','Nurse Practitioners (CRNA)','Physician Assistants (CPSA)','Occupational Therapists (ACOT)','Physiotherapists (CPA)','Clinical Social Workers (ACSW)','Psychologists (CAP)'])}</ul>
<p class="muted" style="margin-bottom:0">Care aides, health care aides and other unregulated care roles aren't on this list. They may be eligible under other streams, such as the Alberta Opportunity Stream or Rural Renewal Stream. Always check the official eligibility page.</p></div>
<h2>All health & care draws</h2>{draws_table(hs, show_sector=False)}
<div class="grid g2" style="margin-top:20px">{newsletter_box()}{affiliate_box()}</div>"""
    page("/health-care-workers/", "Health care worker draws (Alberta AAIP)", "Alberta immigration draws for nurses, physicians and other health professionals: Dedicated Health Care Pathway and Express Entry Health Care draw minimum scores, invitations and pool size.", body)


def build_occupations():
    by = defaultdict(list)
    for d in DRAWS:
        by[d["sector"]].append(d)
    order = ["health-care"] + [s for s in SECTORS if s != "health-care"]
    rows = ""
    for s in order:
        ds = by.get(s)
        if not ds:
            continue
        sc = [d["min_score"] for d in ds if d["min_score"] is not None]
        rows += f'<tr><td><b>{e(SECTORS[s])}</b></td><td class="num">{len(ds)}</td><td class="date">{fdate(ds[0]["date"], True)}</td><td class="num">{ds[0]["min_score"]}</td><td class="num">{min(sc)}–{max(sc)}</td></tr>'
    invited = sum(len(y["nocs_invited"]) for y in OCC.get("years", []))
    body = f"""<h1>Draws by occupation & sector</h1>
<p class="lead">Alberta targets many draws at specific sectors. The draw name tells us the sector (health care, tech, construction, and so on). For 2025, the official Draw Summary also lists exact occupation (NOC) codes.</p>
<div class="table-wrap"><table><thead><tr><th>Sector</th><th class="num">Draws</th><th>Latest</th><th class="num">Latest min</th><th class="num">Range</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="meta">"General / all occupations" covers draws that aren't sector-specific, such as most Alberta Opportunity Stream draws.</p>
<h2>Look up your occupation (NOC code)</h2>
<div class="card" id="noc-lookup" data-base="{BASE}"><label for="noc">NOC code or job title</label><input id="noc" type="search" placeholder="e.g. 31301 or nurse" style="width:100%;max-width:420px">
<p class="small muted">Searches the {invited} occupation codes that received AAIP invitations in 2025 and the NOC lists in targeted 2025 draws (official Draw Summary 2025). 2026 draws on the live page don't list NOC codes.</p><div class="out"></div></div>"""
    page("/occupations/", "AAIP draws by occupation", "Which occupations and sectors Alberta's AAIP draws target: health care, tech, construction, agriculture, aviation and more, plus a NOC code lookup.", body, scripts=("occupations.js",))


def build_checker():
    body = f"""<h1>Where do I stand?</h1>
<p class="lead">Compare your Alberta Worker Expression of Interest (WEOI) score with the minimum scores in recent draws for your stream or pathway.</p>
<div class="grid" style="grid-template-columns:minmax(0,1fr)"><div class="card" id="checker" data-base="{BASE}">
<p id="loading" class="muted">Loading draw data…</p>
<form class="hidden"><div class="grid g3">
<div><label for="cat">Stream / pathway</label><select id="cat" style="width:100%"></select></div>
<div><label for="score">Your WEOI score (0–100)</label><input id="score" type="number" inputmode="numeric" min="0" max="100" placeholder="e.g. 58" style="width:100%" required></div>
<div><label for="window">Compare with</label><select id="window" style="width:100%"><option value="5">Last 5 draws</option><option value="3">Last 3 draws</option><option value="10">Last 10 draws</option><option value="12m">Last 12 months</option></select></div></div>
<p style="margin:14px 0 0"><button class="btn" type="submit">Check my score</button></p></form>
<p class="small muted" style="margin:12px 0 0">Your score stays in your browser. Nothing is sent or saved.</p><div id="out"></div></div></div>
<div class="callout small" style="margin-top:16px"><b>Don't know your score?</b> Your WEOI score comes from Alberta's points grid (language, work experience, job offer, education and more). See the official <a href="https://www.alberta.ca/how-to-apply-to-aaip-worker-streams">how to apply to AAIP worker streams</a> page and Alberta's Eligibility Explorer. This tool can't tell you whether you're eligible or whether you'll be invited. A licensed RCIC or immigration lawyer can.</div>
<div class="grid g2" style="margin-top:20px">{affiliate_box()}{newsletter_box()}</div>"""
    page("/score-checker/", "AAIP score checker: where do I stand?", "Free tool: compare your Alberta WEOI score with recent AAIP draw minimum scores for your stream, including health care pathways.", body, scripts=("checker.js",))


def build_static_pages():
    page("/about/", "About & data sources", "How the Alberta PR Draw Tracker collects AAIP draw data, how often it updates and what the sources are.", f"""
<h1>About this site</h1><p class="lead">{SITE} is an independent, Edmonton-made tracker that turns Alberta's official draw tables into something easier to follow: charts, a score checker and a weekly email.</p>
<div class="card"><h3>Where the data comes from</h3><ul>
<li><a href="{SOURCE_URL}">AAIP processing information</a> (Government of Alberta): current-year draws (Table 10), EOI pool sizes (Table 9) and nomination allocations (Tables 1–8). Checked daily.</li>
<li><a href="https://www.alberta.ca/system/files/im-aaip-draw-history-summary.pdf">AAIP Draw Summary 2025 (PDF)</a>: previous-year draws with selection parameters and occupation (NOC) codes.</li>
<li><a href="https://www.alberta.ca/dedicated-health-care-pathway">Dedicated Health Care Pathway</a>: eligible health professions.</li>
<li><a href="https://www.alberta.ca/aaip-updates">AAIP updates</a>: program changes and announcements.</li></ul>
<p class="small muted">We copy numbers as published. "Less than 10" invitations are shown as published and left out of invitation totals, so those totals are a minimum. If the official page and this site disagree, the official page is right.</p></div>
<div class="card" style="margin-top:14px"><h3>How updates work</h3><p class="small" style="margin:0">A script fetches the official page every day, adds new draws, keeps old ones (so history isn't lost when Alberta moves a year into a PDF) and saves a pool-size snapshot whenever the numbers change. Data last checked {ftime(DATA['last_refreshed'])}.</p></div>
<div class="card" style="margin-top:14px"><h3>Open data</h3><p class="small" style="margin:0">Download the data: <a href="{u('/data/draws.json')}">draws.json</a> · <a href="{u('/data/pools.json')}">pools.json</a> · <a href="{u('/data/occupations.json')}">occupations.json</a> · <a href="{u('/feed.xml')}">RSS</a> · <a href="{u('/feed.json')}">JSON Feed</a></p></div>
<div class="card" style="margin-top:14px"><h3>Contact</h3><p class="small" style="margin:0"><!-- TODO: add contact email once a domain/inbox exists -->Contact details coming soon.</p></div>""")

    page("/disclaimer/", "Disclaimer", "Alberta PR Draw Tracker is informational only, not immigration advice, and not affiliated with the Government of Alberta.", f"""
<h1>Disclaimer</h1><div class="card"><p><b>Informational only.</b> {SITE} publishes information copied from public Government of Alberta web pages, to help people follow Alberta Advantage Immigration Program (AAIP) draws. It is <b>not immigration advice, legal advice or professional advice</b> of any kind.</p>
<p><b>Not affiliated.</b> This site is independent. It is <b>not affiliated with, endorsed by, sponsored by or connected to the Government of Alberta</b>, the Alberta Advantage Immigration Program, Immigration, Refugees and Citizenship Canada (IRCC) or any government body.</p>
<p><b>No guarantees.</b> Data may be delayed, incomplete or wrong. Past draw scores don't predict future draws. AAIP states that the EOI score is not the only factor it uses to select candidates, and draws often target specific occupations, sectors, job offers or other criteria. The score checker is a comparison tool, not an eligibility assessment.</p>
<p><b>Get professional help.</b> Before making any immigration decision, check the <a href="{SOURCE_URL}">official AAIP information</a> and talk to a licensed <b>Regulated Canadian Immigration Consultant (RCIC)</b> (verify a licence at the <a href="https://college-ic.ca/protecting-the-public/find-an-immigration-consultant">College of Immigration and Citizenship Consultants</a>) or a lawyer licensed by a Canadian law society.</p>
<p><b>Affiliate links and sponsors.</b> Some links may be affiliate links, and some spots may be sponsored. Both are always labelled and never change the data.</p>
<p class="muted small">Never pay anyone who promises a guaranteed AAIP invitation or nomination.</p></div>""")

    page("/sponsor/", "Sponsor this site", "Sponsor the Alberta PR Draw Tracker and weekly draws newsletter.", f"""
<h1>Sponsor this site</h1><p class="lead">Reach people actively tracking Alberta immigration draws: newcomers, international graduates, health care workers and the families and employers around them.</p>
<div class="grid g2"><div class="card"><h3>Available placements</h3><ul class="small"><li>Site-wide sponsor slot (one sponsor at a time)</li><li>Weekly "Draws this week" newsletter sponsor</li><li>Score checker results-page placement</li></ul></div>
<div class="card"><h3>Rules</h3><ul class="small"><li>Sponsors are always clearly labelled</li><li>Sponsors never influence data</li><li>Licensed professionals only for immigration services (RCIC / lawyer)</li></ul></div></div>
<div class="slot" style="margin-top:14px"><div class="tag">TODO</div><p class="small" style="margin:6px 0 0">Add rate card, traffic stats and a contact email once the site is live.</p></div>""")

    page("/newsletter/", "Weekly draws newsletter", "Get a short weekly email with every new Alberta AAIP draw, minimum scores and pool changes.", f"""
<h1>Draws this week: the newsletter</h1><p class="lead">Every week: new AAIP draws, minimum scores, invitation counts, pool size changes and a health-care roundup. Short, free, no spam.</p>
<div class="grid g2">{newsletter_box()}<div class="card small"><h3>What you'll get</h3><ul style="margin:0"><li>All draws from the past 7 days</li><li>Score trends for each stream</li><li>Pool size changes</li><li>A health & care workers section</li></ul></div></div>""")

    page("/404.html", "Page not found", "Page not found.", f"<h1>Page not found</h1><p><a href='{u('/')}'>Go to the latest draws →</a></p>")


# ------------------------------------------------------------------ feeds, sitemap
def build_feeds():
    items = DRAWS[:50]
    def title(d):
        return f"{fdate(d['date'], True)}: {d['stream_raw']}, min score {d['min_score_text']}, {d['invitations_text']} invitations"
    def link(d):
        return f"{SITE_URL}/streams/{d['stream']}/#{d['id']}"
    def pub(d):
        return dt.datetime.fromisoformat(d["date"] + "T12:00:00").replace(tzinfo=TZ)
    rss = [f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>{SITE}: AAIP draws</title><link>{SITE_URL}/</link><atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/><description>New Alberta Advantage Immigration Program draws. Informational only, not affiliated with the Government of Alberta.</description><language>en-ca</language><lastBuildDate>{format_datetime(dt.datetime.now(dt.timezone.utc))}</lastBuildDate>']
    for d in items:
        rss.append(f"<item><title>{e(title(d))}</title><link>{e(link(d))}</link><guid isPermaLink=\"false\">{e(d['id'])}</guid><pubDate>{format_datetime(pub(d))}</pubDate><category>{e(d['stream_name'])}</category><description>{e(title(d))}. Source: {SOURCE_URL}</description></item>")
    rss.append("</channel></rss>")
    open(os.path.join(OUT, "feed.xml"), "w").write("\n".join(rss))
    jf = {"version": "https://jsonfeed.org/version/1.1", "title": f"{SITE}: AAIP draws", "home_page_url": SITE_URL + "/",
          "feed_url": SITE_URL + "/feed.json", "description": "New Alberta AAIP draws. Informational only.",
          "items": [{"id": d["id"], "url": link(d), "title": title(d), "content_text": title(d) + f". Source: {SOURCE_URL}",
                     "date_published": pub(d).isoformat(), "tags": [d["stream_name"], d["sector_name"]],
                     "_aaip": {k: d[k] for k in ("date", "stream_raw", "stream", "category", "sector", "min_score", "invitations", "invitations_text")}} for d in items]}
    json.dump(jf, open(os.path.join(OUT, "feed.json"), "w"), indent=1, ensure_ascii=False)
    today = dt.date.today().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in PAGES:
        sm.append(f"<url><loc>{SITE_URL}{p}</loc><lastmod>{today}</lastmod><changefreq>{'daily' if p in ('/', '/draws/', '/health-care-workers/') or p.startswith('/streams/') else 'weekly'}</changefreq></url>")
    sm.append("</urlset>")
    open(os.path.join(OUT, "sitemap.xml"), "w").write("\n".join(sm))
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets"))
    os.makedirs(os.path.join(OUT, "data"))
    for f in os.listdir(os.path.join(ROOT, "src")):
        shutil.copy(os.path.join(ROOT, "src", f), os.path.join(OUT, "assets", f))
    for f in ("draws.json", "pools.json", "occupations.json"):
        shutil.copy(os.path.join(ROOT, "data", f), os.path.join(OUT, "data", f))
    build_home(); build_all_draws(); build_health(); build_streams(); build_occupations(); build_checker(); build_static_pages(); build_feeds()
    print(f"[build] {len(PAGES)} pages + feeds written to {OUT} (SITE_URL={SITE_URL})")


if __name__ == "__main__":
    main()
