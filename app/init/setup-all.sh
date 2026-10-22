#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Unsellable: one-command demo setup.
#
#      cd app && npm run setup          (same as: bash init/setup-all.sh)
#      npm run setup -- --status        show what is done, change nothing
#
#  Safe to re-run: every step checks the current state first and skips what is
#  already done, so after an interruption just run it again.
#
#  Automated: TideCloak container, npm install, realm provisioning (with retry
#  on Tide Fabric errors), enrollment links, governance change requests,
#  waiting/polling, final verification.
#  Needs a human (the script opens the page and waits):
#    - creating each persona's Tide account in the browser (enrollment)
#    - admin.company approving the change requests in the Tide console
#
#  Environment overrides: KC_USER, KC_PASSWORD, TIDECLOAK_LOCAL_URL,
#  NEW_REALM_NAME, ENROLL_LEE=1 (lee is not in the demo by default),
#  NO_OPEN=1 (print links instead of opening a browser).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${APP_DIR}/.." && pwd)"

TIDECLOAK_LOCAL_URL="${TIDECLOAK_LOCAL_URL:-http://localhost:8080}"
REALM_NAME="${NEW_REALM_NAME:-unsellable}"
KC_USER="${KC_USER:-admin}"
KC_PASSWORD="${KC_PASSWORD:-password}"
FIRST_ADMIN="${FIRST_ADMIN_USERNAME:-admin.company}"
CONTAINER="${TIDECLOAK_CONTAINER:-tidecloak}"
ADAPTER="${APP_DIR}/tidecloak.json"
BASE="${TIDECLOAK_LOCAL_URL}/admin/realms/${REALM_NAME}"
CONSOLE_URL="${TIDECLOAK_LOCAL_URL}/realms/${REALM_NAME}/tide-console/"
INIT_LOG="${SCRIPT_DIR}/.tcinit.log"

QUORUM_SEATS="custodian ethics"
# realm-management roles that make admin.acquirer a full app admin (can request
# role changes) without a quorum seat.
ACQUIRER_ROLES="manage-users view-users query-users view-realm"
PERSONAS="maya admin.acquirer custodian ethics"
[[ "${ENROLL_LEE:-0}" == "1" ]] && PERSONAS="${PERSONAS} lee"

STATUS_ONLY=0
[[ "${1:-}" == "--status" ]] && STATUS_ONLY=1

