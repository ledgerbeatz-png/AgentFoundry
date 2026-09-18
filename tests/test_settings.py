from pathlib import Path

import agentfoundry.settings as settings_module
from agentfoundry.settings import AppSettings, load_settings, save_settings


def test_app_settings_roundtrip(tmp_path, monkeypatch) -> None:
    app_dir = tmp_path / "AgentFoundry"
    settings_file = app_dir / "settings.json"
    monkeypatch.setattr(settings_module, "APP_DIR", app_dir)
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_file)

    original = AppSettings(
        llama_server_path=r"C:\Tools\llama-server.exe",
        hermes_path=r"C:\Tools\hermes.exe",
        model_dir=r"C:\AI\Models",
        host="127.0.0.1",
        port=9090,
        first_run_complete=True,
    )
    save_settings(original)
    loaded = load_settings()

    assert loaded.llama_server_path == original.llama_server_path
    assert loaded.hermes_path == original.hermes_path
    assert loaded.model_dir == original.model_dir
    assert loaded.host == "127.0.0.1"
    assert loaded.port == 9090
    assert loaded.first_run_complete is True


def test_normalize_adds_default_model_directory() -> None:
    value = AppSettings(model_dir="").normalize()
    assert value.model_dir
