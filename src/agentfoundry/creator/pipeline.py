from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from .models import ContentBrief, CreatorProfile, PipelineStatus
from .providers import ProviderRegistry


@dataclass(frozen=True)
class ProviderJob:
    provider_id: str
    kind: str
    prompt: str
    negative_prompt: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class PipelineItem:
    item_id: str
    creator: CreatorProfile
    brief: ContentBrief
    status: PipelineStatus
    created_at: str
    approved_by: str = ""
    provider_job: ProviderJob | None = None
    output_uri: str = ""
    rejection_reason: str = ""


def compile_prompt(creator: CreatorProfile, brief: ContentBrief) -> str:
    traits = ", ".join(creator.effective_personality)
    rules = "; ".join(creator.effective_visual_rules) or "preserve identity and facial consistency"
    return (
        f"Fictional adult creator {creator.effective_name}, age {creator.age}. "
        f"Identity: {creator.effective_appearance}. Personality: {traits}. "
        f"Concept: {brief.concept}. Setting: {brief.setting}. Wardrobe: {brief.wardrobe}. "
        f"Mood: {brief.mood}. Camera: {brief.camera}. Continuity rules: {rules}. "
        "The subject is an original fictional adult and must not resemble a real person."
    )


class ContentPipeline:
    """Deterministic workflow; no renderer or publisher is called implicitly."""

    def __init__(self, providers: ProviderRegistry) -> None:
        self.providers = providers

    def create(self, creator: CreatorProfile, brief: ContentBrief) -> PipelineItem:
        creator.validate()
        brief.validate()
        return PipelineItem(
            item_id=uuid4().hex,
            creator=creator,
            brief=brief,
            status=PipelineStatus.DRAFT,
            created_at=datetime.now(UTC).isoformat(),
        )

    def approve(self, item: PipelineItem, approved_by: str) -> PipelineItem:
        if item.status is not PipelineStatus.DRAFT:
            raise ValueError("only draft items can be approved")
        if not approved_by.strip():
            raise ValueError("human approver is required")
        return replace(item, status=PipelineStatus.APPROVED, approved_by=approved_by.strip())

    def prepare(self, item: PipelineItem, provider_id: str) -> PipelineItem:
        if item.status is not PipelineStatus.APPROVED:
            raise ValueError("content requires human approval before provider preparation")
        provider = self.providers.get(provider_id)
        if not provider.supports(item.brief.kind):
            raise ValueError(f"{provider.name} does not support {item.brief.kind.value}")
        job = ProviderJob(
            provider_id=provider.provider_id,
            kind=item.brief.kind.value,
            prompt=compile_prompt(item.creator, item.brief),
            negative_prompt=", ".join(
                value for value in (
                    item.brief.negative_prompt,
                    "real person likeness, minor, ambiguous age",
                    ", ".join(item.creator.forbidden_traits),
                ) if value
            ),
            metadata={
                "creator_id": item.creator.creator_id,
                "title": item.brief.title,
                "platform": item.brief.platform,
                "disclosure": item.creator.effective_disclosure,
            },
        )
        return replace(item, status=PipelineStatus.RENDER_READY, provider_job=job)

    def mark_rendered(self, item: PipelineItem, output_uri: str) -> PipelineItem:
        if item.status is not PipelineStatus.RENDER_READY:
            raise ValueError("only render-ready items can receive an output")
        if not output_uri.strip():
            raise ValueError("output URI is required")
        return replace(item, status=PipelineStatus.RENDERED, output_uri=output_uri.strip())

    def reject(self, item: PipelineItem, reason: str) -> PipelineItem:
        if item.status in (PipelineStatus.RENDERED, PipelineStatus.REJECTED):
            raise ValueError("completed items cannot be rejected")
        if not reason.strip():
            raise ValueError("rejection reason is required")
        return replace(item, status=PipelineStatus.REJECTED, rejection_reason=reason.strip())
