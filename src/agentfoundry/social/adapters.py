from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .models import Channel, SocialDraft


@dataclass(frozen=True)
class DiscoveryItem:
    external_id: str
    author: str
    text: str
    url: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionResult:
    success: bool
    action: str
    channel: Channel
    external_id: str = ""
    url: str = ""
    error: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class ChannelAdapter(Protocol):
    channel: Channel

    def discover(self, query: str, *, limit: int = 10) -> tuple[DiscoveryItem, ...]:
        ...

    def publish(self, draft: SocialDraft) -> ActionResult:
        ...

    def reply(self, external_id: str, text: str) -> ActionResult:
        ...


class InMemoryChannelAdapter:
    """Safe execution adapter used for tests and local end-to-end demos."""

    def __init__(
        self,
        channel: Channel,
        discovery: tuple[DiscoveryItem, ...] = (),
    ) -> None:
        self.channel = channel
        self.discovery = discovery
        self.actions: list[ActionResult] = []

    def discover(self, query: str, *, limit: int = 10) -> tuple[DiscoveryItem, ...]:
        needle = query.casefold().strip()
        matches = (
            item for item in self.discovery
            if not needle or needle in item.text.casefold()
        )
        return tuple(list(matches)[:limit])

    def publish(self, draft: SocialDraft) -> ActionResult:
        external_id = f"memory-post-{len(self.actions) + 1}"
        result = ActionResult(
            success=True,
            action="publish",
            channel=self.channel,
            external_id=external_id,
            url=f"memory://{self.channel.value}/{external_id}",
        )
        self.actions.append(result)
        return result

    def reply(self, external_id: str, text: str) -> ActionResult:
        result_id = f"memory-reply-{len(self.actions) + 1}"
        result = ActionResult(
            success=True,
            action="reply",
            channel=self.channel,
            external_id=result_id,
            url=f"memory://{self.channel.value}/{result_id}",
            metadata={"reply_to": external_id, "text": text},
        )
        self.actions.append(result)
        return result
