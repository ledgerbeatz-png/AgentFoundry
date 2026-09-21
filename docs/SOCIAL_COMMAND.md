# Mercury Social Command

Mercury is AgentFoundry's multi-project social media operator. Each selected project
has an isolated brand profile containing its audience, objective, region, tone,
channels, content pillars and forbidden claims.

## Workflow

1. Register a project brand.
2. Define a measurable campaign and call to action.
3. Build a channel-balanced content calendar.
4. Generate channel-specific drafts from approved content pillars.
5. Apply the project's approval mode.
6. Export a publish-ready payload to a connected platform adapter.
7. Triage inbound engagement into answer, acknowledge, review or escalate.

## Approval modes

- `manual`: planning and drafting only.
- `approval_required`: a named human approves each draft before a publish payload exists.
- `autopilot`: eligible drafts can be prepared without per-post approval, while forbidden
  claims and escalation rules remain active.

No platform credentials are stored by the core pack. Platform adapters should use
their provider's supported authentication and retain an audit trail of every external
action.
