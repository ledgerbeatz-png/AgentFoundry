"""Exercise the actual Tk callbacks without starting a model or changing user settings."""
from dataclasses import asdict
import time

import pytest

tk = pytest.importorskip("tkinter")
from agentfoundry import app as app_module, screens, settings
from agentfoundry.autotune import AutoTuneResult
from agentfoundry.runtime import RuntimeProfile


@pytest.fixture(scope="module")
def tk_application():
    patch = pytest.MonkeyPatch()
    patch.setattr(app_module, "load_settings", lambda: settings.AppSettings(first_run_complete=True))
    patch.setattr(app_module, "load_profiles", lambda: {"Test": RuntimeProfile("model.gguf", gpu_layers=12)})
    try:
        app = app_module.AgentFoundryApp()
    except tk.TclError as exc:
        patch.undo()
        pytest.skip(f"Tk display unavailable: {exc}")
    app.withdraw()
    yield app
    for callback in app.tk.call("after", "info"):
        app.after_cancel(callback)
    app.destroy()
    patch.undo()


@pytest.fixture
def application(tk_application, monkeypatch, tmp_path):
    app = tk_application
    monkeypatch.setattr(settings, "APP_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    app.settings = settings.AppSettings(first_run_complete=True)
    app._apollo_saved_status = "RETEST REQUIRED"
    app.apollo_workers = None
    app.load_selected_profile()
    yield app
    for callback in app.tk.call("after", "info"):
        app.after_cancel(callback)


def make_result(app, status):
    profile = asdict(app.current_profile())
    profile["gpu_layers"] = 20
    return AutoTuneResult(status, "test reason", "identity", profile, [],
                          {"tokens_per_second": 10}, {"recommended_concurrency": 2, "results": []},
                          status != "VERIFIED", {})


@pytest.mark.parametrize("status,expected_layers", [("VERIFIED", "20"), ("UNCERTAIN", "12")])
def test_completed_tune_persists_and_only_applies_verified(application, status, expected_layers):
    app = application
    screen = app.screens["benchmarks"]
    screen.started = time.monotonic()
    screen.source_profile = asdict(app.current_profile())
    screen.source_executable = app.settings.llama_server_path
    screen.running = app.tuning_active = True
    screen._complete_tune(make_result(app, status))
    assert not screen.running
    assert app.gpu_layers.get() == expected_layers
    assert app.settings.apollo_status == status
    import json
    saved = json.loads(settings.SETTINGS_FILE.read_text())
    assert saved["apollo_last_attempt"]["status"] == status
    if status == "VERIFIED":
        assert saved["apollo_workers"] == 2
        assert saved["apollo_profile"]["gpu_layers"] == 20
        assert app.apollo_workers == 2
    else:
        assert saved["apollo_profile"] is None


def test_settings_changed_during_tune_prevents_apply(application):
    app = application
    screen = app.screens["benchmarks"]
    screen.started = time.monotonic()
    screen.source_profile = asdict(app.current_profile())
    screen.source_executable = app.settings.llama_server_path
    result = make_result(app, "VERIFIED")
    app.context.set("8192")
    screen._complete_tune(result)
    assert app.settings.apollo_status == "RETEST REQUIRED"
    assert app.gpu_layers.get() == "12"
    assert app.context.get() == "8192"


def test_failed_save_never_applies_winner(application, monkeypatch):
    app = application
    screen = app.screens["benchmarks"]
    screen.started = time.monotonic()
    screen.source_profile = asdict(app.current_profile())
    screen.source_executable = app.settings.llama_server_path
    def fail(_):
        raise OSError("disk full")
    monkeypatch.setattr(screens, "save_settings", fail)
    screen._complete_tune(make_result(app, "VERIFIED"))
    assert app.gpu_layers.get() == "12"
    assert app.settings.apollo_status == "RETEST REQUIRED"


def test_preflight_failure_returns_ui_to_idle(application, monkeypatch):
    app = application
    screen = app.screens["benchmarks"]
    def fail(*_args, **_kwargs):
        raise RuntimeError("Existing llama-server PIDs: 388, 7080")
    monkeypatch.setattr(screens.AutoTuneRunner, "run", fail)
    screen._start(True)
    deadline = time.monotonic() + 3
    while screen.running and time.monotonic() < deadline:
        app.update()
        time.sleep(.01)
    assert not screen.running
    assert "388, 7080" in screen.recommendation.cget("text")
    assert app.settings.apollo_status == "RETEST REQUIRED"
    assert str(screen.quick_button.cget("state")) == "normal"


@pytest.mark.parametrize("identity_matches", [True, False])
def test_restore_checks_identity_before_reusing_profile(application, monkeypatch, identity_matches):
    from agentfoundry import benchmark_environment
    app = application
    saved = asdict(app.current_profile())
    saved.update(context=8192, gpu_layers=20)
    app.settings.apollo_profile = saved
    app.settings.apollo_fingerprint = "saved"
    app.settings.apollo_gpu_layers = 20
    app.settings.apollo_workers = 2
    app.settings.llama_server_path = "llama.exe"
    app._apollo_saved_status = "VERIFIED"
    monkeypatch.setattr(benchmark_environment, "fingerprint", lambda *_: "saved" if identity_matches else "changed")
    app._validate_saved_tune(restore=True)
    deadline = time.monotonic() + .8
    while time.monotonic() < deadline:
        app.update()
        time.sleep(.01)
    assert app.settings.apollo_status == ("VERIFIED" if identity_matches else "RETEST REQUIRED")
    assert app.context.get() == ("8192" if identity_matches else "65536")
    assert app.apollo_workers == (2 if identity_matches else None)
