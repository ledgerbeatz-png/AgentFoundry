from __future__ import annotations

from dataclasses import dataclass

from .memory import CreatorMemory
from .profile import CreatorProfile
from .providers import BrainProvider, ImageProvider, MediaRequest, MediaResult, VideoProvider, VoiceProvider


@dataclass
class CreatorProviders:
    brain: BrainProvider
    image: ImageProvider | None = None
    voice: VoiceProvider | None = None
    video: VideoProvider | None = None


class CreatorOrchestrator:
    """Coordinates persona, memory, and pluggable generation providers."""

    def __init__(
        self,
        profile: CreatorProfile,
        memory: CreatorMemory,
        providers: CreatorProviders,
    ) -> None:
        profile.validate()
        self.profile = profile
        self.memory = memory
        self.providers = providers

    def reply(self, audience_id: str, message: str) -> str:
        memories = self.memory.recall(self.profile.creator_id, audience_id)
        system = (
            f"You are {self.profile.display_name}. {self.profile.persona}\n"
            f"Voice: {self.profile.voice_style}\n"
            f"Rules: {'; '.join(self.profile.rules)}\n"
            f"Disclosure: {self.profile.ai_disclosure}\n"
            f"Known audience context: {memories}"
        )
        return self.providers.brain.complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ]
        )

    def create_image(self, prompt: str, **metadata: object) -> MediaResult:
        if self.providers.image is None:
            raise RuntimeError("No image provider configured")
        return self.providers.image.generate_image(
            MediaRequest(prompt=prompt, metadata=dict(metadata))
        )

    def create_video(self, prompt: str, **metadata: object) -> MediaResult:
        if self.providers.video is None:
            raise RuntimeError("No video provider configured")
        return self.providers.video.generate_video(
            MediaRequest(prompt=prompt, metadata=dict(metadata))
        )

    def create_voice(self, text: str) -> MediaResult:
        if self.providers.voice is None:
            raise RuntimeError("No voice provider configured")
        return self.providers.voice.synthesize(text, voice=self.profile.voice_style)
