# Updating

Use release assets from one project version only. Do not combine a
container image, Lambda package, or interaction models from different
releases.

## Before updating

Record the currently installed version:

```bash
cat VERSION
```

Back up the bridge configuration:

```bash
cp bridge/.env "bridge/.env.backup.$(date +%Y%m%d_%H%M%S)"
chmod 600 bridge/.env.backup.*
```

The environment file contains credentials and cryptographic secrets.
Keep the backup private and remove it after the update is confirmed.

Check the current service before changing it:

```bash
./scripts/verify.sh
```

Resolve existing errors before starting an update.

## Download the new release

Download the installation archive and `SHA256SUMS` from the same GitHub
release.

Verify the files:

```bash
grep -F   "alexa_local_media_bridge_install_<version>.tar.gz"   SHA256SUMS   | sha256sum --check
```

Extract the new bundle into a separate directory. Do not overwrite the
currently installed directory in place.

## Prepare the new installation directory

Enter the newly extracted release directory.

Copy the existing environment file from the previous installation:

```bash
cp ../alexa_local_media_bridge_<old-version>/bridge/.env bridge/.env
chmod 600 bridge/.env
```

Update the container-image tag to the new project version:

```bash
NEW_VERSION="$(tr -d "[:space:]" < VERSION)"
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$NEW_VERSION/" bridge/.env
```

Review new settings in `bridge/.env.example` and add any variables that
were introduced by the release.

Do not replace existing secrets unless the release notes explicitly
require secret rotation.

Run the preflight check from the new directory:

```bash
./scripts/preflight.sh
```

Resolve every reported error before switching to the new release.

## Update the bridge container

Pull the image selected by `IMAGE_TAG`:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  pull
```

Start or recreate the bridge with the new image:

```bash
docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  up -d
```

Wait for the Docker healthcheck and then run:

```bash
./scripts/verify.sh
```

Confirm that the health response reports the expected release version.

## Update the AWS Lambda function

Download the Lambda ZIP from the same release as the installation
bundle:

```text
alexa_local_media_bridge_lambda_<new-version>.zip
```

In the AWS Lambda console:

1. Open the existing function.
2. Select `Upload from` and `.zip file`.
3. Upload the new Lambda ZIP.
4. Confirm that the handler remains `index.handler`.
5. Confirm that `BRIDGE_BASE_URL` and `CONTROL_SECRET` are unchanged.
6. Save or deploy the updated function.

Do not create a new Function URL or remove the Skill-ID-restricted
Alexa Skills Kit trigger.

Run both synthetic launch events after the upload:

```text
launch_de_DE.json
launch_en_US.json
```

## Update interaction models

Import a new interaction model only when the release notes state that
the corresponding locale changed.

Use the model files from the same release:

```text
alexa_local_media_bridge_interaction_model_de_DE_<new-version>.json
alexa_local_media_bridge_interaction_model_en_US_<new-version>.json
```

For every changed locale:

1. Open its JSON Editor in the Alexa Developer Console.
2. Replace the complete model.
3. Save the model.
4. Build the model.
5. Wait for a successful build.

Do not rename intents or slots independently of the supplied model and
Lambda package.

## Test the updated system

After updating all required components, test:

- German and English launch requests
- Music search and playback
- Audiobook search and playback
- Pause, resume, next, and previous controls
- Audiobook progress restoration
- Chapter selection and seeking

Run the bridge verification again:

```bash
./scripts/verify.sh
```

## Roll back the bridge

Keep the previous installation directory until the update has been
fully verified.

To roll back, enter the previous release directory and run:

```bash
OLD_VERSION="$(tr -d "[:space:]" < VERSION)"
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$OLD_VERSION/" bridge/.env

docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  pull

docker compose \
  --env-file bridge/.env \
  --file bridge/compose.yml \
  up -d
```

Then run `./scripts/verify.sh` from the previous installation.

Lambda and interaction models must be rolled back separately using
assets from that same previous release.

## Remove old files

After the new release has operated successfully:

1. Remove obsolete `.env` backup copies.
2. Remove the previous extracted installation directory.
3. Keep downloaded release archives only in a protected backup.

Never delete the active `bridge/.env` file.

Before deleting the previous release, confirm:

- `./scripts/verify.sh` succeeds
- The reported bridge version is correct
- Both Alexa locales work
- Music and audiobook playback work
- Audiobook progress is saved and restored
- The previous release is no longer needed for rollback
