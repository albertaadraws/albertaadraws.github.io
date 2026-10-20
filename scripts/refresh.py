#!/usr/bin/env python3
"""
Refresh AAIP draw + pool data from the official Government of Alberta page.

  python3 scripts/refresh.py            # fetch live page, merge into data/*.json
  python3 scripts/refresh.py --offline  # re-parse the newest saved snapshot in data/raw/
  python3 scripts/refresh.py --no-pdf   # skip the yearly 'Draw Summary' PDF history import

Safe to run repeatedly (e.g. from a daily cron job):
  * draws are keyed by date + stream text, so re-runs never duplicate rows
  * draws that later disappear from the page (e.g. moved to the yearly PDF) are kept
  * pool snapshots are only appended when the page's numbers change
Exit code 0 = success (changed or not), 1 = fetch/parse failure (existing data left untouched).
"""
import argparse, datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, tempfile, urllib.request
from collections import Counter
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from aaip import SOURCE_URL, classify, slugify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
UA = "Mozilla/5.0 (compatible; AlbertaPRDrawTracker/0.1; personal research)"
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def log(*a):
    print("[refresh]", *a)


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-CA,en"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return body if binary else body.decode("utf-8", "replace")


def parse_date(s):
    s = " ".join(s.replace(",", ", ").split()).replace(" ,", ",")
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y"):
        try:
            return dt.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


def parse_int(s):
    s = (s or "").strip()
    m = re.fullmatch(r"[\d,]+", s)
    return int(s.replace(",", "")) if m else None


def parse_invites(s):
    s = " ".join((s or "").split())
    n = parse_int(s)
    lt10 = "less than 10" in s.lower()
    return n, lt10, s


def cells(tr):
    return [" ".join(c.get_text(" ", strip=True).split()) for c in tr.find_all(["th", "td"])]


def find_table(soup, header_pred):
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        if rows and header_pred(" | ".join(cells(rows[0])).lower()):
            return t
    return None


# ---------------------------------------------------------------- page parsing
def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {"draws": [], "pools": [], "nominations": [], "page_last_updated": None, "history_pdfs": []}

    lu = soup.find(string=re.compile(r"Last updated"))
    if lu:
        txt = lu.parent.parent.get_text(" ", strip=True) if lu.parent else str(lu)
        m = re.search(r"Last updated:?\s*([A-Z][a-z]+ \d{1,2}, \d{4})", txt)
        if m:
            d = parse_date(m.group(1))
            out["page_last_updated"] = d.isoformat() if d else None

    # Draw table
    t = find_table(soup, lambda h: "draw date" in h and "minimum score" in h)
    if t is None:
        raise RuntimeError("Draw table not found - page layout may have changed")
    seen = Counter()
    for tr in t.find_all("tr")[1:]:
        c = cells(tr)
        if len(c) < 4 or not c[0]:
            continue
        d = parse_date(c[0])
        if not d:
            log("WARN unparsed draw date:", c)
            continue
        n, lt10, inv_txt = parse_invites(c[3])
        key = (d.isoformat(), c[1])
        seen[key] += 1
        out["draws"].append(make_draw(d, c[1], parse_int(c[2]), c[2], n, lt10, inv_txt,
                                      source="aaip-processing-information", occurrence=seen[key]))

    # Expression of interest pool table
    t = find_table(soup, lambda h: "selection pool" in h)
    if t is not None:
        parent = ""
        for tr in t.find_all("tr")[1:]:
            c = cells(tr)
            if len(c) < 2:
                continue
            name = c[0].rstrip(":").strip()
            n = parse_int(c[1])
            if n is None and c[1] == "":
                parent = name  # e.g. "Alberta Express Entry Stream:" header row
                continue
            if name.lower().startswith("total"):
                out["pool_total"] = n
                continue
            full = f"{parent} – {name}" if parent else name
            out["pools"].append({"name": name, "group": parent or None, "full_name": full,
                                 "stream": classify(full if parent else name)["stream"], "count": n, "count_text": c[1]})
    else:
        log("WARN pool table not found")

    # Nomination allocation tables (one per stream section)
    for t in soup.find_all("table"):
        rows = t.find_all("tr")
        if not rows:
            continue
        hdr = cells(rows[0])
        hl = " | ".join(hdr).lower()
        if "nomination allocation" not in hl:
            continue
        h2 = t.find_previous("h2")
        section = h2.get_text(" ", strip=True) if h2 else ""
        if section.lower().startswith("processing summary"):
            section = "All streams (2026 summary)"
        for tr in rows[1:]:
            c = cells(tr)
            if len(c) != len(hdr):
                continue
            row = dict(zip(hdr, c))
            label = section
            if hdr[0].lower().startswith("pathway"):
                label = f"{section} – {c[0]}"
            out["nominations"].append({"name": label, "section": section, "values": row})

    # Yearly draw summary PDFs (history from previous years)
    for a in soup.find_all("a"):
        if "draw summary" in a.get_text(" ", strip=True).lower() and a.get("href"):
            href = a["href"]
            if href.startswith("/"):
                href = "https://www.alberta.ca" + href
            out["history_pdfs"].append({"label": a.get_text(" ", strip=True), "url": href})
    return out


