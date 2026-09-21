from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


DEXSCREENER_BASE = "https://api.dexscreener.com"


@dataclass(frozen=True)
class MarketCandidate:
    token_address: str
    symbol: str
    name: str
    pair_address: str
    dex_id: str
    price_usd: float | None
    liquidity_usd: float
    market_cap_usd: float | None
    fdv_usd: float | None
    volume_24h_usd: float
    buys_5m: int
    sells_5m: int
    pair_created_at: int | None
    url: str


class DexScreenerSolanaFeed:
    """Read-only Solana discovery adapter.

    This adapter intentionally exposes market data only. Holder concentration,
    developer ownership, liquidity locks, mint authority and freeze authority
    must be enriched from independent on-chain/risk sources before the
    deterministic trading risk gate can pass a token.
    """

    def __init__(self, timeout: float = 12.0, opener=None) -> None:
        self.timeout = timeout
        self._opener = opener or urlopen

    def _get_json(self, url: str) -> Any:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "AgentFoundry/0.1 SolanaResearchPaper",
            },
        )
        with self._opener(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def latest_profile_addresses(self, limit: int = 20) -> list[str]:
        if limit < 1:
            return []
        payload = self._get_json(f"{DEXSCREENER_BASE}/token-profiles/latest/v1")
        if not isinstance(payload, list):
            return []
        addresses: list[str] = []
        seen: set[str] = set()
        for item in payload:
            if not isinstance(item, dict) or item.get("chainId") != "solana":
                continue
            address = str(item.get("tokenAddress") or "").strip()
            if not address or address in seen:
                continue
            seen.add(address)
            addresses.append(address)
            if len(addresses) >= limit:
                break
        return addresses

    def pairs_for_addresses(self, addresses: list[str]) -> list[dict[str, Any]]:
        clean = [address.strip() for address in addresses if address and address.strip()]
        if not clean:
            return []
        # DEX Screener accepts up to 30 comma-separated token addresses.
        clean = clean[:30]
        token_path = quote(",".join(clean), safe=",")
        payload = self._get_json(f"{DEXSCREENER_BASE}/tokens/v1/solana/{token_path}")
        return payload if isinstance(payload, list) else []

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def normalize_pair(cls, pair: dict[str, Any]) -> MarketCandidate | None:
        if pair.get("chainId") != "solana":
            return None
        base = pair.get("baseToken") or {}
        address = str(base.get("address") or "").strip()
        pair_address = str(pair.get("pairAddress") or "").strip()
        if not address or not pair_address:
            return None

        liquidity = pair.get("liquidity") or {}
        volume = pair.get("volume") or {}
        txns = pair.get("txns") or {}
        m5 = txns.get("m5") or {}

        return MarketCandidate(
            token_address=address,
            symbol=str(base.get("symbol") or "?"),
            name=str(base.get("name") or ""),
            pair_address=pair_address,
            dex_id=str(pair.get("dexId") or ""),
            price_usd=cls._number(pair.get("priceUsd")),
            liquidity_usd=cls._number(liquidity.get("usd")) or 0.0,
            market_cap_usd=cls._number(pair.get("marketCap")),
            fdv_usd=cls._number(pair.get("fdv")),
            volume_24h_usd=cls._number(volume.get("h24")) or 0.0,
            buys_5m=cls._integer(m5.get("buys")),
            sells_5m=cls._integer(m5.get("sells")),
            pair_created_at=cls._integer(pair.get("pairCreatedAt")) or None,
            url=str(pair.get("url") or ""),
        )

    def discover_latest(self, limit: int = 20) -> list[MarketCandidate]:
        addresses = self.latest_profile_addresses(limit=limit)
        pairs = self.pairs_for_addresses(addresses)
        normalized = [candidate for pair in pairs if (candidate := self.normalize_pair(pair))]

        # One representative pool per token: prefer the deepest available liquidity.
        best_by_token: dict[str, MarketCandidate] = {}
        for candidate in normalized:
            previous = best_by_token.get(candidate.token_address)
            if previous is None or candidate.liquidity_usd > previous.liquidity_usd:
                best_by_token[candidate.token_address] = candidate

        ordered = sorted(
            best_by_token.values(),
            key=lambda item: (item.liquidity_usd, item.volume_24h_usd),
            reverse=True,
        )
        return ordered[:limit]
