#!/usr/bin/env python3

import math

from bridge_common import (
    navidrome_json,
    normalize_list,
)


def _finite_number(value):
    if isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _timestamp(milliseconds):
    milliseconds = int(milliseconds)

    hours, remainder = divmod(
        milliseconds,
        3_600_000,
    )

    minutes, remainder = divmod(
        remainder,
        60_000,
    )

    seconds, millis = divmod(
        remainder,
        1_000,
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}."
        f"{millis:03d}"
    )


def _cue_text(value):
    value = str(value or "")

    value = value.replace(
        "\r\n",
        "\n",
    )

    value = value.replace(
        "\r",
        "\n",
    )

    value = value.replace(
        "\x00",
        "",
    )

    value = value.strip()

    value = value.replace(
        "&",
        "&amp;",
    )

    value = value.replace(
        "<",
        "&lt;",
    )

    value = value.replace(
        ">",
        "&gt;",
    )

    return value


def build_navidrome_webvtt(
    lyrics_result,
    duration_seconds,
):
    duration = _finite_number(
        duration_seconds
    )

    if (
        duration is None
        or duration <= 0
    ):
        return None

    duration_ms = int(
        round(
            duration * 1000
        )
    )

    lyrics_list = (
        lyrics_result.get("lyricsList")
        or {}
    )

    tracks = normalize_list(
        lyrics_list.get(
            "structuredLyrics"
        )
    )

    for track in tracks:
        if not isinstance(track, dict):
            continue

        if track.get("synced") is not True:
            continue

        # Non-zero offsets are deliberately ignored
        # until their handling has been verified
        # end-to-end with real library data.
        offset = _finite_number(
            track.get("offset")
        )

        if (
            offset is not None
            and offset != 0
        ):
            continue

        events = []

        for line in normalize_list(
            track.get("line")
        ):
            if not isinstance(line, dict):
                continue

            start = _finite_number(
                line.get("start")
            )

            if (
                start is None
                or start < 0
            ):
                continue

            events.append(
                {
                    "start": int(
                        round(start)
                    ),
                    "value": _cue_text(
                        line.get("value")
                    ),
                }
            )

        if len(events) < 2:
            continue

        if any(
            current["start"]
            <= previous["start"]
            for previous, current
            in zip(
                events,
                events[1:],
            )
        ):
            continue

        cues = []

        for index, event in enumerate(
            events
        ):
            start = event["start"]

            if index + 1 < len(events):
                end = events[
                    index + 1
                ]["start"]
            else:
                end = duration_ms

            value = event["value"]

            if not value:
                continue

            if start >= duration_ms:
                continue

            end = min(
                end,
                duration_ms,
            )

            if end <= start:
                continue

            cues.append(
                {
                    "start": start,
                    "end": end,
                    "value": value,
                }
            )

        if not cues:
            continue

        parts = [
            "WEBVTT",
            "",
        ]

        for cue in cues:
            parts.append(
                (
                    f"{_timestamp(cue['start'])}"
                    " --> "
                    f"{_timestamp(cue['end'])}"
                )
            )

            parts.append(
                cue["value"]
            )

            parts.append("")

        return "\n".join(parts)

    return None


def create_navidrome_caption_data(
    song_id,
    duration_seconds,
):
    song_id = str(
        song_id or ""
    ).strip()

    if not song_id:
        return None

    try:
        lyrics_result = navidrome_json(
            "getLyricsBySongId",
            {
                "id": song_id,
            },
        )
    except Exception:
        # Lyrics are optional and must never
        # prevent audio playback.
        return None

    content = build_navidrome_webvtt(
        lyrics_result,
        duration_seconds,
    )

    if not content:
        return None

    return {
        "type": "WEBVTT",
        "content": content,
    }
