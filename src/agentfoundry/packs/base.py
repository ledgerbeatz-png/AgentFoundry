from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PackStatus(str, Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    DISABLED = "disabled"


@dataclass(frozen=True)
class PackManifest:
    """Metadata and safety boundaries for an AgentFoundry capability pack."""

    pack_id: str
    name: str
    description: str
    version: str = "0.1.0"
    category: str = "general"
    requires_hermes: bool = False
    requires_local_model: bool = True
    paper_only: bool = True
    capabilities: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.pack_id or any(ch.isspace() for ch in self.pack_id):
            raise ValueError("pack_id must be non-empty and contain no whitespace")
        if not self.name:
            raise ValueError("pack name must be non-empty")
        if not self.version:
            raise ValueError("pack version must be non-empty")
