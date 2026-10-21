#!/usr/bin/env python3
"""One parser per official source. Each returns a list of plan dicts or raises.

Rules: only numbers printed on the retailer's own page (or an official AUC/UCA/
regulated-provider page). If a number can't be found, the parser raises and
refresh.py keeps the last good rows for that source. Never guess.

NOTE: the UCA Cost Comparison Tool is deliberately NOT used. Its terms require
written permission for commercial reuse.
"""
import re, subprocess, tempfile, os

DAYS_PER_MONTH = 365 / 12  # 30.42, used to turn $/day admin fees into $/month

BOTH = ["edmonton", "calgary"]


def clean(t):
    return re.sub(r"\s+", " ", t.replace("\u200b", "").replace("\xa0", " "))


def need(pattern, text, what, flags=0):
    m = re.search(pattern, text, flags)
    if not m:
        raise ValueError(f"could not find {what}")
    return m


def plan(**kw):
    base = dict(type="fixed", term_months=None, term_label="", areas=BOTH, conditions="",
                cancellation="Not stated on the retailer page. Check the contract terms.",
                cancellation_fee=None, indicative=False, rate_note="")
    base.update(kw)
    base["admin_monthly"] = round(base["admin_monthly"], 2)
    return base


# ---------------------------------------------------------------- UTILITYnet-platform sign-up pages
def utilitynet_signup(retailer, slug, url, text):
    """Alberta Utility Source, SPOTpower and Park Power share one sign-up page layout."""
    parts = text.split("NOTE: all plans are subject to GST.")
    if len(parts) < 3:
        raise ValueError("unexpected page layout")
    elec, gas = parts[0], parts[1]
    gi = elec.find("Variable Rates for Your Home")
    elec = elec[gi:] if gi >= 0 else elec
    out = []
    pru = ("Requires a refundable prudential deposit (amount depends on usage; see the retailer page).")
    # electricity
    admin_e = float(need(r"Administration Fees \$([\d.]+) per metered site", elec, "electricity admin fee").group(1))
    high = re.search(r"over (\d+) kWh per month will be charged an additional \$([\d.]+)/kWh", elec)
    extra = f" Use over {high.group(1)} kWh/month adds ${high.group(2)}/kWh." if high else ""
    v = re.search(r"Variable Market Price \+ ([\d.]+) cents/kWh Transaction Fee( \(\+ Prudential\))?.*?30-Day Moving Average: ([\d.]+) ¢/kWh.*?as of (\w+ \d+, \d{4})", elec)
    if v:
        out.append(plan(id=f"{slug}-e-var", retailer=retailer, fuel="electricity", type="variable", plan="Variable (floating)",
                        rate=float(v.group(3)), admin_monthly=admin_e, admin_text=f"${admin_e:.2f}/month per site",
                        term_label="No term", indicative=True,
                        rate_note=f"Market price + {v.group(1)}¢/kWh fee. Shown: the retailer's 30-day average incl. fee, as of {v.group(4)}. Changes monthly.",
                        conditions=((pru if v.group(2) else "") + extra).strip(), source_url=url,
                        cancellation="No penalty; 10 days' notice (per retailer).", cancellation_fee=0))
    guar = dict(re.findall(r"(\d) Year \(Guaranteed until (\w+ \d{4})\)", elec))
    for rate, yrs, name, pr in re.findall(r"([\d.]+) ¢/kWh (\d) Year ((?:Senior )?(?:Fixed )?(?:Discount Advantage|Discount|Base|Fixed)(?: Discount)? Rate)( \(\+ Prudential\))?", elec):
        cond = []
        if pr: cond.append(pru)
        if "Senior" in name: cond.append("Seniors age 60+ only.")
        out.append(plan(id=f"{slug}-e-{yrs}y-{re.sub(r'[^a-z]+','-',name.lower()).strip('-')}", retailer=retailer, fuel="electricity",
                        plan=f"{yrs}-year fixed" + (" (seniors, discount)" if "Senior" in name else " (discount)" if "Discount" in name else " (standard)"), rate=float(rate), term_months=12 * int(yrs),
                        term_label=f"{yrs} yr" + (f" (to {guar[yrs]})" if yrs in guar else ""),
                        admin_monthly=admin_e, admin_text=f"${admin_e:.2f}/month per site", conditions=(" ".join(cond) + extra).strip(),
                        source_url=url, cancellation="No penalty; 10 days' notice (per retailer).", cancellation_fee=0))
    # gas
    admin_g = float(need(r"Administration Fees \$([\d.]+) per metered site", gas, "gas admin fee").group(1))
    for fee, pr, avg, asof in re.findall(r"Variable Market Price \+ \$([\d.]+)/GJ Transaction Fee( \(\+ Prudential\))? Sign Up 30-Day Moving Average: ([\d.]+) \$/GJ.*?as of (\w+ \d+, \d{4})", gas):
        out.append(plan(id=f"{slug}-g-var-{fee}", retailer=retailer, fuel="gas", type="variable",
                        plan="Variable" + (" (discount)" if pr else " (standard)"), rate=float(avg), admin_monthly=admin_g,
                        admin_text=f"${admin_g:.2f}/month per site", term_label="No term", indicative=True,
                        rate_note=f"Market price + ${fee}/GJ fee. Shown: the retailer's 30-day average incl. fee, as of {asof}. Changes monthly.",
                        conditions=pru if pr else "", source_url=url,
                        cancellation="No penalty; 10 days' notice (per retailer).", cancellation_fee=0))
    to = re.search(r"Guaranteed to (\w+ \d{4})", gas)
    for rate, name, pr in re.findall(r"([\d.]+) \$/GJ ((?:Fixed Gas Discount|Fixed Gas|Discount Advantage Gas|Base Gas) Rate)( \(\+ Prudential\))?", gas):
        out.append(plan(id=f"{slug}-g-fix-{re.sub(r'[^a-z]+','-',name.lower()).strip('-')}", retailer=retailer, fuel="gas",
                        plan="Fixed" + (" (discount)" if "Discount" in name else " (standard)"),
                        rate=float(rate), term_label=f"to {to.group(1)}" if to else "", term_months=None,
                        admin_monthly=admin_g, admin_text=f"${admin_g:.2f}/month per site", conditions=pru if pr else "",
                        source_url=url, cancellation="No penalty; 10 days' notice (per retailer).", cancellation_fee=0))
    if not any(p["fuel"] == "electricity" for p in out) or not any(p["fuel"] == "gas" for p in out):
        raise ValueError("missing electricity or gas plans")
    return out


