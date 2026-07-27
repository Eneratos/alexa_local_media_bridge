# Troubleshooting

Start with the automated checks before changing the configuration.

## Basic diagnostic sequence

Run:

```bash
./scripts/preflight.sh
```

Then inspect the container state:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  ps
```

View recent bridge logs:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  logs --tail 100 alexa-media-bridge
```

After the container is running, execute:

```bash
./scripts/verify.sh
```

Logs may contain media titles, signed URLs, internal addresses, or other
private details. Remove sensitive information before sharing them.

## Check the installed version

Display the expected release version:

```bash
cat VERSION
```

Display the version reported by the running bridge:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  exec -T alexa-media-bridge \
  python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health").read().decode())'
```

The version in the health response should match `VERSION` and the
configured `IMAGE_TAG`.

## Container does not start

Check whether Docker can resolve and pull the configured image:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  pull
```

Then start the service and inspect its status:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  up -d

docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  ps
```

Common causes include:

- The configured image tag does not exist
- Access to the container registry was denied
- The proxy network does not exist
- `bridge/.env` is missing
- A required environment value is empty or invalid

## Configuration error at startup

The bridge validates its environment before opening port `8000`.
Invalid settings cause the container to exit with a message beginning:

```text
Configuration error:
```

Run the preflight check for a complete validation report:

```bash
./scripts/preflight.sh
```

Check especially:

- Both secrets contain at least 32 characters
- `STREAM_SECRET` and `CONTROL_SECRET` are different
- `PUBLIC_BASE_URL` uses HTTPS on port 443
- Base64 values decode to non-empty UTF-8 text
- Numeric limits contain valid integers
- `MUSIC_STREAM_TTL` does not exceed `MAX_TOKEN_LIFETIME`

## Container remains unhealthy

Inspect the Docker health status:

```bash
CONTAINER_ID="$(docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  ps -q alexa-media-bridge)"

docker inspect \
  --format "{{json .State.Health}}" \
  "$CONTAINER_ID"
```

Test the internal health endpoint from inside the container:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  exec -T alexa-media-bridge \
  python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5).read().decode())'
```

If this request fails, inspect the bridge logs and configuration.

If it succeeds while the public URL fails, the problem is usually in
DNS, TLS, the reverse proxy, or Docker network connectivity.

## Public HTTPS endpoint is unreachable

Test the public health endpoint from a system outside the Docker host:

```bash
curl -i https://media.example.com/health
```

Expected status:

```text
HTTP/2 200
```

The response body should report `"status":"ok"`.

Check:

- Public DNS resolves to the correct address
- The TLS certificate is valid for the bridge hostname
- HTTPS is available on port 443
- The reverse proxy forwards to `alexa-media-bridge:8000`
- The reverse proxy and bridge share the configured Docker network
- No authentication page or access-control middleware intercepts Alexa
- The public URL does not redirect to an unrelated hostname or path

Do not expose the bridge container port directly as a workaround.

## Protected requests return HTTP 401

The bridge rejects control requests when the supplied secret does not
match `CONTROL_SECRET`.

Check that:

- The bridge and Lambda function use the same `CONTROL_SECRET` value
- The value contains no accidental leading or trailing whitespace
- The Lambda environment was saved after changing the value
- The bridge container was recreated after changing `bridge/.env`

Recreate the bridge without displaying its environment:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  up -d --force-recreate
```

Then run `./scripts/verify.sh` again.

Never print or paste `CONTROL_SECRET` into logs or support requests.

## Navidrome or Audiobookshelf is unreachable

Test DNS and TCP connectivity from inside the bridge container:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  exec -T alexa-media-bridge \
  python -c 'import os, socket, urllib.parse; names=("NAVIDROME_URL","AUDIOBOOKSHELF_URL"); [(lambda u, n: (socket.create_connection((u.hostname, u.port or (443 if u.scheme == "https" else 80)), 5).close(), print(f"{n}: TCP connection successful")))(urllib.parse.urlparse(os.environ[n]), n) for n in names]'
```

If either connection fails, check:

- The backend URL and port
- Docker DNS or local DNS resolution
- Firewall rules between the bridge and backend
- Reverse-proxy or TLS certificate errors
- Whether the media service is currently running

If connectivity succeeds but searches fail, run `./scripts/preflight.sh`
and verify the corresponding username, password, token, and library ID.

Do not decode Base64 credentials directly into terminal history.

## Alexa reports a skill error

