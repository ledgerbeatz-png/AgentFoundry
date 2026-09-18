"""Wallet provider interfaces for AgentFoundry."""

from .base import WalletCapability, WalletProvider, WalletStatus
from .paper import PaperWalletProvider

__all__ = ["WalletCapability", "WalletProvider", "WalletStatus", "PaperWalletProvider"]
