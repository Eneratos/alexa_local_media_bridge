# Alexa skill manifest

## Files

- `skill.template.json` is safe to commit and contains a Lambda ARN placeholder.
- `skill.local.json` contains the actual deployment ARN and is excluded from Git.

## German locale

- Display name: `Medienbrücke`
- Invocation name: `medienbrücke`

## English locale

- Display name: `Media Bridge`
- Invocation name: `media bridge`

The German and English locales are both implemented and tested.

## Deployment

Replace `__LAMBDA_ARN__` in the template with the ARN of the operator's own
AWS Lambda function.

Privacy, compliance, icons, distribution, and certification metadata must be
reviewed by each operator before publishing the skill.
