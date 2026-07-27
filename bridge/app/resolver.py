#!/usr/bin/env python3

import hashlib
import os
import secrets
import time

from bridge_common import (
    navidrome_json,
    normalize_list,
)


VALID_MODES = {
    "auto",
    "song",
    "album",
    "artist",
    "playlist",
    "random",
}

MAX_ARTIST_TRACKS = 500

MAX_RANDOM_TRACKS = int(
    os.environ.get(
        "MAX_RANDOM_TRACKS",
        "500",
    )
)

ALL_SONGS_CACHE_TTL = int(
    os.environ.get(
        "ALL_SONGS_CACHE_TTL",
        "300",
    )
)

_ALL_SONGS_CACHE = {
    "loadedAt": 0.0,
    "songs": None,
}


def _text(value):
    return str(value or "").strip()


def _fold(value):
    return _text(value).casefold()


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _song_payload(song):
    return {
        "id": _text(song.get("id")),
        "title": _text(song.get("title")),
        "artist": _text(song.get("artist")),
        "album": _text(song.get("album")),
        "duration": _integer(
            song.get("duration")
        ),
        "track": _integer(
            song.get("track")
        ),
        "disc": _integer(
            song.get("discNumber")
            or song.get("disc")
        ),
    }


def _album_sort_key(album):
    year = _integer(
        album.get("year"),
        9999,
    )

    if year <= 0:
        year = 9999

    return (
        year,
        _fold(album.get("name")),
        _text(album.get("id")),
    )


def _song_sort_key(song):
    disc = _integer(
        song.get("disc"),
        1,
    )

    track = _integer(
        song.get("track"),
        9999,
    )

    if disc <= 0:
        disc = 1

    if track <= 0:
        track = 9999

    return (
        disc,
        track,
        _fold(song.get("title")),
        _text(song.get("id")),
    )


def _deduplicate_songs(songs):
    result = []
    seen = set()

    for song in songs:
        song_id = _text(
            song.get("id")
        )

        if (
            not song_id
            or song_id in seen
        ):
            continue

        seen.add(song_id)
        result.append(song)

    return result


def _find_exact(
    items,
    field,
    query,
):
    query_folded = query.casefold()

    for item in items:
        if (
            _fold(item.get(field))
            == query_folded
        ):
            return item

    return None


def _best_named_match(
    items,
    field,
    query,
):
    exact = _find_exact(
        items,
        field,
        query,
    )

    if exact is not None:
        return exact

    query_folded = query.casefold()
    query_words = set(
        query_folded.split()
    )

    scored = []

    for item in items:
        value = _fold(
            item.get(field)
        )

        if not value:
            continue

        score = 0

        if query_folded in value:
            score += 100

        value_words = set(
            value.split()
        )

        score += 10 * len(
            query_words & value_words
        )

        if value.startswith(
            query_folded
        ):
            score += 25

        scored.append(
            (
                score,
                value,
                _text(item.get("id")),
                item,
            )
        )

    scored.sort(
        key=lambda entry: (
            -entry[0],
            entry[1],
            entry[2],
        )
    )

    if (
        not scored
        or scored[0][0] <= 0
    ):
        return None

    return scored[0][3]


def _search(query):
    result = navidrome_json(
        "search3",
        {
            "query": query,
            "artistCount": 25,
            "albumCount": 25,
            "songCount": 100,
        },
    )

    search_result = result.get(
        "searchResult3",
        {},
    )

    return {
        "artists": normalize_list(
            search_result.get("artist")
        ),
        "albums": normalize_list(
            search_result.get("album")
        ),
        "songs": normalize_list(
            search_result.get("song")
        ),
    }


def _load_playlists():
    result = navidrome_json(
        "getPlaylists",
        {},
    )

    playlists = result.get(
        "playlists",
        {},
    )

    return normalize_list(
        playlists.get("playlist")
    )


