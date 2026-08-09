# Configuration

The bridge is configured through `bridge/.env`.

The repository contains `bridge/.env.example` as a template. Never
commit the generated `.env` file because it contains credentials and
cryptographic secrets.

The recommended way to create the file is:

```bash
./scripts/setup.sh
```

After changing the configuration, run:

```bash
./scripts/preflight.sh
```

Restart the bridge to apply changes:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  up -d
```

## Container image

### `IMAGE_TAG`

Selects the published container-image version.

Example:

```dotenv
IMAGE_TAG=1.0.0
```

Using a fixed release version is recommended for predictable updates.
Avoid using development or untrusted image tags in production.

## Docker network

### `PROXY_NETWORK`

Names the existing Docker network shared by the bridge and reverse
proxy.

Example:

```dotenv
PROXY_NETWORK=proxy
```

The setup script checks that this network already exists. It does not
create the network because it normally belongs to the reverse-proxy
stack.

## Public bridge URL

### `PUBLIC_BASE_URL`

Defines the public HTTPS address used for signed media stream and
cover-art URLs and API requests.

Example:

```dotenv
PUBLIC_BASE_URL=https://media.example.com
```

Requirements:

- HTTPS is mandatory
- Only port 443 is permitted
- Do not include a trailing slash
- Do not include a query string
- Do not include a URL fragment
- The address must be reachable by AWS Lambda and Alexa devices

The reverse proxy should forward this address to the bridge container
on internal HTTP port `8000`.

## Cryptographic secrets

### `STREAM_SECRET`

Signs temporary Navidrome and Audiobookshelf stream and cover-art URLs.

### `CONTROL_SECRET`

Authenticates requests from the AWS Lambda function to the bridge.

The two secrets must:

- Be different from each other
- Contain at least 32 characters
- Be generated from a cryptographically secure random source
- Never be committed to Git
- Never be included in screenshots, logs, or support requests

The setup assistant generates both values automatically.

The same `CONTROL_SECRET` value must be configured as an environment
variable in AWS Lambda. `STREAM_SECRET` remains only on the bridge.

To rotate the control secret:

1. Generate a new random value.
2. Update `CONTROL_SECRET` in `bridge/.env`.
3. Update `CONTROL_SECRET` in AWS Lambda.
4. Restart the bridge.
5. Test the Alexa skill.

Rotating `STREAM_SECRET` immediately invalidates previously generated
signed stream and cover-art URLs.

## Navidrome

### `NAVIDROME_URL`

Defines the internal URL used by the bridge to reach Navidrome.

Example for a container on the same Docker network:

```dotenv
NAVIDROME_URL=http://navidrome:4533
```

A LAN address may also be used when Navidrome is not attached to the
same Docker network.

The URL should normally remain internal. It does not need to be exposed
to Alexa or AWS Lambda.

### `NAVIDROME_USERNAME_B64`

Contains the Navidrome username encoded as Base64.

### `NAVIDROME_PASSWORD_B64`

Contains the Navidrome password encoded as Base64.

Base64 is an encoding format, not encryption. Protect `bridge/.env` as
you would protect the original username and password.

The setup assistant encodes both values automatically and avoids storing
the unencoded credentials in the generated configuration.

The configured Navidrome account must be allowed to:

- Search the music library
- Read song, album, artist, and playlist metadata
- Stream music files
- Submit Navidrome scrobble events

Use a dedicated account when possible instead of an administrator
account.

## Audiobookshelf

### `AUDIOBOOKSHELF_URL`

Defines the internal URL used by the bridge to reach Audiobookshelf.

Example for a container on the same Docker network:

```dotenv
AUDIOBOOKSHELF_URL=http://audiobookshelf:80
```

A LAN address may be used when Audiobookshelf is not attached to the
same Docker network.

The URL should remain internal. Alexa and AWS Lambda communicate only
with the public bridge URL.

### `AUDIOBOOKSHELF_TOKEN_B64`

Contains the Audiobookshelf API token encoded as Base64.

Base64 does not encrypt the token. Keep `bridge/.env` private and never
include this value in logs, screenshots, or issue reports.

The setup assistant encodes the token automatically.

### `AUDIOBOOKSHELF_LIBRARY_ID`

Identifies the Audiobookshelf library that the bridge searches.

The value must be the internal library ID, not merely the visible
library name.

The configured token must be permitted to:

- Search and read the selected library
- Read audiobook metadata and chapters
- Open audiobook playback sessions
- Stream audiobook files
- Read and update playback progress

Use a dedicated Audiobookshelf user when possible.

## Cover artwork

Cover artwork requires no additional environment variables.

For Navidrome music, the bridge uses the `coverArt` identifier returned by
Navidrome and provides the image through a temporary signed HTTPS URL.

For Audiobookshelf, the bridge uses the cover associated with the resolved
library item and provides it through a temporary signed HTTPS URL.

Navidrome and Audiobookshelf remain internal services. Alexa receives the
public bridge URL rather than backend credentials or internal service
addresses.

Cover artwork is optional. Playback continues when no cover is available.
Display-capable Alexa devices may show the supplied artwork, while devices
without a display continue normal audio playback.

The reverse proxy must allow requests to the signed cover-art paths as well
as the media-stream paths.

## Signed URL lifetime

### `MUSIC_STREAM_TTL`

Defines how long newly generated music and audiobook stream URLs remain
valid, in seconds.

Default:

```dotenv
MUSIC_STREAM_TTL=14400
```

The default value is four hours.

### `MAX_TOKEN_LIFETIME`

Sets the maximum lifetime accepted when validating signed URLs.

Default:

```dotenv
MAX_TOKEN_LIFETIME=14400
```

`MUSIC_STREAM_TTL` must not exceed `MAX_TOKEN_LIFETIME`.

Shorter values reduce the useful lifetime of leaked URLs but may cause
long playback sessions to fail after a URL expires.

## Audiobook seeking

### `MAX_ABS_SEEK_SECONDS`

Sets the maximum audiobook seek distance accepted in a single request,
in seconds.

Default:

```dotenv
MAX_ABS_SEEK_SECONDS=86400
```

The default permits a maximum single jump of 24 hours. Requests beyond
this limit are rejected.

## Navidrome resolver limits

### `MAX_RANDOM_TRACKS`

Limits the number of tracks considered when creating random playback.

Default:

```dotenv
MAX_RANDOM_TRACKS=500
```

Higher values may increase memory use and Navidrome API response time.

### `ALL_SONGS_CACHE_TTL`

Defines how long the bridge caches the Navidrome song list, in seconds.

Default:

```dotenv
ALL_SONGS_CACHE_TTL=300
```

A value of `0` disables this cache. Lower values detect library changes
sooner but increase requests to Navidrome.

## Internal bridge port

### `BRIDGE_PORT`

Sets the HTTP port used inside the bridge container.

Default:

```dotenv
BRIDGE_PORT=8000
```

Changing this value also requires matching changes to the Compose file,
container healthcheck, and reverse-proxy target. Keeping the default is
strongly recommended.

## Environment-file permissions

The generated `bridge/.env` file contains credentials and secrets.
Restrict it to the owner:

```bash
chmod 600 bridge/.env
```

Check the current permissions:

```bash
stat -c "%a %n" bridge/.env
```

Expected output:

```text
600 bridge/.env
```

Do not store the file in public backups, shared folders, screenshots,
or support attachments.

## Manual configuration

You may create the configuration manually from the template:

```bash
cp bridge/.env.example bridge/.env
chmod 600 bridge/.env
```

Edit every required value before starting the bridge.

Username, password, and API-token fields ending in `_B64` must contain
valid Base64-encoded UTF-8 values.

Example encoding command:

```bash
printf "%s" "replace-with-the-value" | base64 -w 0
```

Do not include a trailing newline in encoded credentials.

## Validate changes

Run the preflight check after every configuration change:

```bash
./scripts/preflight.sh
```

To validate only the Compose structure without displaying resolved
environment values:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  config >/dev/null
```

Restart the service after successful validation:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  up -d
```

Then run:

```bash
./scripts/verify.sh
```
