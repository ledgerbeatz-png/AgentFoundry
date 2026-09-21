from __future__ import annotations

import json
import secrets
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass


DEFAULT_MCP_URL = "https://api.paybox.sh/mcp?app=world"
DEFAULT_RESOURCE_METADATA = "https://api.paybox.sh/.well-known/oauth-protected-resource?app=world"


@dataclass(frozen=True)
class OAuthDiscovery:
    resource: str
    authorization_servers: tuple[str, ...]


def discover_oauth(resource_metadata_url: str = DEFAULT_RESOURCE_METADATA) -> OAuthDiscovery:
    """Discover PayBox OAuth metadata instead of hard-coding authorization endpoints."""
    with urllib.request.urlopen(resource_metadata_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    resource = str(payload.get("resource", ""))
    servers = tuple(str(v) for v in payload.get("authorization_servers", []) if v)
    if not servers:
        raise RuntimeError("PayBox did not advertise an OAuth authorization server.")
    return OAuthDiscovery(resource=resource, authorization_servers=servers)


def open_authorization_server(discovery: OAuthDiscovery) -> None:
    """Open the advertised OAuth server. Full PKCE callback handling is implemented next."""
    webbrowser.open(discovery.authorization_servers[0])


def new_pkce_verifier() -> str:
    # Kept separate so the future callback/token exchange can use a verifier that never leaves memory.
    return secrets.token_urlsafe(64)
