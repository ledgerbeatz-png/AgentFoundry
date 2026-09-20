from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import math
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GECKOTERMINAL_BASE = "https://api.geckoterminal.com/api/v2"


@dataclass(frozen=True)
class HistoricalCoin:
    symbol: str
    token_address: str
    pool_address: str
    launched_at: int
    cohort: str = "unlabeled"


@dataclass(frozen=True)
class HistoricalSnapshot:
    symbol: str
    token_address: str
    pool_address: str
    launched_at: int
    entry_price: float
    return_15m_pct: float | None
    return_1h_pct: float | None
    return_6h_pct: float | None
    return_24h_pct: float | None
    max_return_24h_pct: float | None
    max_drawdown_24h_pct: float | None
    volume_15m_usd: float
    volume_1h_usd: float
    volume_6h_usd: float
    volume_24h_usd: float
    candles: int
    cohort: str


class GeckoTerminalHistoricalClient:
    """Read-only OHLCV adapter for historical Solana cohort research.

    Public GeckoTerminal currently exposes on-chain OHLCV. The free API has a
    rate limit and older history may require a CoinGecko paid plan, so callers
    should cache results and treat provider coverage as part of the evidence.
    """

    def __init__(self, timeout: float = 15.0, opener=None) -> None:
        self.timeout = timeout
        self._opener = opener or urlopen

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "AgentFoundry/0.1 HistoricalLab",
            },
        )
        with self._opener(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        if not isinstance(body, dict):
            raise TypeError("Unexpected GeckoTerminal response.")
        return body

    def ohlcv_5m_24h(self, pool_address: str, launched_at: int) -> list[list[float]]:
        # 24h at five-minute resolution needs 288 candles. Querying just after
        # the target window keeps the response centered on launch rather than now.
        params = urlencode({
            "aggregate": 5,
            "before_timestamp": int(launched_at) + 24 * 60 * 60 + 300,
            "limit": 300,
            "currency": "usd",
            "token": "base",
            "include_empty_intervals": "false",
        })
        url = (
            f"{GECKOTERMINAL_BASE}/networks/solana/pools/"
            f"{pool_address}/ohlcv/minute?{params}"
        )
        payload = self._get_json(url)
        attributes = ((payload.get("data") or {}).get("attributes") or {})
        rows = attributes.get("ohlcv_list")
        if not isinstance(rows, list):
            return []
        clean: list[list[float]] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            try:
                clean.append([
                    float(row[0]), float(row[1]), float(row[2]),
                    float(row[3]), float(row[4]), float(row[5]),
                ])
            except (TypeError, ValueError):
                continue
        clean.sort(key=lambda item: item[0])
        start = int(launched_at)
        end = start + 24 * 60 * 60 + 300
        return [row for row in clean if start <= row[0] <= end]


def _return(entry: float, price: float | None) -> float | None:
    if not entry or price is None:
        return None
    return (price / entry - 1.0) * 100.0


def _close_at_or_after(candles: list[list[float]], timestamp: int) -> float | None:
    for candle in candles:
        if candle[0] >= timestamp:
            return float(candle[4])
    return float(candles[-1][4]) if candles else None


def _volume_until(candles: list[list[float]], timestamp: int) -> float:
    return sum(float(candle[5]) for candle in candles if candle[0] < timestamp)


def build_snapshot(coin: HistoricalCoin, candles: list[list[float]]) -> HistoricalSnapshot:
    if not candles:
        raise ValueError(f"No historical candles available for {coin.symbol}.")
    entry = float(candles[0][1])
    if not math.isfinite(entry) or entry <= 0:
        raise ValueError(f"Invalid historical entry price for {coin.symbol}.")

    t0 = coin.launched_at
    window = [c for c in candles if t0 <= c[0] <= t0 + 24 * 60 * 60 + 300]
    if not window:
        raise ValueError(f"No candles inside launch window for {coin.symbol}.")

    highs = [float(c[2]) for c in window if float(c[2]) > 0]
    lows = [float(c[3]) for c in window if float(c[3]) > 0]

    return HistoricalSnapshot(
        symbol=coin.symbol,
        token_address=coin.token_address,
        pool_address=coin.pool_address,
        launched_at=coin.launched_at,
        entry_price=entry,
        return_15m_pct=_return(entry, _close_at_or_after(window, t0 + 15 * 60)),
        return_1h_pct=_return(entry, _close_at_or_after(window, t0 + 60 * 60)),
        return_6h_pct=_return(entry, _close_at_or_after(window, t0 + 6 * 60 * 60)),
        return_24h_pct=_return(entry, _close_at_or_after(window, t0 + 24 * 60 * 60)),
        max_return_24h_pct=_return(entry, max(highs) if highs else None),
        max_drawdown_24h_pct=_return(entry, min(lows) if lows else None),
        volume_15m_usd=_volume_until(window, t0 + 15 * 60),
        volume_1h_usd=_volume_until(window, t0 + 60 * 60),
        volume_6h_usd=_volume_until(window, t0 + 6 * 60 * 60),
        volume_24h_usd=_volume_until(window, t0 + 24 * 60 * 60),
        candles=len(window),
        cohort=coin.cohort,
    )


def compare_cohorts(snapshots: list[HistoricalSnapshot]) -> dict[str, dict[str, float]]:
    """Aggregate cohorts without declaring a strategy winner.

    This is descriptive research only. It deliberately keeps cohort labels
    external so winners can be compared with matched losers/control launches.
    """
    grouped: dict[str, list[HistoricalSnapshot]] = {}
    for snapshot in snapshots:
        grouped.setdefault(snapshot.cohort, []).append(snapshot)

    result: dict[str, dict[str, float]] = {}
    fields = (
        "return_15m_pct",
        "return_1h_pct",
        "return_6h_pct",
        "return_24h_pct",
        "max_return_24h_pct",
        "max_drawdown_24h_pct",
        "volume_15m_usd",
        "volume_1h_usd",
    )
    for cohort, rows in grouped.items():
        metrics: dict[str, float] = {"count": float(len(rows))}
        for field in fields:
            values = [
                float(getattr(row, field))
                for row in rows
                if getattr(row, field) is not None
            ]
            if values:
                metrics[f"mean_{field}"] = sum(values) / len(values)
                ordered = sorted(values)
                middle = len(ordered) // 2
                metrics[f"median_{field}"] = (
                    ordered[middle]
                    if len(ordered) % 2
                    else (ordered[middle - 1] + ordered[middle]) / 2.0
                )
        result[cohort] = metrics
    return result


def snapshot_dict(snapshot: HistoricalSnapshot) -> dict[str, Any]:
    return asdict(snapshot)
