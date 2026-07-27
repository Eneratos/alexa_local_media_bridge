# Alexa Skill Setup

This guide connects the installed media bridge to a custom Alexa skill
through an operator-managed AWS Lambda function.

## Components

The complete request path is:

```text
Alexa device
  -> Alexa custom skill
  -> AWS Lambda function
  -> public HTTPS bridge URL
  -> Navidrome or Audiobookshelf
```

The bridge installation must already be reachable through HTTPS on
port 443 before configuring the skill.

## Required accounts

You need:

- An AWS account
- An Amazon Alexa Developer account
- Permission to create and configure an AWS Lambda function
- Permission to create a custom Alexa skill

## Release files

Download these files from the same project release:

```text
alexa_local_media_bridge_lambda_<version>.zip
alexa_local_media_bridge_interaction_model_de_DE_<version>.json
alexa_local_media_bridge_interaction_model_en_US_<version>.json
SHA256SUMS
```

Verify the downloaded files before deploying them:

```bash
grep -E   "alexa_local_media_bridge_(lambda_<version>\.zip|interaction_model_(de_DE|en_US)_<version>\.json)$"   SHA256SUMS   | sha256sum --check
```

The Lambda ZIP is intentionally flat. Its archive root must contain:

```text
index.js
package.json
package-lock.json
node_modules/
```

Do not place the files inside an additional directory before uploading
the ZIP to AWS Lambda.

## Create the AWS Lambda function

Create a new function with these settings:

- Author from scratch
- Runtime: Node.js 24
- Architecture: x86_64
- A new or existing basic Lambda execution role

For a European Alexa skill, `eu-west-1` is the tested deployment region
for this project.

## Upload the Lambda deployment package

Open the function in the AWS Lambda console.

In the Code section:

1. Select `Upload from`.
2. Select `.zip file`.
3. Upload `alexa_local_media_bridge_lambda_<version>.zip`.
4. Save the deployment.

Open the runtime settings and configure:

```text
Handler: index.handler
```

The ZIP must contain `index.js` directly at its root. A wrapper folder
causes Lambda to fail with a module-loading error.

Do not create a Lambda Function URL. Alexa invokes the function through
the Alexa Skills Kit trigger.

## Configure Lambda environment variables

Open the function configuration and add these environment variables:

### `BRIDGE_BASE_URL`

Set this to the public HTTPS URL of the installed bridge.

Example:

```text
https://media.example.com
```

Requirements:

- Use HTTPS
- Use port 443
- Do not add a trailing slash
- Do not include a path, query string, or fragment

### `CONTROL_SECRET`

Set this to exactly the same value as `CONTROL_SECRET` in the bridge
configuration.

Do not configure `STREAM_SECRET` in Lambda. That value remains private
to the bridge.

After saving the variables, deploy or save the updated function
configuration.

## Create the Alexa custom skill

Open the Alexa Developer Console and create a new skill.

Use these settings:

- Skill name: `Media Bridge`
- Primary locale: German (Germany)
- Model: Custom
- Hosting: Use your own backend resources
- Template: Start from scratch

Console labels may differ slightly as the developer interface changes.
The important choices are a Custom interaction model and an externally
managed AWS Lambda backend.

After creating the skill, copy its Skill ID.

It has a format similar to:

