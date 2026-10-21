# Alberta PR Draw Tracker

Static site that tracks every Alberta Advantage Immigration Program (AAIP) draw, pool size and nomination allocation.
Informational only. Not affiliated with the Government of Alberta. Not immigration advice.

Live site: https://albertaadraws.github.io

A second, independent site in this same repository, the [Alberta Power & Gas Rate Tracker](alberta-power/README.md), is served at https://albertaadraws.github.io/alberta-power/. It is built from `alberta-power/` and copied into `public/alberta-power/` by the same Pages workflow. It does not have its own repository or its own deploy job.

## Run it
```bash
pip install -r requirements.txt            # beautifulsoup4 (+ optional markdown); needs poppler-utils for PDF import
python3 scripts/refresh.py                 # fetch alberta.ca -> data/draws.json, data/pools.json, data/occupations.json
python3 scripts/build.py                   # data -> public/ (static site)
python3 scripts/newsletter.py              # newsletter/draws-this-week-YYYY-MM-DD.md + .html (nothing is sent)
python3 -m http.server 8765 --directory public   # preview at http://localhost:8765
```
`SITE_URL` defaults to `https://albertaadraws.github.io`. It is used in the sitemap, RSS and JSON feeds, and canonical tags.
`BASE_PATH` stays empty. This repository is a GitHub Pages user site, so pages and assets are served from the domain root (`/assets/style.css`, `/data/draws.json`). Set `BASE_PATH=/repo-name` only if you host it as a project site instead. The power tracker is the site that uses `BASE_PATH=/alberta-power`. That prefix is not applied here, and this tracker's sitemap stays on the domain root.

Local daily job: `scripts/daily.sh` (refresh and build both sites even if a scrape fails, plus newsletter drafts on Mondays). Nothing in that script sends email. After it runs, `python3 -m http.server 8765 --directory public` serves this tracker at `/` and the power tracker at `/alberta-power/`.

## Daily refresh and deploy
`.github/workflows/pages.yml` runs every day at 14:00 UTC, on every push to `main`, and when started by hand (Actions → Refresh and deploy → Run workflow). One build job produces both sites. One deploy job publishes `public/`.

The workflow installs the root `requirements.txt` and `alberta-power/requirements.txt`, plus `poppler-utils`. It refreshes and builds this tracker into `public/` (`SITE_URL=https://albertaadraws.github.io`, empty `BASE_PATH`), then refreshes and builds the power tracker and copies `alberta-power/public/` to `public/alberta-power/`. It commits changed data JSON for both sites back to `main`, and deploys with `actions/configure-pages` (`enablement: true`), `actions/upload-pages-artifact` and `actions/deploy-pages`.

If a scrape fails, that site's `refresh.py` exits with an error and leaves its existing JSON untouched. The workflow still builds and deploys that data. Raw caches in `data/raw/` and `alberta-power/data/raw/` are not committed, and neither is `alberta-power/public/`. There is no second Pages workflow.

Before the first deploy can succeed, a repository admin has to set **Settings → Pages → Build and deployment → Source** to **GitHub Actions**. The workflow asks `configure-pages` to enable Pages, but the Actions token is not allowed to create a Pages site, and this repo does not store a personal access token. If GitHub offers a starter workflow at that screen, skip it: `.github/workflows/pages.yml` is already the workflow. If the run that started at merge time failed before that setting was changed, open the Actions tab and run **Refresh and deploy** again.

## How the refresh works
* Parses Table 10 (draws), Table 9 (EOI pool) and Tables 1–8 (nomination allocations) on https://www.alberta.ca/aaip-processing-information
* Follows the page's "Draw Summary" PDF link(s) (currently 2025) to import last year's draws plus their NOC codes and selection parameters (cached in data/raw/)
* Draw id = date + stream text, so re-runs never duplicate. Draws that drop off the page are kept. first_seen and last_seen are tracked.
* A pool/nomination snapshot is appended only when the numbers change. Raw HTML snapshots are kept in data/raw/ as an audit trail.
* If the fetch fails or 0 draws are parsed, it exits 1 and leaves the existing data untouched.
* `--offline` re-parses the newest saved snapshot. `--no-pdf` skips the PDF import.

## Still to connect (no third-party accounts in this repo)
* Newsletter form: `newsletter_box()` in scripts/build.py, marked TODO. Point it at Buttondown/beehiiv/Kit.
* Affiliate links: `affiliate_box()`, marked TODO. Plain links for now, no affiliate IDs.
* Sponsor page: add rate card and contact. About page: add contact email.

## Other public sources (occupation-specific draws)
* AAIP Draw Summary 2025 (PDF): https://www.alberta.ca/system/files/im-aaip-draw-history-summary.pdf (per-draw NOC lists + appendix of all NOCs invited in 2025). Already imported.
* Dedicated Health Care Pathway (eligible professions): https://www.alberta.ca/dedicated-health-care-pathway
* AAIP updates (program changes, new pathways, allocation changes): https://www.alberta.ca/aaip-updates
* How to apply to AAIP worker streams (points grid / EOI): https://www.alberta.ca/how-to-apply-to-aaip-worker-streams
* Alberta labour market info (linked from the draw section): https://labour-market.alberta.ca/
* Federal Express Entry rounds (IRCC, includes healthcare category draws): https://www.canada.ca/en/immigration-refugees-citizenship/corporate/mandate/policies-operational-instructions-agreements/ministerial-instructions/express-entry-rounds.html (possible future addition)
