#!/usr/bin/env bash
# Fixed, read-only health check for an unattended orchestrator run (L-05a): one exact allow rule covers it.
# Copy to .cadre/checks.sh and adapt. Run from the repo root:  bash .cadre/checks.sh
set -u
RUN=.cadre/run
echo "== clock";       date +"%Y-%m-%d %H:%M"
echo "== stop files";  for f in STOP USER_BACK; do [ -e "$RUN/$f" ] && echo "PRESENT $f" || echo "absent $f"; done
echo "== model";       curl -s -m 15 "${CADRE_HEALTH_URL:-http://127.0.0.1:8080/v1/models}" | head -c 200 || echo "MODEL DOWN"; echo
echo "== driver";      python cadre/driver.py status
echo "== git";         git status --short | head -20
echo "last commit age min: $(( ( $(date +%s) - $(git log -1 --format=%ct) ) / 60 ))"
git log --oneline -8
echo "== driver log";  tail -8 "$RUN/driver.log" 2>/dev/null || echo "no driver log"
