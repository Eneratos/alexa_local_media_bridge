# AWS Lambda test events

These files contain synthetic Alexa request envelopes for manually
testing the Lambda function in the AWS console.

No real Alexa user IDs, device IDs, application IDs, credentials, or
media service secrets are included.

## Standalone tests

The following events can be executed without contacting the media
bridge:

- `launch_de_DE.json`
- `launch_en_US.json`

They verify locale detection and the localized launch response.

## Media requests

Song, album, and audiobook events require:

- `BRIDGE_BASE_URL` configured in AWS Lambda
- `CONTROL_SECRET` configured in AWS Lambda
- a publicly reachable and correctly configured media bridge
- matching content in Navidrome or Audiobookshelf

## Audiobook controls

The seek and chapter events contain an idle AudioPlayer state. They
therefore verify the localized response for a missing active audiobook.

To test an actual audiobook seek or chapter change, replace these
fields with values from an active audiobook playback session:

```json
"AudioPlayer": {
  "playerActivity": "PLAYING",
  "token": "replace-with-an-active-audiobook-token",
  "offsetInMilliseconds": 0
}
```

Do not commit real customer identifiers, access tokens, signed stream
URLs, or production request envelopes.
