#!/usr/bin/env python3
"""Fetch every retailer / official page, parse plans, and update data/*.json.

Fails gracefully: a source that can't be fetched or parsed keeps its last good
rows (with their original last-checked date) and is flagged in data/status.json.
Raw pages are cached in data/raw/ (git-ignored, excluded from the tarball).
"""
import datetime as dt, json, os, sys, urllib.request
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

    if not plans:
        print("No plan data at all; leaving files untouched."); return 1
    plans.sort(key=lambda p: (p["fuel"], p["retailer"], p["plan"]))
    jsave("plans.json", {"updated": stamp, "plans": plans})
    jsave("defaults.json", defaults)
    jsave("changes.json", changes)
    jsave("status.json", status)
    # daily snapshot for history (small)
    hist = jload("history.json", {"days": {}})
    hist["days"][today] = {p["id"]: p["rate"] for p in plans}
    hist["days"] = dict(sorted(hist["days"].items())[-400:])
    jsave("history.json", hist)
    print(f"{ok_count}/{len(PLAN_SOURCES)} plan sources OK, {len(plans)} plans, {len({p['retailer'] for p in plans})} retailers")
    return 0 if ok_count else 1


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


if __name__ == "__main__":
    sys.exit(main())