def make_draw(d, stream_raw, min_score, min_score_text, n, lt10, inv_txt, source, occurrence=1, nocs=None, params=None):
    stream_raw = " ".join(stream_raw.split())
    did = f"{d.isoformat()}-{slugify(stream_raw)}" + (f"-{occurrence}" if occurrence > 1 else "")
    rec = {"id": did, "date": d.isoformat(), "year": d.year, "stream_raw": stream_raw}
    rec.update(classify(stream_raw))
    rec.update({"min_score": min_score, "min_score_text": min_score_text, "invitations": n,
                "invitations_lt10": lt10, "invitations_text": inv_txt, "source": source})
    if nocs:
        rec["nocs"] = nocs
    if params:
        rec["selection_parameters"] = params
    return rec


# ---------------------------------------------------------------- yearly PDF (history + NOC codes)
def pdf_to_text(pdf_bytes):
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext not installed (apt install poppler-utils)")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "x.pdf")
        open(p, "wb").write(pdf_bytes)
        subprocess.run(["pdftotext", "-layout", p, p + ".txt"], check=True)
        return open(p + ".txt", encoding="utf-8", errors="replace").read()


HEAD = re.compile(r"^\s*([A-Z][a-z]+ \d{1,2}, 20\d\d)\s+[–-]\s+(.+?)\s*$")
NOC = re.compile(r"^\s*(?:•\s*)?(\d{5})\s*[-–]?\s+(\S.*?)\s*$")


def parse_summary_pdf(text, url):
    lines = text.splitlines()
    appendix = next((i for i, l in enumerate(lines) if l.strip() == "Appendix"), len(lines))
    heads = []
    for i, l in enumerate(lines[:appendix]):
        m = HEAD.match(l)
        if m and "...." not in l and not re.search(r"\.\s*\d+\s*$", l):
            heads.append((i, m.group(1), m.group(2)))
    draws, seen = [], Counter()
    for k, (i, ds, title) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else appendix
        body = [l for l in lines[i + 1:end] if not re.match(r"\s*(Page \||©|Classification:)", l)]
        btxt = "\n".join(body)
        inv = re.search(r"Number of Invitations:\s*(.+)", btxt)
        sc = re.search(r"Minimum WEOI Score[^:]*:\s*(.+)", btxt)
        if not inv or not sc:
            log("WARN PDF block missing values:", ds, title)
            continue
        nocs = []
        for l in body:
            m = NOC.match(l)
            if m:
                nocs.append({"code": m.group(1), "title": m.group(2)})
        params = [re.sub(r"^\s*-\s*", "", l).strip() for l in body if re.match(r"^\s{6,}-\s", l)]
        d = parse_date(ds)
        n, lt10, inv_txt = parse_invites(inv.group(1))
        key = (d.isoformat(), title)
        seen[key] += 1
        draws.append(make_draw(d, title, parse_int(sc.group(1)), sc.group(1).strip(), n, lt10, inv_txt,
                               source="aaip-draw-summary-pdf", occurrence=seen[key], nocs=nocs or None, params=params or None))
    # Appendix: NOC codes that received invitations that year
    year = draws[0]["year"] if draws else None
    invited = []
    for l in lines[appendix:]:
        m = NOC.match(l)
        if m:
            invited.append({"code": m.group(1), "title": m.group(2)})
    return draws, {"year": year, "source_url": url, "nocs_invited": invited}


