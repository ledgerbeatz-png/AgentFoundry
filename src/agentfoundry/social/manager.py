from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, timedelta
from uuid import uuid4

from .adapters import ActionResult, ChannelAdapter, DiscoveryItem
from .models import (
    ApprovalMode,
    Campaign,
    Channel,
    DraftStatus,
    EngagementItem,
    ProjectBrand,
    SocialDraft,
)


CHANNEL_GUIDANCE = {
    Channel.X: "short, conversational, one clear point; invite genuine discussion",
    Channel.TIKTOK: "video concept with a first-second hook, scene beats and on-screen text",
    Channel.INSTAGRAM: "visual-first caption with a strong opening and concise story",
    Channel.FACEBOOK: "community-oriented context, accessible wording and a direct question",
    Channel.LINKEDIN: "professional insight, evidence and a practical takeaway",
    Channel.YOUTUBE: "searchable title concept, opening promise and structured story beats",
    Channel.TELEGRAM: "direct community update with useful detail and a clear next action",
}


class SocialMediaManager:
    """Project-aware planning with explicit boundaries around external account actions."""

    def __init__(self) -> None:
        self._projects: dict[str, ProjectBrand] = {}
        self._adapters: dict[Channel, ChannelAdapter] = {}
        self._public_actions_performed = 0

    @property
    def public_actions_performed(self) -> int:
        return self._public_actions_performed

    def connect_adapter(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.channel] = adapter

    def adapter_connected(self, channel: Channel) -> bool:
        return channel in self._adapters

    def discover(self, channel: Channel, query: str, *, limit: int = 10) -> tuple[DiscoveryItem, ...]:
        try:
            adapter = self._adapters[channel]
        except KeyError as exc:
            raise RuntimeError(f"no channel adapter connected for {channel.value}") from exc
        return adapter.discover(query, limit=limit)


    def add_project(self, project: ProjectBrand) -> None:
        project.validate()
        self._projects[project.project_id] = project

    def projects(self) -> tuple[ProjectBrand, ...]:
        return tuple(self._projects.values())

    def get_project(self, project_id: str) -> ProjectBrand:
        try:
            return self._projects[project_id]
        except KeyError as exc:
            raise KeyError(f"unknown social project: {project_id}") from exc

    def build_calendar(self, campaign: Campaign) -> tuple[dict[str, str], ...]:
        campaign.validate()
        project = self.get_project(campaign.project_id)
        start = date.fromisoformat(campaign.start_date)
        end = date.fromisoformat(campaign.end_date)
        if end < start:
            raise ValueError("campaign end_date must not be before start_date")
        entries: list[dict[str, str]] = []
        index = 0
        week_start = start
        while week_start <= end:
            days_left = (end - week_start).days + 1
            days_in_block = min(7, days_left)
            count = min(campaign.posts_per_week, days_in_block)
            offsets = (
                [0] if count == 1 else
                [round(i * (days_in_block - 1) / (count - 1)) for i in range(count)]
            )
            for offset in offsets:
                current = week_start + timedelta(days=offset)
                channel = project.channels[index % len(project.channels)]
                pillar = project.content_pillars[index % len(project.content_pillars)]
                entries.append({"date": current.isoformat(), "channel": channel.value, "pillar": pillar})
                index += 1
            week_start += timedelta(days=7)
        return tuple(entries)

    def create_draft(
        self,
        campaign: Campaign,
        channel: Channel,
        pillar: str,
        idea: str,
        scheduled_for: str = "",
    ) -> SocialDraft:
        campaign.validate()
        project = self.get_project(campaign.project_id)
        if channel not in project.channels:
            raise ValueError(f"{channel.value} is not enabled for {project.name}")
        if pillar not in project.content_pillars:
            raise ValueError(f"unknown content pillar for {project.name}: {pillar}")
        if not idea.strip():
            raise ValueError("a content idea is required")

        region = f" in {project.region}" if project.region else ""
        tone = ", ".join(project.tone)
        clean_idea = idea.strip().rstrip(".")
        hook = f"{clean_idea} — warum das für {project.audience}{region} zählt"
        if channel is Channel.TIKTOK:
            body = (
                f"HOOK (0–2s): {clean_idea}\n"
                f"SZENE 1: Das Problem kurz und ehrlich zeigen.\n"
                f"SZENE 2: {project.name} — {project.summary}\n"
                f"ON-SCREEN: {campaign.call_to_action}\n"
                f"TON: {tone}"
            )
        elif channel is Channel.X:
            body = f"{clean_idea}.\n\n{project.summary}\n\n{campaign.call_to_action}"
        elif channel is Channel.INSTAGRAM:
            body = f"{clean_idea} ✨\n\n{project.summary}\n\n{campaign.call_to_action}"
        elif channel is Channel.FACEBOOK:
            body = (
                f"{clean_idea}\n\n{project.summary}\n\n"
                f"Wie erlebt ihr das{region}?\n\n{campaign.call_to_action}"
            )
        else:
            body = f"{clean_idea}\n\n{project.summary}\n\n{campaign.call_to_action}"
        hashtags = tuple(
            f"#{word.replace('-', '').replace(' ', '')}"
            for word in (project.name, pillar, project.region)
            if word.strip()
        )
        return SocialDraft(
            draft_id=uuid4().hex,
            project_id=project.project_id,
            campaign_id=campaign.campaign_id,
            channel=channel,
            pillar=pillar,
            hook=hook,
            body=body,
            call_to_action=campaign.call_to_action,
            hashtags=hashtags,
            status=DraftStatus.DRAFT,
            scheduled_for=scheduled_for,
        )

    def approve(self, draft: SocialDraft, approved_by: str) -> SocialDraft:
        if draft.status is not DraftStatus.DRAFT:
            raise ValueError("only draft content can be approved")
        if not approved_by.strip():
            raise ValueError("an approver is required")
        return replace(draft, status=DraftStatus.APPROVED, approved_by=approved_by.strip())

    def prepare_publish(self, draft: SocialDraft) -> dict[str, object]:
        project = self.get_project(draft.project_id)
        if project.approval_mode is not ApprovalMode.AUTOPILOT and draft.status is not DraftStatus.APPROVED:
            raise ValueError("this project requires approval before publishing")
        if draft.status not in (DraftStatus.DRAFT, DraftStatus.APPROVED):
            raise ValueError("draft is not eligible for publishing")
        searchable = f"{draft.hook} {draft.body} {draft.call_to_action}".casefold()
        blocked = [claim for claim in project.forbidden_claims if claim.casefold() in searchable]
        if blocked:
            raise ValueError(f"draft contains forbidden claim: {blocked[0]}")
        payload = asdict(draft)
        payload["channel"] = draft.channel.value
        payload["status"] = DraftStatus.READY_TO_PUBLISH.value
        payload["approval_mode"] = project.approval_mode.value
        payload["external_action"] = "connector_required"
        return payload

    def execute_publish(self, draft: SocialDraft) -> ActionResult:
        """Publish only after the existing approval and claim checks succeed."""
        self.prepare_publish(draft)
        try:
            adapter = self._adapters[draft.channel]
        except KeyError as exc:
            raise RuntimeError(f"no channel adapter connected for {draft.channel.value}") from exc
        result = adapter.publish(draft)
        if result.success:
            self._public_actions_performed += 1
        return result

    def execute_reply(
        self,
        project_id: str,
        channel: Channel,
        external_id: str,
        text: str,
        *,
        approved: bool = False,
    ) -> ActionResult:
        """Execute a public reply with the same project approval boundary."""
        project = self.get_project(project_id)
        if project.approval_mode is not ApprovalMode.AUTOPILOT and not approved:
            raise ValueError("this project requires approval before replying")
        if not external_id.strip() or not text.strip():
            raise ValueError("external_id and reply text are required")
        blocked = [claim for claim in project.forbidden_claims if claim.casefold() in text.casefold()]
        if blocked:
            raise ValueError(f"reply contains forbidden claim: {blocked[0]}")
        try:
            adapter = self._adapters[channel]
        except KeyError as exc:
            raise RuntimeError(f"no channel adapter connected for {channel.value}") from exc
        result = adapter.reply(external_id, text)
        if result.success:
            self._public_actions_performed += 1
        return result

    def triage_engagement(self, item: EngagementItem) -> dict[str, str]:
        self.get_project(item.project_id)
        text = item.message.casefold()
        if item.risk != "normal" or any(word in text for word in ("anwalt", "betrug", "drohung", "suicide")):
            action = "escalate"
        elif any(word in text for word in ("preis", "kosten", "link", "wo finde")):
            action = "answer"
        elif any(word in text for word in ("danke", "cool", "liebe", "stark")):
            action = "acknowledge"
        else:
            action = "review"
        return {"action": action, "project_id": item.project_id, "channel": item.channel.value}
