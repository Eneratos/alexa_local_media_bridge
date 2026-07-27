#!/usr/bin/env python3

from bridge_common import navidrome_json
from queue_tokens import parse_queue_token
from resolver import load_queue


VALID_EVENTS = {
    "started",
    "finished",
}


def _integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _track_for_token(token):
    token_data = parse_queue_token(
        token
    )

    queue = load_queue(
        token_data["kind"],
        token_data["resourceId"],
    )

    index = token_data["index"]
    tracks = queue["tracks"]

    if (
        index < 0
        or index >= len(tracks)
    ):
        raise ValueError(
            "Track position outside "
            "der Warteschlange."
        )

    return (
        queue,
        tracks[index],
        index,
    )


def scrobble_queue_token(
    token,
    event,
    listened_at_ms=None,
):
    event = str(
        event or ""
    ).strip().lower()

    if event not in VALID_EVENTS:
        raise ValueError(
            "Invalid scrobble event."
        )

    queue, track, index = (
        _track_for_token(token)
    )

    song_id = str(
        track.get("id") or ""
    ).strip()

    if not song_id:
        raise LookupError(
            "The track no longer exists."
        )

    submission = (
        event == "finished"
    )

    parameters = {
        "id": song_id,
        "submission":
            "true"
            if submission
            else "false",
    }

    submitted_at = None

    if submission:
        submitted_at = _integer(
            listened_at_ms
        )

        if (
            submitted_at is not None
            and submitted_at <= 0
        ):
            raise ValueError(
                "Invalid playback timestamp."
            )

        if submitted_at is not None:
            parameters["time"] = str(
                submitted_at
            )

    navidrome_json(
        "scrobble",
        parameters,
    )

    return {
        "status": "ok",
        "provider": "navidrome",
        "event":
            "submitted"
            if submission
            else "nowPlaying",
        "match": track,
        "queue": {
            "kind": queue["kind"],
            "title": queue["title"],
            "artist": queue["artist"],
            "index": index,
            "position": index + 1,
            "count": len(
                queue["tracks"]
            ),
        },
        "scrobble": {
            "submission": submission,
            "time": submitted_at,
        },
    }
