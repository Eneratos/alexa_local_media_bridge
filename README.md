# Alexa Local Media Bridge

A self-hosted media bridge and custom Alexa skill for playing music from
Navidrome and audiobooks from Audiobookshelf.

The project connects Alexa AudioPlayer requests to local media services
without exposing Navidrome or Audiobookshelf credentials to Alexa.

## Features

### Music

- Play songs, albums, artists, and playlists
- Start random music playback
- Use standard Alexa AudioPlayer controls
- Continue through generated playback queues
- Submit Navidrome scrobbles during music playback

### Audiobooks

- Search by title, series, author, narrator, or category
- Resume saved Audiobookshelf progress
- Start an audiobook from the beginning
- Save Audiobookshelf playback progress automatically
- Seek forward or backward by a spoken duration
- Play a specific chapter
- Move to the next or previous chapter
- Play a random audiobook from a series
- Play a specific numbered episode from a series
- Move to the next or previous audiobook in a series
- Play a random audiobook from the entire library
- Play a random unheard audiobook from a series

### Languages

- German display name: `Medienbrücke`
- German invocation name: `medienbrücke`
- English display name: `Media Bridge`
- English invocation name: `media bridge`

## Architecture

The project contains two runtime components:

1. A local Python bridge running as a Docker container.
2. An AWS Lambda function used as the Alexa custom-skill backend.

Alexa sends skill requests to Lambda. Lambda authenticates to the bridge,
which resolves media through Navidrome or Audiobookshelf and returns
short-lived signed HTTPS stream URLs.

The bridge is intended to run behind an HTTPS reverse proxy. Its container
port should not be published directly to the internet.

## Requirements

- A Linux host with Docker Engine and Docker Compose v2
- An existing Navidrome server
- An existing Audiobookshelf server
- An HTTPS reverse proxy with a publicly reachable hostname
- An AWS account for the Lambda function
- An Amazon Developer account for the Alexa custom skill

The bridge does not publish a host port by default. The reverse proxy must
share its configured external Docker network.

## Installation

Download the installation archive and `SHA256SUMS` from the selected
GitHub release.

Verify only the downloaded installation archive:

```bash
grep -F \
  "alexa_local_media_bridge_install_<version>.tar.gz" \
  SHA256SUMS \
  | sha256sum --check
```

Extract the archive and enter the release directory:

```bash
tar -xzf alexa_local_media_bridge_install_<version>.tar.gz
cd alexa_local_media_bridge_<version>
```

Run the guided setup and validation:

```bash
./scripts/setup.sh
./scripts/preflight.sh
```

Then configure the reverse proxy and start the bridge as described in the
installation guide.

## Documentation

- [`docs/INSTALL.md`](docs/INSTALL.md) — bridge installation
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — environment variables
- [`docs/ALEXA_SKILL_SETUP.md`](docs/ALEXA_SKILL_SETUP.md) — Lambda and skill setup
- [`docs/UPDATING.md`](docs/UPDATING.md) — update and rollback procedure
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — diagnostics and common errors

## Repository structure

```text
.github/workflows/    Continuous integration and release automation
bridge/               Python bridge, Dockerfile, and Compose definition
docs/                 Public installation and operating documentation
scripts/              Setup, validation, and release helper scripts
skill/interaction_model/  German and English Alexa interaction models
skill/lambda/         AWS Lambda backend
skill/manifest/       Alexa skill manifest template
skill/test_events/    Anonymized Lambda test events
VERSION               Authoritative project version
```

## Security model

- Lambda authenticates control requests with `CONTROL_SECRET`.
- Stream URLs are signed with `STREAM_SECRET` and expire automatically.
- Backend credentials are stored only in the local bridge environment.
- The container runs without root privileges.
- The container filesystem is read-only.
- All Linux capabilities are dropped.
- `no-new-privileges` is enabled.
- No host port is published by the supplied Compose file.

Never commit production `.env` files, credentials, private keys, signed
stream URLs, Skill IDs, AWS account identifiers, or deployment-specific
addresses.

## Release artifacts

Each release provides:

- A multi-architecture container image for `linux/amd64` and `linux/arm64`
- An installation bundle
- A flat AWS Lambda deployment ZIP
- German and English interaction-model JSON files
- SHA-256 checksums

The container image is published as:

```text
ghcr.io/eneratos/alexa-local-media-bridge:<version>
```

Do not combine components from different release versions.

## License

Alexa Local Media Bridge is licensed under the MIT License.

See [`LICENSE`](LICENSE) for the complete license text.
