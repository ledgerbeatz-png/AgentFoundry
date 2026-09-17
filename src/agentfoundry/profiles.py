from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .runtime import RuntimeProfile


APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AgentFoundry"
PROFILES_FILE = APP_DIR / "profiles.json"

DEFAULT_PROFILE = RuntimeProfile(
    model_path=r"C:\AI\Models\Qwen3-14B-Abliterated\Qwen3-14B-abliterated-IQ4_XS.gguf",
    context=65536,
    gpu_layers=20,
    kv_cache_k="q4_0",
    kv_cache_v="q4_0",
    rope_scaling="yarn",
    rope_scale=2.0,
    yarn_orig_ctx=40960,
    reasoning="off",
    reasoning_budget=0,
)


def load_profiles() -> dict[str, RuntimeProfile]:
    if not PROFILES_FILE.exists():
        return {"Qwen3-14B Local 64K": DEFAULT_PROFILE}

    try:
        raw = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
        profiles: dict[str, RuntimeProfile] = {}
        for name, value in raw.items():
            profiles[name] = RuntimeProfile(**value)
        if profiles:
            return profiles
    except Exception:
        pass
    return {"Qwen3-14B Local 64K": DEFAULT_PROFILE}


def save_profiles(profiles: dict[str, RuntimeProfile]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    payload = {name: asdict(profile) for name, profile in profiles.items()}
    PROFILES_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
