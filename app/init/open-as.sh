#!/usr/bin/env bash
# Open a URL as a demo persona, in that persona's own Chrome profile.
# Each persona keeps its own sessions and stays signed in, so several personas
# can be open side by side (useful for enrollment and for recording the demo).
#
# Usage: bash init/open-as.sh <persona> [url]     (default url: http://localhost:3000)
#        npm run as -- maya
set -euo pipefail

PERSONA="${1:?usage: bash init/open-as.sh <persona> [url]}"
URL="${2:-http://localhost:3000}"
PROFILE_DIR="${UNSELLABLE_PROFILES:-${HOME}/.unsellable-browsers}/${PERSONA}"
mkdir -p "${PROFILE_DIR}"
FLAGS=(--user-data-dir="${PROFILE_DIR}" --no-first-run --no-default-browser-check)

if [[ "$(uname)" == "Darwin" && -d "/Applications/Google Chrome.app" ]]; then
  open -na "Google Chrome" --args "${FLAGS[@]}" "${URL}"
elif command -v google-chrome >/dev/null 2>&1; then
  google-chrome "${FLAGS[@]}" "${URL}" >/dev/null 2>&1 &
elif command -v chromium >/dev/null 2>&1; then
  chromium "${FLAGS[@]}" "${URL}" >/dev/null 2>&1 &
else
  echo "Chrome not found. Open this URL in a separate browser profile for '${PERSONA}':" >&2
  echo "  ${URL}"
fi