def p_aus(t, url): return utilitynet_signup("Alberta Utility Source", "aus", url, t)
def p_spot(t, url): return utilitynet_signup("SPOTpower", "spot", url, t)
def p_park(t, url): return utilitynet_signup("Park Power", "park", url, t)


# ---------------------------------------------------------------- 8760
def p_8760(t, url, fuel):
    m = need(r"administration fees \(\$([\d.]+) per month\) and daily charges \(\$([\d.]+) per day\)", t, "8760 fees")
    admin = float(m.group(1)) + float(m.group(2)) * DAYS_PER_MONTH
    txt = f"${m.group(1)}/month + ${m.group(2)}/day"
    unit = r"¢/kWh" if fuel == "electricity" else r"\$/GJ"
    rows = re.findall(r"(\d) years? ([\d.]+) " + unit + " on a fixed rate term", t)
    if not rows:
        raise ValueError("no 8760 rates")
    eff = re.search(r"rates effective (\w+ \d+, \d{4})", t)
    return [plan(id=f"8760-{fuel[0]}-{y}y", retailer="8760", fuel=fuel, plan=f"{y}-year fixed", rate=float(r),
                 term_months=12 * int(y), term_label=f"{y} yr", admin_monthly=admin, admin_text=txt, source_url=url,
                 rate_note=f"Rates effective {eff.group(1)}." if eff else "",
                 conditions="Deposit may be required (credit check).",
                 cancellation="No early exit fees (per retailer).", cancellation_fee=0) for y, r in dict(rows).items()]


def p_8760_e(t, url): return p_8760(t, url, "electricity")
def p_8760_g(t, url): return p_8760(t, url, "gas")


# ---------------------------------------------------------------- Direct Energy (competitive)
def p_directenergy(t, url):
    admin = float(need(r"Instead of paying \$([\d.]+) per site each month", t, "DE admin fee").group(1))
    out = []
    for r, y in re.findall(r"([\d.]+) cents/kWh (\d)-year fixed rate Provided by Direct Energy", t):
        out.append(plan(id=f"de-e-{y}y", retailer="Direct Energy", fuel="electricity", plan=f"{y}-year fixed", rate=float(r),
                        term_months=12 * int(y), term_label=f"{y} yr", admin_monthly=admin, admin_text=f"${admin:.2f}/month per site",
                        source_url=url, cancellation="No enrolment or exit fees (per retailer).", cancellation_fee=0,
                        conditions="Bundling gas + electricity cuts the admin fee 20%."))
    for r, y in re.findall(r"\$([\d.]+)/GJ (\d)-year fixed rate Provided by Direct Energy", t):
        out.append(plan(id=f"de-g-{y}y", retailer="Direct Energy", fuel="gas", plan=f"{y}-year fixed", rate=float(r),
                        term_months=12 * int(y), term_label=f"{y} yr", admin_monthly=admin, admin_text=f"${admin:.2f}/month per site",
                        source_url=url, cancellation="No enrolment or exit fees (per retailer).", cancellation_fee=0,
                        conditions="Bundling gas + electricity cuts the admin fee 20%."))
    if not out: raise ValueError("no DE plans")
    return out


# ---------------------------------------------------------------- ENMAX Easymax
def p_enmax(t, url):
    admin_d = float(need(r"Administration Fee of approximately \$([\d.]+) per site, per day", t, "ENMAX admin").group(1))
    admin = admin_d * DAYS_PER_MONTH
    at = f"about ${admin_d:.2f}/day per site"
    canc = "No penalty with 10 days' notice (per retailer)."
    e = need(r"Electricity FIXED ([\d.]+)¢/kWh \* Guaranteed for (\d) year or FLOATING ([\d.]+)¢/kWh \*Δ Alberta historical monthly average \+([\d.]+)¢/kWh", t, "ENMAX electricity")
    g = need(r"Natural Gas FIXED \$([\d.]+)/GJ \* Guaranteed for (\d) year or FLOATING \$([\d.]+)/GJ \*Δ Alberta historical monthly average \+\$([\d.]+)/GJ", t, "ENMAX gas")
    fl = "ENMAX's stated two-year average of its monthly floating rate (fee {}). Past rates don't predict future ones."
    return [
        plan(id="enmax-e-fix", retailer="ENMAX (Easymax)", fuel="electricity", plan=f"{e.group(2)}-year fixed", rate=float(e.group(1)),
             term_months=12 * int(e.group(2)), term_label=f"{e.group(2)} yr", admin_monthly=admin, admin_text=at, source_url=url, cancellation=canc, cancellation_fee=0),
        plan(id="enmax-e-float", retailer="ENMAX (Easymax)", fuel="electricity", type="variable", plan="Floating", rate=float(e.group(3)),
             term_label="Floating", indicative=True, rate_note=fl.format(f"+{e.group(4)}¢/kWh"), admin_monthly=admin, admin_text=at, source_url=url, cancellation=canc, cancellation_fee=0),
        plan(id="enmax-g-fix", retailer="ENMAX (Easymax)", fuel="gas", plan=f"{g.group(2)}-year fixed", rate=float(g.group(1)),
             term_months=12 * int(g.group(2)), term_label=f"{g.group(2)} yr", admin_monthly=admin, admin_text=at, source_url=url, cancellation=canc, cancellation_fee=0),
        plan(id="enmax-g-float", retailer="ENMAX (Easymax)", fuel="gas", type="variable", plan="Floating", rate=float(g.group(3)),
             term_label="Floating", indicative=True, rate_note=fl.format(f"+${g.group(4)}/GJ"), admin_monthly=admin, admin_text=at, source_url=url, cancellation=canc, cancellation_fee=0),
    ]


