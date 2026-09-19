"""Read-only PayBox MCP compatibility client.

Uses MCP JSON-RPC over HTTP. This module intentionally permits only discovery and
read-only tool calls. Signing, swaps, transfers and payments are blocked here.
Authentication headers are supplied by the host after OAuth/connector setup.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from urllib.request import Request, urlopen

DEFAULT_ENDPOINT = "https://api.paybox.sh/mcp"
READ_ONLY_TOOLS = frozenset({"list_credentials", "get_portfolio"})
BLOCKED_MONEY_TOOLS = frozenset({
    "request_swap", "request_transfer", "request_payment", "request_wallet_sign",
    "pay_x402", "use_service", "use_plugin",
})

@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str = ""

class PayBoxMCPClient:
    def __init__(self, endpoint: str = DEFAULT_ENDPOINT, authorization: str | None = None):
        self.endpoint = endpoint
        self.authorization = authorization
        self._id = 0

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        body = json.dumps({"jsonrpc":"2.0","id":self._id,"method":method,"params":params or {}}).encode()
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream"}
        if self.authorization:
            headers["Authorization"] = self.authorization
        req=Request(self.endpoint,data=body,headers=headers,method="POST")
        with urlopen(req,timeout=15) as response:
            raw=response.read().decode("utf-8")
        # Probe client expects a JSON response; full SSE session handling belongs in connector layer.
        return json.loads(raw)

    def list_tools(self) -> tuple[MCPTool, ...]:
        payload=self._rpc("tools/list")
        tools=payload.get("result",{}).get("tools",[])
        return tuple(MCPTool(t.get("name",""),t.get("description","")) for t in tools)

    def call_read_only(self, tool: str, arguments: dict | None = None) -> dict:
        if tool not in READ_ONLY_TOOLS:
            raise PermissionError(f"Tool {tool!r} is not allowed by the read-only PayBox probe")
        return self._rpc("tools/call", {"name":tool,"arguments":arguments or {}})

    def capability_names(self) -> tuple[str, ...]:
        return tuple(sorted(t.name for t in self.list_tools()))
