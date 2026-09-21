"""Project-aware social media management for AgentFoundry."""

from .adapters import ActionResult, ChannelAdapter, DiscoveryItem, InMemoryChannelAdapter
from .manager import CHANNEL_GUIDANCE, SocialMediaManager
from .models import (
    ApprovalMode,
    Campaign,
    Channel,
    DraftStatus,
    EngagementItem,
    ProjectBrand,
    SocialDraft,
)
from .presets import NEARU_IDEAS, nearu_founding_1000_campaign, nearu_project

__all__ = [
    "ActionResult",
    "ChannelAdapter",
    "DiscoveryItem",
    "InMemoryChannelAdapter",
    "ApprovalMode",
    "Campaign",
    "CHANNEL_GUIDANCE",
    "Channel",
    "DraftStatus",
    "EngagementItem",
    "ProjectBrand",
    "SocialDraft",
    "SocialMediaManager",
    "NEARU_IDEAS",
    "nearu_founding_1000_campaign",
    "nearu_project",
]
