"""Provider-neutral wallet contracts.

Wallet providers are intentionally separated from trading intelligence. Agents never
receive private keys; execution must pass through the deterministic execution guard.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class WalletCapability(str, Enum):
    READ_BALANCE = "read_balance"
    READ_POSITIONS = "read_positions"
    SWAP = "swap"
    SIGN = "sign"
    TRANSFER = "transfer"


@dataclass(frozen=True)
class WalletStatus:
    provider: str
    connected: bool
    network: str
    address: str | None = None
    capabilities: tuple[WalletCapability, ...] = ()


class WalletProvider(Protocol):
    """Minimal contract implemented by Paper, PayBox and future OWS providers."""

    def status(self) -> WalletStatus: ...
    def balances(self) -> dict[str, float]: ...
