#!/usr/bin/env python3
"""Build the static site into public/ from data/*.json.

  SITE_URL=https://albertaadraws.github.io BASE_PATH=/alberta-power python3 scripts/build.py

SITE_URL + BASE_PATH form the canonical base (default: https://albertaadraws.github.io/alberta-power/,
a GitHub Pages project site). BASE_PATH prefixes every internal link so the site works under the subpath.
Rankings are by estimated cost only. config/partners.json is read only to show a separately
labelled partner link; it never affects order.
"""
import datetime as dt, html, json, os, shutil, sys
from email.utils import format_datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public")
SITE_URL = os.environ.get("SITE_URL", "https://albertaadraws.github.io").rstrip("/")
BASE = os.environ.get("BASE_PATH", "/alberta-power").rstrip("/")
SITE = "Alberta Power & Gas Rate Tracker"
TZ = ZoneInfo("America/Edmonton")
USAGE = {"kwh": 600, "gj": 10}
USAGE_SRC = "https://ucahelps.alberta.ca/residential/faq/"
PRESETS = {"small": {"kwh": 350, "gj": 5, "label": "Small (apartment/condo)"},
           "avg": {"kwh": 600, "gj": 10, "label": "Average home"},
           "large": {"kwh": 1000, "gj": 15, "label": "Large home"}}
UCA = {
    "rolr": "https://ucahelps.alberta.ca/utility-choices/current-rates-and-pricing/rate-of-last-resort/",
    "switch": "https://ucahelps.alberta.ca/utility-choices/shop-for-utilities/how-to-switch-energy-retailers/",
    "choose": "https://ucahelps.alberta.ca/utility-choices/shop-for-utilities/how-to-choose-a-retailer/",
    "defaults": "https://ucahelps.alberta.ca/utility-choices/current-rates-and-pricing/default-rates/",
    "tool": "https://ucahelps.alberta.ca/cost-comparison-tool/",
    "contact": "https://ucahelps.alberta.ca/contact/",
    "decision": "https://ucahelps.alberta.ca/media/a35cdlk5/decision-29204-d02-2025.pdf",
}
e = lambda s: html.escape(str(s if s is not None else ""), quote=True)
u = lambda p: BASE + p


def load(name, default=None):
    p = os.path.join(ROOT, name)
    return json.load(open(p)) if os.path.exists(p) else default


PLANS = load("data/plans.json")["plans"]
DEF = load("data/defaults.json"); DEF.pop("_parts", None)
CHANGES = load("data/changes.json", {"changes": []})["changes"]
STATUS = load("data/status.json", {"sources": [], "not_published": []})
UPDATED = load("data/plans.json")["updated"]
PARTNERS = load("config/partners.json", {"enabled": False, "partners": {}})


def fdate(iso):
    return dt.date.fromisoformat(iso[:10]).strftime("%b %-d, %Y")


def ftime(iso):
    return dt.datetime.fromisoformat(iso).astimezone(TZ).strftime("%b %-d, %Y, %-I:%M %p") + " MT"


def cost(p, use=None):
    if p["fuel"] == "electricity":
        return (use or USAGE["kwh"]) * p["rate"] / 100 + p["admin_monthly"]
    return (use or USAGE["gj"]) * p["rate"] + p["admin_monthly"]


def ranked(fuel, variable=True, conditional=True):
    ps = [p for p in PLANS if p["fuel"] == fuel and (variable or p["type"] != "variable") and (conditional or not p["conditions"])]
    return sorted(ps, key=lambda p: (round(cost(p), 4), p["retailer"], p["plan"]))  # cost only


def bench(fuel, city="edmonton"):
    return DEF.get("rolr_" + city) if fuel == "electricity" else DEF.get("gas_default")


def rate_txt(p):
    if p["fuel"] == "electricity": return f"{p['rate']:.2f}¢/kWh"
    return f"${p['rate']:.3f}/GJ" if p["type"] == "default" else f"${p['rate']:.2f}/GJ"


def money(x):
    return ("-" if x < 0 else "") + f"${abs(x):,.2f}"


def partner_link(p):
    if not PARTNERS.get("enabled"): return ""
    q = PARTNERS.get("partners", {}).get(p.get("source_key"))
    if not q or not q.get("url"): return ""
    return f' <a class="tag" rel="sponsored nofollow" href="{e(q["url"])}">Partner link (we may be paid)</a>'


# ------------------------------------------------------------------ layout
NAV = [("/", "Best rates"), ("/electricity/", "Electricity"), ("/natural-gas/", "Natural gas"),
       ("/rate-of-last-resort-2027/", "RoLR 2027"), ("/how-switching-works/", "How switching works"), ("/about/", "About")]


