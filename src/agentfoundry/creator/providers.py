from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class MediaRequest:
    """Provider-neutral request for generated creator media."""

    prompt: str
    negative_prompt: str = ""
    reference_images: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaResult:
    """Normalized result returned by image, voice, and video providers."""

    provider: str
    uri: str
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ImageProvider(Protocol):
    name: str

    def generate_image(self, request: MediaRequest) -> MediaResult:
        ...


@runtime_checkable
class VoiceProvider(Protocol):
    name: str

    def synthesize(self, text: str, *, voice: str = "") -> MediaResult:
        ...


@runtime_checkable
class VideoProvider(Protocol):
    name: str

    def generate_video(self, request: MediaRequest) -> MediaResult:
        ...


@runtime_checkable
class BrainProvider(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        ...
