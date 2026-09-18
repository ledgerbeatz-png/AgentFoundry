from agentfoundry.wallets.paper import PaperWalletProvider
from agentfoundry.wallets.paybox import PayBoxWalletProvider
from agentfoundry.wallets.probe import probe_provider

def test_probe_is_non_invasive_for_paper():
    r=probe_provider(PaperWalletProvider({'SOL':1.0}))
    assert r.connected and r.can_read and not r.can_swap and not r.can_sign and not r.can_transfer

def test_paybox_probe_reports_safe_state():
    r=probe_provider(PayBoxWalletProvider())
    assert r.provider=='paybox' and r.network=='solana' and not r.connected
    assert r.can_read and not r.can_swap and not r.can_sign and not r.can_transfer