def page(path, title, desc, body, active=None, extra_head="", scripts=""):
    canon = SITE_URL + BASE + path
    nav = "".join(f'<a href="{u(h)}"{" class=active" if h == active else ""}>{e(t)}</a>' for h, t in NAV)
    stale = [s for s in STATUS.get("sources", []) if not s.get("ok")]
    notice = (f"Rates checked daily from retailers' own pages. Last update {ftime(UPDATED)}."
              + (f" {len(stale)} source(s) couldn't be refreshed today; their last good data is shown with its check date." if stale else ""))
    return f"""<!doctype html><html lang="en-CA"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}"><meta property="og:type" content="website"><meta name="theme-color" content="#0f5132">
<link rel="alternate" type="application/rss+xml" title="{e(SITE)}: rate changes" href="{u('/feed.xml')}">
<link rel="stylesheet" href="{u('/assets/style.css')}">{extra_head}</head><body>
<header class="site"><div class="wrap"><a class="logo" href="{u('/')}"><span class="mark">⚡</span>{e(SITE)}</a>
<button class="menu-btn" onclick="document.querySelector('nav.main').classList.toggle('open')">Menu</button>
<nav class="main">{nav}</nav></div></header>
<div class="notice"><div class="wrap">{e(notice)}</div></div>
<main><div class="wrap">{body}</div></main>
<footer class="site"><div class="wrap">
<div class="disc"><b>Independent.</b> Not affiliated with any retailer, utility or government body. Rankings are by estimated cost only. Not financial advice. Always confirm the price and terms with the retailer before you sign. Official comparison: <a href="{UCA['tool']}">UCA Cost Comparison Tool</a> (310-4822).</div>
<nav><a href="{u('/about/')}">About &amp; disclaimer</a><a href="{u('/sources/')}">Sources &amp; data status</a><a href="{u('/newsletter/')}">Weekly email</a><a href="{u('/feed.xml')}">RSS</a><a href="{u('/data/plans.json')}">Data (JSON)</a></nav>
<p class="small">© {dt.date.today().year} {e(SITE)}. No ads, no trackers, no cookies.</p>
<p class="small">Also by us: <a href="{SITE_URL}/">Alberta PR Draw Tracker</a></p></div></footer>{scripts}</body></html>"""


def write(path, content):
    p = os.path.join(OUT, path.lstrip("/"))
    if path.endswith("/"): p = os.path.join(p, "index.html")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(content)


# ------------------------------------------------------------------ components
def plan_table(fuel, city="edmonton", limit=None, variable=True, conditional=True, show_src=True):
    b = bench(fuel, city)
    bc = cost(b) if b else None
    rows = ranked(fuel, variable, conditional)[:limit] if limit else ranked(fuel, variable, conditional)
    use = f"{USAGE['kwh']} kWh" if fuel == "electricity" else f"{USAGE['gj']} GJ"
    h = ['<div class="table-wrap"><table><thead><tr><th>#</th><th>Retailer and plan</th><th class="num">Rate</th><th class="sec">Term</th>'
         f'<th class="sec">Admin fee</th><th class="sec">Cancellation</th><th class="num">Est./month<br>@ {use}</th><th class="num">vs default</th>'
         + ('<th class="sec">Source</th>' if show_src else '') + '</tr></thead><tbody>']
    if b:
        h.append(f'<tr class="bench"><td>–</td><td><b>{e(b["retailer"])}</b> <span class="tag def">Default</span><br><span class="small muted">{e(b["plan"])}</span></td>'
                 f'<td class="num">{rate_txt(b)}</td><td class="sec small">{e(b["term_label"])}</td><td class="sec small">{e(b["admin_text"])}</td>'
                 f'<td class="sec small">{e(b["cancellation"])}</td><td class="num"><b>{money(bc)}</b></td><td class="num">–</td>'
                 + (f'<td class="sec src">' + "<br>".join(f'<a href="{e(s["url"])}">{e(s["name"].split(":")[0])}</a>' for s in b["sources"]) + f'<br>checked {fdate(b["last_checked"])}</td>' if show_src else '') + '</tr>')
    for i, p in enumerate(rows, 1):
        c = cost(p); d = bc - c if bc is not None else None
        tags = ('<span class="tag var">Variable</span>' if p["type"] == "variable" else "") + (f'<span class="tag cond" title="{e(p["conditions"])}">Conditions</span>' if p["conditions"] else "")
        notes = " ".join(x for x in [p.get("rate_note", ""), p.get("conditions", "")] if x)
        h.append(f'<tr><td class="rank">{i}</td><td><b>{e(p["retailer"])}</b> {tags}{partner_link(p)}<br><span class="small muted">{e(p["plan"])}</span>'
                 + (f'<details class="small muted"><summary>Notes</summary>{e(notes)}</details>' if notes else "") + '</td>'
                 f'<td class="num">{rate_txt(p)}</td><td class="sec small">{e(p["term_label"])}</td><td class="sec small">{e(p["admin_text"])}</td>'
                 f'<td class="sec small">{e(p["cancellation"])}</td><td class="num"><b>{money(c)}</b></td>'
                 f'<td class="num {"save" if d is not None and d >= 0 else "more"}">{"" if d is None else ("save " + money(d) if d >= 0 else money(-d) + " more")}</td>'
                 + (f'<td class="sec src"><a href="{e(p["source_url"])}">{e(p["retailer"])} page</a><br>checked {fdate(p["last_checked"])}</td>' if show_src else '') + '</tr>')
    h.append("</tbody></table></div>")
    return "".join(h)