# ─── Output helpers ──────────────────────────────────────────────────────────
step() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
todo() { printf '  \033[33m•\033[0m %s\n' "$*"; }
die()  { printf '\n\033[31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }

# Open a URL for a persona in a fresh private window so sessions do not mix.
open_private() {
  local url="$1"
  if [[ "${NO_OPEN:-0}" == "1" ]]; then
    echo "    ${url}"
  elif [[ "$(uname)" == "Darwin" && -d "/Applications/Google Chrome.app" ]]; then
    open -na "Google Chrome" --args --incognito "${url}"
  elif [[ "$(uname)" == "Darwin" ]]; then
    open "${url}"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${url}" >/dev/null 2>&1 &
  else
    echo "    Open this URL: ${url}"
  fi
}

# ─── Admin API helpers ───────────────────────────────────────────────────────
token() {
  curl -s -X POST "${TIDECLOAK_LOCAL_URL}/realms/master/protocol/openid-connect/token" \
    -d "username=${KC_USER}" -d "password=${KC_PASSWORD}" \
    -d grant_type=password -d client_id=admin-cli | jq -r '.access_token // empty'
}
# GET with a fresh token (master tokens expire after ~60s).
aget() { curl -s -H "Authorization: Bearer $(token)" -H "Cache-Control: no-store" "$1"; }

realm_exists() {
  [[ "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $(token)" "${BASE}")" == "200" ]]
}
adapter_ready() { [[ -f "${ADAPTER}" ]] && jq -e '.realm' "${ADAPTER}" >/dev/null 2>&1; }

user_json() { aget "${BASE}/users?username=$1&exact=true&briefRepresentation=false"; }
user_id()   { user_json "$1" | jq -r '.[0].id // empty'; }
enrolled()  {
  local j; j="$(user_json "$1")"
  [[ -n "$(jq -r '.[0].attributes.tideUserKey[0] // empty' <<< "$j")" && \
     -n "$(jq -r '.[0].attributes.vuid[0] // empty' <<< "$j")" ]]
}
enroll_link() {
  curl -sf -X POST "${BASE}/tideAdminResources/get-required-action-link?userId=$(user_id "$1")&lifespan=3600" \
    -H "Authorization: Bearer $(token)" -H "Content-Type: application/json" -H "Accept: text/plain" \
    -d '["link-tide-account-action"]'
}

rm_uuid() { aget "${BASE}/clients?clientId=realm-management" | jq -r '.[0].id'; }
has_client_role() { # user role
  aget "${BASE}/users/$(user_id "$1")/role-mappings/clients/$(rm_uuid)" \
    | jq -e --arg r "$2" 'any(.[]?; .name == $r)' >/dev/null
}
pending_crs() { aget "${BASE}/iga/change-requests?status=PENDING" | jq -r 'if type=="array" then .[] | "\(.id) \(.actionType)" else empty end'; }

# Request a realm-management role for a user. Under governance this parks a
# change request; transient Fabric 500s are retried.
request_client_role() { # user role
  local uid rm role code i
  uid="$(user_id "$1")"; rm="$(rm_uuid)"
  role="$(aget "${BASE}/clients/${rm}/roles/$2")"
  for i in 1 2 3; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $(token)" \
      -H "Content-Type: application/json" "${BASE}/users/${uid}/role-mappings/clients/${rm}" -d "[${role}]")
    case "${code}" in
      2*|409) echo "${code}"; return 0 ;;
      5*) sleep 2 ;;
      *) echo "${code}"; return 1 ;;
    esac
  done
  echo "${code}"; return 1
}

# ═════════════════════════════════════════════════════════════════════════════
step "0. Prerequisites"
for c in docker curl jq node npm; do need_cmd "$c"; done
docker info >/dev/null 2>&1 || {
  [[ "${STATUS_ONLY}" == "1" ]] && die "Docker is not running."
  if [[ "$(uname)" == "Darwin" ]]; then
    todo "Starting Docker Desktop..."; open -a Docker
    for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 3; done
  fi
  docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker and re-run."
}
ok "docker, curl, jq, node $(node -v), npm"

# ═════════════════════════════════════════════════════════════════════════════
step "1. TideCloak container"
state="$(docker inspect -f '{{.State.Status}}' "${CONTAINER}" 2>/dev/null || echo missing)"
if [[ "${state}" == "running" ]]; then
  ok "container '${CONTAINER}' running"
elif [[ "${STATUS_ONLY}" == "1" ]]; then
  todo "container '${CONTAINER}' is ${state}"
elif [[ "${state}" == "missing" ]]; then
  mkdir -p "${REPO_DIR}/.tidecloak-data"
  docker run -d --name "${CONTAINER}" -p 8080:8080 \
    -v "${REPO_DIR}/.tidecloak-data:/opt/keycloak/data/h2" \
    -e KC_BOOTSTRAP_ADMIN_USERNAME="${KC_USER}" -e KC_BOOTSTRAP_ADMIN_PASSWORD="${KC_PASSWORD}" \
    tideorg/tidecloak-dev:latest >/dev/null
  ok "container '${CONTAINER}' created"
else
  docker start "${CONTAINER}" >/dev/null; ok "container '${CONTAINER}' started"
fi
if [[ "${STATUS_ONLY}" != "1" ]]; then
  for _ in $(seq 1 90); do [[ -n "$(token)" ]] && break; sleep 2; done
