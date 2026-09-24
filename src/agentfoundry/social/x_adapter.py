from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .adapters import ActionResult, DiscoveryItem
from .models import Channel, SocialDraft


@dataclass
class XChannelAdapter:
    """X adapter boundary.

    Authentication and HTTP transport are injected so AgentFoundry does not
    store credentials in source code. Public writes still pass through
    SocialMediaManager approval checks before reaching this adapter.
    """

    search_fn: Callable[[str, int], tuple[DiscoveryItem, ...]]
    publish_fn: Callable[[SocialDraft], ActionResult]
    reply_fn: Callable[[str, str], ActionResult]
    channel: Channel = Channel.X

    def discover(self, query: str, *, limit: int = 10) -> tuple[DiscoveryItem, ...]:
        return self.search_fn(query, limit)

    def publish(self, draft: SocialDraft) -> ActionResult:
        return self.publish_fn(draft)

    def reply(self, external_id: str, text: str) -> ActionResult:
        return self.reply_fn(external_id, text)
