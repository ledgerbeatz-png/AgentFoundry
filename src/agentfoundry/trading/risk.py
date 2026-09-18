from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenSnapshot:
    symbol: str
    market_cap_usd: float
    liquidity_usd: float
    top10_holder_pct: float
    developer_holding_pct: float
    liquidity_locked: bool
    mint_authority_enabled: bool
    freeze_authority_enabled: bool


@dataclass(frozen=True)
class RiskPolicy:
    min_liquidity_usd: float = 10_000.0
    max_top10_holder_pct: float = 60.0
    max_developer_holding_pct: float = 12.0
    require_locked_liquidity: bool = True
    reject_mint_authority: bool = True
    reject_freeze_authority: bool = True


@dataclass(frozen=True)
class RiskDecision:
    passed: bool
    reasons: tuple[str, ...]


def evaluate_snapshot(snapshot: TokenSnapshot, policy: RiskPolicy | None = None) -> RiskDecision:
    """Apply deterministic pre-AI gates. The LLM cannot override these failures."""
    policy = policy or RiskPolicy()
    reasons: list[str] = []

    if snapshot.liquidity_usd < policy.min_liquidity_usd:
        reasons.append("liquidity_below_minimum")
    if snapshot.top10_holder_pct > policy.max_top10_holder_pct:
        reasons.append("top10_holder_concentration")
    if snapshot.developer_holding_pct > policy.max_developer_holding_pct:
        reasons.append("developer_holding_concentration")
    if policy.require_locked_liquidity and not snapshot.liquidity_locked:
        reasons.append("liquidity_unlocked")
    if policy.reject_mint_authority and snapshot.mint_authority_enabled:
        reasons.append("mint_authority_enabled")
    if policy.reject_freeze_authority and snapshot.freeze_authority_enabled:
        reasons.append("freeze_authority_enabled")

    return RiskDecision(passed=not reasons, reasons=tuple(reasons))
