from agentfoundry.creator import CreatorMemory, CreatorProfile


def test_creator_profile_requires_disclosure():
    profile = CreatorProfile(
        creator_id="maya-demo",
        display_name="Maya Demo",
        persona="A fictional virtual creator used for testing.",
    )
    profile.validate()
    assert profile.ai_disclosure == "Virtual AI creator"


def test_creator_memory_isolated_by_audience(tmp_path):
    memory = CreatorMemory(tmp_path / "creator.db")
    memory.remember("maya-demo", "fan-1", "favorite_topic", "travel")
    memory.remember("maya-demo", "fan-2", "favorite_topic", "music")

    assert memory.recall("maya-demo", "fan-1") == {"favorite_topic": "travel"}
    assert memory.recall("maya-demo", "fan-2") == {"favorite_topic": "music"}
