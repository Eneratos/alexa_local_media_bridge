#!/usr/bin/env python3

import sys

from bridge_common import (
    create_navidrome_stream_url,
    navidrome_json,
    normalize_list,
)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: sign_navidrome_url.py "
            "\"search query\" [lifetime]"
        )

    query = sys.argv[1]

    lifetime = 1800

    if len(sys.argv) >= 3:
        lifetime = int(sys.argv[2])

    result = navidrome_json(
        "search3",
        {
            "query": query,
            "artistCount": 5,
            "albumCount": 5,
            "songCount": 50,
        },
    )

    songs = normalize_list(
        result
        .get("searchResult3", {})
        .get("song")
    )

    if not songs:
        raise SystemExit(
            "No matching track found."
        )

    exact_matches = [
        song
        for song in songs
        if str(
            song.get("title", "")
        ).casefold() == query.casefold()
    ]

    if exact_matches:
        song = exact_matches[0]
    else:
        song = songs[0]

    song_id = str(song["id"])

    print(
        "Selected: "
        + str(song.get("artist", "unknown"))
        + " – "
        + str(song.get("title", "unknown"))
        + " ["
        + str(song.get("album", "unknown"))
        + "]",
        file=sys.stderr,
    )

    print(
        create_navidrome_stream_url(
            song_id,
            lifetime,
        )
    )


if __name__ == "__main__":
    main()
