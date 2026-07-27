#!/usr/bin/env python3

import hashlib
import hmac
import os
import re

from bridge_common import (
    STREAM_SECRET,
    create_navidrome_stream_url,
    decode_resource_id,
    encode_resource_id,
)
from resolver import load_queue


MUSIC_STREAM_TTL = int(
    os.environ.get(
        "MUSIC_STREAM_TTL",
        "14400",
    )
)

TOKEN_PATTERN = re.compile(
    r"^ndq1\."
    r"(song|album|artist|playlist|random)\."
    r"([A-Za-z0-9_-]+)\."
    r"([0-9]+)\."
    r"([0-9a-f]{32})$"
)


def _token_signature(
    kind,
    encoded_resource_id,
    index,
):
    message = (
        f"queue|1|{kind}|"
        f"{encoded_resource_id}|"
        f"{index}"
    ).encode("utf-8")

    return hmac.new(
        STREAM_SECRET,
        message,
        hashlib.sha256,
    ).hexdigest()[:32]


def create_queue_token(
    kind,
    resource_id,
    index,
):
    encoded_resource_id = (
        encode_resource_id(
            str(resource_id)
        )
    )

    signature = _token_signature(
        kind,
        encoded_resource_id,
        index,
    )

    return (
        f"ndq1.{kind}."
        f"{encoded_resource_id}."
        f"{index}."
        f"{signature}"
    )


def parse_queue_token(token):
    match = TOKEN_PATTERN.fullmatch(
        str(token or "")
    )

    if not match:
        raise ValueError(
            "Invalid Alexa token."
        )

    kind = match.group(1)
    encoded_resource_id = (
        match.group(2)
    )
    index = int(
        match.group(3)
    )
    supplied_signature = (
        match.group(4)
    )

    expected_signature = (
        _token_signature(
            kind,
            encoded_resource_id,
            index,
        )
    )

    if not hmac.compare_digest(
        supplied_signature,
        expected_signature,
    ):
        raise ValueError(
            "Invalid token signature."
        )

    resource_id = decode_resource_id(
        encoded_resource_id
    )

    return {
        "kind": kind,
        "resourceId": resource_id,
        "index": index,
    }


def _track_result(
    queue,
    index,
):
    tracks = queue["tracks"]

    if (
        index < 0
        or index >= len(tracks)
    ):
        raise IndexError(
            "Track position outside "
            "der Warteschlange."
        )

    track = tracks[index]

    token = create_queue_token(
        queue["kind"],
        queue["resourceId"],
        index,
    )

    return {
        "status": "ok",
        "provider": "navidrome",
        "match": track,
        "queue": {
            "kind": queue["kind"],
            "title": queue["title"],
            "artist": queue["artist"],
            "index": index,
            "position": index + 1,
            "count": len(tracks),
            "hasNext":
                index + 1 < len(tracks),
        },
        "stream": {
            "url":
                create_navidrome_stream_url(
                    track["id"],
                    MUSIC_STREAM_TTL,
                ),
            "token": token,
            "ttlSeconds":
                MUSIC_STREAM_TTL,
        },
    }


def create_first_queue_result(queue):
    return _track_result(
        queue,
        0,
    )


def create_current_queue_result(
    current_token,
):
    token_data = parse_queue_token(
        current_token
    )

    queue = load_queue(
        token_data["kind"],
        token_data["resourceId"],
    )

    return _track_result(
        queue,
        token_data["index"],
    )


def create_previous_queue_result(
    current_token,
):
    token_data = parse_queue_token(
        current_token
    )

    queue = load_queue(
        token_data["kind"],
        token_data["resourceId"],
    )

    previous_index = max(
        token_data["index"] - 1,
        0,
    )

    return _track_result(
        queue,
        previous_index,
    )


def create_next_queue_result(
    current_token,
):
    token_data = parse_queue_token(
        current_token
    )

    queue = load_queue(
        token_data["kind"],
        token_data["resourceId"],
    )

    next_index = (
        token_data["index"] + 1
    )

    if (
        next_index
        >= len(queue["tracks"])
    ):
        return {
            "status": "end",
            "provider": "navidrome",
            "queue": {
                "kind": queue["kind"],
                "title": queue["title"],
                "artist": queue["artist"],
                "index":
                    token_data["index"],
                "position":
                    token_data["index"] + 1,
                "count":
                    len(queue["tracks"]),
                "hasNext": False,
            },
        }

    return _track_result(
        queue,
        next_index,
    )
