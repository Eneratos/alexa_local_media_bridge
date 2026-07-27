#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version_file = root / "VERSION"
errors = []

if not version_file.is_file():
    raise SystemExit("VERSION file is missing.")

version = version_file.read_text(encoding="utf-8").strip()

if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
    errors.append(f"Invalid VERSION value: {version!r}")

def expect(label, actual, expected):
    if actual != expected:
        errors.append(
            f"{label}: expected {expected!r}, found {actual!r}"
        )

env_values = {}
env_path = root / "bridge" / ".env.example"

for line in env_path.read_text(encoding="utf-8").splitlines():
    if "=" not in line or line.lstrip().startswith("#"):
        continue
    key, value = line.split("=", 1)
    env_values[key] = value

expect("bridge/.env.example IMAGE_TAG",
       env_values.get("IMAGE_TAG"), version)

compose = (root / "bridge" / "compose.yml").read_text(
    encoding="utf-8"
)
compose_tag = f"${{IMAGE_TAG:-{version}}}"

if compose_tag not in compose:
    errors.append(
        "bridge/compose.yml does not use the central version fallback."
    )

setup = (root / "scripts" / "setup.sh").read_text(
    encoding="utf-8"
)
setup_default = (
    """$(tr -d "[:space:]" < "$ROOT_DIR/VERSION")"""
)

if setup_default not in setup:
    errors.append(
        "scripts/setup.sh does not read its default image tag from VERSION."
    )

release_script = (
    root / "scripts" / "build_release_assets.sh"
).read_text(encoding="utf-8")
release_default = 'VERSION="${1:-$(tr -d "[:space:]" < "$ROOT_DIR/VERSION")}"'

if release_default not in release_script:
    errors.append(
        "build_release_assets.sh does not default to the VERSION file."
    )

package_path = root / "skill" / "lambda" / "package.json"
lock_path = root / "skill" / "lambda" / "package-lock.json"

package = json.loads(package_path.read_text(encoding="utf-8"))
lock = json.loads(lock_path.read_text(encoding="utf-8"))

expect("package.json version", package.get("version"), version)
expect("package-lock.json version", lock.get("version"), version)
expect(
    "package-lock.json root package version",
    lock.get("packages", {}).get("", {}).get("version"),
    version,
)

if package.get("private") is not True:
    errors.append("The Lambda npm package must remain private.")

expect("package.json license", package.get("license"), "MIT")
expect(
    "package-lock.json root package license",
    lock.get("packages", {}).get("", {}).get("license"),
    "MIT",
)

license_path = root / "LICENSE"
bridge_license_path = root / "bridge" / "LICENSE"

if not license_path.is_file():
    errors.append("The root LICENSE file is missing.")
elif not bridge_license_path.is_file():
    errors.append("bridge/LICENSE is missing.")
elif license_path.read_bytes() != bridge_license_path.read_bytes():
    errors.append("bridge/LICENSE differs from the root LICENSE.")

if errors:
    print("Version consistency check failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"Version consistency check passed: {version}")
