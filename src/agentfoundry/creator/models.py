from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .profile import CreatorProfile


class ContentKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class PipelineStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    RENDER_READY = "render_ready"
    RENDERED = "rendered"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ContentBrief:
    title: str
    kind: ContentKind
    concept: str
    setting: str
    wardrobe: str
    mood: str
    camera: str = "editorial portrait, natural perspective"
    platform: str = "draft"
    negative_prompt: str = ""

    def validate(self) -> None:
        required = (self.title, self.concept, self.setting, self.wardrobe, self.mood)
        if any(not value.strip() for value in required):
            raise ValueError("brief title, concept, setting, wardrobe and mood are required")
