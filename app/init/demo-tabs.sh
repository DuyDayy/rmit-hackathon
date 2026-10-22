#!/usr/bin/env bash
# Start the app in simulated TideCloak mode and open a new Chrome window with one tab per persona,
# each already signed in on the page it uses in the demo:
#   maya -> My genome · admin.acquirer -> Admin · admin.company, custodian, ethics -> Quorum
#
# Usage: npm run demo                (keeps existing demo data)
#        npm run demo -- --fresh     (starts from an empty demo: removes app/data/*.json first)
# Stop with Ctrl+C.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PORT="${PORT:-3000}"
BASE="http://localhost:${PORT}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [[ "${1:-}" == "--fresh" ]]; then
  rm -f "${APP_DIR}"/data/genomes.json "${APP_DIR}"/data/sim-iga.json
  echo "Demo data cleared."
fi

server_pid=""
if curl -s -o /dev/null "${BASE}/"; then
  echo "An app is already running at ${BASE}; using it. (It must be started with npm run dev:sim.)"
else
  echo "Starting the app in simulated TideCloak mode at ${BASE}..."
  (cd "${APP_DIR}" && NEXT_PUBLIC_TIDE_MODE=simulated npx next dev -p "${PORT}") &
  server_pid=$!
  trap '[[ -n "${server_pid}" ]] && kill "${server_pid}" 2>/dev/null; exit 0' INT TERM
  for _ in $(seq 1 90); do curl -s -o /dev/null "${BASE}/" && break; sleep 1; done
  # Warm up the pages so the first tab switch on camera is instant.
  for p in /sim-login /genome /admin /quorum /database; do curl -s -o /dev/null "${BASE}${p}" || true; done
fi

TABS=(
  "${BASE}/sim-login?as=maya&next=/genome"
  "${BASE}/sim-login?as=admin.acquirer&next=/admin"
  "${BASE}/sim-login?as=admin.company&next=/quorum"
  "${BASE}/sim-login?as=custodian&next=/quorum"
  "${BASE}/sim-login?as=ethics&next=/quorum"
)

if [[ -x "${CHROME}" ]]; then
  "${CHROME}" --new-window "${TABS[@]}" >/dev/null 2>&1 &
  echo "Opened a Chrome window with 5 tabs: maya, admin.acquirer, admin.company, custodian, ethics."
else
  echo "Google Chrome not found. Open these URLs, one per tab:"
  printf '  %s\n' "${TABS[@]}"
fi

if [[ -n "${server_pid}" ]]; then
  echo "App running. Press Ctrl+C to stop."
  wait "${server_pid}"
fi
