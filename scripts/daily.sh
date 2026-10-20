#!/usr/bin/env bash
# Local daily job: refresh data from alberta.ca, rebuild the site, and (Mondays) draft the newsletter.
# The live site is refreshed by GitHub Actions (.github/workflows/pages.yml) at 14:00 UTC.
# Example cron (14:00 UTC):  0 14 * * *  /path/to/alberta-pr-tracker/scripts/daily.sh >> /path/to/refresh.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
export SITE_URL="${SITE_URL:-https://albertaadraws.github.io}"
export BASE_PATH="${BASE_PATH:-}"
# refresh.py exits 1 and leaves data/*.json untouched when the scrape fails.
python3 scripts/refresh.py || echo "[daily] refresh failed; rebuilding from existing data"
python3 scripts/build.py
if [ "$(date +%u)" = "1" ]; then python3 scripts/newsletter.py; fi