def method_note(fuel):
    if fuel == "electricity":
        u_ = f"{USAGE['kwh']} kWh a month, the UCA's figure for a typical Alberta household"
    else:
        u_ = f"{USAGE['gj']} GJ a month, the UCA's typical-household figure (about 120 GJ a year; winter months are much higher)"
    return (f'<p class="small muted"><b>How we estimate:</b> {u_} (<a href="{USAGE_SRC}">UCA FAQ</a>). Est./month = usage × energy rate + the retailer\'s admin or site fee '
            '(daily fees × 30.4). Delivery (transmission and distribution), local access fees, riders and GST are set by your wire or pipe owner and are the same whichever retailer you pick, '
            'so they are left out and your real bill will be higher. Variable rates show the retailer\'s own stated recent average, and next month will differ. '
            '"Conditions" means the price needs something extra (a refundable deposit, age 60+, a bundle or new-customer status). Ranking is by estimated cost only.</p>')


def rolr_note():
    o = DEF.get("rolr_other", {})
    return (f'<div class="callout"><b>Heads-up: the default electricity rate changes on January 1, 2027.</b> The current Rate of Last Resort is fixed until Dec 31, {e(o.get("until","2026"))}. '
            'The next two-year rate (Jan 1, 2027 to Dec 31, 2028) must be filed with the Alberta Utilities Commission at least 30 days before Jan 1, and an adjustment normally can\'t exceed 10% of the current rate '
            f'(<a href="{UCA["decision"]}">AUC Decision 29204-D02-2025</a>, <a href="{UCA["rolr"]}">UCA</a>). We\'ll post the new rates here as soon as they\'re published. '
            f'<a href="{u("/rate-of-last-resort-2027/")}">What it means for you →</a></div>')


def newsletter_cta(small=False):
    return (f'<div class="card" id="newsletter"><h3>Get the weekly "best rates" email</h3><p class="small muted">One short email a week: the cheapest plans, what changed, and a heads-up before the default rate resets. Free. Unsubscribe anytime.</p>'
            f'<a class="btn" href="{u("/newsletter/#signup")}">Sign up for the weekly email</a></div>')


def calculator():
    data = {"plans": [{k: p[k] for k in ("retailer", "plan", "fuel", "type", "rate", "admin_monthly", "term_label", "conditions")} for p in PLANS],
            "defaults": {k: {kk: v[kk] for kk in ("retailer", "plan", "fuel", "rate", "admin_monthly") if kk in v} | ({"avg12": v["avg12"], "avg12_range": v["avg12_range"]} if "avg12" in v else {})
                         for k, v in DEF.items() if k in ("rolr_edmonton", "rolr_calgary", "gas_default")},
            "presets": PRESETS}
    btns = "".join(f'<button type="button" data-p="{k}"{" class=on" if k == "avg" else ""}>{e(v["label"])}</button>' for k, v in PRESETS.items())
    return f"""<div class="card" id="calculator"><h2 style="margin-top:0">What would I pay?</h2>
<p class="small muted">Find your usage on your bill (kWh for electricity, GJ for gas), or pick a home size. Everything runs in your browser. Nothing is sent anywhere.</p>
<form id="calc-form"><div class="presets" style="margin-bottom:12px">{btns}</div>
<div class="calc"><div><label for="city">Where do you live?</label><select id="city"><option value="edmonton">Edmonton (EPCOR area)</option><option value="calgary">Calgary (ENMAX area)</option></select></div>
<div><label for="kwh">Electricity, kWh/month</label><input id="kwh" type="number" min="0" step="10" value="{USAGE['kwh']}" inputmode="numeric"></div>
<div><label for="gj">Natural gas, GJ/month</label><input id="gj" type="number" min="0" step="0.5" value="{USAGE['gj']}" inputmode="decimal"></div></div>
<div class="checks" style="margin-top:12px"><label><input type="checkbox" id="incl-var"> Include variable (floating) plans (rates change monthly)</label><label><input type="checkbox" id="incl-cond" checked> Include plans with conditions (deposit, 60+, bundle)</label></div>
</form><div id="calc-out"></div>
<p class="small muted" style="margin-top:10px">Presets are rough guides, not official figures; your bill shows your real usage. Estimates cover energy + retailer fees only.</p></div>
<script type="application/json" id="rate-data">{json.dumps(data).replace("</", "<\\/")}</script>"""


