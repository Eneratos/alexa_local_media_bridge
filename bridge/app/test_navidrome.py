#!/usr/bin/env python3

import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.environ.get(
    "NAVIDROME_URL",
    "http://navidrome:4533",
).rstrip("/")

USERNAME = base64.b64decode(
    os.environ["NAVIDROME_USERNAME_B64"]
).decode("utf-8")

PASSWORD = base64.b64decode(
    os.environ["NAVIDROME_PASSWORD_B64"]
).decode("utf-8")

CLIENT_NAME = "AlexaMediaBridge"
API_VERSION = "1.16.1"


def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def auth_parameters():
    salt = secrets.token_hex(8)

    token = hashlib.md5(
        (PASSWORD + salt).encode("utf-8")
    ).hexdigest()

    return {
        "u": USERNAME,
        "t": token,
        "s": salt,
        "v": API_VERSION,
        "c": CLIENT_NAME,
        "f": "json",
    }


def create_url(endpoint, parameters=None):
    query = auth_parameters()

    if parameters:
        query.update(parameters)

    return (
        f"{BASE_URL}/rest/{endpoint}.view?"
        + urllib.parse.urlencode(query)
    )


def api_request(endpoint, parameters=None):
    request = urllib.request.Request(
        create_url(endpoint, parameters),
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
        code = error.get("code", "unknown")
        message = error.get(
            "message",
            "Unknown API error",
        )

        raise RuntimeError(
            f"Navidrome error {code}: {message}"
        )

    return result


def main():
    query = "Placebo"

    if len(sys.argv) > 1:
        query = sys.argv[1]

    ping = api_request("ping")

    print("=== Navidrome-Verbindung ===")
    print(f"Status:        {ping.get('status')}")
    print(f"Server:        {ping.get('type', 'unknown')}")
    print(
        f"Serverversion: "
        f"{ping.get('serverVersion', 'unknown')}"
    )
    print()

    search = api_request(
        "search3",
        {
            "query": query,
            "artistCount": 5,
            "albumCount": 5,
            "songCount": 10,
        },
    )

    search_result = search.get(
        "searchResult3",
        {},
    )

    artists = normalize_list(
        search_result.get("artist")
    )

    albums = normalize_list(
        search_result.get("album")
    )

    songs = normalize_list(
        search_result.get("song")
    )

    print("=== Suche ===")
    print(f"Suchbegriff:   {query}")
    print(f"Künstler:      {len(artists)}")
    print(f"Alben:         {len(albums)}")
    print(f"Track:         {len(songs)}")

    for artist in artists[:3]:
        print(
            "Künstlerfund:  "
            + str(artist.get("name", "unknown"))
        )

    for album in albums[:3]:
        print(
            "Albumfund:     "
            + str(album.get("name", "unknown"))
        )

    if not songs:
        random_result = api_request(
            "getRandomSongs",
            {
                "size": 1,
            },
        )

        songs = normalize_list(
            random_result
            .get("randomSongs", {})
            .get("song")
        )

        print(
            "No direct track match; "
            "verwende einen Zufallstitel."
        )

    if not songs:
        raise RuntimeError(
            "Navidrome returned no track."
        )

    song = songs[0]
    song_id = str(song["id"])

    print()
    print("=== Gewählter Testtitel ===")
    print(
        "Track:         "
        + str(song.get("title", "unknown"))
    )
    print(
        "Künstler:      "
        + str(song.get("artist", "unknown"))
    )
    print(
        "Album:         "
        + str(song.get("album", "unknown"))
    )
    print(
        "Quelldatei:    "
        + str(song.get("suffix", "unknown"))
    )
    print(
        "Dauer:         "
        + str(song.get("duration", "unknown"))
        + " seconds"
    )

    stream_url = create_url(
        "stream",
        {
            "id": song_id,
            "format": "mp3",
            "maxBitRate": 320,
            "estimateContentLength": "true",
        },
    )

    stream_request = urllib.request.Request(
        stream_url,
        headers={
            "User-Agent": "AlexaMediaBridge/0.3",
            "Range": "bytes=0-65535",
        },
    )

    with urllib.request.urlopen(
        stream_request,
        timeout=30,
    ) as response:
        audio_data = response.read(65536)

        print()
        print("=== Streamtest ===")
        print(f"HTTP-Status:   {response.status}")
        print(
            "Content-Type: "
            + str(
                response.headers.get(
                    "Content-Type",
                    "fehlt",
                )
            )
        )
        print(
            "Content-Range:"
            + " "
            + str(
                response.headers.get(
                    "Content-Range",
                    "nicht gesetzt",
                )
            )
        )
        print(
            "Testdaten:     "
            + str(len(audio_data))
            + " Bytes"
        )

    print()
    print("Navidrome-API und Stream funktionieren.")


if __name__ == "__main__":
    try:
        main()

    except urllib.error.HTTPError as error:
        print(
            f"HTTP error: {error.code} "
            f"{error.reason}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    except Exception as error:
        print(
            f"Error: {error}",
            file=sys.stderr,
        )
        raise SystemExit(1)
