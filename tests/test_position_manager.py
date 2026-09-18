from agentfoundry.trading.position import ExitAction, PositionSnapshot, PositionState, evaluate_position
from agentfoundry.trading.risk import TokenSnapshot


def token(**changes):
    data = dict(symbol="CAT", market_cap_usd=100000, liquidity_usd=30000, top10_holder_pct=30,
                developer_holding_pct=3, liquidity_locked=True, mint_authority_enabled=False,
                freeze_authority_enabled=False)
    data.update(changes)
    return TokenSnapshot(**data)


def market(price, minutes=10, ratio=2.0, accelerating=True, high=True, **token_changes):
    return PositionSnapshot(price, minutes * 60, ratio, accelerating, high, token(**token_changes))


def test_holds_winner_while_momentum_is_healthy():
    p = PositionState("CAT", 1.0, 100, 0)
    assert evaluate_position(p, market(1.35)).action == ExitAction.HOLD


def test_partial_profit_keeps_runner():
    p = PositionState("CAT", 1.0, 100, 0)
    d = evaluate_position(p, market(1.60))
    assert d.action == ExitAction.PARTIAL
    assert 0 < d.sell_fraction < 1


def test_trailing_stop_exits_after_peak_reversal():
    p = PositionState("CAT", 1.0, 100, 0)
    evaluate_position(p, market(2.0))
    d = evaluate_position(p, market(1.50, minutes=20, ratio=0.7, accelerating=False, high=False))
    assert d.action == ExitAction.EXIT
    assert "trailing_stop" in d.reasons


def test_new_hard_risk_forces_exit():
    p = PositionState("CAT", 1.0, 100, 0)
    d = evaluate_position(p, market(1.20, liquidity_locked=False))
    assert d.action == ExitAction.EXIT
    assert "hard_risk:liquidity_unlocked" in d.reasons


def test_tracks_mfe_and_mae():
    p = PositionState("CAT", 1.0, 100, 0)
    p.observe(1.8)
    p.observe(0.9)
    assert round(p.mfe_pct(), 1) == 80.0
    assert round(p.mae_pct(), 1) == -10.0