def best_cards():
    def best(fuel, fixed_only=True):
        r = ranked(fuel, variable=not fixed_only, conditional=False)
        return r[0] if r else None
    cards = []
    for fuel, label in (("electricity", "Cheapest fixed electricity"), ("gas", "Cheapest fixed natural gas")):
        p = best(fuel)
        if not p: continue
        bE = bench(fuel, "edmonton"); d = cost(bE) - cost(p)
        use = f"{USAGE['kwh']} kWh" if fuel == "electricity" else f"{USAGE['gj']} GJ"
        cards.append(f'<div class="card stat"><div class="l">{label} (no conditions)</div><div class="n">{rate_txt(p)}</div>'
                     f'<div><b>{e(p["retailer"])}</b>, {e(p["plan"])}</div><div class="small muted">About {money(cost(p))}/month at {use} incl. {e(p["admin_text"])} admin · '
                     f'<span class="{"save" if d >= 0 else "more"}">{"saves " + money(d) + "/month vs the default" if d >= 0 else money(-d) + "/month more than the default this month"}</span></div>'
                     f'<div class="src"><a href="{e(p["source_url"])}">Source</a>, checked {fdate(p["last_checked"])}</div></div>')
    for k, label in (("rolr_edmonton", "Default electricity, Edmonton"), ("rolr_calgary", "Default electricity, Calgary"), ("gas_default", "Default natural gas (ATCO Gas area)")):
        b = DEF.get(k)
        if b:
            cards.append(f'<div class="card stat"><div class="l">{label}</div><div class="n">{rate_txt(b)}</div><div><b>{e(b["retailer"])}</b></div>'
                         f'<div class="small muted">{e(b["term_label"])} · admin {e(b["admin_text"])}</div><div class="src"><a href="{e(b["sources"][0]["url"])}">UCA</a>, checked {fdate(b["last_checked"])}</div></div>')
    return '<div class="grid g3">' + "".join(cards) + "</div>"


def recent_changes(n=8):
    ch = [c for c in reversed(CHANGES)][:n]
    if not ch:
        return f'<p class="muted small">No rate changes recorded yet. We started tracking on {fdate(UPDATED)}; changes will appear here and in the <a href="{u("/feed.xml")}">RSS feed</a>.</p>'
    li = []
    for c in ch:
        unit = "¢/kWh" if c["fuel"] == "electricity" else "$/GJ"
        if c["kind"] in ("rate", "default"): t = f'{c["old"]} → {c["new"]} {unit}'
        elif c["kind"] == "new": t = f'new plan at {c["new"]} {unit}'
        else: t = "no longer listed"
        li.append(f'<li><span class="meta">{fdate(c["date"])}</span> · <b>{e(c["retailer"])}</b> {e(c["plan"])} ({e(c["fuel"])}): {e(t)}</li>')
    return "<ul>" + "".join(li) + "</ul>"


# ------------------------------------------------------------------ pages
def build():
    _build()


