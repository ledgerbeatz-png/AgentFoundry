import pytest

from agentfoundry.social import (
    ApprovalMode,
    Campaign,
    Channel,
    DraftStatus,
    EngagementItem,
    DiscoveryItem,
    InMemoryChannelAdapter,
    ProjectBrand,
    SocialMediaManager,
    nearu_founding_1000_campaign,
    nearu_project,
)


def nearu(mode: ApprovalMode = ApprovalMode.APPROVAL_REQUIRED) -> ProjectBrand:
    return ProjectBrand(
        project_id="nearu",
        name="NearU",
        summary="Local-first dating that launches with a real regional community.",
        audience="active singles",
        objective="recruit the Founding 1000",
        tone=("trustworthy", "direct", "local"),
        channels=(Channel.X, Channel.TIKTOK),
        content_pillars=("local dating", "trust", "Founding 1000"),
        region="Frankfurt Rhein-Main",
        forbidden_claims=("guaranteed match",),
        approval_mode=mode,
    )


def campaign() -> Campaign:
    return Campaign(
        campaign_id="founding-1000",
        project_id="nearu",
        name="Founding 1000",
        goal="recruit 1,000 active regional singles",
        call_to_action="Join the Founding 1000",
        start_date="2026-09-21",
        end_date="2026-09-28",
        posts_per_week=5,
    )


def test_project_specific_draft_and_calendar() -> None:
    manager = SocialMediaManager()
    manager.add_project(nearu())
    calendar = manager.build_calendar(campaign())
    draft = manager.create_draft(
        campaign(), Channel.TIKTOK, "Founding 1000", "Warum lokale Dichte Dating verbessert"
    )
    assert calendar
    assert {entry["channel"] for entry in calendar} <= {"x", "tiktok"}
    assert draft.status is DraftStatus.DRAFT
    assert "NearU" in draft.body
    assert "Frankfurt Rhein-Main" in draft.hook


def test_approval_is_required_before_publish_payload() -> None:
    manager = SocialMediaManager()
    manager.add_project(nearu())
    draft = manager.create_draft(campaign(), Channel.X, "trust", "Echte Profile statt leere Versprechen")
    with pytest.raises(ValueError, match="requires approval"):
        manager.prepare_publish(draft)
    approved = manager.approve(draft, "Dennis")
    payload = manager.prepare_publish(approved)
    assert payload["status"] == "ready_to_publish"
    assert payload["external_action"] == "connector_required"


def test_forbidden_claims_are_blocked() -> None:
    manager = SocialMediaManager()
    manager.add_project(nearu())
    draft = manager.create_draft(campaign(), Channel.X, "trust", "Guaranteed match für alle")
    draft = manager.approve(draft, "Dennis")
    with pytest.raises(ValueError, match="forbidden claim"):
        manager.prepare_publish(draft)


def test_high_risk_engagement_is_escalated() -> None:
    manager = SocialMediaManager()
    manager.add_project(nearu())
    result = manager.triage_engagement(
        EngagementItem("nearu", Channel.X, "user", "Mein Anwalt meldet sich")
    )
    assert result["action"] == "escalate"


def test_nearu_preset_builds_exact_five_post_week() -> None:
    manager = SocialMediaManager()
    manager.add_project(nearu_project())
    calendar = manager.build_calendar(nearu_founding_1000_campaign())
    assert len(calendar) == 5
    assert len({entry["date"] for entry in calendar}) == 5


def test_nearu_tiktok_draft_is_publishable_copy_not_internal_guidance() -> None:
    manager = SocialMediaManager()
    project = nearu_project()
    plan = nearu_founding_1000_campaign()
    manager.add_project(project)
    draft = manager.create_draft(
        plan, Channel.TIKTOK, project.content_pillars[0], "1.000 Singles. Eine Region."
    )
    assert "HOOK (0–2s)" in draft.body
    assert "Kanalvorgabe" not in draft.body
    assert "NearU60311" in draft.body


def test_mercury_end_to_end_discover_approve_publish_and_reply() -> None:
    manager = SocialMediaManager()
    manager.add_project(nearu())
    adapter = InMemoryChannelAdapter(
        Channel.X,
        discovery=(
            DiscoveryItem(
                external_id="x-42",
                author="@frankfurt_single",
                text="Dating in Frankfurt fühlt sich leer an",
                url="https://x.example/x-42",
            ),
        ),
    )
    manager.connect_adapter(adapter)

    found = manager.discover(Channel.X, "Dating", limit=5)
    assert len(found) == 1
    assert manager.public_actions_performed == 0

    draft = manager.create_draft(
        campaign(), Channel.X, "trust", "Lokales Dating braucht echte Dichte"
    )
    with pytest.raises(ValueError, match="requires approval"):
        manager.execute_publish(draft)

    approved = manager.approve(draft, "Dennis")
    published = manager.execute_publish(approved)
    assert published.success
    assert published.action == "publish"
    assert published.external_id
    assert manager.public_actions_performed == 1

    with pytest.raises(ValueError, match="requires approval"):
        manager.execute_reply("nearu", Channel.X, found[0].external_id, "Spannender Punkt")

    replied = manager.execute_reply(
        "nearu",
        Channel.X,
        found[0].external_id,
        "Spannender Punkt – genau lokale Dichte wollen wir verbessern.",
        approved=True,
    )
    assert replied.success
    assert replied.action == "reply"
    assert manager.public_actions_performed == 2


def test_mercury_requires_connected_adapter() -> None:
    manager = SocialMediaManager()
    manager.add_project(nearu())
    with pytest.raises(RuntimeError, match="no channel adapter"):
        manager.discover(Channel.X, "Frankfurt")
