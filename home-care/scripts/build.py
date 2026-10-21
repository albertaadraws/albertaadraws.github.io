#!/usr/bin/env python3
"""Build the Edmonton Home Care Finder into public/ from data/agencies.json.

  SITE_URL=https://albertaadraws.github.io BASE_PATH=/home-care python3 scripts/build.py

Every internal link is prefixed with BASE_PATH so the site works under the /home-care/ subpath.
Listings are ALWAYS sorted alphabetically by name. Nothing in the data or config can change the order:
there is no rank, score, featured or boost field. Entries with "publish": false are skipped.
"""
import datetime as dt, html, json, os, re, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public")
SITE_URL = os.environ.get("SITE_URL", "https://albertaadraws.github.io").rstrip("/")
BASE = os.environ.get("BASE_PATH", "/home-care").rstrip("/")
SITE = "Edmonton Home Care Finder"
e = lambda s: html.escape(str(s if s is not None else ""), quote=True)
u = lambda p: BASE + p

DATA = json.load(open(os.path.join(ROOT, "data", "agencies.json")))
CFG = json.load(open(os.path.join(ROOT, "config", "site.json")))
OWNER, AGENCY, EMAIL = CFG["owner_name"], CFG["owner_agency"], CFG["contact_email"]
sort_key = lambda a: re.sub(r"[^a-z0-9 ]", "", a["name"].lower())
AG = sorted([a for a in DATA["agencies"] if a.get("publish")], key=sort_key)  # alphabetical only
UNPUBLISHED = [a for a in DATA["agencies"] if not a.get("publish")]
UPDATED = DATA["updated"]

SRC = {
    "brochure": ("Client Directed Home Care Invoicing brochure (Assisted Living Alberta, Sept 2026)", "https://www.albertahealthservices.ca/assets/info/seniors/if-sen-gen-cdhci-brochure.pdf"),
    "benefact": ("Alberta Blue Cross Provider Benefact: CDHCI 2026/2027 rate change (Sept 2026)", "https://www.ab.bluecross.ca/pdfs/the-client-directed-home-care-invoicing-program.pdf"),
    "guide": ("Alberta Blue Cross CDHCI provider program guide", "https://www.ab.bluecross.ca/pdfs/CDHCI-provider-program-guide.pdf"),
    "abc": ("Alberta Blue Cross: Client Directed Home Care program and service zone map", "https://www.ab.bluecross.ca/resources/government-programs/client-directed-home-care.php"),
    "smc": ("Self-Managed Care brochure (Assisted Living Alberta, Sept 2026)", "https://albertahealthservices.ca/assets/info/seniors/if-sen-self-managed-care-brochure.pdf"),
}
cite = lambda k: f'<a class="cite" href="{SRC[k][1]}">[source]</a>'
SERVICES = ["personal care", "companionship", "respite", "dementia", "nursing", "palliative / end-of-life", "overnight / 24-hour", "housekeeping & meals", "disability support"]
FUNDING = {"CDHCI": "Client Directed Home Care (CDHCI)", "Self-Managed Care": "Self-Managed Care", "FSCD": "FSCD (children with disabilities)", "WCB": "WCB"}
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
NAV = [("/", "Find home care"), ("/client-directed-home-care-edmonton/", "Funded home care guide"), ("/get-listed/", "Agencies: get listed"), ("/newsletter/", "Email"), ("/about/", "About")]


def disclosure_text():
    where = "listed here" if any(a.get("owner") for a in AG) else "in Edmonton that competes with the agencies listed here"
    return (f'<strong>Ownership disclosure:</strong> This site is run by {e(OWNER)}, who owns a home care agency {where} '
         f'(<strong>{e(AGENCY)}</strong>). Listings are sorted alphabetically and are <strong>not ranked</strong>. No agency pays to be listed or to appear higher.')


def disclosure(full=False):
    s = disclosure_text()
    if full:
        s += ' <a href="' + u('/about/#ownership') + '">Read more</a>.'
    return f'<div class="own" role="note"><div class="wrap">{s}</div></div>'


