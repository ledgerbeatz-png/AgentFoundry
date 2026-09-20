from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CreatorProfile:
    """Provider-neutral identity and behavior configuration for a virtual creator."""

    creator_id: str
    display_name: str
    persona: str
    voice_style: str = ""
    visual_identity: str = ""
    rules: tuple[str, ...] = field(default_factory=tuple)
    ai_disclosure: str = "Virtual AI creator"

    def validate(self) -> None:
        if not self.creator_id or any(ch.isspace() for ch in self.creator_id):
            raise ValueError("creator_id must be non-empty and contain no whitespace")
        if not self.display_name.strip():
            raise ValueError("display_name must be non-empty")
        if not self.persona.strip():
            raise ValueError("persona must be non-empty")
        if not self.ai_disclosure.strip():
            raise ValueError("ai_disclosure must be non-empty")
