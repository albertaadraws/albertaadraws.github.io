#!/usr/bin/env python3
"""Draft the weekly newsletter as Markdown in newsletter/YYYY-MM-DD.md (for pasting into beehiiv).
Nothing is sent. Rankings by cost only; partner links are never inserted here automatically."""
import datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build as B

def main():
    today = dt.datetime.now(B.TZ).date()
    since = (today - dt.timedelta(days=7)).isoformat()
    url = B.SITE_URL + B.BASE
    L = [f"# Alberta power & gas: best rates, week of {today.strftime('%B %-d, %Y')}", "",
         f"Prices from retailers' own pages, checked {B.fdate(B.UPDATED)}. Estimates at typical use (600 kWh and 10 GJ a month, per the UCA), energy + retailer admin fees only.", ""]
    for fuel, use in (("electricity", "600 kWh"), ("gas", "10 GJ")):
        b = B.bench(fuel, "edmonton")
        L += [f"## Cheapest fixed {'electricity' if fuel=='electricity' else 'natural gas'} (no conditions)", ""]
        for i, p in enumerate(B.ranked(fuel, variable=False, conditional=False)[:3], 1):
            d = B.cost(b) - B.cost(p)
            L.append(f"{i}. **{p['retailer']}**, {p['plan']}: {B.rate_txt(p)} + {p['admin_text']} admin, about {B.money(B.cost(p))}/month at {use} "
                     f"({'saves ' + B.money(d) if d >= 0 else B.money(-d) + ' more'} vs the default). [Source]({p['source_url']})")
        cond = B.ranked(fuel, variable=False, conditional=True)[0]
        if cond["conditions"]:
            L += ["", f"Lowest with conditions: **{cond['retailer']}** {cond['plan']} at {B.rate_txt(cond)} ({cond['conditions']})"]
        L.append("")
    L += ["## The default rates", ""]
    for k in ("rolr_edmonton", "rolr_calgary", "gas_default"):
        b = B.DEF.get(k)
        if b: L.append(f"- **{b['retailer']}** ({b['plan']}): {B.rate_txt(b)} + {b['admin_text']} admin. {b['term_label']}.")
    g = B.DEF.get("gas_default", {})
    if g.get("avg12"): L.append(f"- Default gas averaged ${g['avg12']:.3f}/GJ over {g['avg12_range']}; it resets monthly and usually rises in winter.")
    days = (dt.date(2027, 1, 1) - today).days
    if days > 0:
        L += ["", f"**{days} days until the Rate of Last Resort resets (Jan 1, 2027).** The new two-year rate must be filed at least 30 days before, and an adjustment normally can't exceed 10%. Leaving the RoLR has no penalty. [What it means]({url}/rate-of-last-resort-2027/)"]
    ch = [c for c in B.CHANGES if c["date"] >= since]
    L += ["", "## What changed this week", ""]
    if ch:
        for c in ch[-15:]:
            unit = "¢/kWh" if c["fuel"] == "electricity" else "$/GJ"
            t = {"rate": f"{c.get('old')} → {c.get('new')} {unit}", "default": f"{c.get('old')} → {c.get('new')} {unit}", "new": f"new at {c.get('new')} {unit}", "removed": "no longer listed"}[c["kind"]]
            L.append(f"- {c['date']}: {c['retailer']} {c['plan']} ({c['fuel']}): {t}")
    else:
        L.append("- No price changes on the plans we track this week.")
    L += ["", f"**[Run your own numbers in the calculator]({url}/#calculator)**", "", "---",
          "Independent and not affiliated with any retailer or government. Rankings are by cost only. Not financial advice. Confirm prices with the retailer before signing.",
          "You're getting this because you signed up at the Alberta Power & Gas Rate Tracker. Unsubscribe anytime."]
    os.makedirs(os.path.join(B.ROOT, "newsletter"), exist_ok=True)
    path = os.path.join(B.ROOT, "newsletter", f"{today.isoformat()}.md")
    open(path, "w").write("\n".join(L) + "\n")
    print("Draft written:", path)

if __name__ == "__main__":
    main()