def page(path, title, desc, body, active=None, scripts=""):
    canon = SITE_URL + BASE + path
    nav = "".join(f'<a href="{u(h)}"{" class=active" if h == active else ""}>{e(t)}</a>' for h, t in NAV)
    return f"""<!doctype html><html lang="en-CA"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}"><meta property="og:type" content="website"><meta name="theme-color" content="#1d4e89">
<link rel="stylesheet" href="{u('/assets/style.css')}"></head><body>
<header class="site"><div class="wrap"><a class="logo" href="{u('/')}"><span class="mark">⌂</span>{e(SITE)}</a>
<button class="menu-btn" onclick="document.querySelector('nav.main').classList.toggle('open')">Menu</button>
<nav class="main">{nav}</nav></div></header>
{disclosure(True)}
<main><div class="wrap">{body}</div></main>
<footer class="site"><div class="wrap">
<div class="disc">{disclosure_text()}<br>Information comes from each agency's own website and was last checked on {e(fdate(UPDATED))}. It may be out of date. Always confirm services, prices, areas and funding directly with the agency. Not medical, legal or financial advice. Not affiliated with Alberta Health Services, Assisted Living Alberta or Alberta Blue Cross.</div>
<nav><a href="{u('/about/')}">About &amp; disclaimer</a><a href="{u('/client-directed-home-care-edmonton/')}">Funded home care guide</a><a href="{u('/get-listed/')}">Fix a listing</a><a href="{u('/newsletter/')}">Email updates</a><a href="{u('/data/agencies.json')}">Data (JSON)</a></nav>
<p class="small">© {dt.date.today().year} {e(SITE)}. No ads, no trackers, no cookies.</p>
<p class="small">Also by us: <a href="{SITE_URL}/">Alberta PR Draw Tracker</a> · <a href="{SITE_URL}/alberta-power/">Alberta Power &amp; Gas Rate Tracker</a></p></div></footer>{scripts}</body></html>"""


def fdate(iso):
    return dt.date.fromisoformat(iso[:10]).strftime("%b %-d, %Y")


