# AgentFoundry Commerce Architecture

AgentFoundry is being designed as a commercial desktop product, not only as a developer launcher.

## Product promise

**Run local AI without the setup pain.**

AgentFoundry detects the machine, helps select a compatible local model, configures the runtime, benchmarks safe settings, and connects agent tooling through one desktop workflow.

## Funnel

1. Traffic / content
2. Free "Can my PC run local AI?" compatibility check
3. Email / lead capture on the product site
4. AgentFoundry Free or trial
5. AgentFoundry Pro checkout
6. Signed entitlement activation
7. First-run wizard
8. Successful local model launch
9. Updates / support / upgrade

## Editions

### Free

Free is useful on its own and is intended to build trust.

- Hardware compatibility scan
- Basic model profiles
- Basic llama.cpp runtime controls
- Local-first settings and logs

### Pro Trial

- One-time 14-day Pro trial
- Unlocks Pro workflows
- Trial start is persisted locally in the desktop client
- Production enforcement should additionally be backed by the licensing service

### Pro

Planned Pro value:

- Resumable model downloads
- Curated model catalog
- Automatic runtime tuning
- Apollo benchmarking
- Hermes automation
- Premium update channel
- Additional runtimes and integrations over time

## Licensing principles

The desktop application must never contain:

- payment-provider secret keys
- private signing keys
- master license keys
- a hard-coded bypass key

Production activation should work like this:

1. Customer completes checkout.
2. Commerce backend receives the payment-provider webhook.
3. Backend creates/updates the customer's license entitlement.
4. Desktop app submits an activation code or authenticated activation request.
5. Backend returns a signed entitlement token.
6. Desktop app verifies the token using a bundled public verification key.
7. A short offline grace period permits normal use when the licensing service is temporarily unavailable.

The current desktop entitlement model is scaffolding for this flow. It is not intended to be the final anti-tamper boundary.

## Feature flags

Feature checks are centralized in `agentfoundry.commerce`.

Current feature groups:

- hardware_scan
- basic_runtime
- basic_models
- setup_wizard
- resumable_downloads
- auto_tuning
- benchmarks
- hermes_automation
- pro_updates

Do not scatter plan-name checks throughout the UI. New paid capabilities should be added as feature flags and checked through the entitlement service.

## Checkout architecture

The payment provider should be isolated from the desktop app.

Suggested flow:

`Landing page -> hosted checkout -> webhook -> license service -> signed entitlement -> desktop activation`

This lets AgentFoundry change checkout providers later without rewriting desktop licensing.

## Funnel metrics

Measure at least:

- landing page -> readiness check
- readiness check -> email
- email -> download
- download -> first successful model launch
- trial start rate
- trial -> paid conversion
- activation success rate
- first-run completion rate
- refund rate
- support tickets per activated customer

## Product KPI

The strongest activation event is not "app installed".

It is:

**A local model successfully launched with an optimized runtime.**

For agent users, the stronger secondary activation is:

**Hermes successfully executes a local tool call through the selected model.**

## Next commercial milestones

1. Signed entitlement format and verification
2. Small licensing backend
3. Hosted checkout
4. Checkout webhook handling
5. Customer/license database
6. Activation / deactivation endpoints
7. Update manifest and signed releases
8. Landing page + readiness-check funnel
9. Installer/code signing
10. Legal pages, privacy, refund and licensing terms
