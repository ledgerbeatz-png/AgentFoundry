from agentfoundry.trading.learning import candidate_can_advance, score_strategy
from agentfoundry.trading.memory import TradeMemory, TradeRecord


def test_trade_memory_and_learning_gate(tmp_path):
    memory = TradeMemory(tmp_path / "trades.db")
    for i in range(2):
        tid = f"t{i}"
        memory.open_trade(TradeRecord(tid, "CAT", "v1", i, 1.0, 100))
        memory.add_decision(tid, i + 1, "hold", ("momentum_intact",), {"price": 1.2})
        memory.close_trade(tid, i + 2, 1.5, 50.0, 80.0, -10.0)
        memory.add_outcome(tid, "1h", i + 3600, 1.7)
    score = score_strategy("v1", memory.closed_trades("v1"))
    assert score.trades == 2
    assert score.mean_pnl_pct == 50.0
    assert not candidate_can_advance(score, score, min_trades=100)
    memory.close()
