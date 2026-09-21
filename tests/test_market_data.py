import json

from agentfoundry.trading.market_data import DexScreenerSolanaFeed


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_latest_profile_addresses_filters_solana_and_deduplicates():
    payload = [
        {"chainId": "ethereum", "tokenAddress": "eth"},
        {"chainId": "solana", "tokenAddress": "A"},
        {"chainId": "solana", "tokenAddress": "A"},
        {"chainId": "solana", "tokenAddress": "B"},
    ]

    feed = DexScreenerSolanaFeed(opener=lambda *_args, **_kwargs: FakeResponse(payload))

    assert feed.latest_profile_addresses(limit=10) == ["A", "B"]


def test_normalize_pair_extracts_market_metrics():
    pair = {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": "PAIR",
        "baseToken": {"address": "TOKEN", "symbol": "CAT", "name": "Labor Cat"},
        "priceUsd": "0.0125",
        "liquidity": {"usd": 25000},
        "marketCap": 125000,
        "fdv": 130000,
        "volume": {"h24": 80000},
        "txns": {"m5": {"buys": 15, "sells": 4}},
        "pairCreatedAt": 123456789,
        "url": "https://dexscreener.com/solana/PAIR",
    }

    candidate = DexScreenerSolanaFeed.normalize_pair(pair)

    assert candidate is not None
    assert candidate.symbol == "CAT"
    assert candidate.liquidity_usd == 25000
    assert candidate.market_cap_usd == 125000
    assert candidate.buys_5m == 15
    assert candidate.sells_5m == 4


def test_discovery_keeps_deepest_pool_per_token():
    feed = DexScreenerSolanaFeed()
    feed.latest_profile_addresses = lambda limit=20: ["TOKEN"]
    feed.pairs_for_addresses = lambda addresses: [
        {
            "chainId": "solana",
            "dexId": "a",
            "pairAddress": "LOW",
            "baseToken": {"address": "TOKEN", "symbol": "T", "name": "Token"},
            "liquidity": {"usd": 5000},
            "volume": {"h24": 1000},
        },
        {
            "chainId": "solana",
            "dexId": "b",
            "pairAddress": "HIGH",
            "baseToken": {"address": "TOKEN", "symbol": "T", "name": "Token"},
            "liquidity": {"usd": 25000},
            "volume": {"h24": 2000},
        },
    ]

    result = feed.discover_latest()

    assert len(result) == 1
    assert result[0].pair_address == "HIGH"
