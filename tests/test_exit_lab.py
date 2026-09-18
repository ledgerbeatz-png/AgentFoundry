from agentfoundry.trading.exit_lab import replay_exit_policies
from agentfoundry.trading.position import PositionSnapshot
from agentfoundry.trading.risk import TokenSnapshot


def token():
    return TokenSnapshot("CAT", 100000, 30000, 30, 3, True, False, False)


def snap(price, minute, ratio=2.0, accelerating=True, high=True):
    return PositionSnapshot(price, minute * 60, ratio, accelerating, high, token())


def test_exit_lab_replays_same_market_across_candidates():
    series = [
        snap(1.10, 5), snap(1.60, 10), snap(2.00, 15),
        snap(1.72, 20, 0.8, False, False),
        snap(1.45, 25, 0.6, False, False),
    ]
    results = replay_exit_policies(1.0, 100, 0, series)
    assert len(results) == 3
    assert {r.name for r in results} == {"tight_trailing", "balanced", "wide_runner"}
    assert all(r.mfe_pct >= 60 for r in results)


def test_exit_lab_requires_market_data():
    try:
        replay_exit_policies(1.0, 100, 0, [])
    except ValueError:
        return
    raise AssertionError("empty replay must fail")
