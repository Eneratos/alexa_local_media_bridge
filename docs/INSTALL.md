# Installation

This guide installs the local media bridge. The AWS Lambda function and
Alexa custom skill are configured separately.

## Prerequisites

You need:

- A Linux system with Docker Engine
- Docker Compose v2
- An existing Navidrome server
- An existing Audiobookshelf server
- A reverse proxy with a public HTTPS endpoint
- A public DNS name for the bridge
- An existing Docker network shared with the reverse proxy
- HTTPS on port 443
- An AWS account
- An Amazon Alexa Developer account

The published container image supports:

- `linux/amd64`
- `linux/arm64`

The bridge does not publish a host port by default. The reverse proxy
must reach the container through the shared Docker network.

## Network requirements

The bridge must be able to reach:

- Navidrome over the internal Docker or LAN network
- Audiobookshelf over the internal Docker or LAN network
- The public bridge URL through the reverse proxy

Alexa and AWS Lambda must reach the bridge through a public HTTPS URL.

The public URL must:

- Start with `https://`
- Use port 443
- Not contain a query string
- Not contain a fragment
- Not end with a trailing slash

Example:

```text
https://media.example.com
```

## Download the release bundle

Download these files from the selected GitHub release:

```text
alexa_local_media_bridge_install_<version>.tar.gz
SHA256SUMS
```

Verify the archive:

```bash
grep -F   "alexa_local_media_bridge_install_<version>.tar.gz"   SHA256SUMS   | sha256sum --check
```

Extract it:

```bash
tar -xzf alexa_local_media_bridge_install_<version>.tar.gz
cd alexa_local_media_bridge_<version>
```

## Run the setup assistant

Run:

```bash
./scripts/setup.sh
```

The setup assistant asks for:

- Container image tag
- Reverse-proxy Docker network
- Public HTTPS bridge URL
- Navidrome URL
- Navidrome username and password
- Audiobookshelf URL
- Audiobookshelf API token
- Audiobookshelf library ID

It also:

- Generates independent random stream and control secrets
- Stores credentials as Base64 values where required
- Creates `bridge/.env`
- Restricts `bridge/.env` permissions
- Validates the Compose configuration

The generated `CONTROL_SECRET` must also be configured in the AWS
Lambda environment. Do not commit or publish the `.env` file.

## Check the configuration

Run:

```bash
./scripts/preflight.sh
```

The preflight check verifies:

- Docker availability
- Docker Compose v2
- Environment-file permissions
- Required configuration values
- HTTPS and port requirements
- Base64-encoded credentials
- Docker network availability
- Compose configuration
- Container-image availability

Resolve every reported error before starting the bridge.

## Start the bridge

Run:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  pull

docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  up -d
```

Check the container:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  ps
```

## Configure the reverse proxy

Create a reverse-proxy host for the public bridge domain.

Forward requests to:

```text
Host: alexa-media-bridge
Port: 8000
Protocol: HTTP
```

The reverse proxy and bridge must use the Docker network configured as
`PROXY_NETWORK`.

Enable:

- A valid public TLS certificate
- HTTPS
- HTTP-to-HTTPS redirection
- Web access through port 443

Do not expose port 8000 directly to the internet.

## Verify the installation

After DNS and the reverse proxy are working, run:

```bash
./scripts/verify.sh
```

The verification checks:

- The bridge container is running
- Docker reports a healthy container
- The process runs without root privileges
- The root filesystem is read-only
- Linux capabilities are dropped
- `no-new-privileges` is enabled
- The configured proxy network is attached
- The public HTTPS health endpoint is reachable
- Unauthenticated API requests are rejected
- The configured control secret is accepted
- Navidrome can process a test lookup

A successful verification ends with:

```text
Verification completed successfully.
```

## Health endpoint

The bridge exposes:

```text
GET /health
```

A healthy release returns a response similar to:

```json
{
  "status": "ok",
  "service": "alexa-media-bridge",
  "version": "1.0.0"
}
```

## View logs

Run:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  logs --tail 100 alexa-media-bridge
```

Follow logs continuously:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  logs --follow alexa-media-bridge
```

Logs may contain media titles or internal service details. Review them
before sharing publicly.

## Stop the bridge

Run:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  down
```

The configuration remains in `bridge/.env`.

## Next steps

Continue with:

1. `CONFIGURATION.md`
2. `ALEXA_SKILL_SETUP.md`
3. `TROUBLESHOOTING.md`

The Lambda `BRIDGE_BASE_URL` and `CONTROL_SECRET` values must match the
installed bridge before testing the Alexa skill.
