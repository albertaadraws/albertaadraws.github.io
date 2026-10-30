#!/usr/bin/env bash
# Local daily job: refresh the scraped sites, build them, copy Desi Macros, and (Mondays) draft newsletters.
# The live site is refreshed by GitHub Actions (.github/workflows/pages.yml) at 14:00 UTC.
# Example cron (14:00 UTC):  0 14 * * *  /path/to/repo/scripts/daily.sh >> /path/to/refresh.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
export SITE_URL="${SITE_URL:-https://albertaadraws.github.io}"
export BASE_PATH="${BASE_PATH:-}"
# refresh.py exits 1 and leaves data/*.json untouched when the scrape fails.
python3 scripts/refresh.py || echo "[daily] AAIP refresh failed; rebuilding from existing data"
python3 scripts/build.py
if [ "$(date +%u)" = "1" ]; then python3 scripts/newsletter.py; fi

# The power tracker builds into alberta-power/public/. Copy that into the
# combined site after the PR build, which replaces public/.
(
  cd alberta-power
  export SITE_URL="${SITE_URL:-https://albertaadraws.github.io}"
  export BASE_PATH="/alberta-power"
  python3 scripts/refresh.py || echo "[daily] power refresh failed; rebuilding from existing data"
  python3 scripts/build.py
  python3 scripts/check_site.py
  if [ "$(TZ=America/Edmonton date +%u)" = "1" ]; then python3 scripts/newsletter.py; fi
)
rm -rf public/alberta-power
mkdir -p public/alberta-power
cp -a alberta-power/public/. public/alberta-power/

# Home care finder is stdlib-only and has no scrape. Build it, then copy into public/home-care/.
(
  cd home-care
  export SITE_URL="${SITE_URL:-https://albertaadraws.github.io}"
  export BASE_PATH="/home-care"
  python3 scripts/build.py
)
rm -rf public/home-care
mkdir -p public/home-care
cp -a home-care/public/. public/home-care/

# Desi Macros is static HTML. Copy it after the builds that replace public/.
rm -rf public/desi-macros
mkdir -p public/desi-macros
cp -a desi-macros/. public/desi-macros/
