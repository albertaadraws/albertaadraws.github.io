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
