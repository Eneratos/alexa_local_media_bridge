#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(
  CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." \
  && pwd
)"

BRIDGE_DIR="$ROOT_DIR/bridge"
COMPOSE_FILE="$BRIDGE_DIR/compose.yml"
ENV_FILE="$BRIDGE_DIR/.env"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

pass() {
  printf 'OK: %s\n' "$*"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 \
    || fail "Required command not found: $1"
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

compose() {
  docker compose \
    --env-file "$ENV_FILE" \
    --file "$COMPOSE_FILE" \
    "$@"
}

printf '%s\n' \
  'Alexa Local Media Bridge preflight check' \
  '----------------------------------------'

require_command docker
require_command awk
require_command stat

pass "Required local commands are available."

docker info >/dev/null 2>&1 \
  || fail "Docker is unavailable or permission was denied."

docker compose version >/dev/null 2>&1 \
  || fail "Docker Compose v2 is required."

pass "Docker and Docker Compose v2 are available."

[[ -f "$COMPOSE_FILE" ]] \
  || fail "Compose file not found: $COMPOSE_FILE"

[[ -f "$ENV_FILE" ]] \
  || fail "Environment file not found. Run ./scripts/setup.sh first."

mode="$(stat -c '%a' "$ENV_FILE")"

if (( 8#$mode & 077 )); then
  fail \
    "$ENV_FILE is accessible by group or other users. " \
    "Run: chmod 600 bridge/.env"
fi

pass "Environment file exists and has safe permissions."

PROXY_NETWORK="$(env_value PROXY_NETWORK)"
PUBLIC_BASE_URL="$(env_value PUBLIC_BASE_URL)"

[[ -n "$PROXY_NETWORK" ]] \
  || fail "PROXY_NETWORK is missing from bridge/.env."

[[ -n "$PUBLIC_BASE_URL" ]] \
  || fail "PUBLIC_BASE_URL is missing from bridge/.env."

docker network inspect "$PROXY_NETWORK" \
  >/dev/null 2>&1 \
  || fail "Docker network does not exist: $PROXY_NETWORK"

pass "External Docker network exists: $PROXY_NETWORK"

compose config >/dev/null \
  || fail "Docker Compose configuration is invalid."

pass "Docker Compose configuration is valid."

IMAGE="$(compose config --images | head -n 1)"

[[ -n "$IMAGE" ]] \
  || fail "Could not determine the bridge image."

if docker image inspect "$IMAGE" >/dev/null 2>&1; then
  pass "Container image is already available locally: $IMAGE"
else
  printf 'Pulling container image: %s\n' "$IMAGE"

  compose pull \
    || fail "Could not pull container image: $IMAGE"

  pass "Container image downloaded successfully."
fi

compose run \
  --rm \
  --no-deps \
  --entrypoint python \
  alexa-media-bridge \
  -c '
from config_validation import validate_environment

validate_environment()
print("Bridge environment validation passed.")
' \
  || fail "Bridge environment validation failed."

pass "Bridge environment validation passed."

printf '\n%s\n' \
  'Preflight check completed successfully.' \
  "Public base URL: $PUBLIC_BASE_URL" \
  "Proxy network: $PROXY_NETWORK" \
  "Container image: $IMAGE"
