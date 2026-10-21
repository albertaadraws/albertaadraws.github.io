# Alberta Power & Gas Rate Tracker

A free, static website that tracks Alberta residential electricity and natural gas plans every day, compares them with the default rates (Rate of Last Resort and the Default Rate Tariff), and ranks them **by estimated cost only**. It includes a client-side "What would I pay?" calculator, an RSS feed of rate changes, and a weekly newsletter draft. Cost: $0 (GitHub Pages and GitHub Actions).

Served at `https://albertaadraws.github.io/alberta-power/` from the `alberta-power/` folder of the albertaadraws GitHub Pages user site. It is not a separate repository. Canonical URLs are `SITE_URL` + `BASE_PATH` (`https://albertaadraws.github.io` + `/alberta-power`). Every internal link and asset is prefixed with `/alberta-power/` so it resolves under that subpath.

## How it works

| Step | Script | Output |
|---|---|---|
| Fetch and parse each retailer's own rate page, plus the official default rates | `scripts/refresh.py` (parsers in `scripts/sources.py`) | `data/plans.json`, `data/defaults.json`, `data/changes.json`, `data/history.json`, `data/status.json` (raw pages cached in `data/raw/`, which is git-ignored) |
| Build the site | `scripts/build.py` | `public/` |
| Sanity checks (subpath links, canonicals, sources, no partner links) | `scripts/check_site.py` | exit code |
| Weekly newsletter draft (Markdown for beehiiv) | `scripts/newsletter.py` | `newsletter/YYYY-MM-DD.md` |
| All of the above, daily | `scripts/daily.sh` locally, or the parent repo's `.github/workflows/pages.yml` | copied to `../public/alberta-power/` |

```bash
pip install -r requirements.txt          # plus poppler-utils for pdftotext
python3 scripts/refresh.py
SITE_URL=https://albertaadraws.github.io BASE_PATH=/alberta-power python3 scripts/build.py
# preview under the same subpath:
mkdir -p /tmp/s && ln -sfn "$PWD/public" /tmp/s/alberta-power && python3 -m http.server 8777 --directory /tmp/s
# open http://localhost:8777/alberta-power/
```

To use a custom domain later, set `SITE_URL=https://yourdomain.ca BASE_PATH=""` in the workflow.

## Data rules
- Every number comes from the retailer's own public page, or official default-rate pages (UCA default-rates page, EPCOR's RoLR rates page, ENMAX's regulated rate tariff PDF, Direct Energy's page for the regulated gas admin fee). Each row stores `source_url` and `last_checked`.
- **The UCA Cost Comparison Tool is not used or copied.** Its terms require written permission for commercial reuse. The site only links to it.
- If a page can't be fetched or parsed, that source keeps its last good rows (with the old check date) and is flagged on `/sources/`. Nothing is guessed. Retailers that don't print a specific plan price (currently ACE and Just Energy) are left out and listed on the About page.
- Estimates = usage × energy rate + retailer admin fee (daily fees × 30.4). Delivery, local access fees, riders and GST are excluded because they're the same whichever retailer you pick. Typical use is 600 kWh and 10 GJ per month ([UCA FAQ](https://ucahelps.alberta.ca/residential/faq/)).
- Variable plans show the retailer's own stated recent average and are tagged "Variable". Plans needing a deposit, age 60+, a bundle or new-customer status are tagged "Conditions". The calculator excludes variable plans by default.

## Parsers
`sources.py` has one function per layout: the UTILITYnet sign-up page (Alberta Utility Source, SPOTpower, Park Power), 8760, Direct Energy, ENMAX Easymax, ATCO Energy (fixed and floating), Encor by EPCOR, and Peace Power. The same file parses Edmonton water (EPCOR), Edmonton waste services, Calgary water, Solar Club blocks on UTILITYnet signup pages, ENMAX Easymax Seasonal Solar, and the rebate pages. When a page redesigns, that parser raises, the old rows stay, and `/sources/` shows the failure. Fix the regex in that one function.

## Water and solar
Water is informational. Edmonton and Calgary residents cannot switch water providers, so `/water/` is not a ranking. Solar Club retailers are discovered from [solarclub.ca/sign-up](https://solarclub.ca/sign-up/). Only rates printed on the retailer's own page are stored. Retailers whose public page does not print a solar rate are named on `/solar/rates/` with no number. The payback calculator's export share starts at 50% and is labelled as an assumption: no official Alberta figure for that share was found. NRCan annual PV potential (south-facing, latitude tilt) supplies the kWh per kW. `config/partners.json` stays disabled; solar and water pages do not add referral or affiliate links.

## Partner links (future, currently empty)
`config/partners.json` is the only place partner "switch" links may go. It is `"enabled": false` with no entries. When it's enabled, build.py adds a separately labelled "Partner link (we may be paid)" next to that retailer's rows plus a disclosure. **The ranking never reads this file.** `check_site.py` fails the build if a sponsored link appears while partners are disabled. Before adding any link, get written confirmation that you act as the licensed retailer's agent (Alberta energy-marketing licensing rules).

## Deploy (GitHub Pages)
This folder does not have its own Pages workflow. The parent repository's `.github/workflows/pages.yml` is the only deploy:

1. Pages on `albertaadraws/albertaadraws.github.io` is already set to **GitHub Actions**. Merging to `main` is enough to publish.
2. The workflow runs on every push to `main`, daily at 14:00 UTC, and manually. It installs this folder's `requirements.txt`, refreshes rates (a failed source keeps its last good rows), builds with `BASE_PATH=/alberta-power`, copies `public/` to `../public/alberta-power/`, and deploys once with the PR tracker.
3. Refreshed `data/*.json` is committed back to `main` with `[skip ci]`. `data/raw/` and this folder's `public/` stay gitignored.

`config/partners.json` stays `"enabled": false` with an empty `partners` object. Do not add affiliate URLs, analytics, or secrets.

## Newsletter
`/newsletter/` has a placeholder sign-up box. Paste the beehiiv (free plan) embed where the `BEEHIIV_EMBED` comment is. Keep it opt-in only (CASL).
