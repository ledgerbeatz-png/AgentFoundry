import pytest

from agentfoundry.creator import (
    ContentBrief,
    ContentKind,
    ContentPipeline,
    CreatorProfile,
    PipelineStatus,
    builtin_providers,
)


def creator(age: int = 24) -> CreatorProfile:
    return CreatorProfile(
        creator_id="maya-v1",
        stage_name="Maya",
        age=age,
        fictional=True,
        disclosure="AI-generated fictional creator",
        appearance="dark wavy hair, brown eyes, consistent oval face",
        personality=("warm", "witty", "curious"),
        voice="friendly and confident",
        visual_rules=("brown eyes", "no tattoos", "same facial proportions"),
        forbidden_traits=("logo", "watermark"),
    )


def brief(kind: ContentKind = ContentKind.IMAGE) -> ContentBrief:
    return ContentBrief(
        title="Evening coffee",
        kind=kind,
        concept="candid lifestyle editorial",
        setting="modern cafe at blue hour",
        wardrobe="black knit dress",
        mood="warm and playful",
        platform="social-preview",
    )


def test_creator_must_be_disclosed_adult() -> None:
    with pytest.raises(ValueError, match="18 or older"):
        creator(age=17).validate()


def test_pipeline_requires_human_approval_before_provider_job() -> None:
    pipeline = ContentPipeline(builtin_providers())
    item = pipeline.create(creator(), brief())
    with pytest.raises(ValueError, match="human approval"):
        pipeline.prepare(item, "higgsfield")

    approved = pipeline.approve(item, "Dennis")
    prepared = pipeline.prepare(approved, "higgsfield")
    assert prepared.status is PipelineStatus.RENDER_READY
    assert prepared.provider_job is not None
    assert "original fictional adult" in prepared.provider_job.prompt
    assert prepared.provider_job.metadata["disclosure"] == "AI-generated fictional creator"


def test_provider_capability_is_enforced() -> None:
    pipeline = ContentPipeline(builtin_providers())
    item = pipeline.approve(pipeline.create(creator(), brief()), "Dennis")
    with pytest.raises(ValueError, match="does not support image"):
        pipeline.prepare(item, "google-flow")


def test_rendered_output_has_explicit_state_transition() -> None:
    pipeline = ContentPipeline(builtin_providers())
    item = pipeline.create(creator(), brief(ContentKind.VIDEO))
    item = pipeline.approve(item, "Dennis")
    item = pipeline.prepare(item, "google-flow")
    item = pipeline.mark_rendered(item, "file:///renders/maya-001.mp4")
    assert item.status is PipelineStatus.RENDERED
    assert item.output_uri.endswith("maya-001.mp4")