def _build():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets")); os.makedirs(os.path.join(OUT, "data"))
    for f in ("style.css", "calc.js"): shutil.copy(os.path.join(ROOT, "src", f), os.path.join(OUT, "assets", f))
    calc_js = f'<script src="{u("/assets/calc.js")}" defer></script>'
    retailers = sorted({p["retailer"] for p in PLANS})
    n_e = sum(p["fuel"] == "electricity" for p in PLANS); n_g = len(PLANS) - n_e

    home = f"""<h1>Cheapest electricity and natural gas rates in Alberta, checked daily</h1>
<p class="lead">{len(PLANS)} plans from {len(retailers)} retailers in Edmonton and Calgary, compared with the default rates. Ranked by estimated monthly cost, fees included. Nobody pays to rank higher.</p>
{best_cards()}<div style="margin-top:18px">{rolr_note()}</div>
{calculator()}
<h2>Top fixed electricity plans right now <span class="small muted">(Edmonton default shown)</span></h2>{plan_table("electricity", limit=8, variable=False, show_src=False)}
<p><a href="{u('/electricity/')}">See all {n_e} electricity plans →</a></p>
<h2>Top fixed natural gas plans right now</h2>{plan_table("gas", limit=6, variable=False, show_src=False)}
<p><a href="{u('/natural-gas/')}">See all {n_g} natural gas plans →</a></p>
{method_note("electricity")}
<h2>Recent rate changes</h2>{recent_changes()}
<div class="grid g2" style="margin-top:20px">{newsletter_cta()}<div class="card"><h3>Is switching a hassle?</h3><p class="small">Leaving the default rate has no penalty. You sign up with the new retailer and it handles the switch; your power and gas never go off. Every competitive contract has a 10-day cooling-off period.</p><a class="btn ghost" href="{u('/how-switching-works/')}">How switching works</a></div></div>"""
    write("/", page("/", "Cheapest Electricity & Gas Rates in Alberta (Edmonton, Calgary) | Updated Daily",
                    f"Compare {len(PLANS)} Alberta electricity and natural gas plans from {len(retailers)} retailers with fees included, against the Rate of Last Resort. Calculator, daily updates, no ads.",
                    home, "/", scripts=calc_js))

    for fuel, path, title, h1, desc in (
        ("electricity", "/electricity/", "Cheapest Electricity Rates in Alberta: Fixed & Variable Plans Compared",
         "Alberta electricity rates: every plan we track", "Daily-updated table of Alberta residential electricity plans (fixed and variable) with admin fees, cancellation terms and estimated monthly cost vs the Rate of Last Resort."),
        ("gas", "/natural-gas/", "Cheapest Natural Gas Rates in Alberta: Fixed & Variable Plans Compared",
         "Alberta natural gas rates: every plan we track", "Daily-updated table of Alberta residential natural gas plans with admin fees and estimated monthly cost vs the default gas rate (Default Rate Tariff).")):
        extra = ""
        if fuel == "electricity":
            extra = (f'<h2>Calgary: compared with the ENMAX default</h2>{plan_table("electricity", city="calgary", limit=10, show_src=False)}'
                     f'<p class="small muted">Plans from competitive retailers are generally offered across both cities; check availability at your address. FortisAlberta-area default (EPCOR): {DEF.get("rolr_other",{}).get("fortis_epcor","?")}¢/kWh; ATCO Electric-area default (Direct Energy Regulated Services): {DEF.get("rolr_other",{}).get("ders_atco_electric","?")}¢/kWh (<a href="{UCA["defaults"]}">UCA</a>).</p>')
            lead = "Ranked by estimated monthly cost at a typical 600 kWh, including the retailer's admin fee. The yellow row is the default rate (Rate of Last Resort) in Edmonton."
        else:
            g = DEF.get("gas_default", {})
            lead = "Ranked by estimated monthly cost at a typical 10 GJ, including the retailer's admin fee. The yellow row is this month's default gas rate in the ATCO Gas area (Edmonton and Calgary)."
            if g.get("avg12"):
                extra = (f'<div class="callout" style="margin-top:14px"><b>Why fixed gas can look "more expensive" right now:</b> the default gas rate resets every month. It is ${g["rate"]:.3f}/GJ for {e(g.get("month",""))}, '
                         f'but averaged ${g["avg12"]:.3f}/GJ over {e(g["avg12_range"])}, with highs like ${max(r["ders"] for r in g["history"]):.3f} in winter (<a href="{UCA["defaults"]}">UCA default rates</a>). '
                         'A fixed rate trades a possibly higher average for no winter surprises. Compare using your own yearly usage in the <a href="' + u("/#calculator") + '">calculator</a>.</div>')
        body = (f'<h1>{h1}</h1><p class="lead">{lead}</p>{rolr_note() if fuel=="electricity" else ""}<div style="margin-top:14px"></div>'
                f'{plan_table(fuel)}{method_note(fuel)}{extra}<p><a class="btn" href="{u("/#calculator")}">Use your own usage in the calculator</a></p>{newsletter_cta()}')
        write(path, page(path, title, desc, body, path))

    for city, name, prov in (("edmonton", "Edmonton", "EPCOR"), ("calgary", "Calgary", "ENMAX")):
        b = DEF.get("rolr_" + city)
        top = ranked("electricity", variable=False, conditional=False)[0]
        body = (f'<h1>Cheapest electricity rates in {name}</h1><p class="lead">If you never picked a plan, you are on the default Rate of Last Resort from {prov}: '
                f'<b>{rate_txt(b)}</b> plus {e(b["admin_text"])} admin. The cheapest no-conditions fixed plan we track is <b>{e(top["retailer"])} {e(top["plan"])} at {rate_txt(top)}</b>, about '
                f'<b class="save">{money(cost(b) - cost(top))}/month less</b> at 600 kWh ({money((cost(b) - cost(top)) * 12)}/year).</p>{rolr_note()}<h2>All {name} electricity plans vs the {prov} default</h2>'
                f'{plan_table("electricity", city=city)}{method_note("electricity")}<h2>Natural gas in {name}</h2><p>{name} is in the ATCO Gas service area, so the default gas rate is Direct Energy Regulated Services\' Default Rate Tariff. '
                f'<a href="{u("/natural-gas/")}">Compare gas plans →</a></p><p><a class="btn" href="{u("/#calculator")}">Calculate with your usage</a></p>{newsletter_cta()}')
        write(f"/{city}/", page(f"/{city}/", f"Cheapest Electricity Rates {name} (Updated {fdate(UPDATED)}) | vs {prov} Rate of Last Resort",
                                 f"Cheapest electricity rates in {name}, Alberta, checked daily from retailers' own pages, with admin fees, compared with the {prov} Rate of Last Resort.", body, None))

    o = DEF.get("rolr_other", {}); be, bc = DEF.get("rolr_edmonton"), DEF.get("rolr_calgary")
    rows = "".join(f'<tr><td>{n}</td><td class="num">{r:.2f}¢</td><td class="num">{r*0.9:.2f}¢ – {r*1.1:.2f}¢</td></tr>' for n, r in
                   (("EPCOR (Edmonton)", be["rate"]), ("EPCOR (FortisAlberta areas)", o.get("fortis_epcor", be["rate"])), ("ENMAX (Calgary)", bc["rate"]), ("Direct Energy Regulated Services (ATCO Electric areas)", o.get("ders_atco_electric", 0))))
    body = f"""<h1>Rate of Last Resort 2027: what changes on January 1</h1>
<p class="lead">Alberta's default electricity rate is fixed for two years at a time. The first term ends December 31, {e(o.get('until','2026'))}. A new rate takes effect January 1, 2027 and runs to December 31, 2028.</p>
<div class="card"><h3>What we know (official sources)</h3><ul>
<li>The rates for the second two-year term (Jan 1, 2027 to Dec 31, 2028) must be filed with the Alberta Utilities Commission <b>at least 30 days before January 1, 2027</b> (<a href="{UCA['decision']}">AUC Decision 29204-D02-2025</a>, para. 8).</li>
<li>Any proposed adjustment <b>cannot normally exceed 10%</b> of the existing rate (<a href="{UCA['rolr']}">UCA</a>).</li>
<li>About 26% of residential electricity consumers are on the RoLR, and you can leave it <b>at any point without penalty</b> (<a href="{UCA['rolr']}">UCA</a>).</li></ul></div>
<h2>Current RoLR and the possible 2027 range (±10%)</h2><div class="table-wrap"><table><thead><tr><th>Provider (area)</th><th class="num">2025–2026 rate</th><th class="num">2027–2028 possible range</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="small muted">The range is simple arithmetic (current rate ± 10%), not a forecast. Current rates: <a href="{UCA['defaults']}">UCA default rates</a>. We'll replace this with the approved 2027 rates the day they're published.</p>
<h2>Should you wait?</h2><p>You don't have to. Leaving the default has no penalty, and most competitive plans we track are already well below 12¢/kWh. At 600 kWh/month the cheapest no-conditions fixed plan today saves about <b class="save">{money(cost(be) - cost(ranked('electricity', False, False)[0]))}/month</b> vs the Edmonton default.</p>
{plan_table('electricity', limit=5, show_src=False)}<p><a href="{u('/electricity/')}">All electricity plans →</a></p>{newsletter_cta()}"""
    write("/rate-of-last-resort-2027/", page("/rate-of-last-resort-2027/", "Rate of Last Resort 2027 Alberta: New Default Electricity Rate from January 1",
                                             "What happens to Alberta's Rate of Last Resort on January 1, 2027: timing, the 10% cap, current EPCOR/ENMAX/Direct Energy rates, and cheaper plans.", body, "/rate-of-last-resort-2027/"))

    body = f"""<h1>How switching works in Alberta</h1><p class="lead">Short version: it's one sign-up, there's no penalty to leave the default rate, and your lights and heat stay on the whole time.</p>
<div class="grid g2">
<div class="card"><h3>1. Leaving the default rate is free</h3><p>You can leave the Rate of Last Resort (electricity) at any point without penalty (<a href="{UCA['rolr']}">UCA</a>). The default gas rate has no contract either. Default retailers can't charge you to leave.</p></div>
<div class="card"><h3>2. Sign up with the new retailer</h3><p>The new retailer handles the switch. You don't need to cancel the old one yourself (<a href="{UCA['switch']}">UCA: how to switch</a>). Have a recent bill handy; your site ID is on it.</p></div>
<div class="card"><h3>3. 10-day cooling-off period</h3><p>Every competitive retailer gives you <b>ten calendar days</b> to cancel a new contract for any reason without penalty (<a href="{UCA['switch']}">UCA</a>).</p></div>
<div class="card"><h3>4. It takes 10 to 90 days</h3><p>A switch can take <b>10 to 90 calendar days</b> to complete. You pay your old retailer until the switch date. The same wires and pipes deliver your energy, so service never stops (<a href="{UCA['switch']}">UCA</a>).</p></div>
<div class="card"><h3>5. Check for cancellation fees</h3><p>If you're on a competitive contract now, check whether it has an exit fee before you switch. Competitive retailers <i>may</i> charge exit fees for leaving early (<a href="{UCA['choose']}">UCA: how to choose a retailer</a>). Many retailers in our table say they charge none; each row shows what the retailer states.</p></div>
<div class="card"><h3>6. Deposits and conditions</h3><p>Some of the lowest prices need a refundable deposit (sometimes called a prudential), a bundle, or new-customer status. Those rows are tagged "Conditions". Competitive retailers may also require a deposit (<a href="{UCA['choose']}">UCA</a>).</p></div></div>
<h2>What stays the same</h2><p>Delivery charges (transmission and distribution), local access fees and riders are set by your wire or pipe owner, not your retailer. They're the same whoever you buy energy from. That's why our estimates only compare the energy rate and the retailer's own admin fee.</p>
<h2>Questions or a problem with a retailer?</h2><p>The Utilities Consumer Advocate is free and independent: call 310-4822 (in Alberta) or use their <a href="{UCA['contact']}">contact form</a>. Their official <a href="{UCA['tool']}">Cost Comparison Tool</a> lists every retailer.</p>{newsletter_cta()}"""
    write("/how-switching-works/", page("/how-switching-works/", "How to Switch Electricity or Gas Retailers in Alberta (No-Fee Exit from RoLR)",
                                        "Switching energy retailers in Alberta: no penalty to leave the Rate of Last Resort, 10-day cooling-off period, 10–90 days to switch, cancellation fee checks.", body, "/how-switching-works/"))

    fails = [s for s in STATUS.get("sources", []) if not s.get("ok")]
    np_ = "".join(f'<li><b>{e(n["retailer"])}</b>: {e(n["reason"])} (<a href="{e(n["url"])}">page</a>)</li>' for n in STATUS.get("not_published", []))
    body = f"""<h1>About this tracker, and our disclaimer</h1>
<div class="card"><h3>Independent</h3><p>{e(SITE)} is an independent website run from Edmonton. It is <b>not affiliated with any energy retailer, utility, the Utilities Consumer Advocate, the Alberta Utilities Commission or the Government of Alberta</b>.</p></div>
<div class="card" style="margin-top:12px" id="disclaimer"><h3>Disclaimer</h3><ul>
<li><b>Rankings are by estimated cost only.</b> No retailer can pay to rank higher. If we ever add partner links, they'll be clearly labelled, and they'll never change the order.</li>
<li><b>Not financial advice.</b> Estimates use typical usage and exclude delivery charges, local access fees, riders and GST. Your bill will differ.</li>
<li><b>Prices can change at any time.</b> We copy each price from the retailer's own public page (or official regulator and provider pages for default rates) and show the date we last checked it. Always confirm the price and contract terms with the retailer before signing.</li>
<li>If a retailer's page can't be read on a given day, we keep showing the last price we confirmed, with its check date, rather than guessing. If a retailer doesn't publish a specific price, we leave it out.</li>
<li>We don't use or copy the UCA Cost Comparison Tool's data. We link to it because it's the official, complete list.</li></ul></div>
<h2>Retailers we track</h2><p>{", ".join(e(r) for r in retailers)}, plus the default providers (EPCOR, ENMAX, Direct Energy Regulated Services).</p>
<h2>Retailers we checked but can't list yet</h2><ul>{np_}</ul>
<h2>Privacy</h2><p>No ads, no analytics, no cookies, no trackers. The calculator runs entirely in your browser.</p>
<h2>Corrections</h2><p>See a wrong price? Each row links to the page we copied it from. Spot an error and we'll fix it on the next daily update.</p>"""
    write("/about/", page("/about/", f"About & Disclaimer | {SITE}", "Independent Alberta energy rate tracker. Not affiliated with any retailer or government. Rankings by cost only. Not financial advice.", body, "/about/"))
    write("/disclaimer/", f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={u("/about/#disclaimer")}"><link rel="canonical" href="{SITE_URL}{BASE}/about/"><a href="{u("/about/#disclaimer")}">Disclaimer</a>')

    srows = "".join(f'<tr><td>{e(s["retailer"])}</td><td>{"✅ updated" if s.get("ok") else "⚠️ kept last good data" if s.get("kept") else "❌ no data"}</td><td class="small">{e(s.get("error",""))}</td><td class="src"><a href="{e(s["url"])}">{e(s["url"][:60])}</a></td></tr>' for s in STATUS.get("sources", []))
    body = f'<h1>Sources and data status</h1><p class="lead">Last run: {ftime(STATUS.get("checked_at", UPDATED))}. Every price on this site comes from one of these pages.</p><div class="table-wrap"><table><thead><tr><th>Source</th><th>Today</th><th>Note</th><th>URL</th></tr></thead><tbody>{srows}</tbody></table></div><p class="small muted">Typical usage figure: <a href="{USAGE_SRC}">UCA FAQ</a>. Raw data: <a href="{u("/data/plans.json")}">plans.json</a>, <a href="{u("/data/defaults.json")}">defaults.json</a>.</p>'
    write("/sources/", page("/sources/", f"Sources & Data Status | {SITE}", "Where every Alberta electricity and gas price on this site comes from, and today's update status.", body, None))

    body = f"""<h1>The weekly "best rates" email</h1><p class="lead">Every week: the cheapest electricity and gas plans in Edmonton and Calgary, what changed, and an early heads-up when the default rate resets on January 1, 2027.</p>
<div class="card" id="signup"><h3>Sign up</h3><p class="muted">Signup opens soon. We're setting up the email form now.</p>
<!-- BEEHIIV_EMBED: paste the beehiiv subscribe form embed here (free plan). Keep it opt-in only (CASL). -->
<p class="small muted">Free. One email a week. Unsubscribe anytime. We'll never sell or share your email.</p></div>
<h2>What's in it</h2><ul><li>Best fixed and variable rates this week, with fees included</li><li>Price changes since last week</li><li>The default rate and what it means for you</li><li>Reminders when it's worth re-checking your plan</li></ul>"""
    write("/newsletter/", page("/newsletter/", "Weekly Alberta Power & Gas Rates Email", "A free weekly email with the cheapest Alberta electricity and natural gas rates and changes.", body, None))

    write("/404.html", page("/404.html", f"Page not found | {SITE}", "Page not found.", f'<h1>Page not found</h1><p><a href="{u("/")}">Go to the best rates →</a></p>', None))

    # data, feeds, sitemap
    shutil.copy(os.path.join(ROOT, "data", "plans.json"), os.path.join(OUT, "data", "plans.json"))
    json.dump(DEF, open(os.path.join(OUT, "data", "defaults.json"), "w"), indent=1, ensure_ascii=False)
    urls = ["/", "/electricity/", "/natural-gas/", "/edmonton/", "/calgary/", "/rate-of-last-resort-2027/", "/how-switching-works/", "/about/", "/sources/", "/newsletter/"]
    today = dt.date.fromisoformat(UPDATED[:10]).isoformat()
    open(os.path.join(OUT, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{SITE_URL}{BASE}{p}</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq></url>\n" for p in urls) + "</urlset>\n")
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}{BASE}/sitemap.xml\n")
    items = []
    for c in list(reversed(CHANGES))[:50]:
        unit = "¢/kWh" if c["fuel"] == "electricity" else "$/GJ"
        t = {"rate": f'{c.get("old")} → {c.get("new")} {unit}', "default": f'default rate {c.get("old")} → {c.get("new")} {unit}', "new": f'new plan at {c.get("new")} {unit}', "removed": "no longer listed"}[c["kind"]]
        title = f'{c["retailer"]} {c["plan"]} ({c["fuel"]}): {t}'
        link = f'{SITE_URL}{BASE}/{"electricity" if c["fuel"]=="electricity" else "natural-gas"}/'
        pub = format_datetime(dt.datetime.fromisoformat(c["date"]).replace(hour=7, tzinfo=TZ))
        items.append(f"<item><title>{e(title)}</title><link>{link}</link><guid isPermaLink=\"false\">{e(c['date'] + ':' + c['id'] + ':' + c['kind'])}</guid><pubDate>{pub}</pubDate><description>{e(title)}</description></item>")
    if not items:
        pub = format_datetime(dt.datetime.fromisoformat(UPDATED))
        items.append(f"<item><title>Tracker launched: {len(PLANS)} plans from {len(retailers)} retailers</title><link>{SITE_URL}{BASE}/</link><guid isPermaLink=\"false\">launch-{today}</guid><pubDate>{pub}</pubDate><description>Rate changes will appear in this feed.</description></item>")
    open(os.path.join(OUT, "feed.xml"), "w").write(f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{e(SITE)}: rate changes</title><link>{SITE_URL}{BASE}/</link>'
        f'<description>Changes to Alberta electricity and natural gas plan prices, checked daily.</description><language>en-ca</language><lastBuildDate>{format_datetime(dt.datetime.fromisoformat(UPDATED))}</lastBuildDate>{"".join(items)}</channel></rss>\n')
    print(f"Built {len(urls)} pages into public/ (base {SITE_URL}{BASE}/), {len(PLANS)} plans, {len(retailers)} retailers")


if __name__ == "__main__":
    build()
