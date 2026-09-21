from agentfoundry.trading.analysis import PaperAnalysis
from agentfoundry.trading.market_data import MarketCandidate
from agentfoundry.trading.memory import TradeMemory
from agentfoundry.trading.paper_engine import PaperResearchEngine
from agentfoundry.trading.position import ExitPolicy
from agentfoundry.trading.risk import RiskDecision
from agentfoundry.trading.risk_enrichment import CandidateRiskAssessment, RiskEvidence


def assessment(price=0.01):
    candidate = MarketCandidate(
        token_address="A" * 32,
        symbol="CAT",
        name="Labor Cat",
        pair_address="PAIR",
        dex_id="raydium",
        price_usd=price,
        liquidity_usd=50000,
        market_cap_usd=150000,
        fdv_usd=150000,
        volume_24h_usd=90000,
        buys_5m=25,
        sells_5m=8,
        pair_created_at=1,
        url="",
    )
    evidence = RiskEvidence(
        top10_holder_pct=30,
        developer_holding_pct=2,
        liquidity_locked=True,
        mint_authority_enabled=False,
        freeze_authority_enabled=False,
        rugged=False,
        score=100,
        missing=(),
        warnings=(),
    )
    return CandidateRiskAssessment(candidate, "PASS", RiskDecision(True, ()), evidence)


def paper_buy():
    return PaperAnalysis(
        action="PAPER_BUY",
        confidence=0.75,
        thesis="Momentum is favorable.",
        risks=("small cap",),
        reasons=("buy pressure",),
        raw={},
    )


class FakeFeed:
    def __init__(self, price, buys=20, sells=10, volume=90000):
        self.price = price
        self.buys = buys
        self.sells = sells
        self.volume = volume

    def pairs_for_addresses(self, addresses):
        return [{
            "chainId": "solana",
            "dexId": "raydium",
            "pairAddress": "PAIR",
            "baseToken": {
                "address": addresses[0],
                "symbol": "CAT",
                "name": "Labor Cat",
            },
            "priceUsd": str(self.price),
            "liquidity": {"usd": 50000},
            "volume": {"h24": self.volume},
            "txns": {"m5": {"buys": self.buys, "sells": self.sells}},
        }]

    @staticmethod
    def normalize_pair(pair):
        return MarketCandidate(
            token_address=pair["baseToken"]["address"],
            symbol="CAT",
            name="Labor Cat",
            pair_address="PAIR",
            dex_id="raydium",
            price_usd=float(pair["priceUsd"]),
            liquidity_usd=50000,
            market_cap_usd=150000,
            fdv_usd=150000,
            volume_24h_usd=float(pair["volume"]["h24"]),
            buys_5m=int(pair["txns"]["m5"]["buys"]),
            sells_5m=int(pair["txns"]["m5"]["sells"]),
            pair_created_at=1,
            url="",
        )


def test_paper_buy_opens_one_simulated_position(tmp_path):
    memory = TradeMemory(tmp_path / "paper.sqlite3")
    engine = PaperResearchEngine(memory, clock=lambda: 1_700_000_000)

    first = engine.open_from_analysis(assessment(), paper_buy())
    second = engine.open_from_analysis(assessment(), paper_buy())

    assert first == second
    assert len(memory.open_trades_with_market()) == 1
    memory.close()


def test_due_outcomes_are_recorded_and_24h_closes_position(tmp_path):
    memory = TradeMemory(tmp_path / "paper.sqlite3")
    opened_at = 1_700_000_000
    engine = PaperResearchEngine(memory, feed=FakeFeed(0.012), clock=lambda: opened_at)
    trade_id = engine.open_from_analysis(assessment(price=0.01), paper_buy())

    updates = engine.refresh_due(now=opened_at + 24 * 60 * 60)

    horizons = set(memory.outcome_horizons(trade_id))
    assert horizons == {"5m", "15m", "1h", "6h", "24h"}
    assert any(item.get("status") == "closed_24h" for item in updates)
    closed = memory.closed_trades()
    assert len(closed) == 1
    assert round(closed[0]["realized_pnl_pct"], 2) == 20.00
    memory.close()


