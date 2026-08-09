#!/usr/bin/env python3

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT / "bridge" / "app"),
)


os.environ.setdefault(
    "STREAM_SECRET",
    "0123456789abcdef0123456789abcdef",
)

os.environ.setdefault(
    "CONTROL_SECRET",
    "fedcba9876543210fedcba9876543210",
)

os.environ.setdefault(
    "PUBLIC_BASE_URL",
    "https://media.example.com",
)

os.environ.setdefault(
    "NAVIDROME_URL",
    "http://navidrome:4533",
)

os.environ.setdefault(
    "NAVIDROME_USERNAME_B64",
    "dGVzdA==",
)

os.environ.setdefault(
    "NAVIDROME_PASSWORD_B64",
    "dGVzdA==",
)

os.environ.setdefault(
    "AUDIOBOOKSHELF_URL",
    "http://audiobookshelf:80",
)

os.environ.setdefault(
    "AUDIOBOOKSHELF_TOKEN_B64",
    "dGVzdA==",
)

os.environ.setdefault(
    "AUDIOBOOKSHELF_LIBRARY_ID",
    "test-library",
)


import lyrics
import queue_tokens


def synced_payload():
    return {
        "lyricsList": {
            "structuredLyrics": [
                {
                    "synced": True,
                    "offset": None,
                    "line": [
                        {
                            "start": 1000,
                            "value": "First <&>",
                        },
                        {
                            "start": 2000,
                            "value": "",
                        },
                        {
                            "start": 3000,
                            "value": "Second",
                        },
                    ],
                }
            ]
        }
    }


def test_webvtt_conversion():
    content = lyrics.build_navidrome_webvtt(
        synced_payload(),
        4,
    )

    assert content is not None

    assert content.startswith(
        "WEBVTT\n\n"
    )

    assert (
        "00:00:01.000 --> 00:00:02.000"
        in content
    )

    assert (
        "00:00:03.000 --> 00:00:04.000"
        in content
    )

    assert (
        "First &lt;&amp;&gt;"
        in content
    )

    assert "Second" in content


def test_unsynced_lyrics_are_ignored():
    payload = {
        "lyricsList": {
            "structuredLyrics": [
                {
                    "synced": False,
                    "line": [
                        {
                            "value":
                                "Unsynchronized text",
                        }
                    ],
                }
            ]
        }
    }

    assert (
        lyrics.build_navidrome_webvtt(
            payload,
            180,
        )
        is None
    )


def test_duplicate_timestamps_are_rejected():
    payload = {
        "lyricsList": {
            "structuredLyrics": [
                {
                    "synced": True,
                    "line": [
                        {
                            "start": 1000,
                            "value": "One",
                        },
                        {
                            "start": 1000,
                            "value": "Two",
                        },
                    ],
                }
            ]
        }
    }

    assert (
        lyrics.build_navidrome_webvtt(
            payload,
            180,
        )
        is None
    )


def test_backwards_timestamps_are_rejected():
    payload = {
        "lyricsList": {
            "structuredLyrics": [
                {
                    "synced": True,
                    "line": [
                        {
                            "start": 2000,
                            "value": "Later",
                        },
                        {
                            "start": 1000,
                            "value": "Earlier",
                        },
                    ],
                }
            ]
        }
    }

    assert (
        lyrics.build_navidrome_webvtt(
            payload,
            180,
        )
        is None
    )


def test_nonzero_offset_is_ignored():
    payload = {
        "lyricsList": {
            "structuredLyrics": [
                {
                    "synced": True,
                    "offset": 500,
                    "line": [
                        {
                            "start": 1000,
                            "value": "One",
                        },
                        {
                            "start": 2000,
                            "value": "Two",
                        },
                    ],
                }
            ]
        }
    }

    assert (
        lyrics.build_navidrome_webvtt(
            payload,
            180,
        )
        is None
    )


def test_lyrics_api_failure_is_nonfatal():
    original = lyrics.navidrome_json

    def fail(
        endpoint,
        parameters,
    ):
        raise RuntimeError(
            "simulated API failure"
        )

    try:
        lyrics.navidrome_json = fail

        assert (
            lyrics.create_navidrome_caption_data(
                "song-1",
                180,
            )
            is None
        )

    finally:
        lyrics.navidrome_json = original


def test_caption_data_shape():
    original = lyrics.navidrome_json

    try:
        lyrics.navidrome_json = (
            lambda endpoint, parameters:
                synced_payload()
        )

        result = (
            lyrics.create_navidrome_caption_data(
                "song-1",
                4,
            )
        )

    finally:
        lyrics.navidrome_json = original

    assert result is not None
    assert result["type"] == "WEBVTT"

    assert result["content"].startswith(
        "WEBVTT\n\n"
    )


def test_queue_preserves_cover_and_captions():
    original_stream = (
        queue_tokens
        .create_navidrome_stream_url
    )

    original_cover = (
        queue_tokens
        .create_navidrome_cover_url
    )

    original_caption = (
        queue_tokens
        .create_navidrome_caption_data
    )

    try:
        queue_tokens.create_navidrome_stream_url = (
            lambda song_id, lifetime:
                "https://media.example.com/audio"
        )

        queue_tokens.create_navidrome_cover_url = (
            lambda cover_id, lifetime:
                "https://media.example.com/cover.jpg"
        )

        queue_tokens.create_navidrome_caption_data = (
            lambda song_id, duration: {
                "type": "WEBVTT",
                "content": (
                    "WEBVTT\n\n"
                    "00:00:01.000 --> "
                    "00:00:02.000\n"
                    "Test\n"
                ),
            }
        )

        queue = {
            "kind": "song",
            "resourceId": "song-1",
            "title": "Bosco",
            "artist": "Placebo",
            "tracks": [
                {
                    "id": "song-1",
                    "title": "Bosco",
                    "artist": "Placebo",
                    "album": "Loud Like Love",
                    "duration": 402,
                    "coverArt": "cover-1",
                }
            ],
        }

        result = queue_tokens._track_result(
            queue,
            0,
        )

        assert (
            result["match"]["coverUrl"]
            == "https://media.example.com/cover.jpg"
        )

        assert (
            result["stream"]
            ["captionData"]
            ["type"]
            == "WEBVTT"
        )

        queue_tokens.create_navidrome_caption_data = (
            lambda song_id, duration:
                None
        )

        fallback = queue_tokens._track_result(
            queue,
            0,
        )

        assert (
            "captionData"
            not in fallback["stream"]
        )

        assert (
            fallback["match"]["coverUrl"]
            == "https://media.example.com/cover.jpg"
        )

    finally:
        queue_tokens.create_navidrome_stream_url = (
            original_stream
        )

        queue_tokens.create_navidrome_cover_url = (
            original_cover
        )

        queue_tokens.create_navidrome_caption_data = (
            original_caption
        )


def main():
    tests = [
        test_webvtt_conversion,
        test_unsynced_lyrics_are_ignored,
        test_duplicate_timestamps_are_rejected,
        test_backwards_timestamps_are_rejected,
        test_nonzero_offset_is_ignored,
        test_lyrics_api_failure_is_nonfatal,
        test_caption_data_shape,
        test_queue_preserves_cover_and_captions,
    ]

    for test in tests:
        test()

        print(
            "Passed:",
            test.__name__,
        )

    print(
        "Lyrics regression tests passed."
    )


if __name__ == "__main__":
    main()
