#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(
  CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." \
  && pwd
)"

BRIDGE_DIR="$ROOT_DIR/bridge"
COMPOSE_FILE="$BRIDGE_DIR/compose.yml"
ENV_FILE="$BRIDGE_DIR/.env"
SERVICE="alexa-media-bridge"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

pass() {
  printf 'OK: %s\n' "$*"
}

compose() {
  docker compose \
    --env-file "$ENV_FILE" \
    --file "$COMPOSE_FILE" \
    "$@"
}

env_value() {
  local key="$1"

  awk -v key="$key" '
    index($0, key "=") == 1 {
      sub(/^[^=]*=/, "")
      print
      exit
    }
  ' "$ENV_FILE"
}

printf '%s\n' \
  'Alexa Local Media Bridge verification' \
  '-------------------------------------'

command -v docker >/dev/null 2>&1 \
  || fail "Docker is not installed."

command -v awk >/dev/null 2>&1 \
  || fail "awk is not installed."

command -v grep >/dev/null 2>&1 \
  || fail "grep is not installed."

docker info >/dev/null 2>&1 \
  || fail "Docker is unavailable or permission was denied."

docker compose version >/dev/null 2>&1 \
  || fail "Docker Compose v2 is required."

[[ -f "$ENV_FILE" ]] \
  || fail "Environment file not found: $ENV_FILE"

[[ -f "$COMPOSE_FILE" ]] \
  || fail "Compose file not found: $COMPOSE_FILE"

CONTAINER_ID="$(compose ps -q "$SERVICE")"

[[ -n "$CONTAINER_ID" ]] \
  || fail \
    "The bridge container does not exist. " \
    "Run docker compose up -d first."

RUNNING="$(
  docker inspect \
    --format '{{.State.Running}}' \
    "$CONTAINER_ID"
)"

[[ "$RUNNING" == "true" ]] \
  || fail "The bridge container is not running."

pass "Bridge container is running."

HEALTH=""

for ((attempt = 1; attempt <= 30; attempt++)); do
  HEALTH="$(
    docker inspect \
      --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
      "$CONTAINER_ID"
  )"

  if [[ "$HEALTH" == "healthy" ]]; then
    break
  fi

  if [[ "$HEALTH" == "unhealthy" ]]; then
    fail "The bridge container is unhealthy."
  fi

  sleep 2
done

[[ "$HEALTH" == "healthy" ]] \
  || fail "The bridge did not become healthy within 60 seconds."

pass "Docker healthcheck reports healthy."

RUNTIME_UID="$(
  compose exec -T "$SERVICE" \
    python -c 'import os; print(os.getuid())'
)"

[[ "$RUNTIME_UID" != "0" ]] \
  || fail "The bridge is running as root."

pass "Bridge runs as unprivileged UID $RUNTIME_UID."

READ_ONLY="$(
  docker inspect \
    --format '{{.HostConfig.ReadonlyRootfs}}' \
    "$CONTAINER_ID"
)"

[[ "$READ_ONLY" == "true" ]] \
  || fail "The container root filesystem is not read-only."

pass "Container root filesystem is read-only."

CAP_DROP="$(
  docker inspect \
    --format '{{json .HostConfig.CapDrop}}' \
    "$CONTAINER_ID"
)"

grep -q '"ALL"' <<<"$CAP_DROP" \
  || fail "Not all Linux capabilities are dropped."

pass "All Linux capabilities are dropped."

SECURITY_OPTIONS="$(
  docker inspect \
    --format '{{json .HostConfig.SecurityOpt}}' \
    "$CONTAINER_ID"
)"

grep -q 'no-new-privileges:true' <<<"$SECURITY_OPTIONS" \
  || fail "no-new-privileges is not enabled."

pass "no-new-privileges is enabled."

PROXY_NETWORK="$(env_value PROXY_NETWORK)"

[[ -n "$PROXY_NETWORK" ]] \
  || fail "PROXY_NETWORK is missing from bridge/.env."

CONTAINER_NETWORKS="$(
  docker inspect \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' \
    "$CONTAINER_ID"
)"

grep -qxF "$PROXY_NETWORK" <<<"$CONTAINER_NETWORKS" \
  || fail \
    "The bridge is not attached to network: $PROXY_NETWORK"

pass "Bridge is attached to proxy network: $PROXY_NETWORK"

compose exec -T "$SERVICE" python - <<'PY'
import json
import os
import urllib.error
import urllib.request


base_url = os.environ["PUBLIC_BASE_URL"].rstrip("/")
control_secret = os.environ["CONTROL_SECRET"]


def request(
    path,
    *,
    payload=None,
    authorized=False,
):
    data = None
    headers = {
        "User-Agent":
            "AlexaLocalMediaBridgeVerifier/1.0",
    }

    if payload is not None:
        data = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

        headers["Content-Type"] = (
            "application/json"
        )

    if authorized:
        headers["Authorization"] = (
            "Bearer " + control_secret
        )

    req = urllib.request.Request(
        base_url + path,
        data=data,
        headers=headers,
        method=(
            "POST"
            if payload is not None
            else "GET"
        ),
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=20,
        ) as response:
            body = response.read()
            return response.status, body
    except urllib.error.HTTPError as error:
        return error.code, error.read()


status, body = request("/health")

if status != 200:
    raise SystemExit(
        f"Public health endpoint returned HTTP {status}."
    )

try:
    health = json.loads(body)
except json.JSONDecodeError as error:
    raise SystemExit(
        "Public health endpoint returned invalid JSON."
    ) from error

if health.get("status") != "ok":
    raise SystemExit(
        "Public health endpoint did not report status ok."
    )

print("OK: Public HTTPS health endpoint is reachable.")


verify_payload = {
    "query":
        "__alexa_media_bridge_verification__",
    "mode":
        "song",
}

status, _ = request(
    "/api/navidrome/resolve",
    payload=verify_payload,
)

if status != 401:
    raise SystemExit(
        "Protected API endpoint returned "
        f"HTTP {status} without authentication; "
        "expected HTTP 401."
    )

print("OK: Protected API rejects unauthenticated requests.")


status, body = request(
    "/api/navidrome/resolve",
    payload=verify_payload,
    authorized=True,
)

if status != 200:
    detail = body.decode(
        "utf-8",
        errors="replace",
    )[:300]

    raise SystemExit(
        "Authenticated Navidrome verification "
        f"returned HTTP {status}: {detail}"
    )

try:
    json.loads(body)
except json.JSONDecodeError as error:
    raise SystemExit(
        "Authenticated Navidrome endpoint "
        "returned invalid JSON."
    ) from error

print("OK: Authenticated Navidrome API request succeeded.")
PY

pass "Public HTTPS, authentication, and Navidrome checks passed."

printf '\n%s\n' \
  'Verification completed successfully.'
