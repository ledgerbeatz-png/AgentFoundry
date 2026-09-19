from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import time
from typing import Callable

from .analysis import PaperAnalysis
from .market_data import DexScreenerSolanaFeed, MarketCandidate
from .memory import TradeMemory, TradeRecord
from .risk_enrichment import CandidateRiskAssessment


HORIZONS = (
    ("5m", 5 * 60),
    ("15m", 15 * 60),
    ("1h", 60 * 60),
    ("6h", 6 * 60 * 60),
    ("24h", 24 * 60 * 60),
)


class PaperResearchEngine:
    """Persistent paper-only executor and outcome tracker.

    It never signs transactions or talks to a wallet. PAPER_BUY creates a
    simulated position in SQLite. Outcomes are sampled from public market data.
    """

    def __init__(
        self,
        memory: TradeMemory,
        feed: DexScreenerSolanaFeed | None = None,
        notional_usd: float = 100.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.memory = memory
        self.feed = feed or DexScreenerSolanaFeed()
        self.notional_usd = max(1.0, float(notional_usd))
        self.clock = clock

    @staticmethod
    def _trade_id(candidate: MarketCandidate, opened_at: float) -> str:
        # Daily bucket prevents repeated scans from opening duplicate positions
        # while still allowing a later re-entry on another day.
        day = datetime.fromtimestamp(opened_at, tz=timezone.utc).strftime("%Y%m%d")
        return f"paper:{candidate.token_address}:{day}"

    def open_from_analysis(
        self,
        assessment: CandidateRiskAssessment,
        analysis: PaperAnalysis,
    ) -> str | None:
        if analysis.action != "PAPER_BUY":
            return None
        candidate = assessment.candidate
        if candidate.price_usd is None or candidate.price_usd <= 0:
            raise ValueError("Cannot open PAPER position without a positive entry price.")

        existing = self.memory.open_trade_for_candidate(candidate.token_address)
        if existing is not None:
            return str(existing["trade_id"])

        opened_at = self.clock()
        trade_id = self._trade_id(candidate, opened_at)
        quantity = self.notional_usd / candidate.price_usd
        record = TradeRecord(
            trade_id=trade_id,
            symbol=candidate.symbol,
            strategy_version="qwen-paper-v1",
            opened_at=opened_at,
            entry_price=candidate.price_usd,
            quantity=quantity,
        )
        self.memory.open_trade(record)
        market = asdict(candidate)
        market["candidate_id"] = candidate.token_address
        market["notional_usd"] = self.notional_usd
        market["qwen_confidence"] = analysis.confidence
        market["qwen_thesis"] = analysis.thesis
        self.memory.add_decision(
            trade_id,
            opened_at,
            "PAPER_BUY",
            tuple(analysis.reasons) + tuple(analysis.risks),
            market,
        )
        return trade_id

    def _current_candidate(self, token_address: str) -> MarketCandidate | None:
        pairs = self.feed.pairs_for_addresses([token_address])
        candidates = [
            candidate
            for pair in pairs
            if (candidate := self.feed.normalize_pair(pair)) is not None
            and candidate.token_address == token_address
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.liquidity_usd)

    def refresh_due(self, now: float | None = None) -> list[dict]:
        now = self.clock() if now is None else float(now)
        updates: list[dict] = []
        for row in self.memory.open_trades_with_market():
            trade_id = str(row["trade_id"])
            opened_at = float(row["opened_at"])
            market = json.loads(row["market_json"])
            token_address = str(market.get("token_address") or market.get("candidate_id") or "")
            if not token_address:
                continue

            completed = set(self.memory.outcome_horizons(trade_id))
            due = [
                (name, seconds)
                for name, seconds in HORIZONS
                if name not in completed and now >= opened_at + seconds
            ]
            if not due:
                continue

            candidate = self._current_candidate(token_address)
            if candidate is None or candidate.price_usd is None or candidate.price_usd <= 0:
                updates.append({
                    "trade_id": trade_id,
                    "symbol": row["symbol"],
                    "status": "price_unavailable",
                })
                continue

            for horizon, _seconds in due:
                self.memory.add_outcome(trade_id, horizon, now, candidate.price_usd)
                updates.append({
                    "trade_id": trade_id,
                    "symbol": row["symbol"],
                    "horizon": horizon,
                    "price": candidate.price_usd,
                })

            completed = set(self.memory.outcome_horizons(trade_id))
            if "24h" in completed:
                outcome_rows = self.memory.outcomes_for_trade(trade_id)
                returns = [float(item["return_from_entry_pct"]) for item in outcome_rows]
                realized = next(
                    float(item["return_from_entry_pct"])
                    for item in outcome_rows
                    if item["horizon"] == "24h"
                )
                self.memory.close_trade(
                    trade_id,
                    now,
                    candidate.price_usd,
                    realized,
                    max(returns) if returns else realized,
                    min(returns) if returns else realized,
                )
                updates.append({
                    "trade_id": trade_id,
                    "symbol": row["symbol"],
                    "status": "closed_24h",
                    "realized_pnl_pct": realized,
                })
        return updates
