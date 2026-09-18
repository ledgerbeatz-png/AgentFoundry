from agentfoundry.wallets.base import WalletCapability
from agentfoundry.wallets.paper import PaperWalletProvider
from agentfoundry.wallets.paybox import PayBoxWalletProvider

def test_paper_provider_is_safe_default():
    w=PaperWalletProvider({"SOL":2.5}); s=w.status()
    assert s.connected and s.network=="simulation"
    assert WalletCapability.SIGN not in s.capabilities and WalletCapability.TRANSFER not in s.capabilities
    assert w.balances()["SOL"]==2.5

def test_paybox_starts_disconnected_and_read_only():
    s=PayBoxWalletProvider().status()
    assert not s.connected and s.network=="solana"
    assert WalletCapability.SWAP not in s.capabilities and WalletCapability.SIGN not in s.capabilities and WalletCapability.TRANSFER not in s.capabilities
