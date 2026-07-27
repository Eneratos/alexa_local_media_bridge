#!/usr/bin/env python3

import hmac
import json
import os
import re
import urllib.error
import urllib.request
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from urllib.parse import urlparse

from app_version import BRIDGE_VERSION
from config_validation import (
    validate_environment,
)


validate_environment()


from bridge_common import (
    decode_resource_id,
    navidrome_json,
    navidrome_url,
    signature_is_valid,
)
from queue_tokens import (
    create_current_queue_result,
    create_first_queue_result,
    create_next_queue_result,
    create_previous_queue_result,
)
from resolver import (
    resolve_navidrome_queue,
)

from scrobble import (
    scrobble_queue_token,
)


from abs_bridge import (
    close_audiobook_playback,
    resolve_audiobook,
    restart_audiobook,
    seek_audiobook_chapter,
    seek_audiobook_time,
    try_proxy_abs_stream,
)


HOST = "0.0.0.0"

PORT = int(
    os.environ.get(
        "BRIDGE_PORT",
        "8000",
    )
)


CONTROL_SECRET = os.environ[
    "CONTROL_SECRET"
]

NAVIDROME_STREAM_PATTERN = re.compile(
    r"^/stream/navidrome/"
    r"([A-Za-z0-9_-]+)/"
    r"([0-9]{10})/"
    r"([0-9a-f]{64})\.mp3$"
)


