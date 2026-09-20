from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CreatorProfile:
    """Provider-neutral identity and continuity sheet for a virtual creator."""

    creator_id: str
    display_name: str = ""
    persona: str = ""
    voice_style: str = ""
    visual_identity: str = ""
    rules: tuple[str, ...] = field(default_factory=tuple)
    ai_disclosure: str = "Virtual AI creator"
    stage_name: str = ""
    age: int = 18
    fictional: bool = True
    disclosure: str = ""
    appearance: str = ""
    personality: tuple[str, ...] = field(default_factory=tuple)
    voice: str = ""
    visual_rules: tuple[str, ...] = field(default_factory=tuple)
    forbidden_traits: tuple[str, ...] = field(default_factory=tuple)

    @property
    def effective_name(self) -> str:
        return self.stage_name.strip() or self.display_name.strip()

    @property
    def effective_disclosure(self) -> str:
        return self.disclosure.strip() or self.ai_disclosure.strip()

    @property
    def effective_appearance(self) -> str:
        return self.appearance.strip() or self.visual_identity.strip()

    @property
    def effective_personality(self) -> tuple[str, ...]:
        return self.personality or ((self.persona.strip(),) if self.persona.strip() else ())

    @property
    def effective_visual_rules(self) -> tuple[str, ...]:
        return self.visual_rules or self.rules

    def validate(self) -> None:
        if not self.creator_id or any(ch.isspace() for ch in self.creator_id):
            raise ValueError("creator_id must be non-empty and contain no whitespace")
        if not self.effective_name:
            raise ValueError("display_name or stage_name must be non-empty")
        if self.age < 18:
            raise ValueError("virtual creators must be explicitly 18 or older")
        if not self.fictional:
            raise ValueError("this studio only supports disclosed fictional identities")
        if not self.effective_disclosure:
            raise ValueError("a visible AI/fictional-character disclosure is required")
        if not self.effective_personality:
            raise ValueError("persona or personality must be non-empty")
