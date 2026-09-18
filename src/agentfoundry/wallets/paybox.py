"""Read-only PayBox placeholder pending capability probe."""
from .base import WalletCapability, WalletStatus

class PayBoxWalletProvider:
    def __init__(self, address: str | None = None) -> None: self.address = address
    def status(self) -> WalletStatus:
        return WalletStatus(provider="paybox", connected=False, network="solana", address=self.address, capabilities=(WalletCapability.READ_BALANCE, WalletCapability.READ_POSITIONS))
    def balances(self) -> dict[str, float]:
        raise RuntimeError("PayBox is not connected; run the compatibility probe first.")
