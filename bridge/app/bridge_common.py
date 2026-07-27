#!/usr/bin/env python3

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
import urllib.request


STREAM_SECRET = os.environ["STREAM_SECRET"].encode("utf-8")

MAX_TOKEN_LIFETIME = int(
    os.environ.get("MAX_TOKEN_LIFETIME", "14400")
)

PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"].rstrip("/")

NAVIDROME_URL = os.environ.get(
    "NAVIDROME_URL",
    "http://navidrome:4533",
).rstrip("/")

NAVIDROME_USERNAME = base64.b64decode(
    os.environ["NAVIDROME_USERNAME_B64"]
).decode("utf-8")

NAVIDROME_PASSWORD = base64.b64decode(
    os.environ["NAVIDROME_PASSWORD_B64"]
).decode("utf-8")

NAVIDROME_CLIENT = "AlexaMediaBridge"
NAVIDROME_API_VERSION = "1.16.1"


def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def navidrome_auth_parameters():
    salt = secrets.token_hex(8)

    token = hashlib.md5(
        (NAVIDROME_PASSWORD + salt).encode("utf-8")
    ).hexdigest()

    return {
        "u": NAVIDROME_USERNAME,
        "t": token,
        "s": salt,
        "v": NAVIDROME_API_VERSION,
        "c": NAVIDROME_CLIENT,
        "f": "json",
    }


def navidrome_url(endpoint, parameters=None):
    query = navidrome_auth_parameters()

    if parameters:
        query.update(parameters)

    return (
        f"{NAVIDROME_URL}/rest/{endpoint}.view?"
        + urllib.parse.urlencode(query)
    )


def navidrome_json(endpoint, parameters=None):
    request = urllib.request.Request(
        navidrome_url(endpoint, parameters),
        headers={
            "User-Agent": "AlexaMediaBridge/0.3",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=15,
    ) as response:
        payload = json.load(response)

    result = payload.get(
        "subsonic-response",
        {},
    )

    if result.get("status") != "ok":
        error = result.get("error", {})

        raise RuntimeError(
            "Navidrome error "
            + str(error.get("code", "unknown"))
            + ": "
            + str(
                error.get(
                    "message",
                    "Unknown API error",
                )
            )
        )

    return result


def encode_resource_id(resource_id):
    encoded = base64.urlsafe_b64encode(
        resource_id.encode("utf-8")
    ).decode("ascii")

    return encoded.rstrip("=")


def decode_resource_id(encoded):
    padding = "=" * (-len(encoded) % 4)

    return base64.urlsafe_b64decode(
        encoded + padding
    ).decode("utf-8")


def create_signature(
    resource_type,
    encoded_resource_id,
    expires,
):
    message = (
        f"{resource_type}|"
        f"{encoded_resource_id}|"
        f"{expires}"
    ).encode("utf-8")

    return hmac.new(
        STREAM_SECRET,
        message,
        hashlib.sha256,
    ).hexdigest()


def signature_is_valid(
    resource_type,
    encoded_resource_id,
    expires,
    supplied_signature,
):
    now = int(time.time())

    if expires < now:
        return False

    if expires > now + MAX_TOKEN_LIFETIME:
        return False

    expected_signature = create_signature(
        resource_type,
        encoded_resource_id,
        expires,
    )

    return hmac.compare_digest(
        expected_signature,
        supplied_signature,
    )


def create_navidrome_stream_url(
    song_id,
    lifetime_seconds,
):
    if (
        lifetime_seconds < 1
        or lifetime_seconds > MAX_TOKEN_LIFETIME
    ):
        raise ValueError(
            "Gültigkeit muss zwischen 1 und "
            f"{MAX_TOKEN_LIFETIME} seconds."
        )

    encoded_song_id = encode_resource_id(
        str(song_id)
    )

    expires = int(time.time()) + lifetime_seconds

    signature = create_signature(
        "navidrome",
        encoded_song_id,
        expires,
    )

    return (
        f"{PUBLIC_BASE_URL}/stream/navidrome/"
        f"{encoded_song_id}/{expires}/"
        f"{signature}.mp3"
    )
