#!/usr/bin/env python3

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from app_version import BRIDGE_VERSION


AUDIOBOOKSHELF_URL = os.environ.get(
    "AUDIOBOOKSHELF_URL",
    "http://audiobookshelf:80",
).rstrip("/")

_token_b64 = os.environ.get(
    "AUDIOBOOKSHELF_TOKEN_B64",
    "",
).strip()

if not _token_b64:
    raise RuntimeError(
        "AUDIOBOOKSHELF_TOKEN_B64 is not configured."
    )

try:
    AUDIOBOOKSHELF_TOKEN = base64.b64decode(
        _token_b64
    ).decode("utf-8")
except Exception as error:
    raise RuntimeError(
        "Audiobookshelf token is not valid base64-encoded UTF-8."
    ) from error


def abs_json(
    path,
    method="GET",
    payload=None,
    query=None,
    expect_json=True,
):
    url = (
        AUDIOBOOKSHELF_URL
        + "/"
        + str(path).lstrip("/")
    )

    if query:
        url += "?" + urllib.parse.urlencode(
            query,
            doseq=True,
        )

    body = None

    headers = {
        "Authorization":
            "Bearer " + AUDIOBOOKSHELF_TOKEN,
        "Accept":
            "application/json",
        "User-Agent":
            f"AlexaMediaBridge/{BRIDGE_VERSION}",
    }

    if payload is not None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        headers["Content-Type"] = (
            "application/json"
        )

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            raw = response.read()

    except urllib.error.HTTPError as error:
        detail = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            "Audiobookshelf HTTP "
            + str(error.code)
            + ": "
            + detail[:500]
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            "Audiobookshelf is not reachable: "
            + str(error.reason)
        ) from error

    if not raw:
        return {}

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError(
            "Audiobookshelf returned an invalid "
            "UTF-8 response."
        ) from error

    if not expect_json:
        return {
            "text": text,
        }

    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Audiobookshelf returned invalid "
            "JSON."
        ) from error
