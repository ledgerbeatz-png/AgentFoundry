from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .risk import RiskPolicy, TokenSnapshot, evaluate_snapshot


class ExitAction(str, Enum):
    HOLD = "hold"
    PARTIAL = "partial_sell"
    EXIT = "exit"


@dataclass(frozen=True)
class ExitPolicy:
    stop_loss_pct: float = -25.0
    partial_take_profit_pct: float = 50.0
    partial_fraction: float = 0.35
    trailing_stop_pct: float = 22.0
    stagnation_minutes: int = 45
    min_buy_sell_ratio_to_hold: float = 1.05
    max_drawdown_from_peak_pct: float = 22.0


@dataclass
class PositionState:
    symbol: str
    entry_price: float
    quantity: float
    opened_at_seconds: float
    peak_price: float | None = None
    trough_price: float | None = None
    partial_taken: bool = False

    def observe(self, price: float) -> None:
        self.peak_price = price if self.peak_price is None else max(self.peak_price, price)
        self.trough_price = price if self.trough_price is None else min(self.trough_price, price)

    def pnl_pct(self, price: float) -> float:
        return (price / self.entry_price - 1.0) * 100.0

    def mfe_pct(self) -> float:
        peak = self.peak_price or self.entry_price
        return (peak / self.entry_price - 1.0) * 100.0

    def mae_pct(self) -> float:
        trough = self.trough_price or self.entry_price
        return (trough / self.entry_price - 1.0) * 100.0


@dataclass(frozen=True)
class PositionSnapshot:
    price: float
    observed_at_seconds: float
    buy_sell_ratio: float
    volume_accelerating: bool
    making_new_high: bool
    token: TokenSnapshot


@dataclass(frozen=True)
class ExitDecision:
    action: ExitAction
    reasons: tuple[str, ...]
    sell_fraction: float = 0.0


def evaluate_position(
    position: PositionState,
    market: PositionSnapshot,
    exit_policy: ExitPolicy | None = None,
    risk_policy: RiskPolicy | None = None,
) -> ExitDecision:
    """Deterministic paper-trading exit layer. AI may add context but cannot override hard exits."""
    policy = exit_policy or ExitPolicy()
    position.observe(market.price)
    pnl = position.pnl_pct(market.price)
    peak = position.peak_price or market.price
    drawdown = (market.price / peak - 1.0) * 100.0
    age_minutes = max(0.0, (market.observed_at_seconds - position.opened_at_seconds) / 60.0)

    risk = evaluate_snapshot(market.token, risk_policy)
    if not risk.passed:
        return ExitDecision(ExitAction.EXIT, tuple(f"hard_risk:{r}" for r in risk.reasons), 1.0)

    if pnl <= policy.stop_loss_pct:
        return ExitDecision(ExitAction.EXIT, ("stop_loss",), 1.0)

    if position.mfe_pct() > 0 and drawdown <= -policy.trailing_stop_pct:
        return ExitDecision(ExitAction.EXIT, ("trailing_stop",), 1.0)

    momentum_healthy = (
        market.buy_sell_ratio >= policy.min_buy_sell_ratio_to_hold
        and (market.volume_accelerating or market.making_new_high)
    )

    if pnl >= policy.partial_take_profit_pct and not position.partial_taken and momentum_healthy:
        return ExitDecision(ExitAction.PARTIAL, ("lock_profit_keep_runner",), policy.partial_fraction)

    if age_minutes >= policy.stagnation_minutes and not momentum_healthy:
        return ExitDecision(ExitAction.EXIT, ("stagnation", "momentum_weak"), 1.0)

    if drawdown <= -policy.max_drawdown_from_peak_pct and not momentum_healthy:
        return ExitDecision(ExitAction.EXIT, ("peak_drawdown", "momentum_weak"), 1.0)

    return ExitDecision(ExitAction.HOLD, ("momentum_intact",) if momentum_healthy else ("no_exit_trigger",))