# ---------------------------------------------------------------- ATCO Energy
def p_atco_fixed(t, url):
    admin_d = float(need(r"daily administration fees of \$([\d.]+) per service per day", t, "ATCO admin").group(1))
    admin = admin_d * DAYS_PER_MONTH
    seg = need(r"Electricity rates (.*?) Natural gas rates (.*?) Great pricing", t, "ATCO rate list")
    out = []
    for y, r in re.findall(r"(\d) years? ([\d.]+)¢ / kWh", seg.group(1)):
        out.append(plan(id=f"atco-e-{y}y", retailer="ATCO Energy", fuel="electricity", plan=f"{y}-year fixed", rate=float(r),
                        term_months=12 * int(y), term_label=f"{y} yr", admin_monthly=admin, admin_text=f"${admin_d:.2f}/day per site", source_url=url))
    for y, r in re.findall(r"(\d) years? \$([\d.]+) / GJ", seg.group(2)):
        out.append(plan(id=f"atco-g-{y}y", retailer="ATCO Energy", fuel="gas", plan=f"{y}-year fixed", rate=float(r),
                        term_months=12 * int(y), term_label=f"{y} yr", admin_monthly=admin, admin_text=f"${admin_d:.2f}/day per site", source_url=url))
    b = re.search(r"rate of ([\d.]+)¢/kWh and natural gas rate of \$([\d.]+)/GJ outside of this period", t)
    if b:
        cond = "New-customer 2-year bundle (electricity + gas). Free energy and admin Dec 1-31, 2026 (up to 1,150 kWh / 25 GJ), not counted here."
        out.append(plan(id="atco-e-2y-bundle", retailer="ATCO Energy", fuel="electricity", plan="2-year fixed bundle (new customers)", rate=float(b.group(1)),
                        term_months=24, term_label="2 yr", admin_monthly=admin, admin_text=f"${admin_d:.2f}/day per site", conditions=cond, source_url=url))
        out.append(plan(id="atco-g-2y-bundle", retailer="ATCO Energy", fuel="gas", plan="2-year fixed bundle (new customers)", rate=float(b.group(2)),
                        term_months=24, term_label="2 yr", admin_monthly=admin, admin_text=f"${admin_d:.2f}/day per site", conditions=cond, source_url=url))
    if not out: raise ValueError("no ATCO plans")
    return out


def p_atco_float(t, url, admin_d=None):
    if admin_d is None:
        raise ValueError("ATCO admin fee unknown (fixed-plan page not parsed yet)")
    e = need(r"Floating Electricity 2-year plan Electricity Plan ([\d.]+)¢\* / kWh.*?Plus ([\d.]+)¢/kWh service fee", t, "ATCO floating electricity")
    g = need(r"Natural Gas Plan \$([\d.]+)\* / GJ.*?Plus \$([\d.]+)/GJ service fee", t, "ATCO floating gas")
    note = "Last month's market average {} + {} service fee. Billed rate differs; changes monthly."
    common = dict(retailer="ATCO Energy", type="variable", plan="2-year floating", term_label="2 yr", indicative=True, source_url=url,
                  admin_monthly=admin_d * DAYS_PER_MONTH, admin_text=f"${admin_d:.2f}/day per site (from ATCO's fixed-plan page)")
    return [plan(id="atco-e-float", fuel="electricity", rate=round(float(e.group(1)) + float(e.group(2)), 3),
                 rate_note=note.format(e.group(1) + "¢", e.group(2) + "¢/kWh"), **common),
            plan(id="atco-g-float", fuel="gas", rate=round(float(g.group(1)) + float(g.group(2)), 3),
                 rate_note=note.format("$" + g.group(1), "$" + g.group(2) + "/GJ"), **common)]


# ---------------------------------------------------------------- Encor by EPCOR
def p_encor(t, url):
    admin_c = float(need(r"daily administration fee of (\d+)¢ per site", t, "Encor admin").group(1))
    admin = admin_c / 100 * DAYS_PER_MONTH
    at = f"${admin_c/100:.2f}/day per site"
    canc = "Change or cancel anytime, penalty-free (per retailer)."
    ef = need(r"Fixed electricity Provided by Encor by EPCOR ([\d.]+)¢ per kWh", t, "Encor fixed electricity")
    ev = need(r"Floating electricity Provided by Encor by EPCOR ([\d.]+)¢ per kWh", t, "Encor floating electricity")
    gf = need(r"Fixed natural gas Provided by Encor by EPCOR \$([\d.]+) per GJ", t, "Encor fixed gas")
    gv = need(r"Floating natural gas Provided by Encor by EPCOR \$([\d.]+) per GJ", t, "Encor floating gas")
    fl = "Floating rate posted is based on the previous period (per retailer). Changes monthly."
    c = dict(retailer="Encor by EPCOR", admin_monthly=admin, admin_text=at, source_url=url, cancellation=canc, cancellation_fee=0)
    return [plan(id="encor-e-2y", fuel="electricity", plan="2-year fixed", rate=float(ef.group(1)), term_months=24, term_label="2 yr", **c),
            plan(id="encor-e-float", fuel="electricity", type="variable", plan="2-year floating", rate=float(ev.group(1)), term_label="2 yr", indicative=True, rate_note=fl, **c),
            plan(id="encor-g-2y", fuel="gas", plan="2-year fixed", rate=float(gf.group(1)), term_months=24, term_label="2 yr", **c),
            plan(id="encor-g-float", fuel="gas", type="variable", plan="2-year floating", rate=float(gv.group(1)), term_label="2 yr", indicative=True, rate_note=fl, **c)]


# ---------------------------------------------------------------- Peace Power
def p_peace(t, url):
    out = []
    v = need(r"Electricity VARIABLE RATE \+ ¢([\d.]+) over spot price 1-year rolling average ([\d.]+)¢/kWh.*?Admin Fee: \$([\d.]+) per metered site", t, "Peace variable electricity")
    out.append(plan(id="peace-e-var", retailer="Peace Power", fuel="electricity", type="variable", plan="Variable", rate=float(v.group(2)),
                    term_label="No term", indicative=True, rate_note=f"Spot price + {v.group(1)}¢/kWh. Shown: the retailer's 1-year rolling average. Changes monthly.",
                    admin_monthly=float(v.group(3)), admin_text=f"${v.group(3)}/month per site", source_url=url,
                    cancellation="No cancellation fee (per retailer).", cancellation_fee=0))
    for r, y, a in re.findall(r"Electricity FIXED RATE ¢ ([\d.]+) /kWh (\d) Year Fixed Rate.*?Admin Fee: \$([\d.]+) per metered site", t):
        out.append(plan(id=f"peace-e-{y}y", retailer="Peace Power", fuel="electricity", plan=f"{y}-year fixed", rate=float(r),
                        term_months=12 * int(y), term_label=f"{y} yr", admin_monthly=float(a), admin_text=f"${a}/month per site", source_url=url))
    gv = re.search(r"NATURAL GAS VARIABLE RATE \+ \$([\d.]+) over spot price 1-year rolling average \$([\d.]+)/GJ.*?Admin Fee: \$([\d.]+)/month", t)
    if gv:
        out.append(plan(id="peace-g-var", retailer="Peace Power", fuel="gas", type="variable", plan="Variable", rate=float(gv.group(2)),
                        term_label="No term", indicative=True, rate_note=f"Spot price + ${gv.group(1)}/GJ. Shown: the retailer's 1-year rolling average. Changes monthly.",
                        admin_monthly=float(gv.group(3)), admin_text=f"${gv.group(3)}/month per site", source_url=url,
                        cancellation="No cancellation fee (per retailer).", cancellation_fee=0))
    gf = re.search(r"NATURAL GAS FIXED RATE \$([\d.]+) GJ Guaranteed Rate (\d) Year Term.*?Admin Fee: \$([\d.]+)/day", t)
    if gf:
        out.append(plan(id="peace-g-fix", retailer="Peace Power", fuel="gas", plan=f"{gf.group(2)}-year fixed", rate=float(gf.group(1)),
                        term_months=12 * int(gf.group(2)), term_label=f"{gf.group(2)} yr", admin_monthly=float(gf.group(3)) * DAYS_PER_MONTH,
                        admin_text=f"${gf.group(3)}/day per site", source_url=url))
    return out