```text
amzn1.ask.skill.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Keep the Skill ID available for configuring the Lambda trigger. It is
not a password, but using the exact value prevents other Alexa skills
from invoking the function.

## Project locales

This project provides two complete locales:

| Locale | Display name | Invocation name |
| --- | --- | --- |
| `de-DE` | `Medienbrücke` | `medienbrücke` |
| `en-US` | `Media Bridge` | `media bridge` |

Create the skill with `de-DE` first. The `en-US` locale is added after
the German interaction model has been imported.

## Import the German interaction model

In the Alexa Developer Console, select the `de-DE` locale.

Open:

```text
Custom -> Interaction Model -> JSON Editor
```

Replace the existing editor content with the complete contents of:

```text
alexa_local_media_bridge_interaction_model_de_DE_<version>.json
```

Then:

1. Save the model.
2. Build the model.
3. Wait until the build completes successfully.

The German interaction model uses:

```text
Invocation name: medienbrücke
```

Do not change intent names or slot names unless the Lambda code is
updated at the same time.

## Add and import the English locale

Add the `en-US` locale to the same skill.

Select `en-US`, open the JSON Editor, and replace its contents with:

```text
alexa_local_media_bridge_interaction_model_en_US_<version>.json
```

Then save and build the English model.

The English interaction model uses:

```text
Invocation name: media bridge
```

Build status is stored separately for each locale. Confirm that both
`de-DE` and `en-US` complete successfully.

## Connect the skill to the Lambda function

Copy the function ARN from the AWS Lambda console.

In the Alexa Developer Console, open:

```text
Custom -> Endpoint
```

Configure:

1. Select `AWS Lambda ARN` as the service endpoint type.
2. Paste the function ARN into `Default Region`.
3. Save the endpoint configuration.

Use the ARN of the Lambda function deployed in `eu-west-1` for the
German and English locales provided by this project.

Do not enter the public bridge URL as the Alexa endpoint. Alexa invokes
Lambda, and Lambda communicates with the bridge.

## Add the Alexa Skills Kit trigger

Return to the AWS Lambda function and add a trigger.

Configure the trigger as follows:

1. Select `Alexa Skills Kit`.
2. Enable Skill ID verification.
3. Paste the exact Skill ID copied from the Alexa Developer Console.
4. Add and save the trigger.

The configured Skill ID must match the skill that uses this function.
Requests carrying a different Skill ID must not invoke the function.

Do not leave an additional Alexa Skills Kit trigger without Skill ID
verification. Remove any unrestricted trigger before testing.

## Test the Lambda function directly

The installation bundle contains synthetic Lambda test events under:

```text
skill/test_events/
```

Start with these standalone events:

```text
launch_de_DE.json
launch_en_US.json
```

They test locale detection and localized launch responses without
requesting media from the bridge.

In the AWS Lambda console:

1. Open the function.
2. Create a new test event.
3. Paste the complete contents of one launch-event JSON file.
4. Save the event.
5. Run the test.

Repeat the test for both locales.

A successful invocation should return a valid Alexa response envelope
and complete without a function error.

The other supplied test events exercise music and audiobook requests.
They require a working public bridge, valid Lambda environment values,
and matching content in the configured media libraries.

Do not replace synthetic identifiers with real Alexa customer or device
identifiers when saving test events.

## Test in the Alexa Simulator

Open the `Test` page in the Alexa Developer Console.

Enable skill testing for:

```text
Development
```

Open the Alexa Simulator and select the locale to test.

Start with the launch requests:

```text
Alexa, öffne Medienbrücke
Alexa, open media bridge
```

Then test representative media requests, for example:

```text
Alexa, sage Medienbrücke, spiele Musik von Placebo
Alexa, ask Media Bridge to play music by Placebo
```

Also test:

- A song request
- An album request
- An artist request
- A playlist request
- Random music playback
- An audiobook request
- Restarting an audiobook from the beginning
- Seeking forward and backward
- Selecting a chapter
- Moving to the next and previous chapter or track
- Pause, resume, and stop controls

Repeat the test set for both `de-DE` and `en-US`.

For each request, inspect `Skill I/O` and confirm:

- The expected intent was selected
- Slot values were recognized correctly
- Lambda returned a valid response envelope
- No function error occurred
- AudioPlayer directives contain an HTTPS URL

When diagnosing a failure, compare the Alexa request and response with
the corresponding AWS Lambda log entry. Remove customer identifiers,
access tokens, signed URLs, and private service addresses before sharing
any diagnostic output.

## Test on a physical Alexa device

After simulator testing succeeds, enable the development skill for the
Amazon account used by the physical Alexa device.

Confirm that the device language matches the locale being tested.

Repeat the main regression tests on the device, especially:

- Starting music and audiobooks
- Audio playback continuing after the spoken response
- Pause and resume
- Next and previous controls
- Audiobook progress restoration
- Chapter changes and seeking

AudioPlayer behavior may differ from text-only simulator responses, so
a successful simulator test does not replace testing on a real device.

## Review AWS Lambda logs

Use the function monitoring page or its CloudWatch log group to inspect
failed requests.

Useful information includes:

- Request type and selected intent
- Resolver or bridge errors
- AudioPlayer lifecycle events
- Function exceptions and stack traces

Do not publish complete production logs without removing:

- Alexa user and device identifiers
- Media titles when they are private
- Signed stream URLs
- Tokens and secrets
- Internal service addresses

## Security checklist

Before regular use, confirm:

- The bridge is exposed only through HTTPS on port 443
- Port 8000 is not published directly to the internet
- Lambda has no public Function URL
- `CONTROL_SECRET` matches on Lambda and the bridge
- The Alexa Skills Kit trigger is restricted to the exact Skill ID
- No unrestricted duplicate Alexa trigger exists
- Production `.env` files are not committed
- Synthetic test events contain no real customer identifiers

## Update the Lambda function and interaction models

For a project update:

1. Download all assets from the same release version.
2. Verify `SHA256SUMS`.
3. Upload the new flat Lambda ZIP.
4. Confirm that the handler remains `index.handler`.
5. Import changed interaction models for each locale.
6. Save and rebuild every changed locale.
7. Repeat Lambda, simulator, and physical-device tests.

Do not combine a Lambda ZIP from one release with interaction models
from another release.

## Distribution and certification

The included manifest template is a starting point only.

Before submitting a skill for public certification, review and provide:

- Distribution countries
- Skill icons
- Privacy-policy information
- Terms of use where applicable
- Testing instructions
- Compliance and data-handling disclosures
- Public descriptions and example phrases for every locale

Private development testing does not automatically make the skill ready
for public distribution or certification.
