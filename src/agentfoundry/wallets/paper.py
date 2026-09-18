"""Safe default wallet provider: no chain access and no signing."""
from dataclasses import dataclass, field
from .base import WalletCapability, WalletStatus

@dataclass
class PaperWalletProvider:
    starting_balances: dict[str, float] = field(default_factory=lambda: {"SOL": 0.0})
    def status(self) -> WalletStatus:
        return WalletStatus(provider="paper", connected=True, network="simulation", capabilities=(WalletCapability.READ_BALANCE, WalletCapability.READ_POSITIONS))
    def balances(self) -> dict[str, float]: return dict(self.starting_balances)