def _load_all_songs_uncached():
    albums = []
    offset = 0
    page_size = 100

    while True:
        result = navidrome_json(
            "getAlbumList2",
            {
                "type":
                    "alphabeticalByName",
                "size": page_size,
                "offset": offset,
            },
        )

        page = normalize_list(
            result.get(
                "albumList2",
                {},
            ).get("album")
        )

        albums.extend(page)

        if len(page) < page_size:
            break

        offset += page_size

    songs = []

    for album in albums:
        album_id = _text(
            album.get("id")
        )

        if not album_id:
            continue

        album_result = navidrome_json(
            "getAlbum",
            {
                "id": album_id,
            },
        )

        full_album = (
            album_result.get("album")
            or {}
        )

        songs.extend(
            _song_payload(song)
            for song in normalize_list(
                full_album.get("song")
            )
        )

    songs = [
        song
        for song in songs
        if song["id"]
    ]

    return _deduplicate_songs(
        songs
    )


def _load_all_songs():
    now = time.monotonic()

    cached_songs = (
        _ALL_SONGS_CACHE["songs"]
    )

    loaded_at = float(
        _ALL_SONGS_CACHE["loadedAt"]
    )

    if (
        cached_songs is not None
        and now - loaded_at
        < ALL_SONGS_CACHE_TTL
    ):
        return list(
            cached_songs
        )

    songs = _load_all_songs_uncached()

    _ALL_SONGS_CACHE["songs"] = list(
        songs
    )

    _ALL_SONGS_CACHE["loadedAt"] = now

    return songs


def load_song_queue(song_id):
    result = navidrome_json(
        "getSong",
        {
            "id": song_id,
        },
    )

    song = result.get("song") or {}
    payload = _song_payload(song)

    if not payload["id"]:
        raise LookupError(
            "The track no longer exists."
        )

    return {
        "kind": "song",
        "resourceId": payload["id"],
        "title": payload["title"],
        "artist": payload["artist"],
        "tracks": [
            payload,
        ],
    }


def load_album_queue(album_id):
    result = navidrome_json(
        "getAlbum",
        {
            "id": album_id,
        },
    )

    album = result.get("album") or {}

    songs = [
        _song_payload(song)
        for song in normalize_list(
            album.get("song")
        )
    ]

    songs = [
        song
        for song in songs
        if song["id"]
    ]

    songs = _deduplicate_songs(
        songs
    )

    songs.sort(
        key=_song_sort_key
    )

    if not songs:
        raise LookupError(
            "The album contains no tracks."
        )

    return {
        "kind": "album",
        "resourceId": _text(
            album.get("id")
            or album_id
        ),
        "title": _text(
            album.get("name")
            or album.get("title")
        ),
        "artist": _text(
            album.get("artist")
        ),
        "tracks": songs,
    }


def load_artist_queue(artist_id):
    result = navidrome_json(
        "getArtist",
        {
            "id": artist_id,
        },
    )

    artist = result.get("artist") or {}

    albums = normalize_list(
        artist.get("album")
    )

    albums.sort(
        key=_album_sort_key
    )

    songs = []

    for album in albums:
        album_id = _text(
            album.get("id")
        )

        if not album_id:
            continue

        album_queue = load_album_queue(
            album_id
        )

        songs.extend(
            album_queue["tracks"]
        )

        if (
            len(songs)
            >= MAX_ARTIST_TRACKS
        ):
            songs = songs[
                :MAX_ARTIST_TRACKS
            ]
            break

    songs = _deduplicate_songs(
        songs
    )

    if not songs:
        raise LookupError(
            "Für diesen Künstler wurden "
            "no tracks found."
        )

    artist_name = _text(
        artist.get("name")
    )

    return {
        "kind": "artist",
        "resourceId": _text(
            artist.get("id")
            or artist_id
        ),
        "title": artist_name,
        "artist": artist_name,
        "tracks": songs,
    }


def load_playlist_queue(playlist_id):
    result = navidrome_json(
        "getPlaylist",
        {
            "id": playlist_id,
        },
    )

    playlist = (
        result.get("playlist")
        or {}
    )

    songs = [
        _song_payload(song)
        for song in normalize_list(
            playlist.get("entry")
        )
    ]

    songs = [
        song
        for song in songs
        if song["id"]
    ]

    songs = _deduplicate_songs(
        songs
    )

    if not songs:
        raise LookupError(
            "The playlist contains no tracks."
        )

    return {
        "kind": "playlist",
        "resourceId": _text(
            playlist.get("id")
            or playlist_id
        ),
        "title": _text(
            playlist.get("name")
        ),
        "artist": "",
        "tracks": songs,
    }


