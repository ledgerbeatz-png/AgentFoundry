from agentfoundry.trading.analysis import PaperAnalysis
from agentfoundry.trading.manual_evaluator import ManualTokenEvaluator, normalize_token_input
from agentfoundry.trading.market_data import MarketCandidate
from agentfoundry.trading.risk import RiskDecision
from agentfoundry.trading.risk_enrichment import CandidateRiskAssessment, RiskEvidence


TOKEN = "A" * 32


def candidate():
    return MarketCandidate(
        token_address=TOKEN,
        symbol="TEST",
        name="Test Coin",
        pair_address="PAIR",
        dex_id="raydium",
        price_usd=0.01,
        liquidity_usd=25000,
        market_cap_usd=100000,
        fdv_usd=100000,
        volume_24h_usd=80000,
        buys_5m=30,
        sells_5m=10,
        pair_created_at=1,
        url="",
    )


def risk(passed=True):
    evidence = RiskEvidence(
        top10_holder_pct=25,
        developer_holding_pct=1,
        liquidity_locked=True,
        mint_authority_enabled=False,
        freeze_authority_enabled=False,
        rugged=False,
        score=100,
        missing=(),
        warnings=(),
    )
    decision = RiskDecision(passed, () if passed else ("liquidity_below_minimum",))
    return CandidateRiskAssessment(candidate(), "PASS" if passed else "BLOCK", decision, evidence)


class Feed:
    def pairs_for_addresses(self, addresses):
        assert addresses == [TOKEN]
        return [{"fake": True}]

    @staticmethod
    def normalize_pair(_pair):
        return candidate()


class RiskClient:
    def __init__(self, passed=True):
        self.passed = passed

    def assess(self, _candidate):
        return risk(self.passed)


class Analyst:
    def __init__(self):
        self.calls = 0

    def analyze(self, _assessment):
        self.calls += 1
        return PaperAnalysis("PAPER_BUY", 0.8, "Interesting setup.", (), ("momentum",), {})


def test_manual_evaluator_runs_qwen_only_after_pass():
    analyst = Analyst()
    result = ManualTokenEvaluator(Feed(), RiskClient(True), analyst).evaluate(TOKEN)

    assert result.risk.decision.passed is True
    assert result.analysis.action == "PAPER_BUY"
    assert analyst.calls == 1


def test_manual_evaluator_block_skips_qwen():
    analyst = Analyst()
    result = ManualTokenEvaluator(Feed(), RiskClient(False), analyst).evaluate(TOKEN)

    assert result.risk.decision.passed is False
    assert result.analysis is None
    assert analyst.calls == 0


def test_normalize_token_input_accepts_mint_and_url():
    assert normalize_token_input(TOKEN) == TOKEN
    assert normalize_token_input(f"https://example.test/token/{TOKEN}") == TOKEN
