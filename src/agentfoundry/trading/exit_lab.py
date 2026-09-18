from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .position import ExitAction, ExitDecision, ExitPolicy, PositionSnapshot, PositionState, evaluate_position


@dataclass(frozen=True)
class ExitPolicyCandidate:
    name: str
    policy: ExitPolicy


@dataclass
class ExitPolicyResult:
    name: str
    exit_price: float
    realized_pnl_pct: float
    mfe_pct: float
    mae_pct: float
    exit_reason: tuple[str, ...]
    partial_events: list[tuple[float, float]] = field(default_factory=list)


def default_candidates() -> tuple[ExitPolicyCandidate, ...]:
    return (
        ExitPolicyCandidate("tight_trailing", ExitPolicy(trailing_stop_pct=15.0, max_drawdown_from_peak_pct=15.0)),
        ExitPolicyCandidate("balanced", ExitPolicy()),
        ExitPolicyCandidate("wide_runner", ExitPolicy(partial_take_profit_pct=75.0, trailing_stop_pct=30.0, max_drawdown_from_peak_pct=30.0, stagnation_minutes=75)),
    )


def replay_exit_policies(
    entry_price: float,
    quantity: float,
    opened_at_seconds: float,
    snapshots: Iterable[PositionSnapshot],
    candidates: Iterable[ExitPolicyCandidate] | None = None,
) -> list[ExitPolicyResult]:
    """Replay identical paper-market snapshots through several deterministic exit policies."""
    series = list(snapshots)
    if not series:
        raise ValueError("At least one market snapshot is required.")

    results: list[ExitPolicyResult] = []
    for candidate in tuple(candidates or default_candidates()):
        position = PositionState(series[0].token.symbol, entry_price, quantity, opened_at_seconds)
        remaining = 1.0
        realized_return = 0.0
        partials: list[tuple[float, float]] = []
        final_decision = ExitDecision(ExitAction.HOLD, ("end_of_replay",))
        final_price = series[-1].price

        for market in series:
            decision = evaluate_position(position, market, candidate.policy)
            if decision.action == ExitAction.PARTIAL and not position.partial_taken:
                fraction = min(max(decision.sell_fraction, 0.0), remaining)
                realized_return += fraction * position.pnl_pct(market.price)
                remaining -= fraction
                position.partial_taken = True
                partials.append((market.price, fraction))
            elif decision.action == ExitAction.EXIT:
                realized_return += remaining * position.pnl_pct(market.price)
                remaining = 0.0
                final_decision = decision
                final_price = market.price
                break

        if remaining > 0:
            realized_return += remaining * position.pnl_pct(final_price)

        results.append(
            ExitPolicyResult(
                name=candidate.name,
                exit_price=final_price,
                realized_pnl_pct=realized_return,
                mfe_pct=position.mfe_pct(),
                mae_pct=position.mae_pct(),
                exit_reason=final_decision.reasons,
                partial_events=partials,
            )
        )
    return results
