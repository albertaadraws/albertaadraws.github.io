# Edmonton Home Care Finder (test site)

Free static directory of Edmonton-area home care agencies, built to be served at
https://albertaadraws.github.io/home-care/ (all links are prefixed with BASE_PATH=/home-care).

Build:  `SITE_URL=https://albertaadraws.github.io BASE_PATH=/home-care python3 scripts/build.py`  (stdlib only, no installs)
Preview: serve a folder that contains `public/` as `home-care/`, e.g.
`mkdir -p /tmp/s && ln -sfn $PWD/public /tmp/s/home-care && python3 -m http.server 8770 --directory /tmp/s` then open http://localhost:8770/home-care/

## Files
- `data/agencies.json`: 20 agencies + 1 unpublished placeholder for the owner's agency (`publish: false`). Every field comes from the agency's own website (see `sources`, `checked`). Blank = not stated. No reviews or star ratings.
- `config/site.json`: owner name, **owner_agency**, and **contact_email** (`albertacarestaffing@gmail.com`) used in the disclosure and the get-listed mailto.
- `scripts/build.py`: generator. Order is alphabetical only. There is no rank/featured field.
- `src/style.css`: styles. `research/`: fetch script + evidence snippets used to fill the data (raw pages excluded from the tarball).

## Before publishing (TODO for Hanzala)
1. Put the agency's exact public name in `config/site.json` → `owner_agency`.
2. Fill in the placeholder entry in `data/agencies.json` (name, website, phone, areas, services, funding, languages, a source URL) and set `"publish": true` and keep `"owner": true` (shows an "Owned by this site's owner" tag).
3. Paste the beehiiv embed in the newsletter page (see `BEEHIIV_EMBED` comment in build.py).

## Deploy
This folder has no Pages workflow of its own. The parent repository's `.github/workflows/pages.yml` builds it on every push to `main` and on the daily run (`SITE_URL=https://albertaadraws.github.io`, `BASE_PATH=/home-care`) and copies `public/` to `../public/home-care/`. There is no scrape step. `research/pages/` and `public/` are gitignored.

## Data rules
- Alberta Blue Cross site terms: content is for non-commercial personal use only; robots/scraping and copying for commercial purposes are prohibited (https://www.ab.bluecross.ca/web-site-policy.php). So the CDHCI provider map is **linked, not copied**.
- AHS site terms: limited licence for personal, non-commercial use only (https://www.albertahealthservices.ca/about/Page635.aspx). Linked/cited, not copied.
- Re-check each agency every month; remove claims that disappear from the agency's site.
