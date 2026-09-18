"""Non-invasive wallet compatibility probing; never signs or trades."""
from dataclasses import dataclass
from .base import WalletCapability, WalletProvider

@dataclass(frozen=True)
class CompatibilityReport:
    provider: str
    connected: bool
    network: str
    address_present: bool
    capabilities: tuple[str, ...]
    can_read: bool
    can_swap: bool
    can_sign: bool
    can_transfer: bool

def probe_provider(provider: WalletProvider) -> CompatibilityReport:
    s=provider.status(); caps=set(s.capabilities)
    return CompatibilityReport(s.provider,s.connected,s.network,bool(s.address),tuple(sorted(c.value for c in caps)),WalletCapability.READ_BALANCE in caps,WalletCapability.SWAP in caps,WalletCapability.SIGN in caps,WalletCapability.TRANSFER in caps)