class BridgeHandler(
    BaseHTTPRequestHandler
):
    protocol_version = "HTTP/1.1"
    server_version = (
        f"AlexaMediaBridge/{BRIDGE_VERSION}"
    )

    def log_message(
        self,
        fmt,
        *args,
    ):
        message = fmt % args

        message = re.sub(
            r"/stream/navidrome/"
            r"[A-Za-z0-9_-]+/"
            r"[0-9]{10}/"
            r"[0-9a-f]{64}\.mp3",
            "/stream/navidrome/"
            "<redacted>.mp3",
            message,
        )

        message = re.sub(
            r"/stream/audiobookshelf/"
            r"[A-Za-z0-9_-]+/"
            r"[0-9]{10}/"
            r"[0-9a-f]{64}\.m4b",
            "/stream/audiobookshelf/"
            "<redacted>.m4b",
            message,
        )

        print(
            f"{self.client_address[0]} "
            f"[{self.log_date_time_string()}] "
            f"{message}",
            flush=True,
        )

    def _common_headers(self):
        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        self.send_header(
            "Referrer-Policy",
            "no-referrer",
        )

    def _send_empty(
        self,
        status,
    ):
        self.send_response(status)

        self.send_header(
            "Content-Length",
            "0",
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self._common_headers()
        self.end_headers()

    def _send_json(
        self,
        payload,
        status=200,
    ):
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self._common_headers()
        self.end_headers()

        self.wfile.write(body)

    def _send_health(
        self,
        send_body,
    ):
        body = json.dumps(
            {
                "status": "ok",
                "service": "alexa-media-bridge",
                "version": BRIDGE_VERSION,
            },
            separators=(",", ":"),
        ).encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self._common_headers()
        self.end_headers()

        if send_body:
            self.wfile.write(body)

    def _authorized(self):
        supplied = self.headers.get(
            "Authorization",
            "",
        )

        expected = (
            "Bearer "
            + CONTROL_SECRET
        )

        return hmac.compare_digest(
            supplied,
            expected,
        )

    def _read_json(self):
        length_text = self.headers.get(
            "Content-Length",
            "0",
        )

        try:
            content_length = int(
                length_text
            )
        except ValueError:
            raise ValueError(
                "Invalid Content-Length."
            )

        if (
            content_length < 1
            or content_length > 4096
        ):
            raise ValueError(
                "Invalid request size."
            )

        raw_body = self.rfile.read(
            content_length
        )

        try:
            return json.loads(
                raw_body.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            raise ValueError(
                "Invalid JSON."
            )

    def _proxy_navidrome(
        self,
        song_id,
        send_body,
    ):
        upstream_url = navidrome_url(
            "stream",
            {
                "id": song_id,
                "format": "mp3",
                "maxBitRate": 320,
                "estimateContentLength":
                    "true",
            },
        )

        headers = {
            "User-Agent":
                f"AlexaMediaBridge/{BRIDGE_VERSION}",
            "Accept-Encoding":
                "identity",
        }

        range_header = self.headers.get(
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
            response = (
                urllib.request.urlopen(
                    request,
                    timeout=60,
                )
            )

        except urllib.error.HTTPError as error:
            requested_range = self.headers.get(
                "Range",
                "",
            )

            print(
                "Navidrome returned HTTP "
                + str(error.code)
                + " for Range "
                + (
                    requested_range
                    or "<none>"
                ),
                flush=True,
            )

            if error.code == 404:
                self._send_empty(404)

            elif error.code == 416:
                self.send_response(416)

                content_range = error.headers.get(
                    "Content-Range"
                )

                if content_range:
                    self.send_header(
                        "Content-Range",
                        content_range,
                    )

                self.send_header(
                    "Accept-Ranges",
                    "bytes",
                )

                self.send_header(
                    "Content-Length",
                    "0",
                )

                self.send_header(
                    "Cache-Control",
                    "private, no-store",
                )

                self._common_headers()
                self.end_headers()

            else:
                self._send_empty(502)

            error.close()
            return

        except Exception as error:
            print(
                "Navidrome connection error: "
                + type(error).__name__,
                flush=True,
            )

            self._send_empty(502)
            return

        with response:
            status = response.status

            if status not in (
                200,
                206,
            ):
                self._send_empty(502)
                return

            self.send_response(status)

            self.send_header(
                "Content-Type",
                response.headers.get(
                    "Content-Type",
                    "audio/mpeg",
                ),
            )

            for header_name in (
                "Content-Length",
                "Content-Range",
                "ETag",
                "Last-Modified",
            ):
                value = (
                    response.headers.get(
                        header_name
                    )
                )

                if value:
                    self.send_header(
                        header_name,
                        value,
                    )

            self.send_header(
                "Accept-Ranges",
                response.headers.get(
                    "Accept-Ranges",
                    "bytes",
                ),
            )

            self.send_header(
                "Cache-Control",
                "private, no-store",
            )

            if not response.headers.get(
                "Content-Length"
            ):
                self.send_header(
                    "Connection",
                    "close",
                )

                self.close_connection = True

            self._common_headers()
            self.end_headers()

            if not send_body:
                return

            while True:
                chunk = response.read(
                    128 * 1024
                )

                if not chunk:
                    break

                try:
                    self.wfile.write(
                        chunk
                    )

                except (
                    BrokenPipeError,
                    ConnectionResetError,
                ):
                    break

    def _dispatch_get(
        self,
        send_body,
    ):
        path = urlparse(
            self.path
        ).path

        if path == "/health":
            self._send_health(
                send_body
            )
            return

        if try_proxy_abs_stream(
            self,
            path,
            send_body,
        ):
            return

        match = (
            NAVIDROME_STREAM_PATTERN
            .fullmatch(path)
        )

        if not match:
            self._send_empty(404)
            return

        encoded_song_id = (
            match.group(1)
        )

        expires = int(
            match.group(2)
        )

        supplied_signature = (
            match.group(3)
        )

        if not signature_is_valid(
            "navidrome",
            encoded_song_id,
            expires,
            supplied_signature,
        ):
            self._send_empty(403)
            return

        try:
            song_id = decode_resource_id(
                encoded_song_id
            )
        except Exception:
            self._send_empty(403)
            return

        self._proxy_navidrome(
            song_id,
            send_body,
        )

    def _abs_resolve_request(
        self,
        payload,
    ):
        query = str(
            payload.get(
                "query",
                "",
            )
        ).strip()

        from_start = payload.get(
            "fromStart",
            False,
        )

        if not isinstance(
            from_start,
            bool,
        ):
            raise ValueError(
                "Invalid start option."
            )

        return resolve_audiobook(
            query,
            from_start=from_start,
        )

    def _abs_restart_request(
        self,
        payload,
    ):
        token = str(
            payload.get(
                "token",
                "",
            )
        ).strip()

        if (
            not token
            or len(token) > 1024
        ):
            raise ValueError(
                "Invalid audiobook token."
            )

        return restart_audiobook(
            token
        )

    def _abs_chapter_request(
        self,
        payload,
    ):
        token = str(
            payload.get(
                "token",
                "",
            )
        ).strip()

        action = str(
            payload.get(
                "action",
                "",
            )
        ).strip().lower()

        offset_in_milliseconds = (
            payload.get(
                "offsetInMilliseconds",
                0,
            )
        )

        chapter_number = payload.get(
            "chapterNumber"
        )

        if (
            not token
            or len(token) > 1024
        ):
            raise ValueError(
                "Invalid audiobook token."
            )

        return seek_audiobook_chapter(
            token,
            action,
            offset_in_milliseconds,
            chapter_number,
        )

    def _abs_seek_request(
        self,
        payload,
    ):
        token = str(
            payload.get(
                "token",
                "",
            )
        ).strip()

        direction = str(
            payload.get(
                "direction",
                "",
            )
        ).strip().lower()

        seconds = payload.get(
            "seconds"
        )

        offset_in_milliseconds = (
            payload.get(
                "offsetInMilliseconds",
                0,
            )
        )

        if (
            not token
            or len(token) > 1024
        ):
            raise ValueError(
                "Invalid audiobook token."
            )

        return seek_audiobook_time(
            token,
            direction,
            seconds,
            offset_in_milliseconds,
        )

    def _abs_progress_request(
        self,
        payload,
    ):
        token = str(
            payload.get(
                "token",
                "",
            )
        ).strip()

        event = str(
            payload.get(
                "event",
                "",
            )
        ).strip().lower()

        offset_in_milliseconds = (
            payload.get(
                "offsetInMilliseconds"
            )
        )

        if (
            not token
            or len(token) > 1024
        ):
            raise ValueError(
                "Invalid audiobook token."
            )

        return close_audiobook_playback(
            token,
            event,
            offset_in_milliseconds,
        )

    def _verify_navidrome_request(
        self,
    ):
        navidrome_json(
            "ping"
        )

        return {
            "status": "ok",
            "service": "navidrome",
        }

    def _resolve_request(
        self,
        payload,
    ):
        query = str(
            payload.get(
                "query",
                "",
            )
        ).strip()

        mode = str(
            payload.get(
                "mode",
                "auto",
            )
        ).strip().lower()

        if len(query) > 200:
            raise ValueError(
                "Invalid search query."
            )

        if (
            not query
            and mode != "random"
        ):
            raise ValueError(
                "Invalid search query."
            )

        queue = (
            resolve_navidrome_queue(
                query,
                mode,
            )
        )

        return create_first_queue_result(
            queue
        )

    def _current_request(
        self,
        payload,
    ):
        token = str(
            payload.get(
                "token",
                "",
            )
        ).strip()

        if (
            not token
            or len(token) > 1024
        ):
            raise ValueError(
                "Invalid Alexa token."
            )

        return create_current_queue_result(
            token
        )

    def _previous_request(
        self,
        payload,
    ):
        token = str(
            payload.get(
                "token",
                "",
            )
        ).strip()

        if (
            not token
            or len(token) > 1024
        ):
            raise ValueError(
                "Invalid Alexa token."
            )

        return create_previous_queue_result(
            token
        )

    def _next_request(
        self,
        payload,
    ):
        token = str(
            payload.get(
                "token",
                "",
            )
        ).strip()

        if (
            not token
            or len(token) > 1024
        ):
            raise ValueError(
                "Invalid Alexa token."
            )

        return create_next_queue_result(
            token
        )

    def _scrobble_request(
        self,
        payload,
    ):
        token = str(
            payload.get(
                "token",
                "",
            )
        ).strip()

        event = str(
            payload.get(
                "event",
                "",
            )
        ).strip().lower()

        listened_at_ms = payload.get(
            "time"
        )

        if (
            not token
            or len(token) > 1024
        ):
            raise ValueError(
                "Invalid Alexa token."
            )

        return scrobble_queue_token(
            token,
            event,
            listened_at_ms,
        )

    def do_GET(self):
        self._dispatch_get(
            send_body=True
        )

    def do_HEAD(self):
        self._dispatch_get(
            send_body=False
        )

    def do_POST(self):
        path = urlparse(
            self.path
        ).path

        if path not in (
            "/api/audiobookshelf/resolve",
            "/api/audiobookshelf/restart",
            "/api/audiobookshelf/chapter",
            "/api/audiobookshelf/seek",
            "/api/audiobookshelf/progress",
            "/api/navidrome/verify",
            "/api/navidrome/resolve",
            "/api/navidrome/current",
            "/api/navidrome/next",
            "/api/navidrome/previous",
            "/api/navidrome/scrobble",
        ):
            self._send_empty(404)
            return

        if not self._authorized():
            self.close_connection = True
            self._send_empty(401)
            return

        try:
            payload = self._read_json()

            if (
                path
                == "/api/audiobookshelf/resolve"
            ):
                result = (
                    self._abs_resolve_request(
                        payload
                    )
                )

            elif (
                path
                == "/api/audiobookshelf/restart"
            ):
                result = (
                    self._abs_restart_request(
                        payload
                    )
                )

            elif (
                path
                == "/api/audiobookshelf/chapter"
            ):
                result = (
                    self._abs_chapter_request(
                        payload
                    )
                )

            elif (
                path
                == "/api/audiobookshelf/seek"
            ):
                result = (
                    self._abs_seek_request(
                        payload
                    )
                )

            elif (
                path
                == "/api/audiobookshelf/progress"
            ):
                result = (
                    self._abs_progress_request(
                        payload
                    )
                )

            elif (
                path
                == "/api/navidrome/verify"
            ):
                result = (
                    self._verify_navidrome_request()
                )

            elif (
                path
                == "/api/navidrome/resolve"
            ):
                result = (
                    self._resolve_request(
                        payload
                    )
                )

            elif (
                path
                == "/api/navidrome/current"
            ):
                result = (
                    self._current_request(
                        payload
                    )
                )

            elif (
                path
                == "/api/navidrome/previous"
            ):
                result = (
                    self._previous_request(
                        payload
                    )
                )

            elif (
                path
                == "/api/navidrome/scrobble"
            ):
                result = (
                    self._scrobble_request(
                        payload
                    )
                )

            else:
                result = (
                    self._next_request(
                        payload
                    )
                )

        except ValueError as error:
            self._send_json(
                {
                    "status": "error",
                    "error": str(error),
                },
                status=400,
            )
            return

        except LookupError as error:
            self._send_json(
                {
                    "status": "error",
                    "error": str(error),
                },
                status=404,
            )
            return

        except Exception as error:
            print(
                "API error: "
                + type(error).__name__
                + ": "
                + str(error)[:500],
                flush=True,
            )

            self._send_json(
                {
                    "status": "error",
                    "error":
                        "The media service is currently "
                        "unavailable.",
                },
                status=502,
            )
            return

        self._send_json(result)


if __name__ == "__main__":
    server = ThreadingHTTPServer(
        (HOST, PORT),
        BridgeHandler,
    )

    print(
        "Alexa Media Bridge listening on "
        f"{HOST}:{PORT}",
        flush=True,
    )

    server.serve_forever()