# ---------------------------------------------------------------- Default (benchmark) rates
def p_uca_defaults(t, url):
    """Official default rates published by the UCA (this page, not the Cost Comparison Tool)."""
    m = need(r"Until Dec\. 31 (\d{4}) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)", t, "RoLR table")
    seg = need(r"(\d{4}) Natural Gas Regulated Rates in \$/GJ Retailer Direct Energy Regulated Services (.*?) (?:\d{4} Natural Gas Regulated Rates|Share )", t, "DRT table")
    months = re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December) ([\d.]+) ([\d.]+)", seg.group(2))
    if not months: raise ValueError("no DRT months")
    mon, ders, apex = months[-1]
    hist = []
    for yr, body in re.findall(r"(\d{4}) Natural Gas Regulated Rates in \$/GJ Retailer Direct Energy Regulated Services (.*?)(?= \d{4} Natural Gas Regulated Rates| Share )", t):
        for mo, d, a in re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December) ([\d.]+) ([\d.]+)", body):
            hist.append({"year": int(yr), "month": mo, "ders": float(d), "apex": float(a)})
    return {"drt_history": hist,"rolr_until": m.group(1), "rolr": {"epcor": float(m.group(2)), "fortis": float(m.group(3)), "enmax": float(m.group(4)), "ders": float(m.group(5))},
            "drt": {"month": f"{mon} {seg.group(1)}", "ders": float(ders), "apex": float(apex)}}


def p_epcor_rolr(t, url):
    m = need(r"Current rates and fees - (\w+ \d{4}) Rate of Last Resort Electricity Rate \(¢ per kWh\) Administration Charges \(\$ per day\) ([\d.]+) ¢ \$([\d.]+)", t, "EPCOR RoLR")
    return {"month": m.group(1), "rate": float(m.group(2)), "admin_day": float(m.group(3))}


def p_enmax_rolr_pdf(data, url):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(data); path = f.name
    try:
        txt = clean(subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout)
    finally:
        os.unlink(path)
    m = need(r"Residential .*?Energy Charge \$([\d.]+) per kWh Administration Charge \$([\d.]+) per day", txt, "ENMAX RoLR residential")
    yr = re.search(r"(?:INTERIM )?(\d{4}) REGULATED RATE TARIFF", txt)
    return {"rate": round(float(m.group(1)) * 100, 3), "admin_day": float(m.group(2)), "tariff_year": yr.group(1) if yr else ""}


def p_de_regulated_gas(t, url):
    m = need(r"\*\*Plus a daily administration fee of \$([\d.]+) per site", t, "DERS gas admin")
    return {"admin_day": float(m.group(1))}


def _plausible_cents(rate, what):
    if not (0.5 <= rate <= 80):
        raise ValueError(f"implausible {what} {rate}")
    return rate


def _meter_table(seg, what):
    rows = re.findall(r"(\d+)\s*mm(?:\s*\([^)]*\))?\s*\$([\d.]+)", seg)
    if not rows:
        raise ValueError(f"no meter rows for {what}")
    out = {}
    for mm, rate in rows:
        out[int(mm)] = float(rate)
    return out


# ---------------------------------------------------------------- Edmonton water (EPCOR)
def p_epcor_water(t, url):
    """Residential water, wastewater, sanitary and stormwater from EPCOR's Edmonton rate page."""
    if t.count("0 m3 - 10.0 m3") != 1:
        raise ValueError("water tier table was not unique")
    tiers = need(
        r"0 m3 - ([\d.]+) m3 \$([\d.]+) ([\d.]+) m3 - ([\d.]+) m3 \$([\d.]+) Over ([\d.]+) m3 \$([\d.]+)",
        t, "Edmonton water tiers")
    water_fixed = _meter_table(need(
        r"Fixed Daily Service Charge Per Meter Size\s*2026 Daily Rate (.*?) Public Fire Protection",
        t, "water fixed charges").group(1), "water fixed")
    fire = _meter_table(need(
        r"Public Fire Protection Monthly Charge Per Meter Size\s*2026 Daily Rate (.*?) Wastewater treatment",
        t, "fire protection").group(1), "fire protection")
    ww = need(
        r"Wastewater treatment rates Residential Consumption Charge \(per m3\)\s*2026 Rate All consumption \$([\d.]+) Fixed daily service charge 2026 Rate Fixed daily service charge \$([\d.]+)",
        t, "wastewater treatment")
    san_var = float(need(r"Residential \$([\d.]+) per m3 Sewer collection and transmission—fixed rate", t, "sanitary variable").group(1))
    san_fixed = _meter_table(need(
        r"Sewer collection and transmission—fixed rate Meter Size 2026 Daily Rate (.*?) Stormwater charges",
        t, "sanitary fixed").group(1), "sanitary fixed")
    storm_hits = re.findall(r"daily rate as of ([A-Za-z]+ \d+, \d{4}) is \$(\d+\.\d+)", t)
    if not storm_hits or len(set(storm_hits)) != 1:
        raise ValueError("stormwater daily rate missing or inconsistent")
    usage_bill = need(r"Most customers pay about \$(\d+) per month for water usage on an average, single-family residential household bill", t, "average usage bill")
    eff = need(r"These rates are effective ([A-Za-z]+ \d+, \d{4})\.", t, "effective date")
    if 15 not in water_fixed or 15 not in fire or 15 not in san_fixed:
        raise ValueError("15mm residential meter row missing")
    return {
        "city": "edmonton",
        "provider": "EPCOR Water Services and Drainage (City of Edmonton utility)",
        "effective": eff.group(1),
        "billing": "Fixed charges on this page are daily as of the effective date (they used to be monthly). A bill varies with the number of days in the period.",
        "water_tiers_m3": [
            {"up_to": float(tiers.group(1)), "rate": float(tiers.group(2))},
            {"up_to": float(tiers.group(4)), "rate": float(tiers.group(5))},
            {"up_to": None, "rate": float(tiers.group(7))},
        ],
        "meters_daily": {
            str(mm): {
                "water_fixed": water_fixed.get(mm),
                "fire_protection": fire.get(mm),
                "sanitary_fixed": san_fixed.get(mm),
            } for mm in sorted(set(water_fixed) | set(fire) | set(san_fixed))
        },
        "wastewater_treatment_per_m3": float(ww.group(1)),
        "wastewater_treatment_daily": float(ww.group(2)),
        "sanitary_per_m3": san_var,
        "stormwater": {
            "formula": "A × I × R × daily rate (property area in m² × development intensity × runoff coefficient × rate)",
            "daily_rate": float(storm_hits[0][1]),
            "as_of": storm_hits[0][0],
            "note": "Not a flat or per-m³ charge. Intensity defaults to 1.0. The runoff coefficient depends on zoning and is not a single residential number on this page, so a typical stormwater bill is not estimated.",
        },
        "average_usage_note": f"Most customers pay about ${usage_bill.group(1)} per month for water usage on an average single-family bill, before fixed fees. EPCOR does not print that average in cubic metres.",
        "source_url": url,
    }


