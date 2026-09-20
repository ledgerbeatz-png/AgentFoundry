from agentfoundry.creator.memory import CreatorMemory
from agentfoundry.creator.orchestrator import CreatorOrchestrator, CreatorProviders
from agentfoundry.creator.profile import CreatorProfile
from agentfoundry.creator.providers import MediaResult


class FakeBrain:
    name = "fake-brain"

    def complete(self, messages, **kwargs):
        return messages[-1]["content"]


class FakeImage:
    name = "fake-image"

    def generate_image(self, request):
        return MediaResult(provider=self.name, uri="memory://image")


def test_orchestrator_uses_brain_and_optional_image(tmp_path):
    profile = CreatorProfile(
        creator_id="maya-demo",
        display_name="Maya Demo",
        persona="Fictional test creator.",
    )
    memory = CreatorMemory(tmp_path / "creator.db")
    orchestrator = CreatorOrchestrator(
        profile,
        memory,
        CreatorProviders(brain=FakeBrain(), image=FakeImage()),
    )

    assert orchestrator.reply("fan-1", "hello") == "hello"
    assert orchestrator.create_image("portrait").uri == "memory://image"


def test_missing_video_provider_fails_explicitly(tmp_path):
    orchestrator = CreatorOrchestrator(
        CreatorProfile("maya-demo", "Maya Demo", "Fictional test creator."),
        CreatorMemory(tmp_path / "creator.db"),
        CreatorProviders(brain=FakeBrain()),
    )

    try:
        orchestrator.create_video("short clip")
    except RuntimeError as exc:
        assert "video provider" in str(exc).lower()
    else:
        raise AssertionError("Expected missing provider error")
