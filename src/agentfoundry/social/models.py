from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Channel(str, Enum):
    X = "x"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    TELEGRAM = "telegram"


class ApprovalMode(str, Enum):
    MANUAL = "manual"
    APPROVAL_REQUIRED = "approval_required"
    AUTOPILOT = "autopilot"


class DraftStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ProjectBrand:
    project_id: str
    name: str
    summary: str
    audience: str
    objective: str
    tone: tuple[str, ...]
    channels: tuple[Channel, ...]
    content_pillars: tuple[str, ...]
    region: str = ""
    website: str = ""
    forbidden_claims: tuple[str, ...] = field(default_factory=tuple)
    approval_mode: ApprovalMode = ApprovalMode.APPROVAL_REQUIRED

    def validate(self) -> None:
        if not self.project_id.strip() or any(ch.isspace() for ch in self.project_id):
            raise ValueError("project_id is required and may not contain whitespace")
        required = (self.name, self.summary, self.audience, self.objective)
        if any(not value.strip() for value in required):
            raise ValueError("name, summary, audience and objective are required")
        if not self.tone:
            raise ValueError("at least one tone attribute is required")
        if not self.channels:
            raise ValueError("at least one social channel is required")
        if not self.content_pillars:
            raise ValueError("at least one content pillar is required")


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    project_id: str
    name: str
    goal: str
    call_to_action: str
    start_date: str
    end_date: str
    posts_per_week: int = 5

    def validate(self) -> None:
        if any(not value.strip() for value in (
            self.campaign_id, self.project_id, self.name, self.goal,
            self.call_to_action, self.start_date, self.end_date,
        )):
            raise ValueError("all campaign fields are required")
        if not 1 <= self.posts_per_week <= 70:
            raise ValueError("posts_per_week must be between 1 and 70")


@dataclass(frozen=True)
class SocialDraft:
    draft_id: str
    project_id: str
    campaign_id: str
    channel: Channel
    pillar: str
    hook: str
    body: str
    call_to_action: str
    hashtags: tuple[str, ...]
    status: DraftStatus
    scheduled_for: str = ""
    approved_by: str = ""
    rejection_reason: str = ""
    external_id: str = ""


@dataclass(frozen=True)
class EngagementItem:
    project_id: str
    channel: Channel
    author: str
    message: str
    risk: str = "normal"