fi
[[ -n "$(token)" ]] || die "TideCloak at ${TIDECLOAK_LOCAL_URL} is not answering with ${KC_USER}/${KC_PASSWORD}."
ok "TideCloak ready at ${TIDECLOAK_LOCAL_URL}"

# ═════════════════════════════════════════════════════════════════════════════
step "2. App dependencies"
if [[ -d "${APP_DIR}/node_modules" ]]; then ok "node_modules present"
elif [[ "${STATUS_ONLY}" == "1" ]]; then todo "run npm install"
else (cd "${APP_DIR}" && npm install --no-audit --no-fund) && ok "npm install done"
fi

# ═════════════════════════════════════════════════════════════════════════════
step "3. Realm '${REALM_NAME}' (first admin: ${FIRST_ADMIN})"

# Wait for a running tcinit.sh: open the first admin's enrollment link, then
# block until the script exits.
wait_for_tcinit() {
  local pid="$1" opened=0
  while kill -0 "${pid}" 2>/dev/null; do
    if [[ "${opened}" == "0" ]] && realm_exists && [[ -n "$(user_id "${FIRST_ADMIN}")" ]] \
       && ! enrolled "${FIRST_ADMIN}" && grep -q "ACTION REQUIRED" "${INIT_LOG}" 2>/dev/null; then
      todo "Create the Tide account for ${FIRST_ADMIN} in the browser window that just opened."
      open_private "$(enroll_link "${FIRST_ADMIN}")"
      opened=1
    fi
    sleep 4
  done
}

if realm_exists && adapter_ready; then
  ok "realm provisioned, adapter at app/tidecloak.json"
elif [[ "${STATUS_ONLY}" == "1" ]]; then
  realm_exists && todo "realm exists but provisioning is not finished" || todo "realm not created"
else
  running_pid="$(pgrep -f "init/tcinit.sh" | head -1 || true)"
  if [[ -n "${running_pid}" ]]; then
    todo "a provisioning run is already in progress (pid ${running_pid}); waiting for it"
    INIT_LOG=/dev/null
    if ! enrolled "${FIRST_ADMIN}"; then
      todo "Create the Tide account for ${FIRST_ADMIN} in the browser window that just opened."
      open_private "$(enroll_link "${FIRST_ADMIN}")"
    fi
    while kill -0 "${running_pid}" 2>/dev/null; do sleep 4; done
  else
    if realm_exists; then
      [[ "${RESET:-0}" == "1" ]] || die "realm '${REALM_NAME}' exists but was not fully provisioned.
       Re-run with RESET=1 to delete it and start over (all enrollments are lost)."
      curl -s -o /dev/null -X DELETE -H "Authorization: Bearer $(token)" "${BASE}"
      todo "deleted half-provisioned realm"
    fi
    for attempt in 1 2 3 4; do
      todo "provisioning (attempt ${attempt}), log: app/init/.tcinit.log"
      (cd "${APP_DIR}" && bash init/tcinit.sh > "${INIT_LOG}" 2>&1) &
      wait_for_tcinit $!
      wait $! 2>/dev/null && break || true
      adapter_ready && break
      if grep -q "KEYGEN_FAILED\|setUpTideRealm failed" "${INIT_LOG}"; then
        todo "Tide Fabric error (temporary). Deleting the realm and retrying..."
        curl -s -o /dev/null -X DELETE -H "Authorization: Bearer $(token)" "${BASE}"
        sleep 5
      else
        tail -20 "${INIT_LOG}" >&2; die "provisioning failed (see app/init/.tcinit.log)."
      fi
    done
  fi
  adapter_ready || die "provisioning did not produce app/tidecloak.json (see app/init/.tcinit.log)."
  ok "realm provisioned, adapter written to app/tidecloak.json"
fi
realm_exists || exit 0