def load_random_queue(seed):
    seed = _text(seed)

    if not seed:
        raise ValueError(
            "Invalid random key."
        )

    songs = _load_all_songs()

    if not songs:
        raise LookupError(
            "Die Musikbibliothek ist leer."
        )

    def random_sort_key(song):
        value = (
            seed
            + "|"
            + song["id"]
        ).encode("utf-8")

        return hashlib.sha256(
            value
        ).digest()

    songs.sort(
        key=random_sort_key
    )

    songs = songs[
        :MAX_RANDOM_TRACKS
    ]

    return {
        "kind": "random",
        "resourceId": seed,
        "title": "Zufallswiedergabe",
        "artist": "",
        "tracks": songs,
    }


def load_queue(
    kind,
    resource_id,
):
    if kind == "song":
        return load_song_queue(
            resource_id
        )

    if kind == "album":
        return load_album_queue(
            resource_id
        )

    if kind == "artist":
        return load_artist_queue(
            resource_id
        )

    if kind == "playlist":
        return load_playlist_queue(
            resource_id
        )

    if kind == "random":
        return load_random_queue(
            resource_id
        )

    raise ValueError(
        "Unbekannter Warteschlangentyp."
    )


def resolve_navidrome_queue(
    query,
    mode="auto",
):
    query = query.strip()
    mode = mode.strip().lower()

    if mode not in VALID_MODES:
        raise ValueError(
            "Invalid playback mode."
        )

    if mode == "random":
        seed = secrets.token_hex(16)

        return load_random_queue(
            seed
        )

    if not query:
        raise ValueError(
            "Der Suchbegriff ist leer."
        )

    if mode == "playlist":
        playlists = _load_playlists()

        playlist = _best_named_match(
            playlists,
            "name",
            query,
        )

        if playlist is None:
            raise LookupError(
                "No matching playlist found."
            )

        return load_playlist_queue(
            _text(
                playlist.get("id")
            )
        )

    search = _search(query)

    exact_song = _find_exact(
        search["songs"],
        "title",
        query,
    )

    exact_album = _find_exact(
        search["albums"],
        "name",
        query,
    )

    exact_artist = _find_exact(
        search["artists"],
        "name",
        query,
    )

    if mode == "song":
        item = exact_song

        if (
            item is None
            and search["songs"]
        ):
            item = search["songs"][0]

        if item is None:
            raise LookupError(
                "No matching track found."
            )

        return load_song_queue(
            _text(item.get("id"))
        )

    if mode == "album":
        item = exact_album

        if (
            item is None
            and search["albums"]
        ):
            item = search["albums"][0]

        if item is None:
            raise LookupError(
                "No matching album found."
            )

        return load_album_queue(
            _text(item.get("id"))
        )

    if mode == "artist":
        item = exact_artist

        if (
            item is None
            and search["artists"]
        ):
            item = search["artists"][0]

        if item is None:
            raise LookupError(
                "No matching artist found."
            )

        return load_artist_queue(
            _text(item.get("id"))
        )

    if exact_song is not None:
        return load_song_queue(
            _text(
                exact_song.get("id")
            )
        )

    if exact_album is not None:
        return load_album_queue(
            _text(
                exact_album.get("id")
            )
        )

    if exact_artist is not None:
        return load_artist_queue(
            _text(
                exact_artist.get("id")
            )
        )

    if search["songs"]:
        return load_song_queue(
            _text(
                search["songs"][0].get(
                    "id"
                )
            )
        )

    if search["albums"]:
        return load_album_queue(
            _text(
                search["albums"][0].get(
                    "id"
                )
            )
        )

    if search["artists"]:
        return load_artist_queue(
            _text(
                search["artists"][0].get(
                    "id"
                )
            )
        )

    raise LookupError(
        "No matching content found."
    )
