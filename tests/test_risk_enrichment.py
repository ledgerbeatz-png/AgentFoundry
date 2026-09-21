from agentfoundry.trading.market_data import MarketCandidate
from agentfoundry.trading.risk_enrichment import RugCheckClient


def candidate(liquidity=25000):
    return MarketCandidate(
        token_address="A" * 32,
        symbol="CAT",
        name="Labor Cat",
        pair_address="PAIR",
        dex_id="raydium",
        price_usd=0.01,
        liquidity_usd=liquidity,
        market_cap_usd=100000,
        fdv_usd=100000,
        volume_24h_usd=50000,
        buys_5m=20,
        sells_5m=5,
        pair_created_at=1,
        url="",
    )


def clean_report():
    return {
        "creator": "DEV",
        "mintAuthority": None,
        "freezeAuthority": None,
        "rugged": False,
        "score": 100,
        "topHolders": [
            {"owner": "DEV", "percentage": 5},
            {"owner": "A", "percentage": 8},
            {"owner": "B", "percentage": 7},
            {"owner": "C", "percentage": 6},
        ],
        "markets": [{"lp": {"lpLockedPct": 100}}],
        "risks": [],
    }


def test_parse_clean_rugcheck_report():
    evidence = RugCheckClient.parse(clean_report())

    assert evidence.top10_holder_pct == 26
    assert evidence.developer_holding_pct == 5
    assert evidence.liquidity_locked is True
    assert evidence.mint_authority_enabled is False
    assert evidence.freeze_authority_enabled is False
    assert evidence.missing == ()


def test_missing_evidence_blocks_instead_of_guessing(monkeypatch):
    client = RugCheckClient(delay_seconds=0)
    report = clean_report()
    report.pop("markets")
    monkeypatch.setattr(client, "report", lambda _mint: report)

    assessment = client.assess(candidate())

    assert assessment.status == "BLOCK"
    assert "missing_liquidity_lock" in assessment.decision.reasons


def test_hard_risk_gate_rejects_mint_authority(monkeypatch):
    client = RugCheckClient(delay_seconds=0)
    report = clean_report()
    report["mintAuthority"] = "ACTIVE"
    monkeypatch.setattr(client, "report", lambda _mint: report)

    assessment = client.assess(candidate())

    assert assessment.status == "BLOCK"
    assert "mint_authority_enabled" in assessment.decision.reasons


def test_hard_risk_gate_accepts_complete_clean_evidence(monkeypatch):
    client = RugCheckClient(delay_seconds=0)
    monkeypatch.setattr(client, "report", lambda _mint: clean_report())

    assessment = client.assess(candidate())

    assert assessment.status == "PASS"
    assert assessment.decision.passed is True


class FakeRpc:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def enrich(self, mint, creator="", supply=None, need_authorities=False):
        self.calls.append((mint, creator, supply, need_authorities))
        return dict(self.payload)


def test_rpc_fallback_fills_missing_holder_and_developer_evidence(monkeypatch):
    report = clean_report()
    report["creator"] = "DEV"
    report.pop("topHolders")
    rpc = FakeRpc({
        "top10_holder_pct": 31.5,
        "developer_holding_pct": 4.25,
        "mint_authority_enabled": False,
        "freeze_authority_enabled": False,
    })
    client = RugCheckClient(delay_seconds=0, rpc_client=rpc)
    monkeypatch.setattr(client, "report", lambda _mint: report)

    assessment = client.assess(candidate())

    assert rpc.calls == [("A" * 32, "DEV", None, False)]
    assert assessment.evidence.top10_holder_pct == 31.5
    assert assessment.evidence.developer_holding_pct == 4.25
    assert assessment.status == "PASS"
    assert "solana_rpc_fallback_used" in assessment.evidence.warnings


def test_rpc_fallback_stays_fail_closed_when_creator_is_unavailable(monkeypatch):
    report = clean_report()
    report["creator"] = ""
    report.pop("topHolders")
    rpc = FakeRpc({
        "top10_holder_pct": 25.0,
        "developer_holding_pct": None,
        "mint_authority_enabled": False,
        "freeze_authority_enabled": False,
    })
    client = RugCheckClient(delay_seconds=0, rpc_client=rpc)
    monkeypatch.setattr(client, "report", lambda _mint: report)

    assessment = client.assess(candidate())

    assert assessment.status == "BLOCK"
    assert "missing_developer_holding_pct" in assessment.decision.reasons
