from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class StrategyScore:
    strategy_version: str
    trades: int
    mean_pnl_pct: float
    win_rate: float
    mean_mfe_capture: float


def score_strategy(strategy_version: str, trades) -> StrategyScore:
    rows = list(trades)
    if not rows:
        return StrategyScore(strategy_version, 0, 0.0, 0.0, 0.0)
    pnls = [float(r["realized_pnl_pct"]) for r in rows]
    captures = []
    for r in rows:
        mfe = float(r["mfe_pct"] or 0.0)
        pnl = float(r["realized_pnl_pct"] or 0.0)
        if mfe > 0:
            captures.append(max(0.0, min(1.0, pnl / mfe)))
    return StrategyScore(
        strategy_version=strategy_version,
        trades=len(rows),
        mean_pnl_pct=mean(pnls),
        win_rate=sum(p > 0 for p in pnls) / len(pnls),
        mean_mfe_capture=mean(captures) if captures else 0.0,
    )


def candidate_can_advance(candidate: StrategyScore, baseline: StrategyScore, min_trades: int = 100) -> bool:
    """Conservative paper-only promotion gate; prevents tiny samples from rewriting strategy."""
    if candidate.trades < min_trades or baseline.trades < min_trades:
        return False
    return (
        candidate.mean_pnl_pct > baseline.mean_pnl_pct
        and candidate.mean_mfe_capture >= baseline.mean_mfe_capture
    )
