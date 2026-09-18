from agentfoundry.packs import builtin_registry
from agentfoundry.trading import RiskPolicy, TokenSnapshot, evaluate_snapshot


def test_builtin_sol_research_pack_is_paper_only() -> None:
    pack = builtin_registry().get("trading.solana-research")
    assert pack.category == "trading"
    assert pack.paper_only is True
    assert "parallel-ai-analysis" in pack.capabilities


def test_safe_snapshot_passes_default_gates() -> None:
    snapshot = TokenSnapshot(
        symbol="TESTCAT", market_cap_usd=84_000, liquidity_usd=27_500,
        top10_holder_pct=31, developer_holding_pct=2.8,
        liquidity_locked=True, mint_authority_enabled=False,
        freeze_authority_enabled=False,
    )
    decision = evaluate_snapshot(snapshot)
    assert decision.passed is True
    assert decision.reasons == ()


def test_risk_trap_cannot_be_overridden_by_ai() -> None:
    snapshot = TokenSnapshot(
        symbol="ROCKETCAT", market_cap_usd=112_000, liquidity_usd=13_800,
        top10_holder_pct=67, developer_holding_pct=14.8,
        liquidity_locked=False, mint_authority_enabled=True,
        freeze_authority_enabled=True,
    )
    decision = evaluate_snapshot(snapshot, RiskPolicy())
    assert decision.passed is False
    assert set(decision.reasons) == {
        "top10_holder_concentration",
        "developer_holding_concentration",
        "liquidity_unlocked",
        "mint_authority_enabled",
        "freeze_authority_enabled",
    }