def p_edmonton_waste(t, url):
    m = need(
        r"Monthly waste utility rates as of (January 1, \d{4}) are: Curbside Collection: "
        r"\$([\d.]+): Small \(120 L\) garbage cart "
        r"\$([\d.]+): Large \(240 L\) garbage cart "
        r"\$([\d.]+): Excess \(360 L\) garbage cart "
        r"Apartment and Condo Collection: \$([\d.]+)",
        t, "Edmonton waste utility rates")
    return {
        "city": "edmonton",
        "provider": "City of Edmonton Waste Services (charged on the EPCOR bill)",
        "as_of": m.group(1),
        "curbside": [
            {"id": "small", "label": "Small (120 L) garbage cart", "monthly": float(m.group(2))},
            {"id": "large", "label": "Large (240 L) garbage cart", "monthly": float(m.group(3))},
            {"id": "excess", "label": "Excess (360 L) garbage cart", "monthly": float(m.group(4)),
             "note": "Limited to home health-care waste or households of 7 or more registered in the Excess Garbage Cart Program."},
        ],
        "apartment_monthly": float(m.group(5)),
        "note": "A flat monthly charge, not based on water use. Recycling costs moved to producers under Extended Producer Responsibility on April 1, 2025, which is why the City says the rate is lower.",
        "source_url": url,
    }


def p_calgary_water(t, url):
    m = need(
        r"Residential Metered Customers \(Based on household using (\d+)m3 per month\) "
        r"2025 2026 % change Impact on monthly bill 2026 monthly bill "
        r"Water treatment and supply Usage rate per cubic metre \(1 cubic metre = 1000 litres\) "
        r"\$([\d.]+) \$([\d.]+) \+[0-9.]+% \+\$[\d.]+ \$([\d.]+) "
        r"Service charge per 30 days \$([\d.]+) \$([\d.]+) "
        r"Wastewater collection and treatment Usage rate per cubic metre\*? \(1 cubic metre = 1000 litres\) "
        r"\$([\d.]+) \$([\d.]+) \+[0-9.]+% \+\$[\d.]+ \$([\d.]+) "
        r"Service charge per 30 days \$([\d.]+) \$([\d.]+) "
        r"Stormwater management Service charge per 30 days "
        r"\$([\d.]+) \$([\d.]+) \+[0-9.]+% \+\$[\d.]+ \$([\d.]+)",
        t, "Calgary 2026 residential metered rates")
    factor = float(need(r"wastewater usage is your water usage multiplied by (0\.\d+)", t, "wastewater return factor").group(1))
    m3 = int(m.group(1))
    water_rate, water_bill = float(m.group(3)), float(m.group(4))
    water_fixed = float(m.group(6))
    ww_rate, ww_bill = float(m.group(8)), float(m.group(9))
    ww_fixed = float(m.group(11))
    storm, storm_bill = float(m.group(13)), float(m.group(14))
    calc_w = round(m3 * water_rate + water_fixed, 2)
    calc_ww = round(m3 * factor * ww_rate + ww_fixed, 2)
    if abs(calc_w - water_bill) > 0.02 or abs(calc_ww - ww_bill) > 0.02 or abs(storm - storm_bill) > 0.02:
        raise ValueError(f"Calgary bill check failed: water {calc_w} vs {water_bill}, wastewater {calc_ww} vs {ww_bill}")
    flat = None
    fm = re.search(
        r"\$ per thousand square feet of actual lot area\* 2023: ([\d.]+) 2024: [\d.]+ 2025: [\d.]+ 2026: ([\d.]+) "
        r"\$ per thousand square feet of gross building area\* 2023: ([\d.]+) 2024: [\d.]+ 2025: [\d.]+ 2026: ([\d.]+)",
        t)
    wm = re.search(r"Percentage of water charge for flat rate customers 2023: [\d.]+% 2024: [\d.]+% 2025: [\d.]+% 2026: ([\d.]+)%", t)
    if fm and wm:
        flat = {
            "lot_per_1000_sqft": float(fm.group(2)),
            "building_per_1000_sqft": float(fm.group(4)),
            "wastewater_percent_of_water": float(wm.group(1)),
            "stormwater_per_30_days": storm,
            "note": "Unmetered homes. The City's worked example uses these 2026 figures. Minimum monthly water rate and the exact lot rules are on the City page.",
        }
    return {
        "city": "calgary",
        "provider": "City of Calgary water utility",
        "example_m3": m3,
        "example_label": f"The City illustrates a residential metered bill at {m3} m³ per month.",
        "period": "Service charges are published per 30 days. The City's '2026 monthly bill' column uses that 30-day charge.",
        "water_per_m3": water_rate,
        "water_fixed_per_30_days": water_fixed,
        "water_example_bill": water_bill,
        "wastewater_per_m3": ww_rate,
        "wastewater_fixed_per_30_days": ww_fixed,
        "wastewater_return_factor": factor,
        "wastewater_example_bill": ww_bill,
        "stormwater_per_30_days": storm,
        "flat_rate": flat,
        "source_url": url,
    }


