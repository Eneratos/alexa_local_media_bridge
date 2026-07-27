#!/usr/bin/env python3

import base64
import hashlib
import hmac
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from abs_common import (
    AUDIOBOOKSHELF_TOKEN,
    AUDIOBOOKSHELF_URL,
    abs_json,
)


STREAM_SECRET = os.environ[
    "STREAM_SECRET"
].encode("utf-8")

PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL",
    "",
).rstrip("/")

AUDIOBOOKSHELF_LIBRARY_ID = os.environ.get(
    "AUDIOBOOKSHELF_LIBRARY_ID",
    "",
).strip()

MUSIC_STREAM_TTL = int(
    os.environ.get(
        "MUSIC_STREAM_TTL",
        "14400",
    )
)

MAX_TOKEN_LIFETIME = int(
    os.environ.get(
        "MAX_TOKEN_LIFETIME",
        "14400",
    )
)


MAX_ABS_SEEK_SECONDS = int(
    os.environ.get(
        "MAX_ABS_SEEK_SECONDS",
        "86400",
    )
)

ABS_STREAM_PATTERN = re.compile(
    r"^/stream/audiobookshelf/"
    r"([A-Za-z0-9_-]+)/"
    r"([0-9]{10})/"
    r"([0-9a-f]{64})\.m4b$"
)

ABS_TOKEN_PATTERN = re.compile(
    r"^abs1\."
    r"([A-Za-z0-9_-]+)\."
    r"([A-Za-z0-9_-]+)\."
    r"([0-9a-f]{32})$"
)


def _text(value):
    return str(
        value or ""
    ).strip()


def _fold(value):
    return _text(
        value
    ).casefold()


def _encode_text(value):
    raw = str(value).encode(
        "utf-8"
    )

    return base64.urlsafe_b64encode(
        raw
    ).decode(
        "ascii"
    ).rstrip("=")


def _decode_text(value):
    padding = "=" * (
        (-len(value)) % 4
    )

    return base64.urlsafe_b64decode(
        value + padding
    ).decode("utf-8")


def _stream_signature(
    encoded_resource,
    expires,
):
    message = (
        "audiobookshelf|"
        + encoded_resource
        + "|"
        + str(expires)
    ).encode("utf-8")

    return hmac.new(
        STREAM_SECRET,
        message,
        hashlib.sha256,
    ).hexdigest()


def _token_signature(
    encoded_session_id,
    encoded_item_id,
):
    message = (
        "abs-token|1|"
        + encoded_session_id
        + "|"
        + encoded_item_id
    ).encode("utf-8")

    return hmac.new(
        STREAM_SECRET,
        message,
        hashlib.sha256,
    ).hexdigest()[:32]


def create_abs_token(
    session_id,
    item_id,
):
    encoded_session_id = (
        _encode_text(
            session_id
        )
    )

    encoded_item_id = (
        _encode_text(
            item_id
        )
    )

    signature = _token_signature(
        encoded_session_id,
        encoded_item_id,
    )

    return (
        "abs1."
        + encoded_session_id
        + "."
        + encoded_item_id
        + "."
        + signature
    )


def parse_abs_token(token):
    match = ABS_TOKEN_PATTERN.fullmatch(
        _text(token)
    )

    if not match:
        raise ValueError(
            "Invalid audiobook token."
        )

    encoded_session_id = (
        match.group(1)
    )

    encoded_item_id = (
        match.group(2)
    )

    supplied_signature = (
        match.group(3)
    )

    expected_signature = (
        _token_signature(
            encoded_session_id,
            encoded_item_id,
        )
    )

    if not hmac.compare_digest(
        supplied_signature,
        expected_signature,
    ):
        raise ValueError(
            "Invalid audiobook token signature."
        )

    return {
        "sessionId":
            _decode_text(
                encoded_session_id
            ),
        "itemId":
            _decode_text(
                encoded_item_id
            ),
    }