# ---------------------------------------------------------------- merge + write
def load(path, default):
    try:
        return json.load(open(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def merge_draws(existing, incoming):
    by_id = {d["id"]: d for d in existing}
    added, updated = 0, 0
    for d in incoming:
        old = by_id.get(d["id"])
        if old is None:
            d["first_seen"] = d["last_seen"] = NOW
            by_id[d["id"]] = d
            added += 1
            continue
        merged = dict(old)
        # Live page wins for numbers; PDF adds NOC codes + parameters
        for k, v in d.items():
            if k in ("nocs", "selection_parameters"):
                if v:
                    merged[k] = v
            elif d["source"] == "aaip-processing-information" or old.get("source") != "aaip-processing-information":
                merged[k] = v
        if old.get("source") == "aaip-processing-information" and d["source"] != old["source"]:
            merged["source"] = old["source"]
            merged["also_in"] = d["source"]
        merged["first_seen"] = old.get("first_seen", NOW)
        merged["last_seen"] = NOW
        cmp_keys = ("min_score", "invitations", "invitations_text", "stream_raw", "category")
        if any(old.get(k) != merged.get(k) for k in cmp_keys):
            updated += 1
        by_id[d["id"]] = merged
    out = sorted(by_id.values(), key=lambda x: (x["date"], x["id"]), reverse=True)
    return out, added, updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="parse newest saved snapshot instead of fetching")
    ap.add_argument("--no-pdf", action="store_true", help="skip yearly Draw Summary PDF import")
    ap.add_argument("--force-pdf", action="store_true", help="re-download PDFs even if cached")
    args = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)

    try:
        if args.offline:
            snaps = sorted(f for f in os.listdir(RAW) if f.endswith(".html"))
            html = open(os.path.join(RAW, snaps[-1]), encoding="utf-8").read()
            log("offline: using", snaps[-1])
        else:
            html = fetch(SOURCE_URL)
            log(f"fetched {SOURCE_URL} ({len(html):,} bytes)")
        page = parse_page(html)
    except Exception as e:
        log("ERROR:", e, "- existing data left untouched")
        return 1
    if len(page["draws"]) == 0:
        log("ERROR: 0 draws parsed - refusing to overwrite data")
        return 1

    # keep a raw snapshot whenever the content changes (audit trail)
    h = hashlib.sha256(html.encode()).hexdigest()[:12]
    if not args.offline:
        stamp = page["page_last_updated"] or dt.date.today().isoformat()
        snap = os.path.join(RAW, f"aaip-processing-{stamp}-{h}.html")
        if not os.path.exists(snap):
            open(snap, "w", encoding="utf-8").write(html)

    incoming = list(page["draws"])
    occupations = load(os.path.join(DATA, "occupations.json"), {"years": []})
    if not args.no_pdf:
        for pdf in page["history_pdfs"]:
            cache = os.path.join(RAW, os.path.basename(pdf["url"]))
            try:
                if args.force_pdf or not os.path.exists(cache):
                    open(cache, "wb").write(fetch(pdf["url"], binary=True))
                    log("downloaded", pdf["url"])
                pdraws, occ = parse_summary_pdf(pdf_to_text(open(cache, "rb").read()), pdf["url"])
                log(f"PDF '{pdf['label']}': {len(pdraws)} draws, {len(occ['nocs_invited'])} invited NOC codes")
                incoming.extend(pdraws)
                occupations["years"] = [y for y in occupations["years"] if y.get("year") != occ["year"]] + [occ]
            except Exception as e:
                log("WARN PDF import failed:", pdf["url"], e)

    draws_path = os.path.join(DATA, "draws.json")
    existing = load(draws_path, {"draws": []})["draws"]
    merged, added, updated = merge_draws(existing, incoming)
    write_json(draws_path, {
        "source_url": SOURCE_URL,
        "page_last_updated": page["page_last_updated"],
        "last_refreshed": NOW,
        "count": len(merged),
        "draws": merged,
    })

    pools_path = os.path.join(DATA, "pools.json")
    pools = load(pools_path, {"snapshots": []})
    snap = {"page_last_updated": page["page_last_updated"], "fetched_at": NOW,
            "total": page.get("pool_total"), "pools": page["pools"], "nominations": page["nominations"]}
    sig = lambda s: json.dumps([s.get("total"), s["pools"], s["nominations"]], sort_keys=True)
    snaps = pools["snapshots"]
    if snaps and sig(snaps[-1]) == sig(snap):
        snaps[-1]["last_checked"] = NOW
        pool_msg = "unchanged"
    else:
        snap["last_checked"] = NOW
        snaps.append(snap)
        pool_msg = "new snapshot"
    write_json(pools_path, {"source_url": SOURCE_URL, "last_refreshed": NOW, "latest": snaps[-1], "snapshots": snaps})

    occupations["updated"] = NOW
    write_json(os.path.join(DATA, "occupations.json"), occupations)

    page_n = len(page["draws"])
    log(f"page draws parsed: {page_n} | total draws stored: {len(merged)} | added: {added} | changed: {updated}")
    log(f"pools: {len(page['pools'])} rows, total {page.get('pool_total')} ({pool_msg}) | page last updated {page['page_last_updated']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