Check the AWS Lambda logs for the failed request. Do not share complete
log entries before removing request IDs, media titles, URLs, and other
private information.

Verify:

- The Lambda handler is `index.handler`
- `BRIDGE_BASE_URL` contains the public HTTPS bridge URL
- `CONTROL_SECRET` matches the bridge configuration
- The Alexa Skills Kit trigger is restricted to the correct Skill ID
- The requested locale has a successfully built interaction model
- The Lambda ZIP contains `index.js` at its root

Run the supplied synthetic launch event for the affected locale. If the
synthetic event succeeds, test the same locale in the Alexa simulator
and then on a physical device.

If Lambda cannot contact the bridge, test the public health endpoint and
resolve DNS, TLS, or reverse-proxy problems first.

## Playback does not start or stops immediately

Alexa retrieves media streams independently from the Lambda function.
Every generated stream URL must therefore be reachable publicly over
HTTPS without an interactive login page.

Check:

- `PUBLIC_BASE_URL` is the externally reachable bridge URL
- The TLS certificate is valid and trusted
- Stream requests are not intercepted by access-control middleware
- The reverse proxy permits long-running media responses
- Navidrome or Audiobookshelf can serve the requested media file
- `MUSIC_STREAM_TTL` is long enough for the intended playback session
- `MUSIC_STREAM_TTL` does not exceed `MAX_TOKEN_LIFETIME`

Inspect bridge logs immediately after a failed playback request. HTTP
status codes `401` or `403` usually indicate authentication or expired
signing data. A backend `404` usually indicates a missing or changed
media item.

Never publish a signed stream URL while troubleshooting. It temporarily
grants access to the referenced media stream.

## Audiobook progress is not restored

Progress synchronization requires the same Audiobookshelf user and
library configuration for both resolving and updating an audiobook.

Check:

- `AUDIOBOOKSHELF_TOKEN_B64` contains a valid token
- `AUDIOBOOKSHELF_LIBRARY_ID` identifies the correct library
- The token belongs to the user whose progress should be synchronized
- The audiobook still has the same Audiobookshelf item identifier
- The bridge can reach the Audiobookshelf API
- Progress updates are not rejected with HTTP `401` or `403`

Resume playback after listening for long enough to create a meaningful
progress change. Then inspect the Audiobookshelf user interface and the
bridge logs for the corresponding update request.

Starting an audiobook explicitly from the beginning intentionally
ignores its saved resume position for that playback request.

## Chapter selection or seeking fails

Chapter commands depend on valid chapter metadata in the audiobook file
and on a successful audiobook resolution.

Check:

- The audiobook contains chapter metadata
- The requested chapter number exists
- The selected audiobook is the currently active audiobook
- Seek values do not exceed `MAX_ABS_SEEK_SECONDS`
- The resulting position remains within the media duration

Test both a relative seek command and a specific chapter command. If
ordinary playback works but chapter selection does not, inspect the
resolved chapter list and bridge logs without publishing signed URLs.

For files without usable chapter metadata, normal playback and relative
seeking may still work while chapter selection remains unavailable.

## Search returns no result or the wrong item

Search quality depends on the metadata stored in Navidrome and
Audiobookshelf.

Check:

- Artist, album, title, and audiobook metadata are correct
- The requested item is visible to the configured backend user
- The correct Audiobookshelf library is configured
- The spoken language matches the active Alexa locale
- Names containing numbers or abbreviations are pronounced clearly
- `MAX_RANDOM_TRACKS` is large enough for the intended random selection

Try a distinctive full title before testing shorter or ambiguous names.
If several items have similar titles, include the artist, album, or
audiobook author in the request.

After changing backend metadata, allow any backend indexing process to
finish before testing again.

## Collect diagnostics safely

Record the following information without exposing secrets:

```bash
cat VERSION

docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  ps

docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  logs --tail 100 alexa-media-bridge
```

Also record:

- Which Alexa locale was used
- The operation that failed
- The approximate time of the failure
- The HTTP status code, when available
- Whether `/health` works internally and publicly
- Whether Navidrome and Audiobookshelf are reachable

Before sharing diagnostics, remove:

- Secrets, passwords, and access tokens
- Base64-encoded credentials
- Signed media URLs
- Private hostnames and IP addresses
- Media titles when they should remain private
- AWS account identifiers and complete ARNs

Do not share the complete `bridge/.env` file or the output of commands
that render the container environment.
