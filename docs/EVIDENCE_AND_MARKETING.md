# Evidence & Marketing Documentation

AgentFoundry should earn trust with reproducible evidence rather than profit promises.

## Evidence record

Every paper-trading decision should eventually be exportable with:

- timestamp and strategy/version identifier
- hardware profile and local model/profile
- market snapshot at entry
- deterministic entry gate result and reason codes
- AI RISK / ALPHA outputs when used
- entry price and simulated size
- every HOLD / PARTIAL / EXIT decision with reason codes
- peak/trough observations and MFE / MAE
- simulated fees and slippage assumptions
- realized net paper PnL
- 5m / 15m / 1h / 6h / 24h post-decision outcome snapshots

## Reproducibility

A case study is marketing-ready only when the underlying decision can be traced to stored inputs, strategy version, model profile and deterministic rules. Cherry-picked screenshots without the underlying record are not sufficient evidence.

## Public case-study format

A public case study should clearly label PAPER results and show a compact timeline, for example:

Entry -> HOLD -> Partial profit -> HOLD -> Trailing exit

Include the market conditions and the reason for each action. Report fees/slippage assumptions and net simulated result. Never imply that historical or paper performance guarantees future returns.

## Product claims

Preferred claims describe capabilities that can be demonstrated:

- local AI setup and hardware-aware optimization
- deterministic risk gates before AI interpretation
- parallel local AI analysis
- auditable paper-trade decisions
- adaptive position management
- benchmark-driven worker selection
- replayable strategy evaluation

Avoid unsupported claims such as guaranteed profits, a guaranteed win rate, or "maximum profit".

## Development rule

New trading features should expose machine-readable reason codes and enough state to reconstruct the decision later. Documentation is therefore a product requirement, not an afterthought.
