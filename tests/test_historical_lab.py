from agentfoundry.trading.historical_lab import (
    HistoricalCoin,
    build_snapshot,
    compare_cohorts,
)


def candles(start, prices, volume=1000):
    rows = []
    for index, price in enumerate(prices):
        ts = start + index * 300
        rows.append([ts, price, price * 1.05, price * 0.95, price, volume])
    return rows


def test_build_snapshot_derives_early_and_24h_features():
    start = 1_700_000_000
    prices = [1.0] * 288
    prices[3] = 1.2
    prices[12] = 1.5
    prices[72] = 2.0
    prices[-1] = 3.0

    coin = HistoricalCoin("WIN", "TOKEN", "POOL", start, "profitable")
    snap = build_snapshot(coin, candles(start, prices))

    assert snap.return_15m_pct == 20.0
    assert snap.return_1h_pct == 50.0
    assert snap.return_6h_pct == 100.0
    assert round(snap.return_24h_pct, 6) == 200.0
    assert snap.volume_15m_usd == 3000
    assert snap.cohort == "profitable"


def test_compare_cohorts_keeps_controls_separate():
    start = 1_700_000_000
    winner = build_snapshot(
        HistoricalCoin("WIN", "A", "PA", start, "profitable"),
        candles(start, [1.0] * 287 + [2.0]),
    )
    control = build_snapshot(
        HistoricalCoin("LOSE", "B", "PB", start, "matched_control"),
        candles(start, [1.0] * 287 + [0.5]),
    )

    result = compare_cohorts([winner, control])

    assert result["profitable"]["count"] == 1
    assert result["matched_control"]["count"] == 1
    assert result["profitable"]["mean_return_24h_pct"] > 0
    assert result["matched_control"]["mean_return_24h_pct"] < 0
