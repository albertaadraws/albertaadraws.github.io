#!/usr/bin/env python3
"""Fetch every retailer / official page, parse plans, and update data/*.json.

Fails gracefully: a source that can't be fetched or parsed keeps its last good
rows (with their original last-checked date) and is flagged in data/status.json.
Raw pages are cached in data/raw/ (git-ignored, excluded from the tarball).
"""
import datetime as dt, json, os, re, sys, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
import sources as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
TZ = ZoneInfo("America/Edmonton")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36 AlbertaPowerTracker/1.0 (+https://albertaadraws.github.io/alberta-power/about/)"

# key, retailer/publisher, URL, parser.  Plan sources return lists of plans.
PLAN_SOURCES = [
    ("aus", "Alberta Utility Source", "https://www.albertautility.com/mysecure/rates/signup/index.html", S.p_aus),
    ("spot", "SPOTpower", "https://www.spotpower.net/mysecure/rates/signup/index.html", S.p_spot),
    ("park", "Park Power", "https://secure.parkpower.ca/mysecure/rates/signup/index.html", S.p_park),
    ("8760-e", "8760", "https://www.8760.ca/home-electricity-rates", S.p_8760_e),
    ("8760-g", "8760", "https://www.8760.ca/home-natural-gas-rates", S.p_8760_g),
    ("de", "Direct Energy", "https://www.directenergy.ca/en/compare-alberta-energy-rates", S.p_directenergy),
    ("enmax", "ENMAX (Easymax)", "https://www.enmax.com/electricity-and-natural-gas", S.p_enmax),
    ("atco", "ATCO Energy", "https://www.atcoenergy.com/home-energy/fixed-rate-plan", S.p_atco_fixed),
    ("atco-float", "ATCO Energy", "https://www.atcoenergy.com/home-energy/floating-rate-plan", S.p_atco_float),
    ("encor", "Encor by EPCOR", "https://www.epcor.com/ca/en/ab/edmonton/start-services/home/compare-electricity-rates/encor-electricity-plans.html", S.p_encor),
    ("peace", "Peace Power", "https://peacepower.ca/rates/", S.p_peace),
]
# Retailers we tried but whose public pages don't print a specific plan price in the HTML.
NOT_PUBLISHED = [
    ("Alberta Co-operative Energy (ACE)", "https://acenergy.ca/rate-plans/electricity/",
     "Only 'as low as' prices and a margin adder are in the page; the actual plan rates load separately. Omitted rather than guessed."),
    ("Just Energy", "https://justenergy.com/service-areas/canada/alberta/", "No Alberta residential rates printed on the public page."),
]
DEFAULT_SOURCES = {
    "uca": ("Utilities Consumer Advocate: default rates", "https://ucahelps.alberta.ca/utility-choices/current-rates-and-pricing/default-rates/", S.p_uca_defaults),
    "epcor": ("EPCOR: Rate of Last Resort rates and fees (Edmonton)", "https://www.epcor.com/ca/en/ab/edmonton/account/rates/current-and-historical-rates/historical-electricity-rates.html", S.p_epcor_rolr),
    "enmax": ("ENMAX Energy: Regulated Rate Tariff schedule, City of Calgary (PDF)", "https://assets.enmax.com/api/public/content/516f331f11314de58342afacbb98bc1e?v=52c9f5c0", S.p_enmax_rolr_pdf),
    "ders": ("Direct Energy: regulated natural gas rate (Direct Energy Regulated Services)", "https://www.directenergy.ca/en/compare-alberta-energy-rates", S.p_de_regulated_gas),
}


def now():
    return dt.datetime.now(TZ)


def jload(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default


def jsave(name, obj):
    tmp = os.path.join(DATA, name + ".tmp")
    json.dump(obj, open(tmp, "w"), indent=1, ensure_ascii=False)
    os.replace(tmp, os.path.join(DATA, name))


_cache = {}
def fetch(url):
    if url in _cache: return _cache[url]
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-CA,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
    _cache[url] = data
    return data


def page_text(data):
    soup = BeautifulSoup(data.decode("utf-8", "ignore"), "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]): t.decompose()
    return S.clean(soup.get_text(" "))


def main():
    os.makedirs(RAW, exist_ok=True)
    today = now().date().isoformat()
    stamp = now().isoformat(timespec="seconds")
    old = jload("plans.json", {"plans": []})
    old_by_src = {}
    for p in old["plans"]: old_by_src.setdefault(p["source_key"], []).append(p)
    status = {"checked_at": stamp, "sources": [], "not_published": [dict(retailer=a, url=b, reason=c) for a, b, c in NOT_PUBLISHED]}
    plans, ok_count = [], 0
    atco_admin = None
    for key, name, url, parser in PLAN_SOURCES:
        try:
            data = fetch(url)
            open(os.path.join(RAW, f"{key}.html"), "wb").write(data)
            text = page_text(data)
            rows = parser(text, url, atco_admin) if key == "atco-float" else parser(text, url)
            if key == "atco-float" and atco_admin is None: raise ValueError("ATCO admin fee unknown")
            if not rows: raise ValueError("no plans parsed")
            if key == "atco":
                atco_admin = round(rows[0]["admin_monthly"] / S.DAYS_PER_MONTH, 2)
            for r in rows:
                r.update(source_key=key, source_name=name, last_checked=today)
            plans += rows; ok_count += 1
            status["sources"].append(dict(key=key, retailer=name, url=url, ok=True, plans=len(rows)))
            print(f"OK   {key:11s} {len(rows):2d} plans")
        except Exception as ex:  # keep last good data
            keep = old_by_src.get(key, [])
            plans += keep
            status["sources"].append(dict(key=key, retailer=name, url=url, ok=False, error=str(ex)[:200], kept=len(keep)))
            print(f"FAIL {key:11s} {ex} (kept {len(keep)} old rows)")
            if key == "atco" and keep: atco_admin = round(keep[0]["admin_monthly"] / S.DAYS_PER_MONTH, 2)

    # ---- defaults / benchmarks
    dold = jload("defaults.json", {})
    parts = {}
    for key, (name, url, parser) in DEFAULT_SOURCES.items():
        try:
            data = fetch(url)
            open(os.path.join(RAW, f"default-{key}.{'pdf' if key=='enmax' else 'html'}"), "wb").write(data)
            parts[key] = parser(data if key == "enmax" else page_text(data), url)
            parts[key]["_checked"] = today
            status["sources"].append(dict(key="default-" + key, retailer=name, url=url, ok=True))
            print(f"OK   default-{key}")
        except Exception as ex:
            parts[key] = (dold.get("_parts") or {}).get(key)
            status["sources"].append(dict(key="default-" + key, retailer=name, url=url, ok=False, error=str(ex)[:200], kept=bool(parts[key])))
            print(f"FAIL default-{key}: {ex}")
    defaults = build_defaults(parts, dold)
    defaults["_parts"] = parts

    # ---- change log (for RSS + newsletter)
    changes = jload("changes.json", {"changes": []})
    prev = {p["id"]: p for p in old["plans"]}
    cur = {p["id"]: p for p in plans}
    if old["plans"]:
        for pid, p in cur.items():
            if pid not in prev:
                changes["changes"].append(dict(date=today, kind="new", id=pid, retailer=p["retailer"], plan=p["plan"], fuel=p["fuel"], new=p["rate"]))
            elif abs(prev[pid]["rate"] - p["rate"]) > 1e-9 or abs(prev[pid]["admin_monthly"] - p["admin_monthly"]) > 0.005:
                changes["changes"].append(dict(date=today, kind="rate", id=pid, retailer=p["retailer"], plan=p["plan"], fuel=p["fuel"],
                                               old=prev[pid]["rate"], new=p["rate"], old_admin=prev[pid]["admin_monthly"], new_admin=p["admin_monthly"]))
        for pid, p in prev.items():
            if pid not in cur:
                changes["changes"].append(dict(date=today, kind="removed", id=pid, retailer=p["retailer"], plan=p["plan"], fuel=p["fuel"], old=p["rate"]))
        for k in ("rolr_edmonton", "rolr_calgary", "gas_default"):
            a, b = (dold.get(k) or {}).get("rate"), (defaults.get(k) or {}).get("rate")
            if a is not None and b is not None and abs(a - b) > 1e-9:
                changes["changes"].append(dict(date=today, kind="default", id=k, retailer=defaults[k]["retailer"], plan=defaults[k]["plan"], fuel=defaults[k]["fuel"], old=a, new=b))
    changes["changes"] = changes["changes"][-500:]

    if plans:
        plans.sort(key=lambda p: (p["fuel"], p["retailer"], p["plan"]))
        jsave("plans.json", {"updated": stamp, "plans": plans})
        jsave("defaults.json", defaults)
        jsave("changes.json", changes)
        hist = jload("history.json", {"days": {}})
        hist["days"][today] = {p["id"]: p["rate"] for p in plans}
        hist["days"] = dict(sorted(hist["days"].items())[-400:])
        jsave("history.json", hist)
        print(f"{ok_count}/{len(PLAN_SOURCES)} plan sources OK, {len(plans)} plans, {len({p['retailer'] for p in plans})} retailers")
    else:
        print("No plan data at all; electricity and gas files left untouched.")
    try:
        refresh_water(today, status)
    except Exception as ex:
        print(f"FAIL water section {ex}")
    try:
        refresh_solar(plans, today, status)
    except Exception as ex:
        print(f"FAIL solar section {ex}")
    jsave("status.json", status)
    return 0 if ok_count and plans else 1


def build_defaults(parts, dold):
    uca, ep, en, de = parts.get("uca"), parts.get("epcor"), parts.get("enmax"), parts.get("ders")
    out = dict(dold) if dold else {}
    U = DEFAULT_SOURCES
    if uca and ep:
        out["rolr_edmonton"] = dict(retailer="EPCOR Energy Alberta", plan="Rate of Last Resort (default)", fuel="electricity", type="default",
            area="edmonton", rate=uca["rolr"]["epcor"], admin_day=ep["admin_day"], admin_monthly=round(ep["admin_day"] * S.DAYS_PER_MONTH, 2),
            admin_text=f"${ep['admin_day']:.3f}/day per site", term_label=f"Fixed to Dec 31, {uca['rolr_until']}",
            cancellation="Leave anytime, no penalty (UCA).", cancellation_fee=0,
            sources=[dict(name=U["uca"][0], url=U["uca"][1], checked=uca["_checked"]), dict(name=U["epcor"][0], url=U["epcor"][1], checked=ep["_checked"])],
            last_checked=min(uca["_checked"], ep["_checked"]),
            rate_note="Includes a 0.1¢/kWh consumer awareness surcharge. Delivery charges extra.")
    if uca and en:
        out["rolr_calgary"] = dict(retailer="ENMAX Energy", plan="Rate of Last Resort (default)", fuel="electricity", type="default",
            area="calgary", rate=uca["rolr"]["enmax"], admin_day=en["admin_day"], admin_monthly=round(en["admin_day"] * S.DAYS_PER_MONTH, 2),
            admin_text=f"${en['admin_day']:.4f}/day per site ({en.get('tariff_year','')} interim tariff)", term_label=f"Fixed to Dec 31, {uca['rolr_until']}",
            cancellation="Leave anytime, no penalty (UCA).", cancellation_fee=0,
            sources=[dict(name=U["uca"][0], url=U["uca"][1], checked=uca["_checked"]), dict(name=U["enmax"][0], url=U["enmax"][1], checked=en["_checked"])],
            last_checked=min(uca["_checked"], en["_checked"]),
            rate_note="Includes a 0.1¢/kWh consumer awareness surcharge. Delivery charges extra.")
    if uca and de:
        out["gas_default"] = dict(retailer="Direct Energy Regulated Services", plan=f"Default Rate Tariff ({uca['drt']['month']})", fuel="gas", type="default",
            area="both", rate=uca["drt"]["ders"], admin_day=de["admin_day"], admin_monthly=round(de["admin_day"] * S.DAYS_PER_MONTH, 2),
            admin_text=f"${de['admin_day']:.3f}/day per site", term_label="Changes monthly",
            cancellation="No contract; switch anytime.", cancellation_fee=0, month=uca["drt"]["month"],
            sources=[dict(name=U["uca"][0], url=U["uca"][1], checked=uca["_checked"]), dict(name=U["ders"][0], url=U["ders"][1], checked=de["_checked"])],
            last_checked=min(uca["_checked"], de["_checked"]),
            rate_note="Default gas rate in the ATCO Gas area (Edmonton and Calgary). AUC-approved, set monthly. Delivery charges extra.")
        MO = ["January","February","March","April","May","June","July","August","September","October","November","December"]
        h = sorted(uca.get("drt_history", []), key=lambda r: (r["year"], MO.index(r["month"])))[-12:]
        if len(h) == 12:
            out["gas_default"]["avg12"] = round(sum(r["ders"] for r in h) / 12, 3)
            out["gas_default"]["avg12_range"] = f"{h[0]['month']} {h[0]['year']} to {h[-1]['month']} {h[-1]['year']}"
            out["gas_default"]["history"] = h
    if uca:
        out["rolr_other"] = dict(fortis_epcor=uca["rolr"]["fortis"], ders_atco_electric=uca["rolr"]["ders"], until=uca["rolr_until"], apex_gas=uca["drt"]["apex"])
    return out


SOLAR_SIGNUP = "https://solarclub.ca/sign-up/"
ENMAX_SOLAR_URL = "https://www.enmax.com/solar/easymax-seasonal-solar"
NRCAN_PAGE = "https://natural-resources.canada.ca/energy-sources/renewable-energy/photovoltaic-potential-solar-resource-maps-canada"
NRCAN_QUERY = ("https://maps-cartes.services.geo.ca/server_serveur/rest/services/NRCan/PPSRMC_CEPESPC_EN/MapServer/0/query"
               "?where=" + urllib.parse.quote(
                   "Province = 'Alberta' AND Variable = 'Photovoltaic potential (kWh/kWp)' "
                   "AND Orientation = 'South-facing with latitude tilt' AND time = 13 "
                   "AND (Municipality = 'Edmonton' OR Municipality = 'Calgary')")
               + "&outFields=Municipality,Province,Variable,Orientation,time,Value&returnGeometry=false&f=json")

# Public rates pages that describe solar or micro-generation, checked because they do not print a buyback rate.
SOLAR_UNPRICED = [
    ("Alberta Co-operative Energy (ACE)", "https://acenergy.ca/rate-plans/electricity/",
     "The public electricity page says micro-generators get credit for excess energy, but it does not print an export or import rate."),
    ("Direct Energy", "https://www.directenergy.ca/en/compare-alberta-energy-rates",
     "No micro-generation export or import rate is printed on the public Alberta rates page."),
    ("ATCO Energy", "https://www.atcoenergy.com/home-energy/fixed-rate-plan",
     "The fixed-rate page mentions renewable add-ons (hydro, wind and solar) but does not print a micro-generation export rate."),
    ("Encor by EPCOR", "https://www.epcor.com/ca/en/ab/edmonton/start-services/home/compare-electricity-rates/encor-electricity-plans.html",
     "No solar or micro-generation plan rate is printed on the Encor electricity plans page."),
    ("Peace Power", "https://peacepower.ca/rates/",
     "No solar or micro-generation rate is printed on the public rates page."),
    ("8760", "https://www.8760.ca/home-electricity-rates",
     "No solar or micro-generation rate is printed on the public electricity rates page."),
    ("Just Energy", "https://justenergy.com/service-areas/canada/alberta/",
     "No Alberta residential solar rate is printed on the public Alberta page."),
]


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def discover_solar_marketers(html):
    soup = BeautifulSoup(html, "html.parser")
    found, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.endswith("/mysecure/rates/signup/index.html") or href in seen:
            continue
        seen.add(href)
        name = re.sub(r"^Sign Up With\s+", "", a.get_text(" ", strip=True)).strip()
        if not name:
            raise ValueError("Solar Club signup link has no retailer name")
        found.append((name, href))
    if len(found) < 5:
        raise ValueError(f"only {len(found)} Solar Club marketers on the signup page")
    return found


def _keep_solar(old_plans, key):
    return [p for p in old_plans if p.get("source_key") == key]


def attach_enmax_import(row, elec_plans):
    """The solar page says winter use is billed at the Easymax rate. Copy that rate from ENMAX's own electricity page."""
    if not any(p.get("id") == "enmax-e-fix" for p in elec_plans):
        elec_plans = (jload("plans.json", {"plans": []}).get("plans") or [])
    fix = next((p for p in elec_plans if p.get("id") == "enmax-e-fix"), None)
    flt = next((p for p in elec_plans if p.get("id") == "enmax-e-float"), None)
    if not fix:
        row["import_text"] = "Your Easymax plan rate. The solar page does not print the cents, and the Easymax electricity page could not be read."
        return
    row["import_rate"] = fix["rate"]
    row["import_rate_kind"] = "easymax_fixed_reference"
    row["import_text"] = f"Easymax fixed {fix['rate']:.2f}¢/kWh while that plan is the active rate"
    row["import_source_url"] = fix["source_url"]
    row["import_checked"] = fix["last_checked"]
    if flt:
        row["import_alt"] = {
            "rate": flt["rate"],
            "label": f"Easymax floating {flt['rate']:.2f}¢/kWh (the retailer's stated recent average, not a fixed rate)",
            "indicative": True,
            "source_url": flt["source_url"],
            "last_checked": flt["last_checked"],
        }
        row["import_text"] += f", or floating {flt['rate']:.2f}¢/kWh (stated recent average)"
    row["admin_monthly"] = fix["admin_monthly"]
    row["admin_text"] = fix["admin_text"] + " (Easymax admin from the electricity rates page; the solar page does not restate it)"
    row["admin_source_url"] = fix["source_url"]
    if fix.get("cancellation"):
        row["cancellation"] = "Not stated on the solar page. The Easymax electricity page says: " + fix["cancellation"]
        row["cancellation_source_url"] = fix["source_url"]


def refresh_solar(elec_plans, today, status):
    old = jload("solar.json", {})
    old_plans = old.get("plans") or []
    plans = []
    try:
        raw_html = fetch(SOLAR_SIGNUP)
        open(os.path.join(RAW, "solar-signup.html"), "wb").write(raw_html)
        marketers = discover_solar_marketers(raw_html.decode("utf-8", "ignore"))
        status["sources"].append(dict(key="solar-signup", retailer="Solar Club authorized retailers", url=SOLAR_SIGNUP, ok=True, plans=len(marketers)))
        print(f"OK   solar-signup {len(marketers)} marketers")
    except Exception as ex:
        seen = []
        marketers = []
        for p in old_plans:
            if p.get("plan_kind") == "solar_club" and p.get("source_url") not in seen:
                seen.append(p["source_url"])
                marketers.append((p["retailer"], p["source_url"]))
        status["sources"].append(dict(key="solar-signup", retailer="Solar Club authorized retailers", url=SOLAR_SIGNUP, ok=False, error=str(ex)[:200], kept=len(marketers)))
        print(f"FAIL solar-signup {ex} (kept {len(marketers)} previous retailers)")

    for retailer, url in marketers:
        key = "solar-" + _slug(retailer)
        try:
            data = fetch(url)
            open(os.path.join(RAW, key + ".html"), "wb").write(data)
            soup = BeautifulSoup(data.decode("utf-8", "ignore"), "html.parser")
            el = soup.find(id="residenceSOLAR")
            if el is None:
                raise ValueError("no residential solar block")
            block = S.clean(el.get_text(" "))
            rows = S.p_utilitynet_solar(block, page_text(data), url, retailer)
            if not any(r["plan_kind"] == "solar_club" for r in rows):
                raise ValueError("no Solar Club HI/LO row")
            for r in rows:
                suffix = r.pop("id_suffix")
                r["id"] = f"{key}-{suffix}"
                r.update(source_key=key, source_name=retailer, last_checked=today)
            plans += rows
            status["sources"].append(dict(key=key, retailer=retailer + " solar", url=url, ok=True, plans=len(rows)))
            print(f"OK   {key:28s} {len(rows)} solar rows")
        except Exception as ex:
            keep = _keep_solar(old_plans, key)
            plans += keep
            status["sources"].append(dict(key=key, retailer=retailer + " solar", url=url, ok=False, error=str(ex)[:200], kept=len(keep)))
            print(f"FAIL {key:28s} {ex} (kept {len(keep)})")

    key = "solar-enmax"
    try:
        data = fetch(ENMAX_SOLAR_URL)
        open(os.path.join(RAW, "solar-enmax.html"), "wb").write(data)
        rows = S.p_enmax_solar(page_text(data), ENMAX_SOLAR_URL)
        for r in rows:
            suffix = r.pop("id_suffix")
            r["id"] = f"{key}-{suffix}"
            r.update(source_key=key, source_name="ENMAX (Easymax Seasonal Solar)", last_checked=today)
            attach_enmax_import(r, elec_plans)
        plans += rows
        status["sources"].append(dict(key=key, retailer="ENMAX (Easymax Seasonal Solar)", url=ENMAX_SOLAR_URL, ok=True, plans=len(rows)))
        print(f"OK   {key}")
    except Exception as ex:
        keep = _keep_solar(old_plans, key)
        plans += keep
        status["sources"].append(dict(key=key, retailer="ENMAX (Easymax Seasonal Solar)", url=ENMAX_SOLAR_URL, ok=False, error=str(ex)[:200], kept=len(keep)))
        print(f"FAIL {key} {ex} (kept {len(keep)})")

    absent = []
    for retailer, url, reason in SOLAR_UNPRICED:
        key = "solar-unpriced-" + _slug(retailer)
        try:
            data = fetch(url)
            absent.append(S.solar_rates_absent(page_text(data), retailer, url, reason))
            status["sources"].append(dict(key=key, retailer=retailer + " (no solar rate published)", url=url, ok=True))
            print(f"OK   {key} (no rate published)")
        except Exception as ex:
            prev = next((x for x in (old.get("not_published") or []) if x.get("url") == url), None)
            if prev and "prints a cents figure" not in str(ex):
                absent.append(prev)
            status["sources"].append(dict(key=key, retailer=retailer + " (no solar rate published)", url=url, ok=False, error=str(ex)[:200], kept=bool(prev)))
            print(f"FAIL {key} {ex}")

    programs, old_progs = [], {p["id"]: p for p in (old.get("programs") or [])}
    program_sources = [
        ("prog-yeg-ceip", "City of Edmonton CEIP", "https://www.edmonton.ca/city_government/environmental_stewardship/clean-energy-improvement-program", S.p_edmonton_ceip),
        ("prog-yyc-ceip", "City of Calgary residential CEIP", "https://www.calgary.ca/environment/programs/clean-energy-improvement-program.html", S.p_calgary_ceip),
        ("prog-ceip-table", "Alberta Municipalities CEIP status", "https://ceip.abmunis.ca/contractor/", S.p_ceip_admin_table),
        ("prog-gh-loan", "Canada Greener Homes Loan", "https://natural-resources.canada.ca/energy-efficiency/home-energy-efficiency/canada-greener-homes-initiative/canada-greener-homes-loan", S.p_greener_loan),
        ("prog-gh-grant", "Canada Greener Homes Grant", "https://natural-resources.canada.ca/energy-efficiency/home-energy-efficiency/canada-greener-homes-initiative/canada-greener-homes-initiative", S.p_greener_grant),
        ("prog-uca", "UCA renewable energy grants", "https://ucahelps.alberta.ca/residential/renewable-energy/renewable-energy-grants-and-programs/", S.p_uca_solar_programs),
        ("prog-uca-provincial", "UCA: no Alberta provincial solar program", "https://ucahelps.alberta.ca/residential/renewable-energy/renewable-energy-faqs/", S.p_uca_no_provincial_solar),
    ]
    for key, name, url, parser in program_sources:
        try:
            data = fetch(url)
            open(os.path.join(RAW, key + ".html"), "wb").write(data)
            row = parser(page_text(data), url)
            row.update(source_key=key, source_name=name, last_checked=today)
            programs.append(row)
            status["sources"].append(dict(key=key, retailer=name, url=url, ok=True))
            print(f"OK   {key}")
        except Exception as ex:
            prev = next((p for p in old_progs.values() if p.get("source_key") == key), None)
            if prev:
                programs.append(prev)
            status["sources"].append(dict(key=key, retailer=name, url=url, ok=False, error=str(ex)[:200], kept=bool(prev)))
            print(f"FAIL {key} {ex}")

    production = old.get("production") or []
    try:
        data = fetch(NRCAN_QUERY)
        open(os.path.join(RAW, "nrcan-pv.json"), "wb").write(data)
        payload = json.loads(data.decode("utf-8", "ignore"))
        if payload.get("error"):
            raise ValueError(payload["error"].get("message", "NRCan query failed"))
        rows = [f["attributes"] for f in payload.get("features") or []]
        production = S.p_nrcan_pv(rows, NRCAN_PAGE, NRCAN_QUERY)
        for row in production:
            row["last_checked"] = today
        status["sources"].append(dict(key="nrcan-pv", retailer="NRCan photovoltaic potential (Edmonton and Calgary)", url=NRCAN_PAGE, ok=True))
        print("OK   nrcan-pv", ", ".join(f"{r['city_label']} {r['kwh_per_kw']}" for r in production))
    except Exception as ex:
        status["sources"].append(dict(key="nrcan-pv", retailer="NRCan photovoltaic potential (Edmonton and Calgary)", url=NRCAN_PAGE, ok=False, error=str(ex)[:200], kept=bool(production)))
        print(f"FAIL nrcan-pv {ex}")

    installed = old.get("installed_cost")
    cost_url = "https://ucahelps.alberta.ca/residential/renewable-energy/renewable-energy-faqs/"
    try:
        installed = S.p_uca_installed_cost(page_text(fetch(cost_url)), cost_url)
        installed["last_checked"] = today
        installed["source_name"] = "Utilities Consumer Advocate: renewable energy FAQs"
        status["sources"].append(dict(key="solar-installed-cost", retailer="UCA residential solar installed cost", url=cost_url, ok=True))
        print("OK   solar-installed-cost")
    except Exception as ex:
        status["sources"].append(dict(key="solar-installed-cost", retailer="UCA residential solar installed cost", url=cost_url, ok=False, error=str(ex)[:200], kept=bool(installed)))
        print(f"FAIL solar-installed-cost {ex}")

    if not plans and old_plans:
        print("Solar parse produced nothing; previous solar plans left in place.")
        plans = old_plans
    plans.sort(key=lambda p: (p.get("export_rate") is None, -(p.get("export_rate") or 0), p.get("admin_monthly") if p.get("admin_monthly") is not None else 10**6, p.get("retailer") or "", p.get("plan") or ""))
    jsave("solar.json", {
        "updated": now().isoformat(timespec="seconds"),
        "plans": plans,
        "not_published": absent,
        "production": production,
        "installed_cost": installed,
        "programs": programs,
        "export_share_assumption": {
            "share": 0.5,
            "note": "Assumption, not a published Alberta figure. No official province-wide share of home-solar production that is exported was found, so the calculator starts at half exported and half used at home. Change it.",
        },
    })
    print(f"solar plans: {len(plans)}; unpublished solar pages: {len(absent)}")


def refresh_water(today, status):
    old = jload("water.json", {})
    parts = dict(old.get("_parts") or {})
    sources = [
        ("water-epcor", "EPCOR Edmonton water, wastewater and drainage",
         "https://www.epcor.com/ca/en/ab/edmonton/account/rates/current-and-historical-rates/water-and-wastewater.html", S.p_epcor_water),
        ("water-yeg-waste", "City of Edmonton waste utility rates",
         "https://www.edmonton.ca/programs_services/garbage_waste/rates-fees", S.p_edmonton_waste),
        ("water-calgary", "City of Calgary residential water, wastewater and stormwater",
         "https://www.calgary.ca/water/water-utility/residential-water-rates-and-billing.html", S.p_calgary_water),
        ("water-tips", "EPCOR: conservation inside your home",
         "https://www.epcor.com/ca/en/ab/edmonton/conservation/home/inside.html", S.p_epcor_water_tips),
    ]
    for key, name, url, parser in sources:
        try:
            data = fetch(url)
            open(os.path.join(RAW, key + ".html"), "wb").write(data)
            parsed = parser(page_text(data), url)
            parsed.update(last_checked=today, source_name=name, source_key=key)
            parts[key] = parsed
            status["sources"].append(dict(key=key, retailer=name, url=url, ok=True))
            print(f"OK   {key}")
        except Exception as ex:
            status["sources"].append(dict(key=key, retailer=name, url=url, ok=False, error=str(ex)[:200], kept=bool(parts.get(key))))
            print(f"FAIL {key} {ex}")
    jsave("water.json", {
        "updated": now().isoformat(timespec="seconds"),
        "edmonton": parts.get("water-epcor"),
        "calgary": parts.get("water-calgary"),
        "edmonton_waste": parts.get("water-yeg-waste"),
        "tips": parts.get("water-tips"),
        "_parts": parts,
    })


if __name__ == "__main__":
    sys.exit(main())
