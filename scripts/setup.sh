#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

ROOT_DIR="$(
  CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." \
  && pwd
)"

BRIDGE_DIR="$ROOT_DIR/bridge"
COMPOSE_FILE="$BRIDGE_DIR/compose.yml"
ENV_FILE="$BRIDGE_DIR/.env"
FORCE=0

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 \
    || fail "Required command not found: $1"
}

prompt_value() {
  local variable_name="$1"
  local label="$2"
  local default_value="${3:-}"
  local value=""

  if [[ -n "$default_value" ]]; then
    read -r -p "$label [$default_value]: " value
    value="${value:-$default_value}"
  else
    while [[ -z "$value" ]]; do
      read -r -p "$label: " value
    done
  fi

  printf -v "$variable_name" '%s' "$value"
}

prompt_secret() {
  local variable_name="$1"
  local label="$2"
  local value=""

  while [[ -z "$value" ]]; do
    read -r -s -p "$label: " value
    printf '\n'
  done

  printf -v "$variable_name" '%s' "$value"
}

encode_base64() {
  printf '%s' "$1" \
    | base64 \
    | tr -d '\r\n'
}

random_secret() {
  od -An -N32 -tx1 /dev/urandom \
    | tr -d ' \r\n'
}

strip_trailing_slashes() {
  local value="$1"

  while [[ "$value" == */ ]]; do
    value="${value%/}"
  done

  printf '%s' "$value"
}

show_help() {
  cat <<'HELP'
Usage: ./scripts/setup.sh [--force]

Creates bridge/.env interactively.

Options:
  --force  Back up and replace an existing bridge/.env
  --help   Show this help text
HELP
}

case "${1:-}" in
  "")
    ;;
  --force)
    FORCE=1
    ;;
  --help|-h)
    show_help
    exit 0
    ;;
  *)
    show_help >&2
    exit 1
    ;;
esac

require_command docker
require_command base64
require_command od
require_command tr

docker info >/dev/null 2>&1 \
  || fail "Docker is unavailable or permission was denied."

docker compose version >/dev/null 2>&1 \
  || fail "Docker Compose v2 is required."

[[ -f "$COMPOSE_FILE" ]] \
  || fail "Compose file not found: $COMPOSE_FILE"

if [[ -e "$ENV_FILE" ]]; then
  if [[ "$FORCE" -ne 1 ]]; then
    fail "$ENV_FILE already exists. Use --force to replace it."
  fi

  backup_file="$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
  cp -- "$ENV_FILE" "$backup_file"
  chmod 600 "$backup_file"

  printf 'Existing environment backed up to:\n%s\n\n' \
    "$backup_file"
fi

printf '%s\n' \
  'Alexa Local Media Bridge setup' \
  '--------------------------------'

prompt_value IMAGE_TAG \
  "Container image tag" \
  "$(tr -d "[:space:]" < "$ROOT_DIR/VERSION")"

prompt_value PROXY_NETWORK \
  "Existing reverse proxy Docker network" \
  "proxy"

prompt_value PUBLIC_BASE_URL \
  "Public HTTPS base URL"

PUBLIC_BASE_URL="$(
  strip_trailing_slashes "$PUBLIC_BASE_URL"
)"

[[ "$PUBLIC_BASE_URL" == https://* ]] \
  || fail "PUBLIC_BASE_URL must begin with https://"

if [[ "$PUBLIC_BASE_URL" =~ :([0-9]+)(/|$) ]]; then
  [[ "${BASH_REMATCH[1]}" == "443" ]] \
    || fail "PUBLIC_BASE_URL must use HTTPS port 443."
fi

prompt_value NAVIDROME_URL \
  "Navidrome URL reachable from the bridge container" \
  "http://navidrome:4533"

NAVIDROME_URL="$(
  strip_trailing_slashes "$NAVIDROME_URL"
)"

prompt_value NAVIDROME_USERNAME \
  "Navidrome username"

prompt_secret NAVIDROME_PASSWORD \
  "Navidrome password"

prompt_value AUDIOBOOKSHELF_URL \
  "Audiobookshelf URL reachable from the bridge container" \
  "http://audiobookshelf:80"

AUDIOBOOKSHELF_URL="$(
  strip_trailing_slashes "$AUDIOBOOKSHELF_URL"
)"

prompt_secret AUDIOBOOKSHELF_TOKEN \
  "Audiobookshelf API token"

prompt_value AUDIOBOOKSHELF_LIBRARY_ID \
  "Audiobookshelf library ID"

docker network inspect "$PROXY_NETWORK" \
  >/dev/null 2>&1 \
  || fail "Docker network does not exist: $PROXY_NETWORK"

STREAM_SECRET="$(random_secret)"
CONTROL_SECRET="$(random_secret)"

NAVIDROME_USERNAME_B64="$(
  encode_base64 "$NAVIDROME_USERNAME"
)"

NAVIDROME_PASSWORD_B64="$(
  encode_base64 "$NAVIDROME_PASSWORD"
)"

AUDIOBOOKSHELF_TOKEN_B64="$(
  encode_base64 "$AUDIOBOOKSHELF_TOKEN"
)"

cat > "$ENV_FILE" <<ENV
IMAGE_TAG=$IMAGE_TAG
PROXY_NETWORK=$PROXY_NETWORK

PUBLIC_BASE_URL=$PUBLIC_BASE_URL

STREAM_SECRET=$STREAM_SECRET
CONTROL_SECRET=$CONTROL_SECRET

NAVIDROME_URL=$NAVIDROME_URL
NAVIDROME_USERNAME_B64=$NAVIDROME_USERNAME_B64
NAVIDROME_PASSWORD_B64=$NAVIDROME_PASSWORD_B64

AUDIOBOOKSHELF_URL=$AUDIOBOOKSHELF_URL
AUDIOBOOKSHELF_TOKEN_B64=$AUDIOBOOKSHELF_TOKEN_B64
AUDIOBOOKSHELF_LIBRARY_ID=$AUDIOBOOKSHELF_LIBRARY_ID

MUSIC_STREAM_TTL=14400
MAX_TOKEN_LIFETIME=14400
MAX_ABS_SEEK_SECONDS=86400

MAX_RANDOM_TRACKS=500
ALL_SONGS_CACHE_TTL=300
ENV

chmod 600 "$ENV_FILE"

unset NAVIDROME_PASSWORD
unset AUDIOBOOKSHELF_TOKEN
unset STREAM_SECRET
unset CONTROL_SECRET

if ! docker compose \
  --env-file "$ENV_FILE" \
  --file "$COMPOSE_FILE" \
  config \
  >/dev/null
then
  rm -f "$ENV_FILE"
  fail "Compose validation failed. The generated file was removed."
fi

printf '\n%s\n' \
  'Configuration created successfully.' \
  "Environment file: $ENV_FILE" \
  'File permissions: 600' \
  'Compose configuration: valid' \
  '' \
  'The generated CONTROL_SECRET must also be configured in AWS Lambda.' \
  'Do not commit or share bridge/.env.'