def test_ignore_does_not_open_position(tmp_path):
    memory = TradeMemory(tmp_path / "paper.sqlite3")
    engine = PaperResearchEngine(memory)
    ignore = PaperAnalysis("IGNORE", 0.5, "Weak setup.", (), (), {})

    assert engine.open_from_analysis(assessment(), ignore) is None
    assert memory.open_trades_with_market() == []
    memory.close()


def test_stop_loss_closes_before_24h(tmp_path):
    memory = TradeMemory(tmp_path / "paper.sqlite3")
    opened_at = 1_700_000_000
    feed = FakeFeed(0.0074)
    engine = PaperResearchEngine(memory, feed=feed, clock=lambda: opened_at)
    trade_id = engine.open_from_analysis(assessment(price=0.01), paper_buy())

    updates = engine.refresh_due(now=opened_at + 60)

    assert memory.open_trade_for_candidate("A" * 32) is None
    assert memory.closed_trades()[0]["trade_id"] == trade_id
    assert round(memory.closed_trades()[0]["realized_pnl_pct"], 1) == -26.0
    assert updates[-1]["exit_reasons"] == ["stop_loss"]
    memory.close()


def test_trailing_stop_survives_multiple_refreshes(tmp_path):
    memory = TradeMemory(tmp_path / "paper.sqlite3")
    opened_at = 1_700_000_000
    feed = FakeFeed(0.02, volume=100000)
    engine = PaperResearchEngine(memory, feed=feed, clock=lambda: opened_at)
    trade_id = engine.open_from_analysis(assessment(price=0.01), paper_buy())

    engine.refresh_due(now=opened_at + 60)  # establish a +100% peak
    feed.price = 0.0155  # 22.5% below peak, still +55% from entry
    updates = engine.refresh_due(now=opened_at + 120)

    assert memory.closed_trades()[0]["trade_id"] == trade_id
    assert updates[-1]["exit_reasons"] == ["trailing_stop"]
    memory.close()


def test_trailing_stop_rebuilds_peak_from_existing_outcomes(tmp_path):
    memory = TradeMemory(tmp_path / "paper.sqlite3")
    opened_at = 1_700_000_000
    feed = FakeFeed(0.0155)
    engine = PaperResearchEngine(memory, feed=feed, clock=lambda: opened_at)
    trade_id = engine.open_from_analysis(assessment(price=0.01), paper_buy())
    memory.add_outcome(trade_id, "5m", opened_at + 5 * 60, 0.02)

    updates = engine.refresh_due(now=opened_at + 10 * 60)

    assert memory.closed_trades()[0]["trade_id"] == trade_id
    assert updates[-1]["exit_reasons"] == ["trailing_stop"]
    memory.close()


def test_partial_profit_is_taken_only_once(tmp_path):
    memory = TradeMemory(tmp_path / "paper.sqlite3")
    opened_at = 1_700_000_000
    feed = FakeFeed(0.016, buys=30, sells=10, volume=100000)
    engine = PaperResearchEngine(memory, feed=feed, clock=lambda: opened_at)
    trade_id = engine.open_from_analysis(assessment(price=0.01), paper_buy())

    first = engine.refresh_due(now=opened_at + 60)
    remaining = memory.db.execute(
        "SELECT quantity FROM trades WHERE trade_id=?", (trade_id,)
    ).fetchone()["quantity"]
    second = engine.refresh_due(now=opened_at + 120)

    assert first[-1]["status"] == "partial_profit"
    assert round(remaining, 8) == 6500.0
    assert not any(item.get("status") == "partial_profit" for item in second)
    memory.close()


def test_stagnation_exit_uses_configured_age(tmp_path):
    memory = TradeMemory(tmp_path / "paper.sqlite3")
    opened_at = 1_700_000_000
    feed = FakeFeed(0.0101, buys=5, sells=10)
    engine = PaperResearchEngine(
        memory,
        feed=feed,
        clock=lambda: opened_at,
        exit_policy=ExitPolicy(stagnation_minutes=45),
    )
    engine.open_from_analysis(assessment(price=0.01), paper_buy())

    updates = engine.refresh_due(now=opened_at + 46 * 60)

    assert updates[-1]["exit_reasons"] == ["stagnation", "momentum_weak"]
    memory.close()