def write(path, content):
    p = os.path.join(OUT, path.strip("/"), "index.html") if path.endswith("/") else os.path.join(OUT, path.strip("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(content)


def card(a):
    areas = ", ".join(a["areas"]) or "Not stated"
    svc = "".join(f'<span class="pill">{e(s)}</span>' for s in a["services"]) or '<span class="muted small">Not stated</span>'
    fund = "".join(f'<span class="pill fund">{e(FUNDING.get(f, f))}</span>' for f in a["funding"]) or '<span class="muted small">Not stated on its website</span>'
    langs = ", ".join(a["languages"]) or "Not stated"
    tel = re.sub(r"[^0-9+]", "", a["phone"])
    host = re.sub(r"^https?://(www\.)?", "", a["website"]).split("/")[0]
    srcs = " · ".join(f'<a href="{e(s)}">{e(re.sub(r"^https?://(www\\.)?", "", s)[:60])}</a>' for s in a["sources"])
    owner = '<span class="tag own-tag">Owned by this site\'s owner</span>' if a.get("owner") else ""
    data = (f'data-areas="{e("|".join(slug(x) for x in a["areas"]))}" data-services="{e("|".join(slug(x) for x in a["services"]))}" '
            f'data-langs="{e("|".join(slug(x) for x in a["languages"]))}" data-funding="{e("|".join(slug(x) for x in a["funding"]))}"')
    return f"""<article class="card agency" {data}><h3>{e(a['name'])} {owner}</h3>
<p class="contact"><a href="tel:{e(tel)}">{e(a['phone'])}</a> · <a href="{e(a['website'])}" rel="nofollow">{e(host)}</a></p>
<dl><dt>Areas</dt><dd>{e(areas)}</dd><dt>Services</dt><dd>{svc}</dd><dt>Funding accepted</dt><dd>{fund}{f'<div class="small muted">{e(a["funding_note"])}</div>' if a.get("funding_note") else ""}</dd>
<dt>Languages</dt><dd>{e(langs)}</dd></dl>{f'<p class="small">{e(a["notes"])}</p>' if a.get("notes") else ""}
<p class="src">Source: {srcs} · checked {e(fdate(a['checked']))}</p></article>"""


def opts(values, label):
    return f'<option value="">{e(label)}</option>' + "".join(f'<option value="{e(slug(v))}">{e(v)}</option>' for v in values)


def newsletter_cta():
    return (f'<div class="card" id="newsletter"><h3>Get the monthly family caregiver email</h3><p class="small muted">Plain-language updates on funded home care in Edmonton: rate changes, program rules and new agencies. Free. Unsubscribe anytime.</p>'
            f'<a class="btn" href="{u("/newsletter/#signup")}">Sign up</a></div>')


# id="reset" on a form control shadows HTMLFormElement.reset, so the click handler
# calls the prototype method. Otherwise Reset throws and the filters stay applied.
FILTER_JS = """<script>
(function(){var f=document.getElementById('filters');if(!f)return;var cards=[].slice.call(document.querySelectorAll('.agency'));var c=document.getElementById('count');
function run(){var v={};['areas','services','langs','funding'].forEach(function(k){v[k]=f.elements[k].value});var n=0;
cards.forEach(function(el){var ok=Object.keys(v).every(function(k){return !v[k]||el.getAttribute('data-'+k).split('|').indexOf(v[k])>-1});el.hidden=!ok;if(ok)n++});
c.textContent=n+' of '+cards.length+' agencies shown';document.getElementById('none').hidden=n>0}
f.addEventListener('change',run);document.getElementById('reset').addEventListener('click',function(){HTMLFormElement.prototype.reset.call(f);run()});run()})();
</script>"""


def build():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets")); os.makedirs(os.path.join(OUT, "data"))
    shutil.copy(os.path.join(ROOT, "src", "style.css"), os.path.join(OUT, "assets", "style.css"))
    core = ["Edmonton", "St. Albert", "Sherwood Park", "Spruce Grove", "Stony Plain", "Leduc", "Beaumont", "Fort Saskatchewan", "Devon", "Morinville"]
    areas = [x for x in core if any(x in a["areas"] for a in AG)] + sorted({x for a in AG for x in a["areas"]} - set(core))
    langs = sorted({x for a in AG for x in a["languages"]})
    funds = [f for f in FUNDING if any(f in a["funding"] for a in AG)]
    n_cd = sum("CDHCI" in a["funding"] for a in AG)

    body = f"""<section class="hero"><div><h1>Home care in Edmonton: compare {len(AG)} home care agencies</h1>
<p class="lead">A free list of Edmonton-area home care agencies. Filter by area, service, language and whether they say they accept government-funded <a href="{u('/client-directed-home-care-edmonton/')}">client directed home care (CDHCI)</a>. Every detail links to the agency's own website.</p>
<p class="meta">Sorted A to Z. Not ranked. Last checked {e(fdate(UPDATED))}.</p></div>
<div class="card callout"><h3>Need funded home care?</h3><p class="small">Call <b>811</b> or Edmonton Home and Community Care intake at <b><a href="tel:17804961300">780-496-1300</a></b> to ask for an assessment. {cite('brochure')}</p><p class="small">From Oct 1, 2026, CDHCI pays registered agencies up to <b>$35.03/hour</b> for your authorized hours. {cite('benefact')}</p><a class="btn ghost" href="{u('/client-directed-home-care-edmonton/')}">Read the step-by-step guide</a></div></section>
<h2 id="agencies">Home care agencies in Edmonton</h2>
<form id="filters" class="filters" onsubmit="return false">
<label>Area<select name="areas">{opts(areas, 'Any area')}</select></label>
<label>Service<select name="services">{opts(SERVICES, 'Any service')}</select></label>
<label>Language<select name="langs">{opts(langs, 'Any language')}</select></label>
<label>Funding accepted<select name="funding">{opts(funds, 'Any funding')}</select></label>
<button type="button" id="reset" class="btn ghost">Reset</button></form>
<p class="meta" id="count">{len(AG)} agencies</p>
<p class="small muted">"Not stated" means we couldn't find it on the agency's website, not that they don't offer it. {n_cd} of {len(AG)} agencies say on their own website that they take CDHCI. To check any agency is registered, use the <a href="{SRC['abc'][1]}">Alberta Blue Cross service zone map</a> or call 1-800-394-1965. {cite('brochure')}</p>
<div class="grid g2" id="list">{''.join(card(a) for a in AG)}</div>
<p id="none" class="callout" hidden>No agency matches all of those filters. Try removing one.</p>
<div class="grid g2" style="margin-top:22px">{newsletter_cta()}<div class="card"><h3>Run an agency?</h3><p class="small">Listings are free for now. Add your agency or fix your details.</p><a class="btn ghost" href="{u('/get-listed/')}">Get listed / fix your listing</a></div></div>"""
    write("/", page("/", "Home Care Edmonton | Compare Home Care Agencies in Edmonton (Free, Not Ranked)",
                    f"Compare {len(AG)} home care agencies in Edmonton by area, service, language and client directed home care (CDHCI) funding. Free, alphabetical, no ads.", body, "/", FILTER_JS))

    body = f"""<article class="prose"><h1>Client directed home care in Edmonton: how to get government-funded home care</h1>
<p class="lead">A plain-language guide for families. Checked {e(fdate(UPDATED))}. Programs change, so confirm details with your case manager.</p>
<div class="callout"><b>Short version:</b> call 811 or 780-496-1300 for an assessment. If a case manager approves you for client directed home care (CDHCI), you choose any agency registered with Alberta Blue Cross, and it bills Alberta Blue Cross directly, up to $35.03 an hour for your authorized hours. {cite('brochure')} {cite('benefact')}</div>
<h2>1. Ask for a home care assessment</h2>
<p>Publicly funded home care in Alberta is now arranged through <b>Assisted Living Alberta (ALA) Home and Community Care</b>. You, a family member, a friend or a health professional can call on your behalf. {cite('brochure')}</p>
<ul><li><b>Edmonton:</b> 1-780-496-1300</li><li><b>Anywhere in Alberta:</b> 811 (Health Link)</li><li>Email: continuingcare@assistedlivingalberta.ca</li></ul>
<p>A case manager visits, assesses your needs and decides which services and how many hours a month you're authorized for.</p>
<h2>2. Ask about client directed home care (CDHCI)</h2>
<p>With CDHCI, instead of being assigned a care team, <b>you choose an agency</b> registered with Alberta Blue Cross. The agency submits claims to Alberta Blue Cross, which administers the program. {cite('brochure')}</p>
<p>You may be eligible if you have a valid Alberta Health Care number, live in a community setting, have been assessed as needing home care, your case manager decides CDHCI suits your needs, and you (or a person you name as your "CDHCI manager") can direct and monitor your care. <b>You don't need an Alberta Blue Cross insurance plan.</b> {cite('brochure')}</p>
<h3>What it can cover</h3>
<ul><li><b>Personal care:</b> hygiene, dressing, toileting, moving and transfers, home exercises, nutrition, medication assistance and respiratory care.</li>
<li><b>Homemaking:</b> only tasks tied to keeping you healthy at home, and not as a stand-alone service.</li>
<li><b>Respite:</b> a break for family caregivers when you can't safely be left alone, as decided by your case manager.</li></ul>
<p>{cite('brochure')} If you need professional health services (like nursing), those are provided by ALA/AHS or a contracted provider, not through CDHCI. {cite('guide')}</p>
<h2>3. The funded rate: $35.03 an hour from Oct 1, 2026</h2>
<p>From <b>October 1, 2026</b>, Alberta Blue Cross reimburses CDHCI claims up to your authorized monthly hours at <b>$35.03 an hour</b>. The same rate applies on weekends and statutory holidays. {cite('benefact')}</p>
<p><b>What you might pay yourself:</b> any hours above your authorized hours, and the difference if your agency charges more than the maximum hourly rate. Some agencies have a minimum visit length (for example 2 to 3 hours), and extra time to meet a minimum isn't funded. {cite('brochure')} {cite('guide')} Ask every agency: "What's your hourly rate, and will I pay anything on top of the funded rate?"</p>
<h2>4. Sign the paperwork</h2>
<ul><li>A <b>Consent to Disclose Information</b> form for Alberta Blue Cross.</li><li>The <b>CDHCI Letter of Agreement</b>.</li><li>You'll then get an <b>approval letter</b> from Alberta Blue Cross with your authorized hours, start date and customer number.</li></ul><p>{cite('brochure')}</p>
<h2>5. Choose an agency</h2>
<p>ALA doesn't evaluate or guarantee any agency, so it's up to you to research them. {cite('brochure')} Start with the <a href="{SRC['abc'][1]}">official Alberta Blue Cross service zone map</a> (or call 1-800-394-1965), then compare agencies on <a href="{u('/')}">our list</a>.</p>
<p>Questions worth asking: Do you serve my address? What's your minimum visit? Can I keep the same caregiver? Do your caregivers speak my language? Who do I call at night or on weekends? What happens if a caregiver is sick?</p>
<h2>Another option: Self-Managed Care</h2>
<p>With Self-Managed Care, ALA gives you funding through a one-year agreement to pay for and manage your own personal care and home support. It's meant for people with stable, predictable, longer-term needs who are willing to take on contracting their own care. {cite('smc')}</p>
<h2>Sources</h2><ul class="small">{''.join(f'<li><a href="{v[1]}">{e(v[0])}</a></li>' for v in SRC.values())}</ul>
<p class="small muted">This guide is general information, not medical, legal or financial advice. Your case manager makes the final decisions about eligibility, services and hours.</p></article>{newsletter_cta()}"""
    write("/client-directed-home-care-edmonton/", page("/client-directed-home-care-edmonton/", "Client Directed Home Care Edmonton: How to Get Government-Funded Home Care (2026)",
          "How to get government-funded home care in Edmonton: call 811 or 780-496-1300, ask about client directed home care (CDHCI), and how the $35.03/hour rate from Oct 1, 2026 works.", body, "/client-directed-home-care-edmonton/"))

    subj = "Home Care Finder listing"
    body = f"""<article class="prose"><h1>Agencies: get listed or fix your listing</h1>
<p class="lead">Listing an Edmonton-area home care agency is <b>free</b> right now. Listings are sorted alphabetically and are never ranked.</p>
<div class="callout">{disclosure_text()}</div>
<h2>How to add or fix a listing</h2>
<p>Email us from an address at your agency's website domain, with:</p>
<ul><li>Agency name, website and main phone</li><li>Areas you serve</li><li>Services you provide</li><li>Funding you accept (for example CDHCI, Self-Managed Care, FSCD), only if it's stated on your website</li><li>Languages your caregivers speak</li><li>A page on your website where we can confirm each detail</li></ul>
<p><a class="btn" href="mailto:{e(EMAIL)}?subject={e(subj)}">Email us about a listing</a></p>
<p class="small muted">Email: {e(EMAIL)}</p>
<h2>Our rules</h2><ul><li>We only publish what we can confirm on your own website.</li><li>We don't copy Google reviews or star ratings.</li><li>We don't edit other agencies' listings because you ask us to.</li><li>We remove a listing on request.</li></ul></article>"""
    write("/get-listed/", page("/get-listed/", "Get Listed: Home Care Agencies Edmonton | Free Listing", "Add or correct your Edmonton home care agency's free listing on the Edmonton Home Care Finder.", body, "/get-listed/"))

    body = f"""<article class="prose"><h1>About this site and disclaimer</h1>
<h2 id="ownership">Who runs this site</h2>
<div class="callout"><p>This site is run by <b>{e(OWNER)}</b>, who owns <b>{e(AGENCY)}</b>, a home care agency in Edmonton. That agency is a competitor of the other agencies listed here.</p>
<p>Because of that, we follow strict rules: every listing is sorted <b>alphabetically</b>, with no ranking, scores, "featured" spots or "best" labels. The owner's agency gets the same type of listing as everyone else, and is marked "Owned by this site's owner". No agency pays to be listed.</p></div>
<h2>Where the information comes from</h2>
<p>Each listing is written in our own words from the agency's own website, and each card links to the exact pages we used and the date we checked them. "Not stated" means we couldn't find the detail on the agency's site.</p>
<p>We don't copy the Alberta Blue Cross provider map or Alberta Health Services lists. Their website terms only allow personal, non-commercial use, so we link to them instead. We don't copy Google reviews or star ratings.</p>
<h2 id="disclaimer">Disclaimer</h2>
<p>Information may be wrong or out of date. Always confirm services, prices, service areas and funding directly with the agency and your case manager before you decide. This site isn't medical, legal or financial advice. We aren't affiliated with or endorsed by Alberta Health Services, Assisted Living Alberta, Alberta Blue Cross or any agency listed. A listing isn't a recommendation.</p>
<h2>Privacy</h2><p>No ads, no trackers, no analytics and no cookies. If you email us, we use your email only to reply.</p>
<h2>Corrections</h2><p>Spot something wrong? <a href="{u('/get-listed/')}">Tell us</a> and we'll fix it.</p></article>"""
    write("/about/", page("/about/", f"About & Disclaimer | {SITE}", "Who runs the Edmonton Home Care Finder, how listings work (alphabetical, not ranked), and our disclaimer.", body, "/about/"))

    body = f"""<article class="prose"><h1>The family caregiver email</h1><p class="lead">A short monthly email for Edmonton families: changes to funded home care, the CDHCI rate, and new agencies on the list.</p>
<div class="card" id="signup"><h3>Sign up</h3><p class="muted">Signup opens soon. We're setting up the email form now.</p>
<!-- BEEHIIV_EMBED: paste the beehiiv subscribe form embed here (free plan). Keep it opt-in only (CASL). -->
<p class="small muted">Free. Unsubscribe anytime. We'll never sell or share your email.</p></div></article>"""
    write("/newsletter/", page("/newsletter/", f"Family Caregiver Email | {SITE}", "A free monthly email about home care and client directed home care in Edmonton.", body, "/newsletter/"))
    write("/404.html", page("/404.html", f"Page not found | {SITE}", "Page not found.", f'<h1>Page not found</h1><p><a href="{u("/")}">Find home care in Edmonton →</a></p>'))

    pub = {"updated": UPDATED, "note": "Alphabetical, not ranked. Source: each agency's own website.", "agencies": [{k: v for k, v in a.items() if k != "publish"} for a in AG]}
    json.dump(pub, open(os.path.join(OUT, "data", "agencies.json"), "w"), indent=1, ensure_ascii=False)
    urls = ["/", "/client-directed-home-care-edmonton/", "/get-listed/", "/about/", "/newsletter/"]
    open(os.path.join(OUT, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{SITE_URL}{BASE}{p}</loc><lastmod>{UPDATED}</lastmod></url>\n" for p in urls) + "</urlset>\n")
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}{BASE}/sitemap.xml\n")
    print(f"Built {len(urls)} pages into public/ (base {SITE_URL}{BASE}/), {len(AG)} agencies published")
    for a in UNPUBLISHED:
        print(f"  NOTE: not published (publish=false): {a['name']}")
    if "[" in AGENCY: print("  WARNING: config/site.json owner_agency is still a placeholder")
    if "[" in EMAIL: print("  WARNING: config/site.json contact_email is still a placeholder")


if __name__ == "__main__":
    build()