def p_epcor_water_tips(t, url):
    """A few indoor water-saving figures printed by EPCOR. Raises if the numbers move."""
    need(r"less than 4\.7 L/min", t, "faucet tip")
    need(r"less than 7\.0 L/min", t, "shower-head tip")
    need(r"4\.8 litres or less per flush", t, "toilet tip")
    need(r"Cutting your shower time by just 2 minutes", t, "shower-time tip")
    return {"source_url": url, "tips": [
        "Turn off the tap while brushing, shaving or washing your face. When you replace a faucet aerator, EPCOR says to choose one under 4.7 L/min or labelled WaterSense.",
        "Take a shower instead of a bath. Five minutes is the ideal shower EPCOR names, and cutting a shower by 2 minutes makes a noticeable difference. A WaterSense shower head is under 7.0 L/min.",
        "Check the toilet for leaks with food colouring in the tank (colour in the bowl after 15–20 minutes means a leak). A replacement toilet should use 4.8 litres or less per flush.",
        "Check faucets, pipes, taps and hoses for drips. EPCOR says a hardware store can fix most minor leaks.",
    ]}


# ---------------------------------------------------------------- Solar Club (UTILITYnet signup pages) and ENMAX
def p_utilitynet_solar(block, full_text, url, retailer):
    """HI/LO Solar Club, pre-solar and the variable rate printed in the residential solar block.

    Export and import on a single Solar Club row are the HI and LO rates you switch between.
    They are not both active in the same billing period.
    """
    pair = need(
        r"(\d) Year \(Guaranteed until ([^)]+)\) ([\d.]+) ¢/kWh (LO-[\w-]+) MicroGen Solar Club Rate \( Expires ([^)]+) \) "
        r"(.*?) Sign Up ([\d.]+) ¢/kWh (HI-[\w-]+) MicroGen Solar Club Rate \( Expires ([^)]+) \) (.*?) Sign Up",
        block, "Solar Club HI/LO rates")
    lo_rate = _plausible_cents(float(pair.group(3)), "LO rate")
    hi_rate = _plausible_cents(float(pair.group(7)), "HI rate")
    admin = float(need(r"Administration Fees \$([\d.]+) per metered site", block, "solar admin").group(1))
    if not (0 <= admin <= 40):
        raise ValueError(f"implausible solar admin {admin}")
    years, until = int(pair.group(1)), pair.group(2).strip()
    lo_note, hi_note = clean(pair.group(6)), clean(pair.group(10))
    sw = re.search(r"Customers can switch to the Solar Club fixed HI and/or LO rate anytime.*?beneficial\.", block)
    if not sw:
        sw = re.search(r"Customers can switch to the Solar Club fixed HI and/or LO rate anytime.*?\.", block)
    switch = clean(sw.group(0)) if sw else "Not stated on the solar rate block."
    qual = re.search(r"To qualify for all of the benefits included in this Solar Club.*?\. ", block)
    club_eligibility = clean(qual.group(0)).strip() if qual else "Small micro-generator. See the retailer page for the exact qualifier."
    area = re.search(
        r"We can service all locations in Alberta except for the City of Medicine Hat and some specific REAs \. The specific REAs we cannot service are: (.*?)\.",
        full_text)
    area_txt = ""
    if area:
        area_txt = " Service area: all of Alberta except the City of Medicine Hat and these REAs: " + clean(area.group(1)) + "."
    club_eligibility += area_txt
    term = f"{years} years, guaranteed until {until}"
    admin_text = f"${admin:.2f}/month per site"
    over = re.search(
        r"Customers who consume over ([\d,]+) kWh per month will be charged an additional \$(\d+\.\d+)/kWh",
        block)
    if over:
        admin_text += f". Above {over.group(1)} kWh in a month: extra ${over.group(2)}/kWh"
    common = dict(retailer=retailer, admin_monthly=admin, admin_text=admin_text, source_url=url,
                  cancellation="Not stated on the solar rate block.", cancellation_fee=None)
    rows = [dict(
        id_suffix="solar-club", plan="Solar Club HI/LO", plan_kind="solar_club",
        export_rate=hi_rate, import_rate=lo_rate,
        export_text=f"{hi_rate:.2f}¢/kWh HI rate ({pair.group(8).strip()})",
        import_text=f"{lo_rate:.2f}¢/kWh LO rate ({pair.group(4).strip()})",
        switch_rules=switch + " The page describes the LO rate as the one for importing more than you export"
            + (f" ({clean(lo_note)})" if lo_note.strip() else "")
            + ", and the HI rate as the one for exporting more than you import"
            + (f" ({clean(hi_note)})" if hi_note.strip() else "") + ".",
        rate_note="While one of these rates is active, that rate is your retail rate for the billing period. Small micro-generators are credited at their retail rate, so that period's export credit uses the active rate rather than a blend of HI and LO.",
        eligibility=club_eligibility,
        indicative=False, term_label=term, term_months=years * 12, **common)]
    pre = re.search(r"Pre-Solar Rate ([\d.]+) ¢/kWh Pre-Solar Rate \(.*?\) \*(Pre-Solar Rate is valid for (\d+) days.*?)(?:Sign Up|$)", block)
    if pre:
        rows.append(dict(
            id_suffix="solar-presolar", plan="Pre-Solar", plan_kind="presolar",
            export_rate=None, import_rate=_plausible_cents(float(pre.group(1)), "pre-solar"),
            export_text="n/a (site is not a micro-generator yet, so there is no export credit)",
            import_text=f"{float(pre.group(1)):.2f}¢/kWh",
            switch_rules="Not a high/low export plan. " + clean(pre.group(2)),
            rate_note="For customers waiting on installation or a micro-generation flag.",
            eligibility="Signed installation contract, as printed on the pre-solar rate. Not an export plan yet." + area_txt,
            indicative=False, term_label=f"{pre.group(3)} days from enrolment", term_months=None, **common))
    var = re.search(
        r"Variable Market Price \+ ([\d.]+) cents/kWh Transaction Fee.*?30-Day Moving Average:\s*([\d.]+) ¢/kWh.*?as of (\w+ \d+, \d{4})",
        block)
    if var:
        avg = _plausible_cents(float(var.group(2)), "solar variable average")
        rows.append(dict(
            id_suffix="solar-var", plan="Variable (solar page)", plan_kind="variable",
            export_rate=avg, import_rate=avg,
            export_text=f"{avg:.2f}¢/kWh 30-day average",
            import_text=f"{avg:.2f}¢/kWh 30-day average",
            switch_rules=switch,
            rate_note=f"Market price + {var.group(1)}¢/kWh. Shown figure is the retailer's 30-day average including the fee, as of {var.group(3)}. It changes. Export credit while you stay on this rate is this retail rate.",
            eligibility="Printed on the retailer's solar rate page. The variable line says it is not eligible for cash back." + area_txt,
            indicative=True, term_label="No fixed term", term_months=None, **common))
    return rows


