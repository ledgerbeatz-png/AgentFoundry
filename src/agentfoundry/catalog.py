from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelManifest:
    id: str
    name: str
    family: str
    quantization: str
    download_url: str
    filename: str
    default_profile: dict


def manifest_directories() -> list[Path]:
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "model-manifests")

    candidates.append(Path(__file__).resolve().parents[2] / "model-manifests")
    candidates.append(Path.cwd() / "model-manifests")

    unique: list[Path] = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    return unique


def load_model_manifests() -> list[ModelManifest]:
    manifests: list[ModelManifest] = []
    seen: set[str] = set()

    for directory in manifest_directories():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                source = payload.get("source") or {}
                download_url = str(source.get("download_url") or "")
                filename = str(source.get("filename") or "")
                manifest_id = str(payload["id"])
                if manifest_id in seen:
                    continue
                manifests.append(
                    ModelManifest(
                        id=manifest_id,
                        name=str(payload.get("name") or manifest_id),
                        family=str(payload.get("family") or ""),
                        quantization=str(payload.get("quantization") or ""),
                        download_url=download_url,
                        filename=filename,
                        default_profile=dict(payload.get("default_profile") or {}),
                    )
                )
                seen.add(manifest_id)
            except (OSError, ValueError, KeyError, TypeError):
                continue

    return manifests
