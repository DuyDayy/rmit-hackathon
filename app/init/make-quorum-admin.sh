#!/usr/bin/env bash
# Request the tide-realm-admin role for an enrolled user, making them a quorum
# administrator. After npm run init the realm is governed, so this creates a
# change request that existing quorum admins must approve in the Tide console:
#   http://localhost:8080/realms/unsellable/tide-console/
# Usage: bash init/make-quorum-admin.sh <username>     e.g. bash init/make-quorum-admin.sh custodian
set -euo pipefail

USERNAME="${1:?usage: bash init/make-quorum-admin.sh <username>}"
TIDECLOAK_LOCAL_URL="${TIDECLOAK_LOCAL_URL:-http://localhost:8080}"
REALM_NAME="${NEW_REALM_NAME:-unsellable}"
KC_USER="${KC_USER:-admin}"
KC_PASSWORD="${KC_PASSWORD:-password}"
ADMIN_ROLE_NAME="${ADMIN_ROLE_NAME:-tide-realm-admin}"
BASE="${TIDECLOAK_LOCAL_URL}/admin/realms/${REALM_NAME}"

TOKEN=$(curl -s -X POST "${TIDECLOAK_LOCAL_URL}/realms/master/protocol/openid-connect/token" \
  -d "username=${KC_USER}" -d "password=${KC_PASSWORD}" -d grant_type=password -d client_id=admin-cli \
  | jq -r .access_token)
auth=(-H "Authorization: Bearer ${TOKEN}")

USER_JSON=$(curl -s "${auth[@]}" "${BASE}/users?username=${USERNAME}&exact=true&briefRepresentation=false")
USER_ID=$(jq -r '.[0].id // empty' <<< "${USER_JSON}")
[[ -z "${USER_ID}" ]] && { echo "ERROR: user '${USERNAME}' not found." >&2; exit 1; }
if [[ -z "$(jq -r '.[0].attributes.tideUserKey[0] // empty' <<< "${USER_JSON}")" ]]; then
  echo "ERROR: '${USERNAME}' has not enrolled a Tide account yet. Run: bash init/enroll-link.sh ${USERNAME}" >&2
  exit 1
fi

RM_UUID=$(curl -s "${auth[@]}" "${BASE}/clients?clientId=realm-management" | jq -r '.[0].id')
ROLE_REP=$(curl -s "${auth[@]}" "${BASE}/clients/${RM_UUID}/roles/${ADMIN_ROLE_NAME}")

code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${auth[@]}" -H "Content-Type: application/json" \
  "${BASE}/users/${USER_ID}/role-mappings/clients/${RM_UUID}" -d "[${ROLE_REP}]")
echo "grant ${ADMIN_ROLE_NAME} to ${USERNAME} -> HTTP ${code}"

echo "Pending change requests:"
curl -s "${auth[@]}" "${BASE}/iga/change-requests?status=PENDING" \
  | jq -r '.[] | "  \(.id)  \(.actionType)  approvals \(.authorizationCount)/\(.threshold)"'