def p_enmax_solar(t, url):
    m = need(r"access to a ([\d.]+)¢/kWh rate", t, "ENMAX seasonal solar rate")
    rate = _plausible_cents(float(m.group(1)), "ENMAX solar rate")
    alt = re.search(r"(\d+\.\d+)¢\s*/\s*kWh", t)
    if alt and abs(float(alt.group(1)) - rate) > 0.05:
        raise ValueError("ENMAX solar page prints two different solar rates")
    need(r"less than 150\s*kW", t, "ENMAX 150 kW limit")
    need(r"Your active rate applies to both the electricity you buy and the credits", t, "ENMAX same-rate rule")
    return [dict(
        id_suffix="solar-seasonal", retailer="ENMAX (Easymax)", plan="Easymax Seasonal Solar", plan_kind="seasonal",
        export_rate=rate, import_rate=None,
        export_text=f"{rate:.1f}¢/kWh while Seasonal Solar is the active rate",
        import_text="Your Easymax fixed or floating rate while that plan is the active rate. The solar page does not reprint the cents.",
        switch_rules=("You switch yourself in the online account (ENMAX will not change it automatically) and can schedule a change up to 30 days ahead. "
                      "The page recommends the higher rate in sunnier months when you export more than you use, and your regular Easymax rate when you draw more than you produce. "
                      "The active rate applies to both electricity you buy and credits for electricity you send back."),
        term_label="Same term as the Easymax fixed or floating plan you choose",
        term_months=None,
        admin_monthly=None, admin_text="Not stated on the solar page.",
        cancellation="Not stated on the solar page.", cancellation_fee=None,
        eligibility=("Bi-directional residential meter, an Easymax electricity plan, small solar micro-generator under 150 kW, "
                     "and the distributor has activated the site. A separate 'is solar right for my home' note on the page says a single detached or semi-attached home."),
        rate_note="There is no separate low solar rate. Winter imports use whatever Easymax rate you picked.",
        indicative=False, source_url=url,
    )]


# ---------------------------------------------------------------- Rebates / programs (status must be printed on the page)
def p_edmonton_ceip(t, url):
    if not re.search(r"waitlist", t, re.I):
        raise ValueError("Edmonton CEIP status word not found")
    need(r"minimum of \$3,000 and up to \$50,000", t, "Edmonton CEIP residential cap")
    need(r"Current tranche 6\.00%", t, "Edmonton CEIP interest")
    need(r"up to 20 years", t, "Edmonton CEIP term")
    need(r"there are no available rebates", t, "Edmonton rebate sentence")
    return {
        "id": "edmonton-ceip", "name": "City of Edmonton Clean Energy Improvement Program (CEIP)",
        "status": "waitlist", "status_label": "Waitlist (residential pre-qualification)",
        "summary": ("Financing, not a rebate. Residential and multi-unit owners: $3,000 to $50,000, up to 100% of project cost, "
                    "fixed 6.00% in the current tranche, repayment up to 20 years (or the upgrade's useful life, if shorter) on the property tax bill. "
                    "The City says pre-qualification goes on a waitlist because the program is nearing capacity, and that there is no City of Edmonton residential rebate right now. "
                    "Solar PV is an eligible upgrade. At least three upgrades are required unless the property can reach net zero with fewer, or the owner has used CEIP on it before."),
        "source_url": url,
    }


def p_calgary_ceip(t, url):
    need(r"Application intake closed", t, "Calgary CEIP closed banner")
    need(r"closed until winter 2026/2027", t, "Calgary CEIP reopen window")
    need(r"maximum of \$50,000", t, "Calgary CEIP cap")
    need(r"6\.00% - 6\.10%", t, "Calgary CEIP interest range")
    need(r"up to 20 years", t, "Calgary CEIP term")
    need(r"CEIP is not a rebate program", t, "Calgary not-a-rebate line")
    return {
        "id": "calgary-ceip", "name": "City of Calgary Clean Energy Improvement Program (residential)",
        "status": "closed", "status_label": "Intake closed until winter 2026/2027",
        "summary": ("Financing, not a rebate. Up to 100% of project costs, maximum $50,000, repaid on the property tax bill for up to 20 years. "
                    "The City estimates the fixed interest rate at 6.00%–6.10% when you sign, and says it can be higher or lower. "
                    "The balance can be paid off without a penalty or transferred to a buyer. Low-rise residential properties in Calgary."),
        "source_url": url,
    }


def p_ceip_admin_table(t, url):
    """Alberta Municipalities publishes the open/paused/waitlist table for every CEIP."""
    yyc = need(r"City of Calgary – Residential Next intake: ([A-Za-z.]+ \d{4}) \*Estimated ([\d.]+) – ([\d.]+)%", t, "Calgary row")
    yeg = need(r"City of Edmonton – Residential (Waitlisting|Open|Paused|Closed) ([\d.]+)%", t, "Edmonton row")
    return {
        "id": "ceip-admin-table", "name": "Alberta Municipalities CEIP status table",
        "status": "reference",
        "status_label": "Program-administrator status table",
        "summary": (f"City of Calgary residential: next intake {yyc.group(1)}, estimated interest {yyc.group(2)}–{yyc.group(3)}%, no CEIP rebate. "
                    f"City of Edmonton residential: {yeg.group(1).lower()}, interest {yeg.group(2)}%, no CEIP rebate. "
                    "Other Alberta municipalities on the same table have their own status. This row is the administrator's list, not a rate of our own."),
        "calgary_next_intake": yyc.group(1),
        "edmonton_residential_status": yeg.group(1).lower(),
        "source_url": url,
    }


