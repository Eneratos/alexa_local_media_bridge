#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(
  CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." \
  && pwd
)"

VERSION="${1:-$(tr -d "[:space:]" < "$ROOT_DIR/VERSION")}"
OUTPUT_DIR="${2:-$ROOT_DIR/dist/release}"
WORK_DIR="$ROOT_DIR/dist/.release-work"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 \
    || fail "Required command not found: $1"
}

show_help() {
  cat <<'HELP'
Usage:
  ./scripts/build_release_assets.sh [VERSION] [OUTPUT_DIRECTORY]

Examples:
  ./scripts/build_release_assets.sh 1.2.3
  ./scripts/build_release_assets.sh v1.2.3 /tmp/release

Creates:
  - Flat AWS Lambda deployment ZIP
  - German and English interaction models
  - Installation bundle
  - SHA-256 checksums
HELP
}

if [[ "$VERSION" == "--help" || "$VERSION" == "-h" ]]; then
  show_help
  exit 0
fi

[[ -n "$VERSION" ]] \
  || fail "A release version is required."

VERSION="${VERSION#v}"

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]] \
  || fail "Invalid release version: $VERSION"

require_command docker
require_command python3
require_command sha256sum

docker info >/dev/null 2>&1 \
  || fail "Docker is unavailable or permission was denied."

rm -rf "$WORK_DIR"
mkdir -p \
  "$WORK_DIR/lambda" \
  "$WORK_DIR/install" \
  "$OUTPUT_DIR"

cleanup() {
  rm -rf "$WORK_DIR"
}

trap cleanup EXIT

printf 'Building Lambda package for version %s...\n' \
  "$VERSION"

cp \
  "$ROOT_DIR/skill/lambda/index.js" \
  "$ROOT_DIR/skill/lambda/package.json" \
  "$ROOT_DIR/skill/lambda/package-lock.json" \
  "$ROOT_DIR/LICENSE" \
  "$WORK_DIR/lambda/"

docker run --rm \
  --user "$(id -u):$(id -g)" \
  --env HOME=/tmp \
  --env npm_config_cache=/tmp/npm-cache \
  --volume "$WORK_DIR/lambda:/work" \
  --workdir /work \
  node:24-alpine \
  npm ci --omit=dev

docker run --rm \
  --user "$(id -u):$(id -g)" \
  --volume "$WORK_DIR/lambda:/work:ro" \
  --workdir /work \
  node:24-alpine \
  node --check index.js

LAMBDA_ZIP="$OUTPUT_DIR/alexa_local_media_bridge_lambda_${VERSION}.zip"

rm -f "$LAMBDA_ZIP"

python3 - "$WORK_DIR/lambda" "$LAMBDA_ZIP" <<'PY'
import sys
import zipfile
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])

with zipfile.ZipFile(
    target,
    "w",
    zipfile.ZIP_DEFLATED,
) as archive:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            archive.write(
                path,
                path.relative_to(source).as_posix(),
            )
PY

python3 - "$LAMBDA_ZIP" <<'PY'
import sys
import zipfile

path = sys.argv[1]

required = {
    "index.js",
    "package.json",
    "package-lock.json",
    "LICENSE",
    "node_modules/ask-sdk-core/package.json",
}

with zipfile.ZipFile(path) as archive:
    names = set(archive.namelist())

missing = sorted(required - names)

if missing:
    raise SystemExit(
        "Missing Lambda ZIP entries: "
        + ", ".join(missing)
    )

for name in names:
    first = name.split("/", 1)[0]

    if first.startswith("lambda_") or first == "dist":
        raise SystemExit(
            "Lambda ZIP contains a wrapper directory."
        )

print("Lambda ZIP structure is valid.")
PY

MODEL_DE="$OUTPUT_DIR/alexa_local_media_bridge_interaction_model_de_DE_${VERSION}.json"
MODEL_EN="$OUTPUT_DIR/alexa_local_media_bridge_interaction_model_en_US_${VERSION}.json"

cp \
  "$ROOT_DIR/skill/interaction_model/de_DE.json" \
  "$MODEL_DE"

cp \
  "$ROOT_DIR/skill/interaction_model/en_US.json" \
  "$MODEL_EN"

INSTALL_ROOT="$WORK_DIR/install/alexa_local_media_bridge_${VERSION}"

mkdir -p \
  "$INSTALL_ROOT/bridge" \
  "$INSTALL_ROOT/scripts" \
  "$INSTALL_ROOT/docs" \
  "$INSTALL_ROOT/skill/interaction_model" \
  "$INSTALL_ROOT/skill/test_events"

cp "$ROOT_DIR/README.md" \
  "$INSTALL_ROOT/README.md"

cp "$ROOT_DIR/VERSION" \
  "$INSTALL_ROOT/VERSION"

cp "$ROOT_DIR/LICENSE" \
  "$INSTALL_ROOT/LICENSE"

cp \
  "$ROOT_DIR/bridge/compose.yml" \
  "$ROOT_DIR/bridge/.env.example" \
  "$INSTALL_ROOT/bridge/"

cp \
  "$ROOT_DIR/scripts/setup.sh" \
  "$ROOT_DIR/scripts/preflight.sh" \
  "$ROOT_DIR/scripts/verify.sh" \
  "$INSTALL_ROOT/scripts/"

cp \
  "$ROOT_DIR/docs/INSTALL.md" \
  "$ROOT_DIR/docs/CONFIGURATION.md" \
  "$ROOT_DIR/docs/ALEXA_SKILL_SETUP.md" \
  "$ROOT_DIR/docs/UPDATING.md" \
  "$ROOT_DIR/docs/TROUBLESHOOTING.md" \
  "$INSTALL_ROOT/docs/"

cp "$ROOT_DIR"/skill/interaction_model/*.json \
  "$INSTALL_ROOT/skill/interaction_model/"

cp "$ROOT_DIR"/skill/test_events/* \
  "$INSTALL_ROOT/skill/test_events/"

chmod 755 "$INSTALL_ROOT"/scripts/*.sh

INSTALL_ARCHIVE="$OUTPUT_DIR/alexa_local_media_bridge_install_${VERSION}.tar.gz"

rm -f "$INSTALL_ARCHIVE"

python3 - \
  "$WORK_DIR/install" \
  "$INSTALL_ARCHIVE" <<'PY'
import sys
import tarfile
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])

with tarfile.open(
    target,
    "w:gz",
) as archive:
    for path in sorted(source.rglob("*")):
        archive.add(
            path,
            arcname=path.relative_to(source),
            recursive=False,
        )
PY

python3 - "$MODEL_DE" "$MODEL_EN" <<'PY'
import json
import sys
from pathlib import Path

for filename in sys.argv[1:]:
    path = Path(filename)

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        json.load(handle)

    print(f"Valid JSON: {path.name}")
PY

CHECKSUM_FILE="$OUTPUT_DIR/SHA256SUMS"

(
  cd "$OUTPUT_DIR"

  sha256sum \
    "$(basename "$LAMBDA_ZIP")" \
    "$(basename "$MODEL_DE")" \
    "$(basename "$MODEL_EN")" \
    "$(basename "$INSTALL_ARCHIVE")" \
    >"$(basename "$CHECKSUM_FILE")"

  sha256sum --check \
    "$(basename "$CHECKSUM_FILE")"
)

printf '\nRelease assets created:\n'

find "$OUTPUT_DIR" \
  -maxdepth 1 \
  -type f \
  -printf '  %f\n' \
| sort