# ═════════════════════════════════════════════════════════════════════════════
step "4. Enroll demo personas (one Tide account each)"
for u in ${PERSONAS}; do
  if enrolled "$u"; then ok "$u enrolled"; continue; fi
  if [[ "${STATUS_ONLY}" == "1" ]]; then todo "$u not enrolled"; continue; fi
  todo "Create the Tide account for '$u' in the private window that just opened. Waiting..."
  open_private "$(enroll_link "$u")"
  n=0
  until enrolled "$u"; do
    sleep 4; n=$((n + 1))
    # Links last an hour; send a new one every 15 minutes in case the tab was closed.
    if (( n % 225 == 0 )); then todo "still waiting for $u, opening a new link"; open_private "$(enroll_link "$u")"; fi
  done
  ok "$u enrolled"
done

# ═════════════════════════════════════════════════════════════════════════════
step "5. Governance requests"
missing=0
for u in ${QUORUM_SEATS}; do
  if has_client_role "$u" tide-realm-admin; then ok "$u holds a quorum seat"; continue; fi
  missing=1
  if [[ "${STATUS_ONLY}" == "1" ]]; then todo "$u has no quorum seat yet"; continue; fi
  enrolled "$u" || die "$u must be enrolled before getting a quorum seat."
  ok "quorum seat for $u requested (HTTP $(request_client_role "$u" tide-realm-admin))"
done
for r in ${ACQUIRER_ROLES}; do
  if has_client_role admin.acquirer "$r"; then ok "admin.acquirer has $r"; continue; fi
  missing=1
  if [[ "${STATUS_ONLY}" == "1" ]]; then todo "admin.acquirer lacks $r"; continue; fi
  ok "admin.acquirer $r requested (HTTP $(request_client_role admin.acquirer "$r"))"
done

# ═════════════════════════════════════════════════════════════════════════════
step "6. Quorum approval in the Tide console"
crs="$(pending_crs)"
if [[ -z "${crs}" && "${missing}" == "0" ]]; then
  ok "nothing pending"
elif [[ "${STATUS_ONLY}" == "1" ]]; then
  [[ -n "${crs}" ]] && echo "${crs}" | sed 's/^/  • pending: /'
else
  echo "${crs}" | sed 's/^/  • pending: /'
  todo "Sign in to the Tide console as ${FIRST_ADMIN}, then approve and commit every pending change request."
  open_private "${CONSOLE_URL}"
  until [[ -z "$(pending_crs)" ]]; do sleep 5; done
  ok "no pending change requests left"
fi

# ═════════════════════════════════════════════════════════════════════════════
step "7. Verification"
fail=0
check() { if eval "$2"; then ok "$1"; else todo "NOT YET: $1"; fail=1; fi; }
maya_roles="$(aget "${BASE}/users/$(user_id maya)/role-mappings/realm" | jq -r '[.[].name] | join(" ")')"
acq_roles="$(aget "${BASE}/users/$(user_id admin.acquirer)/role-mappings/realm/composite" | jq -r '[.[].name] | join(" ")')"
check "maya holds _tide_genome.selfencrypt and selfdecrypt" \
  '[[ "${maya_roles}" == *_tide_genome.selfencrypt* && "${maya_roles}" == *_tide_genome.selfdecrypt* ]]'
check "admin.acquirer holds no genome role" '[[ "${acq_roles}" != *_tide_genome.* ]]'
for u in ${FIRST_ADMIN} ${QUORUM_SEATS}; do check "$u holds a quorum seat" "has_client_role $u tide-realm-admin"; done
for r in ${ACQUIRER_ROLES}; do check "admin.acquirer has $r" "has_client_role admin.acquirer $r"; done
for u in ${PERSONAS}; do check "$u enrolled" "enrolled $u"; done

echo
if [[ "${fail}" == "0" ]]; then
  printf '\033[32mSetup complete.\033[0m Start the app:  cd app && npm run dev   →  http://localhost:3000\n'
else
  echo "Some steps are not done yet. Run 'npm run setup' to continue."
fi
