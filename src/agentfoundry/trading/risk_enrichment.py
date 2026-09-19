from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .market_data import MarketCandidate
from .risk import RiskDecision, RiskPolicy, TokenSnapshot, evaluate_snapshot


RUGCHECK_BASE = "https://api.rugcheck.xyz"


@dataclass(frozen=True)
class RiskEvidence:
    top10_holder_pct: float | None
    developer_holding_pct: float | None
    liquidity_locked: bool | None
    mint_authority_enabled: bool | None
    freeze_authority_enabled: bool | None
    rugged: bool | None
    score: float | None
    missing: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CandidateRiskAssessment:
    candidate: MarketCandidate
    status: str
    decision: RiskDecision
    evidence: RiskEvidence


class RugCheckClient:
    """Read-only RugCheck adapter with defensive parsing.

    Missing or ambiguous evidence never becomes a pass. The deterministic gate
    only evaluates a token after every required safety field is available.
    """

    def __init__(self, timeout: float = 15.0, opener=None, delay_seconds: float = 0.35) -> None:
        self.timeout = timeout
        self._opener = opener or urlopen
        self.delay_seconds = max(0.0, delay_seconds)

    def report(self, mint: str) -> dict[str, Any]:
        mint = mint.strip()
        if len(mint) < 32:
            raise ValueError("A valid-looking Solana mint address is required.")
        request = Request(
            f"{RUGCHECK_BASE}/v1/tokens/{quote(mint, safe='')}/report",
            headers={
                "Accept": "application/json",
                "User-Agent": "AgentFoundry/0.1 SolanaResearchPaper",
            },
        )
        with self._opener(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Unexpected RugCheck response format.")
        return payload

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _holder_pct(cls, holder: dict[str, Any]) -> float | None:
        for key in ("pct", "percentage", "percent"):
            number = cls._number(holder.get(key))
            if number is not None:
                return number
        return None

    @staticmethod
    def _authority(report: dict[str, Any], key: str) -> tuple[bool | None, bool]:
        token = report.get("token") if isinstance(report.get("token"), dict) else {}
        if key in report:
            return report.get(key) is not None, True
        if key in token:
            return token.get(key) is not None, True
        return None, False

    @classmethod
    def parse(cls, report: dict[str, Any]) -> RiskEvidence:
        missing: list[str] = []
        warnings: list[str] = []

        holders = report.get("topHolders")
        if not isinstance(holders, list):
            holders = []
        holder_pcts = [
            pct for holder in holders[:10]
            if isinstance(holder, dict) and (pct := cls._holder_pct(holder)) is not None
        ]
        top10 = sum(holder_pcts) if holder_pcts else None
        if top10 is None:
            missing.append("top10_holder_pct")

        creator = str(report.get("creator") or "").strip()
        developer = None
        if creator and holders:
            creator_pcts = []
            for holder in holders:
                if not isinstance(holder, dict):
                    continue
                owner = str(holder.get("owner") or holder.get("address") or "").strip()
                pct = cls._holder_pct(holder)
                if owner == creator and pct is not None:
                    creator_pcts.append(pct)
            if creator_pcts:
                developer = sum(creator_pcts)
            else:
                # Creator is known and absent from reported top holders. Treat this
                # as zero only if RugCheck supplied a holder set; otherwise unknown.
                developer = 0.0
        if developer is None:
            missing.append("developer_holding_pct")

        mint_enabled, mint_known = cls._authority(report, "mintAuthority")
        freeze_enabled, freeze_known = cls._authority(report, "freezeAuthority")
        if not mint_known:
            missing.append("mint_authority")
        if not freeze_known:
            missing.append("freeze_authority")

        lock_values: list[float] = []
        markets = report.get("markets")
        if isinstance(markets, list):
            for market in markets:
                if not isinstance(market, dict):
                    continue
                lp = market.get("lp") if isinstance(market.get("lp"), dict) else {}
                for key in ("lpLockedPct", "lpBurnedPct", "lockedPct", "burnedPct"):
                    value = cls._number(lp.get(key))
                    if value is not None:
                        lock_values.append(value)
        liquidity_locked = max(lock_values) >= 95.0 if lock_values else None
        if liquidity_locked is None:
            missing.append("liquidity_lock")

        risks = report.get("risks")
        if isinstance(risks, list):
            for risk in risks:
                if isinstance(risk, dict):
                    name = str(risk.get("name") or risk.get("description") or "").strip()
                    if name:
                        warnings.append(name)

        rugged = report.get("rugged") if isinstance(report.get("rugged"), bool) else None
        score = cls._number(report.get("score"))

        return RiskEvidence(
            top10_holder_pct=top10,
            developer_holding_pct=developer,
            liquidity_locked=liquidity_locked,
            mint_authority_enabled=mint_enabled,
            freeze_authority_enabled=freeze_enabled,
            rugged=rugged,
            score=score,
            missing=tuple(missing),
            warnings=tuple(warnings[:8]),
        )

    def assess(
        self,
        candidate: MarketCandidate,
        policy: RiskPolicy | None = None,
    ) -> CandidateRiskAssessment:
        report = self.report(candidate.token_address)
        evidence = self.parse(report)

        reasons: list[str] = []
        if evidence.rugged is True:
            reasons.append("rugcheck_rugged")
        reasons.extend(f"missing_{name}" for name in evidence.missing)

        if reasons:
            decision = RiskDecision(False, tuple(reasons))
            status = "BLOCK"
        else:
            snapshot = TokenSnapshot(
                symbol=candidate.symbol,
                market_cap_usd=candidate.market_cap_usd or 0.0,
                liquidity_usd=candidate.liquidity_usd,
                top10_holder_pct=float(evidence.top10_holder_pct),
                developer_holding_pct=float(evidence.developer_holding_pct),
                liquidity_locked=bool(evidence.liquidity_locked),
                mint_authority_enabled=bool(evidence.mint_authority_enabled),
                freeze_authority_enabled=bool(evidence.freeze_authority_enabled),
            )
            decision = evaluate_snapshot(snapshot, policy)
            status = "PASS" if decision.passed else "BLOCK"

        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return CandidateRiskAssessment(candidate, status, decision, evidence)