def p_greener_loan(t, url):
    if not re.search(r"This program is closed", t, re.I):
        raise ValueError("Greener Homes Loan does not say it is closed")
    need(r"New loan applications cannot be approved", t, "loan closure line")
    need(r"Maximum: \$40,000", t, "loan maximum")
    need(r"10 years, interest-free", t, "loan term")
    return {
        "id": "greener-loan", "name": "Canada Greener Homes Loan",
        "status": "ended", "status_label": "Ended (funding fully committed)",
        "summary": ("Natural Resources Canada says this program is closed and new applications cannot be approved. "
                    "Loans already approved are unchanged. What the closed program offered, still printed on the page: interest-free financing, minimum $5,000, maximum $40,000, 10-year repayment, unsecured."),
        "source_url": url,
    }


def p_greener_grant(t, url):
    need(r"Closed: Canada Greener Homes Grant THIS PROGRAM IS CLOSED December 31, 2025, was the last day to submit your documents", t, "grant closure")
    return {
        "id": "greener-grant", "name": "Canada Greener Homes Grant",
        "status": "ended", "status_label": "Ended (last documents December 31, 2025)",
        "summary": "Natural Resources Canada marks the grant closed. December 31, 2025 was the last day to submit documents. The page does not print a current grant amount.",
        "source_url": url,
    }


def p_uca_solar_programs(t, url):
    """What the UCA grants page actually prints. No extra programs are inferred."""
    sharp = need(r"SHARP provides low-interest home equity loans \(up to \$40,000\)", t, "SHARP")
    closed = need(r"The Canada Greener Homes Loan closed on ([A-Za-z]+ \d+(?:st|nd|rd|th)?, \d{4})", t, "UCA loan date")
    cmhc = re.search(r"up to 25% mortgage insurance premium refund.*?minimum \$20,000", t)
    ofep = re.search(r"OFEP offers up to \$0\.60 per watt, capped at 25% of project cost or \$50,000", t)
    era = re.search(r"up to \$250,000 per project for commercial and farm", t)
    if not cmhc or not ofep or not era:
        raise ValueError("UCA program figures missing")
    return {
        "id": "uca-programs", "name": "Utilities Consumer Advocate: renewable energy grants and programs",
        "status": "reference", "status_label": "UCA's own list",
        "summary": ("UCA says the Canada Greener Homes Loan closed on " + closed.group(1) + ". "
                    "SHARP, which UCA lists under provincial programs: " + sharp.group(0) + " for repairs or energy efficiency upgrades like furnaces, insulation and windows, repaid when the home is sold. UCA does not call SHARP a solar rebate. "
                    "CMHC Eco Improvement, as printed by the UCA: up to a 25% mortgage-insurance premium refund, minimum $20,000 of eligible upgrades including renewable energy. "
                    "Not residential: On-Farm Efficiency Program up to $0.60/W, capped at 25% of cost or $50,000; Emissions Reduction Alberta Energy Savings for Business up to $250,000 per commercial or farm project."),
        "source_url": url,
    }


def p_uca_no_provincial_solar(t, url):
    m = need(r"Currently, Alberta does not offer provincial programs for solar installations", t, "no provincial solar rebate")
    return {
        "id": "alberta-no-provincial-solar", "name": "Alberta provincial solar programs",
        "status": "none", "status_label": "No provincial solar program (UCA)",
        "summary": m.group(0) + ", but some municipal and federal programs may provide rebates, incentives or grants. Confirm on the official program site.",
        "source_url": url,
    }


def p_nrcan_pv(rows, page_url, query_url):
    """rows: attributes from the NRCan municipality layer. Annual = time period 13."""
    want = "South-facing with latitude tilt"
    out = []
    for city in ("Edmonton", "Calgary"):
        hit = [r for r in rows if r.get("Municipality") == city and r.get("Orientation") == want and int(r.get("time") or 0) == 13
               and r.get("Variable") == "Photovoltaic potential (kWh/kWp)"]
        if len(hit) != 1:
            raise ValueError(f"NRCan annual PV for {city} not unique ({len(hit)})")
        val = float(hit[0]["Value"])
        if not (800 <= val <= 2000):
            raise ValueError(f"implausible PV potential {val}")
        out.append({
            "city": city.lower(),
            "city_label": city,
            "kwh_per_kw": val,
            "orientation": want,
            "period": "Annual (NRCan time period 13)",
            "unit": "kWh/kWp (kWh per kW of installed DC capacity)",
            "source_url": query_url,
            "source_page": page_url,
            "source_name": "Natural Resources Canada, photovoltaic potential map, municipality layer",
        })
    return out


def solar_rates_absent(text, retailer, url, reason):
    """Used only after a successful fetch. Never invents a rate.

    A cents figure counts only when it sits next to the words solar or micro-generation.
    Ordinary electricity rates on the same page are not solar rates.
    """
    for m in re.finditer(r"solar|micro-?generation|microgen", text, re.I):
        window = text[max(0, m.start() - 160):m.end() + 200]
        if re.search(r"\d+(?:\.\d+)?\s*¢", window):
            raise ValueError(f"{retailer} page now prints a cents figure beside solar or micro-generation; add a parser instead of listing it as unpublished")
    return {"retailer": retailer, "url": url, "reason": reason}


def p_uca_installed_cost(t, url):
    m = need(r"market prices average \$([\d.]+)[–-]\$([\d.]+)/Watt installed, or \$([\d,]+)[–-]\$([\d,]+) for a (\d+) kW system", t, "UCA installed cost")
    low, high = float(m.group(1)), float(m.group(2))
    if not (0.5 <= low < high <= 15):
        raise ValueError("implausible installed-cost range")
    return {
        "low_per_watt": low,
        "high_per_watt": high,
        "example_kw": int(m.group(5)),
        "example_low": int(m.group(3).replace(",", "")),
        "example_high": int(m.group(4).replace(",", "")),
        "default_per_watt": round((low + high) / 2, 2),
        "default_note": "The calculator starts at the midpoint of this published range. The midpoint is arithmetic, not a separate quoted price.",
        "source_url": url,
    }
