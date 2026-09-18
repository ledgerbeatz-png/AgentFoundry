from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AgentFoundry"
SETTINGS_FILE = APP_DIR / "settings.json"


@dataclass
class AppSettings:
    llama_server_path: str = ""
    hermes_path: str = ""
    model_dir: str = ""
    host: str = "127.0.0.1"
    port: int = 8080
    first_run_complete: bool = False

    def normalize(self) -> "AppSettings":
        if not self.model_dir:
            self.model_dir = str(Path.home() / "AgentFoundry" / "models")
        return self


def _first_existing(candidates: list[str | None]) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path)
    return ""


def _glob_first(patterns: list[str]) -> str:
    for pattern in patterns:
        for path in sorted(Path().glob(pattern)):
            if path.is_file():
                return str(path)
    return ""


def _windows_package_executable(filename: str) -> str:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return ""
    packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
    if not packages.is_dir():
        return ""
    try:
        for path in packages.rglob(filename):
            if path.is_file():
                return str(path)
    except OSError:
        pass
    return ""


def detect_runtime_paths() -> AppSettings:
    llama_candidates = [
        shutil.which("llama-server"),
        shutil.which("llama-server.exe"),
        r"C:\Program Files\llama.cpp\llama-server.exe",
        r"C:\Program Files\llama.cpp\bin\llama-server.exe",
        str(Path.home() / "llama.cpp" / "llama-server.exe"),
        str(Path.home() / "Downloads" / "llama-server.exe"),
        _windows_package_executable("llama-server.exe") if os.name == "nt" else "",
    ]
    hermes_candidates = [
        shutil.which("hermes"),
        shutil.which("hermes.exe"),
        str(Path.home() / ".local" / "bin" / "hermes"),
        str(Path.home() / "AppData" / "Roaming" / "Python" / "Scripts" / "hermes.exe"),
        _windows_package_executable("hermes.exe") if os.name == "nt" else "",
    ]

    return AppSettings(
        llama_server_path=_first_existing(llama_candidates),
        hermes_path=_first_existing(hermes_candidates),
        model_dir=str(Path.home() / "AgentFoundry" / "models"),
    )


def load_settings() -> AppSettings:
    detected = detect_runtime_paths()
    if not SETTINGS_FILE.exists():
        return detected.normalize()

    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        loaded = AppSettings(**raw).normalize()
    except Exception:
        return detected.normalize()

    if not loaded.llama_server_path:
        loaded.llama_server_path = detected.llama_server_path
    if not loaded.hermes_path:
        loaded.hermes_path = detected.hermes_path
    return loaded


def save_settings(settings: AppSettings) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(asdict(settings.normalize()), indent=2),
        encoding="utf-8",
    )
