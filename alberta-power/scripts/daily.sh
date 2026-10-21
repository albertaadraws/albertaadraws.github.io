#!/usr/bin/env bash
# Daily job for this folder only: refresh rates, rebuild alberta-power/public/, and (Mondays) draft the newsletter.
# The live site is the parent repo's .github/workflows/pages.yml, which copies public/ to ../public/alberta-power/.
# Example cron (6:30 AM Edmonton time):  30 6 * * *  /path/to/repo/alberta-power/scripts/daily.sh >> /path/to/refresh.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/refresh.py || echo "Some or all sources failed; last good data kept."
python3 scripts/build.py
python3 scripts/check_site.py
if [ "$(date +%u)" = "1" ]; then python3 scripts/newsletter.py; fi
