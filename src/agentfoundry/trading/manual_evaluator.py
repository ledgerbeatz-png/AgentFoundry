from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .analysis import LocalQwenAnalyst, PaperAnalysis
from .market_data import DexScreenerSolanaFeed, MarketCandidate
from .risk_enrichment import CandidateRiskAssessment, RugCheckClient


@dataclass(frozen=True)
class ManualEvaluation:
    candidate: MarketCandidate
    risk: CandidateRiskAssessment
    analysis: PaperAnalysis | None


def normalize_token_input(value: str) -> str:
    """Accept a Solana mint or a common token/pair URL and return the final id."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Paste a Solana token address or token URL.")

    if "://" in value:
        parsed = urlparse(value)
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("Could not find a token address in that URL.")
        # DexScreener URLs often end in a pair address rather than the token mint.
        # The caller resolves either form through DEX market data.
        value = parts[-1]

    if len(value) < 32:
        raise ValueError("Token address looks too short.")
    return value


class ManualTokenEvaluator:
    """One-shot read-only evaluator for a user-selected Solana token."""

    def __init__(
        self,
        feed: DexScreenerSolanaFeed,
        risk_client: RugCheckClient,
        analyst: LocalQwenAnalyst,
    ) -> None:
        self.feed = feed
        self.risk_client = risk_client
        self.analyst = analyst

    def _candidate_for_input(self, token_or_pair: str) -> MarketCandidate:
        # First treat the input as a token mint.
        pairs = self.feed.pairs_for_addresses([token_or_pair])
        candidates = [
            candidate
            for pair in pairs
            if (candidate := self.feed.normalize_pair(pair)) is not None
        ]
        if candidates:
            return max(candidates, key=lambda item: item.liquidity_usd)

        # If a DEX URL supplied a pair address, search can still be added by a
        # provider-specific adapter later. Keep the failure explicit for now.
        raise ValueError(
            "No Solana token market found for that address. Paste the token mint address rather than a pair address."
        )

    def evaluate(self, value: str) -> ManualEvaluation:
        token = normalize_token_input(value)
        candidate = self._candidate_for_input(token)
        risk = self.risk_client.assess(candidate)
        analysis = self.analyst.analyze(risk) if risk.decision.passed else None
        return ManualEvaluation(candidate=candidate, risk=risk, analysis=analysis)