def create_abs_stream_url(
    session_id,
    item_id,
    content_url,
    lifetime=None,
):
    if not PUBLIC_BASE_URL:
        raise RuntimeError(
            "PUBLIC_BASE_URL fehlt."
        )

    if lifetime is None:
        lifetime = MUSIC_STREAM_TTL

    lifetime = int(
        lifetime
    )

    if (
        lifetime < 60
        or lifetime
        > MAX_TOKEN_LIFETIME
    ):
        raise ValueError(
            "Invalid stream lifetime."
        )

    resource = {
        "sessionId": session_id,
        "itemId": item_id,
        "contentUrl": content_url,
    }

    encoded_resource = _encode_text(
        json.dumps(
            resource,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )

    expires = (
        int(time.time())
        + lifetime
    )

    signature = _stream_signature(
        encoded_resource,
        expires,
    )

    return (
        PUBLIC_BASE_URL
        + "/stream/audiobookshelf/"
        + encoded_resource
        + "/"
        + str(expires)
        + "/"
        + signature
        + ".m4b"
    )


def _series_payload(metadata):
    series = metadata.get(
        "series"
    ) or []

    if isinstance(
        series,
        dict,
    ):
        series = [
            series,
        ]

    result = []

    for entry in series:
        if not isinstance(
            entry,
            dict,
        ):
            continue

        result.append({
            "id":
                _text(
                    entry.get("id")
                ),
            "name":
                _text(
                    entry.get("name")
                ),
            "sequence":
                _text(
                    entry.get("sequence")
                ),
        })

    return result


def _result_score(
    result,
    query,
):
    item = (
        result.get(
            "libraryItem"
        )
        or {}
    )

    media = (
        item.get("media")
        or {}
    )

    metadata = (
        media.get("metadata")
        or {}
    )

    title = _fold(
        metadata.get("title")
    )

    author = _fold(
        metadata.get("authorName")
        or metadata.get("author")
    )

    series_entries = (
        _series_payload(
            metadata
        )
    )

    series_text = " ".join(
        (
            entry["name"]
            + " "
            + entry["sequence"]
        ).strip()
        for entry in series_entries
    ).casefold()

    query_folded = query.casefold()
    query_words = set(
        query_folded.split()
    )

    corpus = " ".join(
        [
            title,
            author,
            series_text,
        ]
    )

    score = 0

    if title == query_folded:
        score += 1000

    if query_folded in title:
        score += 300

    if query_folded in series_text:
        score += 200

    if title.startswith(
        query_folded
    ):
        score += 100

    score += 20 * len(
        query_words
        & set(corpus.split())
    )

    return score


def _select_search_result(
    query,
):
    if not AUDIOBOOKSHELF_LIBRARY_ID:
        raise RuntimeError(
            "AUDIOBOOKSHELF_LIBRARY_ID fehlt."
        )

    response = abs_json(
        "/api/libraries/"
        + AUDIOBOOKSHELF_LIBRARY_ID
        + "/search",
        query={
            "q": query,
            "limit": 25,
        },
    )

    results = response.get(
        "book"
    ) or []

    candidates = []

    for result in results:
        item = (
            result.get(
                "libraryItem"
            )
            or {}
        )

        item_id = _text(
            item.get("id")
        )

        if not item_id:
            continue

        candidates.append(
            (
                _result_score(
                    result,
                    query,
                ),
                item_id,
                result,
            )
        )

    candidates.sort(
        key=lambda entry: (
            -entry[0],
            entry[1],
        )
    )

    if (
        not candidates
        or candidates[0][0] <= 0
    ):
        raise LookupError(
            "No matching audiobook found."
        )

    return candidates[0][2]


def _select_track(
    tracks,
    resume_seconds,
):
    if not tracks:
        raise LookupError(
            "Audiobookshelf lieferte "
            "keine Audio-Tracks."
        )

    selected = tracks[0]

    for track in tracks:
        start = float(
            track.get(
                "startOffset"
            )
            or 0
        )

        duration = float(
            track.get(
                "duration"
            )
            or 0
        )

        if (
            resume_seconds >= start
            and (
                duration <= 0
                or resume_seconds
                < start + duration
            )
        ):
            selected = track
            break

    return selected


def resolve_audiobook(
    query="",
    from_start=False,
    item_id="",
    start_at_seconds=None,
):
    query = _text(
        query
    )

    item_id = _text(
        item_id
    )

    if item_id:
        if len(item_id) > 200:
            raise ValueError(
                "Invalid audiobook ID."
            )

    else:
        if (
            not query
            or len(query) > 200
        ):
            raise ValueError(
                "Invalid audiobook search query."
            )

        search_result = (
            _select_search_result(
                query
            )
        )

        result_item = (
            search_result.get(
                "libraryItem"
            )
            or {}
        )

        item_id = _text(
            result_item.get("id")
        )

    item = abs_json(
        "/api/items/"
        + item_id,
        query={
            "expanded": 1,
            "include":
                "progress,authors",
        },
    )

    media = (
        item.get("media")
        or {}
    )

    metadata = (
        media.get("metadata")
        or {}
    )

    progress = (
        item.get(
            "userMediaProgress"
        )
        or {}
    )

    resume_seconds = float(
        progress.get(
            "currentTime"
        )
        or 0
    )

    requested_start = None

    if from_start:
        requested_start = 0.0

    elif start_at_seconds is not None:
        requested_start = _float(
            start_at_seconds,
            -1.0,
        )

        if (
            requested_start < 0
            or not math.isfinite(
                requested_start
            )
        ):
            raise ValueError(
                "Invalid audiobook start position."
            )

    if requested_start is not None:
        media_duration = max(
            0.0,
            _float(
                media.get(
                    "duration"
                )
            ),
        )

        if media_duration > 0:
            requested_start = min(
                requested_start,
                media_duration,
            )

            progress_ratio = min(
                1.0,
                requested_start
                / media_duration,
            )
        else:
            progress_ratio = 0.0

        abs_json(
            "/api/me/progress/"
            + item_id,
            method="PATCH",
            payload={
                "currentTime":
                    round(
                        requested_start,
                        3,
                    ),
                "progress":
                    progress_ratio,
                "isFinished":
                    False,
            },
            expect_json=False,
        )

        resume_seconds = requested_start

    session = abs_json(
        "/api/items/"
        + item_id
        + "/play",
        method="POST",
        payload={
            "deviceInfo": {
                "deviceId":
                    "alexa-media-bridge",
                "clientName":
                    "Alexa Media Bridge",
                "clientVersion":
                    "1.0.1",
                "manufacturer":
                    "Amazon",
                "model":
                    "Alexa AudioPlayer",
            },
            "forceDirectPlay": True,
            "forceTranscode": False,
            "supportedMimeTypes": [
                "audio/mp4",
                "audio/m4a",
                "audio/aac",
                "audio/mpeg",
            ],
            "mediaPlayer":
                "alexa-audioplayer",
        },
    )

    session_id = _text(
        session.get("id")
        or session.get(
            "sessionId"
        )
    )

    if not session_id:
        raise RuntimeError(
            "Audiobookshelf lieferte "
            "keine Session-ID."
        )

    try:
        tracks = (
            session.get(
                "audioTracks"
            )
            or []
        )

        track = _select_track(
            tracks,
            resume_seconds,
        )

        content_url = _text(
            track.get(
                "contentUrl"
            )
        )

        if not content_url:
            raise RuntimeError(
                "Der Audiobookshelf-Track "
                "hat keine Content-URL."
            )

        track_start = float(
            track.get(
                "startOffset"
            )
            or 0
        )

        track_offset_seconds = max(
            0.0,
            resume_seconds
            - track_start,
        )

        duration = float(
            session.get(
                "duration"
            )
            or media.get(
                "duration"
            )
            or 0
        )

        title = _text(
            metadata.get("title")
            or session.get(
                "displayTitle"
            )
        )

        author = _text(
            metadata.get(
                "authorName"
            )
            or metadata.get(
                "author"
            )
            or session.get(
                "displayAuthor"
            )
        )

        chapters = (
            media.get("chapters")
            or session.get(
                "chapters"
            )
            or []
        )

        stream_url = (
            create_abs_stream_url(
                session_id,
                item_id,
                content_url,
            )
        )

        token = create_abs_token(
            session_id,
            item_id,
        )

        return {
            "status": "ok",
            "provider":
                "audiobookshelf",
            "match": {
                "itemId": item_id,
                "title": title,
                "author": author,
                "series":
                    _series_payload(
                        metadata
                    ),
                "duration": duration,
                "chapterCount":
                    len(chapters),
            },
            "playback": {
                "sessionId":
                    session_id,
                "resumeSeconds":
                    resume_seconds,
                "offsetInMilliseconds":
                    int(
                        round(
                            track_offset_seconds
                            * 1000
                        )
                    ),
                "trackIndex":
                    track.get("index"),
                "trackCount":
                    len(tracks),
                "trackStartOffset":
                    track_start,
            },
            "stream": {
                "url": stream_url,
                "token": token,
                "mimeType":
                    _text(
                        track.get(
                            "mimeType"
                        )
                    )
                    or "audio/mp4",
                "ttlSeconds":
                    MUSIC_STREAM_TTL,
            },
        }

    except Exception:
        try:
            abs_json(
                "/api/session/"
                + session_id
                + "/close",
                method="POST",
                payload={
                    "currentTime":
                        resume_seconds,
                    "timeListened": 0,
                    "duration":
                        float(
                            session.get(
                                "duration"
                            )
                            or 0
                        ),
                },
                expect_json=False,
            )
        except Exception:
            pass

        raise


def restart_audiobook(token):
    token_data = parse_abs_token(
        token
    )

    return resolve_audiobook(
        from_start=True,
        item_id=token_data["itemId"],
    )


VALID_CHAPTER_ACTIONS = {
    "next",
    "previous",
    "number",
}


def _normalized_chapters(chapters):
    result = []

    for chapter in chapters or []:
        if not isinstance(
            chapter,
            dict,
        ):
            continue

        start = max(
            0.0,
            _float(
                chapter.get(
                    "start"
                )
            ),
        )

        end = max(
            start,
            _float(
                chapter.get(
                    "end"
                ),
                start,
            ),
        )

        result.append({
            "id":
                chapter.get(
                    "id"
                ),
            "start": start,
            "end": end,
            "title":
                _text(
                    chapter.get(
                        "title"
                    )
                ),
        })

    result.sort(
        key=lambda chapter: (
            chapter["start"],
            chapter["end"],
            chapter["title"],
        )
    )

    return result


def _chapter_index_at(
    chapters,
    current_time,
):
    selected_index = 0

    for index, chapter in enumerate(
        chapters
    ):
        start = chapter["start"]
        end = chapter["end"]

        if current_time < start:
            break

        selected_index = index

        if (
            current_time >= start
            and (
                end <= start
                or current_time < end
            )
        ):
            break

    return selected_index


def _absolute_session_position(
    session,
    offset_in_milliseconds,
):
    offset_ms = _integer(
        offset_in_milliseconds
    )

    if (
        offset_ms is None
        or offset_ms < 0
    ):
        raise ValueError(
            "Invalid audiobook position."
        )

    resume_seconds = max(
        0.0,
        _float(
            session.get(
                "currentTime"
            ),
            _float(
                session.get(
                    "startTime"
                )
            ),
        ),
    )

    tracks = (
        session.get(
            "audioTracks"
        )
        or []
    )

    if not tracks:
        return resume_seconds

    track = _select_track(
        tracks,
        resume_seconds,
    )

    track_start = max(
        0.0,
        _float(
            track.get(
                "startOffset"
            )
        ),
    )

    track_duration = max(
        0.0,
        _float(
            track.get(
                "duration"
            )
        ),
    )

    current_time = (
        track_start
        + offset_ms / 1000.0
    )

    if (
        offset_ms == 0
        and resume_seconds > track_start
    ):
        current_time = resume_seconds

    if track_duration > 0:
        current_time = min(
            current_time,
            track_start
            + track_duration,
        )

    duration = max(
        0.0,
        _float(
            session.get(
                "duration"
            )
        ),
    )

    if duration > 0:
        current_time = min(
            current_time,
            duration,
        )

    return max(
        0.0,
        current_time,
    )


def seek_audiobook_chapter(
    token,
    action,
    offset_in_milliseconds=0,
    chapter_number=None,
):
    action = _text(
        action
    ).lower()

    if action not in VALID_CHAPTER_ACTIONS:
        raise ValueError(
            "Invalid chapter action."
        )

    token_data = parse_abs_token(
        token
    )

    session_id = token_data[
        "sessionId"
    ]

    item_id = token_data[
        "itemId"
    ]

    item = abs_json(
        "/api/items/"
        + item_id,
        query={
            "expanded": 1,
            "include":
                "progress,authors",
        },
    )

    media = (
        item.get(
            "media"
        )
        or {}
    )

    chapters = _normalized_chapters(
        media.get(
            "chapters"
        )
    )

    if not chapters:
        raise LookupError(
            "The audiobook contains "
            "no chapter markers."
        )

    progress = (
        item.get(
            "userMediaProgress"
        )
        or {}
    )

    current_time = max(
        0.0,
        _float(
            progress.get(
                "currentTime"
            )
        ),
    )

    session = None

    try:
        session = abs_json(
            "/api/session/"
            + session_id
        )
    except RuntimeError as error:
        if (
            "Audiobookshelf HTTP 404:"
            not in str(error)
        ):
            raise

    if session is not None:
        session_item_id = _text(
            session.get(
                "libraryItemId"
            )
        )

        if (
            session_item_id
            and session_item_id != item_id
        ):
            raise ValueError(
                "Audiobook session and token "
                "passen nicht zusammen."
            )

        current_time = (
            _absolute_session_position(
                session,
                offset_in_milliseconds,
            )
        )

    current_index = _chapter_index_at(
        chapters,
        current_time,
    )

    if action == "next":
        target_index = (
            current_index + 1
        )

        if target_index >= len(
            chapters
        ):
            return {
                "status": "end",
                "provider":
                    "audiobookshelf",
                "chapter": {
                    "number":
                        current_index + 1,
                    "count":
                        len(chapters),
                    "title":
                        chapters[
                            current_index
                        ]["title"],
                },
            }

    elif action == "previous":
        target_index = max(
            0,
            current_index - 1,
        )

    else:
        parsed_number = _integer(
            chapter_number
        )

        if (
            parsed_number is None
            or parsed_number < 1
            or parsed_number > len(
                chapters
            )
        ):
            raise ValueError(
                "This chapter number "
                "gibt es nicht."
            )

        target_index = (
            parsed_number - 1
        )

    target_chapter = chapters[
        target_index
    ]

    if session is not None:
        close_audiobook_playback(
            token,
            "stopped",
            offset_in_milliseconds,
        )

    result = resolve_audiobook(
        item_id=item_id,
        start_at_seconds=
            target_chapter[
                "start"
            ],
    )

    result["chapter"] = {
        "id":
            target_chapter["id"],
        "number":
            target_index + 1,
        "count":
            len(chapters),
        "title":
            target_chapter[
                "title"
            ],
        "start":
            target_chapter[
                "start"
            ],
        "end":
            target_chapter[
                "end"
            ],
    }

    return result


VALID_TIME_SEEK_DIRECTIONS = {
    "forward",
    "backward",
}


def seek_audiobook_time(
    token,
    direction,
    seconds,
    offset_in_milliseconds=0,
):
    direction = _text(
        direction
    ).lower()

    if (
        direction
        not in VALID_TIME_SEEK_DIRECTIONS
    ):
        raise ValueError(
            "Invalid seek direction."
        )

    seek_seconds = _float(
        seconds,
        -1.0,
    )

    if (
        seek_seconds <= 0
        or not math.isfinite(
            seek_seconds
        )
        or seek_seconds
        > MAX_ABS_SEEK_SECONDS
    ):
        raise ValueError(
            "Invalid duration."
        )

    token_data = parse_abs_token(
        token
    )

    session_id = token_data[
        "sessionId"
    ]

    item_id = token_data[
        "itemId"
    ]

    item = abs_json(
        "/api/items/"
        + item_id,
        query={
            "expanded": 1,
            "include":
                "progress,authors",
        },
    )

    media = (
        item.get(
            "media"
        )
        or {}
    )

    progress = (
        item.get(
            "userMediaProgress"
        )
        or {}
    )

    current_time = max(
        0.0,
        _float(
            progress.get(
                "currentTime"
            )
        ),
    )

    duration = max(
        0.0,
        _float(
            media.get(
                "duration"
            )
        ),
    )

    session = None

    try:
        session = abs_json(
            "/api/session/"
            + session_id
        )
    except RuntimeError as error:
        if (
            "Audiobookshelf HTTP 404:"
            not in str(error)
        ):
            raise

    if session is not None:
        session_item_id = _text(
            session.get(
                "libraryItemId"
            )
        )

        if (
            session_item_id
            and session_item_id != item_id
        ):
            raise ValueError(
                "Audiobook session and token "
                "passen nicht zusammen."
            )

        current_time = (
            _absolute_session_position(
                session,
                offset_in_milliseconds,
            )
        )

        duration = max(
            duration,
            _float(
                session.get(
                    "duration"
                )
            ),
        )

    if direction == "forward":
        requested_time = (
            current_time
            + seek_seconds
        )
    else:
        requested_time = (
            current_time
            - seek_seconds
        )

    target_time = max(
        0.0,
        requested_time,
    )

    boundary = ""

    if requested_time < 0:
        boundary = "start"

    if duration > 0:
        if duration > 1.0:
            maximum_time = (
                duration - 1.0
            )
        else:
            maximum_time = 0.0

        if target_time > maximum_time:
            target_time = maximum_time
            boundary = "end"

    if session is not None:
        close_audiobook_playback(
            token,
            "stopped",
            offset_in_milliseconds,
        )

    result = resolve_audiobook(
        item_id=item_id,
        start_at_seconds=
            target_time,
    )

    result["seek"] = {
        "direction": direction,
        "seconds":
            round(
                seek_seconds,
                3,
            ),
        "fromSeconds":
            round(
                current_time,
                3,
            ),
        "toSeconds":
            round(
                target_time,
                3,
            ),
        "boundary": boundary,
    }

    return result



VALID_ABS_PROGRESS_EVENTS = {
    "stopped",
    "finished",
}


def _integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def close_audiobook_playback(
    token,
    event,
    offset_in_milliseconds,
):
    event = _text(
        event
    ).lower()

    if event not in VALID_ABS_PROGRESS_EVENTS:
        raise ValueError(
            "Invalid audiobook event."
        )

    offset_ms = _integer(
        offset_in_milliseconds
    )

    if (
        offset_ms is None
        or offset_ms < 0
    ):
        raise ValueError(
            "Invalid audiobook position."
        )

    token_data = parse_abs_token(
        token
    )

    session_id = token_data[
        "sessionId"
    ]

    item_id = token_data[
        "itemId"
    ]

    try:
        session = abs_json(
            "/api/session/"
            + session_id
        )
    except RuntimeError as error:
        if (
            "Audiobookshelf HTTP 404:"
            in str(error)
        ):
            return {
                "status": "ok",
                "provider":
                    "audiobookshelf",
                "event": event,
                "session": {
                    "id": session_id,
                    "state":
                        "alreadyClosed",
                },
            }

        raise

    session_item_id = _text(
        session.get(
            "libraryItemId"
        )
    )

    if (
        session_item_id
        and session_item_id != item_id
    ):
        raise ValueError(
            "Audiobook session and token "
            "passen nicht zusammen."
        )

    duration = max(
        0.0,
        _float(
            session.get(
                "duration"
            )
        ),
    )

    resume_seconds = max(
        0.0,
        _float(
            session.get(
                "currentTime"
            ),
            _float(
                session.get(
                    "startTime"
                )
            ),
        ),
    )

    tracks = (
        session.get(
            "audioTracks"
        )
        or []
    )

    track_start = 0.0
    track_duration = 0.0

    if tracks:
        track = _select_track(
            tracks,
            resume_seconds,
        )

        track_start = max(
            0.0,
            _float(
                track.get(
                    "startOffset"
                )
            ),
        )

        track_duration = max(
            0.0,
            _float(
                track.get(
                    "duration"
                )
            ),
        )

    alexa_track_seconds = (
        offset_ms / 1000.0
    )

    if (
        event == "finished"
        and track_duration > 0
    ):
        current_time = (
            track_start
            + track_duration
        )
    else:
        current_time = (
            track_start
            + alexa_track_seconds
        )

    if (
        event == "stopped"
        and offset_ms == 0
        and resume_seconds > track_start
    ):
        current_time = resume_seconds

    if track_duration > 0:
        current_time = min(
            current_time,
            track_start
            + track_duration,
        )

    if duration > 0:
        current_time = min(
            current_time,
            duration,
        )

    current_time = max(
        0.0,
        current_time,
    )

    time_listened = max(
        0.0,
        current_time
        - resume_seconds,
    )

    payload = {
        "currentTime":
            round(
                current_time,
                3,
            ),
        "timeListened":
            round(
                time_listened,
                3,
            ),
        "duration":
            round(
                duration,
                3,
            ),
    }

    try:
        abs_json(
            "/api/session/"
            + session_id
            + "/close",
            method="POST",
            payload=payload,
            expect_json=False,
        )
    except RuntimeError as error:
        if (
            "Audiobookshelf HTTP 404:"
            in str(error)
        ):
            return {
                "status": "ok",
                "provider":
                    "audiobookshelf",
                "event": event,
                "session": {
                    "id": session_id,
                    "state":
                        "alreadyClosed",
                },
            }

        raise

    return {
        "status": "ok",
        "provider":
            "audiobookshelf",
        "event": event,
        "session": {
            "id": session_id,
            "state": "closed",
        },
        "progress": {
            "currentTime":
                payload[
                    "currentTime"
                ],
            "timeListened":
                payload[
                    "timeListened"
                ],
            "duration":
                payload[
                    "duration"
                ],
            "isFinished": bool(
                duration > 0
                and current_time
                >= max(
                    0.0,
                    duration - 1.0,
                )
            ),
        },
    }

def _send_416(
    handler,
    error,
):
    handler.send_response(416)

    content_range = (
        error.headers.get(
            "Content-Range"
        )
    )

    if content_range:
        handler.send_header(
            "Content-Range",
            content_range,
        )

    handler.send_header(
        "Accept-Ranges",
        "bytes",
    )

    handler.send_header(
        "Content-Length",
        "0",
    )

    handler.send_header(
        "Cache-Control",
        "private, no-store",
    )

    handler._common_headers()
    handler.end_headers()


def try_proxy_abs_stream(
    handler,
    path,
    send_body,
):
    match = ABS_STREAM_PATTERN.fullmatch(
        path
    )

    if not match:
        return False

    encoded_resource = (
        match.group(1)
    )

    expires = int(
        match.group(2)
    )

    supplied_signature = (
        match.group(3)
    )

    if (
        expires < int(time.time())
        or expires
        > int(time.time())
        + MAX_TOKEN_LIFETIME
    ):
        handler._send_empty(403)
        return True

    expected_signature = (
        _stream_signature(
            encoded_resource,
            expires,
        )
    )

    if not hmac.compare_digest(
        supplied_signature,
        expected_signature,
    ):
        handler._send_empty(403)
        return True

    try:
        resource = json.loads(
            _decode_text(
                encoded_resource
            )
        )

        content_url = _text(
            resource.get(
                "contentUrl"
            )
        )

        if not content_url:
            raise ValueError(
                "Content-URL fehlt."
            )

    except Exception:
        handler._send_empty(403)
        return True

    upstream_url = urllib.parse.urljoin(
        AUDIOBOOKSHELF_URL + "/",
        content_url.lstrip("/"),
    )

    headers = {
        "Authorization":
            "Bearer "
            + AUDIOBOOKSHELF_TOKEN,
        "Accept-Encoding":
            "identity",
        "User-Agent":
            "AlexaMediaBridge/1.0.1",
    }

    range_header = handler.headers.get(
        "Range"
    )

    if range_header:
        headers["Range"] = (
            range_header
        )

    elif not send_body:
        headers["Range"] = (
            "bytes=0-0"
        )

    request = urllib.request.Request(
        upstream_url,
        headers=headers,
        method="GET",
    )

    try:
        response = urllib.request.urlopen(
            request,
            timeout=60,
        )

    except urllib.error.HTTPError as error:
        print(
            "Audiobookshelf meldet HTTP "
            + str(error.code),
            flush=True,
        )

        if error.code == 404:
            handler._send_empty(404)

        elif error.code == 416:
            _send_416(
                handler,
                error,
            )

        else:
            handler._send_empty(502)

        error.close()
        return True

    except Exception as error:
        print(
            "Audiobookshelf-Streamfehler: "
            + type(error).__name__,
            flush=True,
        )

        handler._send_empty(502)
        return True

    with response:
        status = response.status

        if status not in (
            200,
            206,
        ):
            handler._send_empty(502)
            return True

        handler.send_response(
            status
        )

        handler.send_header(
            "Content-Type",
            response.headers.get(
                "Content-Type",
                "audio/mp4",
            ),
        )

        for header_name in (
            "Content-Length",
            "Content-Range",
            "ETag",
            "Last-Modified",
        ):
            value = response.headers.get(
                header_name
            )

            if value:
                handler.send_header(
                    header_name,
                    value,
                )

        handler.send_header(
            "Accept-Ranges",
            response.headers.get(
                "Accept-Ranges",
                "bytes",
            ),
        )

        handler.send_header(
            "Cache-Control",
            "private, no-store",
        )

        if not response.headers.get(
            "Content-Length"
        ):
            handler.send_header(
                "Connection",
                "close",
            )

            handler.close_connection = True

        handler._common_headers()
        handler.end_headers()

        if not send_body:
            return True

        while True:
            chunk = response.read(
                128 * 1024
            )

            if not chunk:
                break

            try:
                handler.wfile.write(
                    chunk
                )

            except (
                BrokenPipeError,
                ConnectionResetError,
            ):
                break

    return True
