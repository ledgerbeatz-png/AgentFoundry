from __future__ import annotations

from .base import PackManifest


class PackRegistry:
    def __init__(self) -> None:
        self._packs: dict[str, PackManifest] = {}

    def register(self, manifest: PackManifest) -> None:
        manifest.validate()
        if manifest.pack_id in self._packs:
            raise ValueError(f"Pack already registered: {manifest.pack_id}")
        self._packs[manifest.pack_id] = manifest

    def get(self, pack_id: str) -> PackManifest:
        try:
            return self._packs[pack_id]
        except KeyError as exc:
            raise KeyError(f"Unknown pack: {pack_id}") from exc

    def all(self) -> tuple[PackManifest, ...]:
        return tuple(self._packs.values())


def builtin_registry() -> PackRegistry:
    registry = PackRegistry()
    registry.register(
        PackManifest(
            pack_id="trading.solana-research",
            name="Solana Research",
            description=(
                "Paper-first Solana market research with deterministic risk gates "
                "and optional local AI analysis."
            ),
            category="trading",
            requires_hermes=False,
            requires_local_model=True,
            paper_only=True,
            capabilities=(
                "market-discovery",
                "risk-gates",
                "parallel-ai-analysis",
                "paper-trading",
                "outcome-tracking",
            ),
        )
    )
    return registry
