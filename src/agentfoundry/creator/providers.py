from __future__ import annotations

from dataclasses import dataclass

from .models import ContentKind


@dataclass(frozen=True)
class Provider:
    provider_id: str
    name: str
    content_kinds: tuple[ContentKind, ...]
    configured: bool = False
    automation: str = "manual-export"

    def supports(self, kind: ContentKind) -> bool:
        return kind in self.content_kinds


class ProviderRegistry:
    def __init__(self, providers: tuple[Provider, ...] = ()) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}

    def get(self, provider_id: str) -> Provider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"Unknown creator provider: {provider_id}") from exc

    def compatible(self, kind: ContentKind) -> tuple[Provider, ...]:
        return tuple(provider for provider in self._providers.values() if provider.supports(kind))

    def all(self) -> tuple[Provider, ...]:
        return tuple(self._providers.values())


def builtin_providers() -> ProviderRegistry:
    return ProviderRegistry(
        (
            Provider("mock", "Preview / dry run", (ContentKind.IMAGE, ContentKind.VIDEO), True, "local"),
            Provider("google-flow", "Google Flow", (ContentKind.VIDEO,), False, "manual-export"),
            Provider("higgsfield", "Higgsfield", (ContentKind.IMAGE, ContentKind.VIDEO), False, "manual-export"),
        )
    )
