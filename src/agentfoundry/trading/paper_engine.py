from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import time
from typing import Callable

from .analysis import PaperAnalysis
from .market_data import DexScreenerSolanaFeed, MarketCandidate
from .memory import TradeMemory, TradeRecord
from .position import (
    ExitAction,
    ExitPolicy,
    PositionSnapshot,
    PositionState,
    evaluate_position,
)
from .risk import RiskPolicy, TokenSnapshot
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
        exit_policy: ExitPolicy | None = None,
        risk_policy: RiskPolicy | None = None,
    ) -> None:
        self.memory = memory
        self.feed = feed or DexScreenerSolanaFeed()
        self.notional_usd = max(1.0, float(notional_usd))
        self.clock = clock
        self.exit_policy = exit_policy or ExitPolicy()
        self.risk_policy = risk_policy

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
        # Persist the risk evidence with the trade.  Exit checks can therefore
        # still enforce deterministic hard-risk rules after a process restart.
        market["risk_evidence"] = asdict(assessment.evidence)
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

    def _position_state(self, row: object) -> PositionState:
        trade_id = str(row["trade_id"])
        state = PositionState(
            symbol=str(row["symbol"]),
            entry_price=float(row["entry_price"]),
            quantity=float(row["quantity"]),
            opened_at_seconds=float(row["opened_at"]),
        )

        # Decisions are the durable observation log. Replaying prices rebuilds
        # the trailing peak/trough after every restart without a schema change.
        decisions = self.memory.db.execute(
            "SELECT action, market_json FROM decisions WHERE trade_id=? ORDER BY observed_at, id",
            (trade_id,),
        )
        for decision in decisions:
            if str(decision["action"]) == "PAPER_PARTIAL_SELL":
                state.partial_taken = True
            try:
                observed = json.loads(decision["market_json"])
                price = float(observed.get("price_usd") or observed.get("price") or 0.0)
            except (TypeError, ValueError, json.JSONDecodeError):
                price = 0.0
            if price > 0:
                state.observe(price)

        # Older positions may only have horizon outcomes because the previous
        # engine did not record HOLD observations. Include those prices so an
        # already-reached peak is not forgotten when this fix is deployed.
        outcomes = self.memory.db.execute(
            "SELECT price FROM outcomes WHERE trade_id=? ORDER BY observed_at",
            (trade_id,),
        )
        for outcome in outcomes:
            price = float(outcome["price"] or 0.0)
            if price > 0:
                state.observe(price)
        return state

    @staticmethod
    def _token_snapshot(candidate: MarketCandidate, opening_market: dict) -> TokenSnapshot:
        evidence = opening_market.get("risk_evidence") or {}
        return TokenSnapshot(
            symbol=candidate.symbol,
            market_cap_usd=float(candidate.market_cap_usd or 0.0),
            liquidity_usd=float(candidate.liquidity_usd or 0.0),
            top10_holder_pct=float(evidence.get("top10_holder_pct") or 0.0),
            developer_holding_pct=float(evidence.get("developer_holding_pct") or 0.0),
            # Backward-compatible safe defaults for positions opened before
            # risk evidence was persisted; live liquidity is still checked.
            liquidity_locked=bool(evidence.get("liquidity_locked", True)),
            mint_authority_enabled=bool(evidence.get("mint_authority_enabled", False)),
            freeze_authority_enabled=bool(evidence.get("freeze_authority_enabled", False)),
        )

    @staticmethod
    def _observation_market(candidate: MarketCandidate, opening_market: dict) -> dict:
        market = asdict(candidate)
        market["candidate_id"] = candidate.token_address
        if "risk_evidence" in opening_market:
            market["risk_evidence"] = opening_market["risk_evidence"]
        return market

    def _close_from_decision(
        self,
        row: object,
        state: PositionState,
        candidate: MarketCandidate,
        now: float,
        reasons: tuple[str, ...],
        updates: list[dict],
        opening_market: dict,
    ) -> None:
        trade_id = str(row["trade_id"])
        realized = state.pnl_pct(candidate.price_usd)
        self.memory.add_decision(
            trade_id,
            now,
            "PAPER_EXIT",
            reasons,
            self._observation_market(candidate, opening_market),
        )
        self.memory.close_trade(
            trade_id,
            now,
            candidate.price_usd,
            realized,
            state.mfe_pct(),
            state.mae_pct(),
        )
        updates.append({
            "trade_id": trade_id,
            "symbol": row["symbol"],
            "status": "closed_exit_policy",
            "exit_reasons": list(reasons),
            "realized_pnl_pct": realized,
        })

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

            state = self._position_state(row)
            completed = set(self.memory.outcome_horizons(trade_id))
            if "24h" in completed:
                state.observe(candidate.price_usd)
                realized = state.pnl_pct(candidate.price_usd)
                self.memory.add_decision(
                    trade_id,
                    now,
                    "PAPER_EXIT",
                    ("max_holding_time_24h",),
                    self._observation_market(candidate, market),
                )
                self.memory.close_trade(
                    trade_id,
                    now,
                    candidate.price_usd,
                    realized,
                    state.mfe_pct(),
                    state.mae_pct(),
                )
                updates.append({
                    "trade_id": trade_id,
                    "symbol": row["symbol"],
                    "status": "closed_24h",
                    "realized_pnl_pct": realized,
                    "exit_reasons": ["max_holding_time_24h"],
                })
                continue

            previous_peak = state.peak_price or state.entry_price
            buy_sell_ratio = candidate.buys_5m / max(1, candidate.sells_5m)
            opening_volume = float(market.get("volume_24h_usd") or 0.0)
            snapshot = PositionSnapshot(
                price=candidate.price_usd,
                observed_at_seconds=now,
                buy_sell_ratio=buy_sell_ratio,
                volume_accelerating=(
                    opening_volume > 0
                    and float(candidate.volume_24h_usd or 0.0) > opening_volume
                ),
                making_new_high=candidate.price_usd > previous_peak,
                token=self._token_snapshot(candidate, market),
            )
            decision = evaluate_position(
                state,
                snapshot,
                exit_policy=self.exit_policy,
                risk_policy=self.risk_policy,
            )

            if decision.action == ExitAction.EXIT:
                self._close_from_decision(
                    row, state, candidate, now, decision.reasons, updates, market
                )
                continue

            observation = self._observation_market(candidate, market)
            if decision.action == ExitAction.PARTIAL:
                remaining_quantity = state.quantity * (1.0 - decision.sell_fraction)
                self.memory.db.execute(
                    "UPDATE trades SET quantity=? WHERE trade_id=? AND status='open'",
                    (remaining_quantity, trade_id),
                )
                self.memory.db.commit()
                self.memory.add_decision(
                    trade_id,
                    now,
                    "PAPER_PARTIAL_SELL",
                    decision.reasons,
                    observation,
                )
                updates.append({
                    "trade_id": trade_id,
                    "symbol": row["symbol"],
                    "status": "partial_profit",
                    "sell_fraction": decision.sell_fraction,
                    "remaining_quantity": remaining_quantity,
                    "reasons": list(decision.reasons),
                })
            else:
                # HOLD observations persist the high-water mark used by the
                # trailing stop, including across application restarts.
                self.memory.add_decision(
                    trade_id,
                    now,
                    "PAPER_HOLD",
                    decision.reasons,
                    observation,
                )

        return updates
