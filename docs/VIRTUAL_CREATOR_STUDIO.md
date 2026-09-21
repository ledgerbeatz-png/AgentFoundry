# Virtual Creator Studio MVP

The Creator Studio adds a safe, provider-neutral production core to AgentFoundry.
It is designed for an original, clearly disclosed fictional adult character.

## Workflow

`CHARACTER → BRIEF → HUMAN APPROVAL → PROVIDER JOB → RENDERED ASSET`

The MVP intentionally stops before network rendering or publishing. It produces a
portable provider job containing the continuity prompt, negative prompt and
disclosure metadata. Google Flow and Higgsfield are registered as provider targets;
their current mode is manual export until stable, authorized APIs are configured.

## Guardrails

- Every creator profile must explicitly be 18 or older.
- Only fictional identities are accepted.
- An AI/fictional-character disclosure is mandatory.
- Prompts forbid resemblance to real people and ambiguous age.
- A named human approval is required before a provider job can be prepared.
- No asset is published automatically in this MVP.

## Core API

```python
from agentfoundry.creator import ContentPipeline, builtin_providers

pipeline = ContentPipeline(builtin_providers())
draft = pipeline.create(profile, brief)
approved = pipeline.approve(draft, approved_by="operator")
job = pipeline.prepare(approved, provider_id="higgsfield")
```

`job.provider_job` can be exported by the future desktop screen or passed to an
authorized provider adapter without changing the character and approval model.
