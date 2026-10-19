#!/usr/bin/env bash
# Fixed, read-only health check for an unattended orchestrator run (L-05a): one exact allow rule covers it.
# Copy to .wrightcrew/checks.sh and adapt. Run from the repo root:  bash .wrightcrew/checks.sh
set -u
RUN=.wrightcrew/run
# Model health URL: env WRIGHTCREW_HEALTH_URL, else `health_url` from wrightcrew.config.json, else the default below.
URL="${WRIGHTCREW_HEALTH_URL:-}"
[ -z "$URL" ] && [ -f wrightcrew.config.json ] && URL=$(python -c 'import json;print(json.load(open("wrightcrew.config.json")).get("health_url") or "")' 2>/dev/null)
URL="${URL:-http://127.0.0.1:8080/v1/models}"
echo "== clock";       date +"%Y-%m-%d %H:%M"
echo "== stop files";  for f in STOP USER_BACK; do [ -e "$RUN/$f" ] && echo "PRESENT $f" || echo "absent $f"; done
echo "== model";       out=$(curl -sf -m 15 "$URL") && echo "${out:0:200}" || echo "MODEL DOWN"
echo "== driver";      python wrightcrew/driver.py status
echo "== git";         git status --short | head -20
echo "last commit age min: $(( ( $(date +%s) - $(git log -1 --format=%ct) ) / 60 ))"
git log --oneline -8
echo "== driver log";  tail -8 "$RUN/driver.log" 2>/dev/null || echo "no driver log"
