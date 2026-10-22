#!/usr/bin/env bash
# Print a fresh Tide enrollment link for a demo user (valid for 1 hour).
# Usage: bash init/enroll-link.sh <username>     e.g. bash init/enroll-link.sh maya
set -euo pipefail

USERNAME="${1:?usage: bash init/enroll-link.sh <username>}"
TIDECLOAK_LOCAL_URL="${TIDECLOAK_LOCAL_URL:-http://localhost:8080}"
REALM_NAME="${NEW_REALM_NAME:-unsellable}"
KC_USER="${KC_USER:-admin}"
KC_PASSWORD="${KC_PASSWORD:-password}"
BASE="${TIDECLOAK_LOCAL_URL}/admin/realms/${REALM_NAME}"

TOKEN=$(curl -s -X POST "${TIDECLOAK_LOCAL_URL}/realms/master/protocol/openid-connect/token" \
  -d "username=${KC_USER}" -d "password=${KC_PASSWORD}" -d grant_type=password -d client_id=admin-cli \
  | jq -r .access_token)

USER_ID=$(curl -s -H "Authorization: Bearer ${TOKEN}" "${BASE}/users?username=${USERNAME}&exact=true" | jq -r '.[0].id // empty')
[[ -z "${USER_ID}" ]] && { echo "ERROR: user '${USERNAME}' not found in realm '${REALM_NAME}'." >&2; exit 1; }

curl -sf -X POST "${BASE}/tideAdminResources/get-required-action-link?userId=${USER_ID}&lifespan=3600" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" -H "Accept: text/plain" \
  -d '["link-tide-account-action"]'
echo
