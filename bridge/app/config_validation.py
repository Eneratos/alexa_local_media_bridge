#!/usr/bin/env python3

import base64
import binascii
import os
import sys
from urllib.parse import urlparse


def _value(name):
    return os.environ.get(name, "").strip()


def _check_url(
    name,
    default="",
    require_https=False,
    require_port_443=False,
):
    value = _value(name) or default

    if not value:
        return None

    parsed = urlparse(value)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
    ):
        return (
            f"{name} must be an absolute "
            "HTTP or HTTPS URL."
        )

    if require_https and parsed.scheme != "https":
        return f"{name} must use HTTPS."

    try:
        port = parsed.port
    except ValueError:
        return f"{name} contains an invalid port."

    if (
        require_port_443
        and port not in {None, 443}
    ):
        return f"{name} must use HTTPS port 443."

    if parsed.query or parsed.fragment:
        return (
            f"{name} must not contain "
            "a query string or fragment."
        )

    return None


def _check_base64(name):
    value = _value(name)

    if not value:
        return None

    try:
        decoded = base64.b64decode(
            value,
            validate=True,
        )
    except (ValueError, binascii.Error):
        return f"{name} must contain valid Base64."

    if not decoded:
        return (
            f"{name} must decode "
            "to a non-empty value."
        )

    try:
        decoded.decode("utf-8")
    except UnicodeDecodeError:
        return (
            f"{name} must decode "
            "to valid UTF-8."
        )

    return None


def _integer(
    name,
    default,
    minimum,
):
    raw = _value(name) or str(default)

    try:
        value = int(raw)
    except ValueError:
        return None, f"{name} must be an integer."

    if value < minimum:
        return (
            None,
            f"{name} must be at least {minimum}.",
        )

    return value, None


def validate_environment():
    errors = []

    required = (
        "STREAM_SECRET",
        "PUBLIC_BASE_URL",
        "NAVIDROME_USERNAME_B64",
        "NAVIDROME_PASSWORD_B64",
        "CONTROL_SECRET",
        "AUDIOBOOKSHELF_TOKEN_B64",
        "AUDIOBOOKSHELF_LIBRARY_ID",
    )

    for name in required:
        if not _value(name):
            errors.append(f"{name} is required.")

    for name in (
        "STREAM_SECRET",
        "CONTROL_SECRET",
    ):
        value = _value(name)

        if value and len(value) < 32:
            errors.append(
                f"{name} must contain "
                "at least 32 characters."
            )

    for error in (
        _check_url(
            "PUBLIC_BASE_URL",
            require_https=True,
            require_port_443=True,
        ),
        _check_url(
            "NAVIDROME_URL",
            default="http://navidrome:4533",
        ),
        _check_url(
            "AUDIOBOOKSHELF_URL",
            default="http://audiobookshelf:80",
        ),
        _check_base64(
            "NAVIDROME_USERNAME_B64"
        ),
        _check_base64(
            "NAVIDROME_PASSWORD_B64"
        ),
        _check_base64(
            "AUDIOBOOKSHELF_TOKEN_B64"
        ),
    ):
        if error:
            errors.append(error)

    music_ttl, error = _integer(
        "MUSIC_STREAM_TTL",
        14400,
        60,
    )
    if error:
        errors.append(error)

    max_lifetime, error = _integer(
        "MAX_TOKEN_LIFETIME",
        14400,
        60,
    )
    if error:
        errors.append(error)

    for name, default, minimum in (
        ("MAX_ABS_SEEK_SECONDS", 86400, 1),
        ("MAX_RANDOM_TRACKS", 500, 1),
        ("ALL_SONGS_CACHE_TTL", 300, 0),
        ("BRIDGE_PORT", 8000, 1),
    ):
        _, error = _integer(
            name,
            default,
            minimum,
        )

        if error:
            errors.append(error)

    if (
        music_ttl is not None
        and max_lifetime is not None
        and music_ttl > max_lifetime
    ):
        errors.append(
            "MUSIC_STREAM_TTL must not exceed "
            "MAX_TOKEN_LIFETIME."
        )

    if errors:
        print(
            "Configuration error:",
            file=sys.stderr,
        )

        for error in errors:
            print(
                f"- {error}",
                file=sys.stderr,
            )

        raise SystemExit(2)
