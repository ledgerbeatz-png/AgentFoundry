import pytest
from agentfoundry.wallets.paybox_mcp import PayBoxMCPClient, READ_ONLY_TOOLS

def test_probe_allowlist_is_read_only():
    assert READ_ONLY_TOOLS == {"list_credentials", "get_portfolio"}

@pytest.mark.parametrize("tool", ["request_swap","request_transfer","request_payment","request_wallet_sign","pay_x402"])
def test_money_tools_are_blocked(tool):
    with pytest.raises(PermissionError):
        PayBoxMCPClient("http://127.0.0.1:9").call_read_only(tool)
