from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock
import socket
import subprocess

import pytest

from agentfoundry import autotune, benchmark, benchmark_environment as environment
from agentfoundry.autotune import AutoTuneRunner, confidence
from agentfoundry.benchmark import BenchmarkResult, BenchmarkRunner, ConcurrencyBenchmarkSummary, validate_completion
from agentfoundry.hardware import HardwareInfo
from agentfoundry.runtime import RuntimeProfile
from agentfoundry.self_setup import ConcurrencyResult


def measured(layers=12, speed=10, spread=2):
    return BenchmarkResult(layers, True, 19.2, 192, speed,
                           variability_pct=spread, samples=(speed, speed, speed))


@pytest.mark.parametrize("quick,telemetry,spread,retest_speed,expected", [
    (False, True, 2, 10, "VERIFIED"),
    (True, True, 0, 10, "QUICK READY"),
    (False, False, 2, 10, "UNCERTAIN"),
    (False, True, 25, 10, "UNCERTAIN"),
    (False, True, 2, 6, "UNCERTAIN"),
    (False, True, 2, float("nan"), "RETEST REQUIRED"),
])
def test_confidence(quick, telemetry, spread, retest_speed, expected):
    assert confidence([measured(spread=spread)], measured(speed=retest_speed), quick, telemetry)[0] == expected


def test_only_matching_history_is_compared():
    previous = {"fingerprint": "same", "gpu_layers": 12, "tokens_per_second": 20}
    assert confidence([measured()], measured(), False, True, previous, "same")[0] == "UNCERTAIN"
    assert confidence([measured()], measured(), False, True, previous, "different")[0] == "VERIFIED"


def test_failed_candidate_prevents_verification():
    assert confidence([measured(), BenchmarkResult(24, False)], measured(), False, True)[0] == "UNCERTAIN"


@pytest.mark.parametrize("response", [{}, {"usage": {"completion_tokens": 0}},
    {"choices": [{}], "usage": {"completion_tokens": 95}},
    {"error": "failed", "choices": [{}], "usage": {"completion_tokens": 96}}])
def test_incomplete_response_rejected(response):
    with pytest.raises(ValueError):
        validate_completion(response, 96)


def test_preflight_blocks_foreign_processes(monkeypatch):
    monkeypatch.setattr(environment, "server_pids", lambda: [388, 7080])
    with pytest.raises(RuntimeError, match="388, 7080"):
        environment.assert_idle(18080)


def test_preflight_blocks_busy_port(monkeypatch):
    monkeypatch.setattr(environment, "server_pids", lambda: [])
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        with pytest.raises(RuntimeError, match="already in use"):
            environment.assert_idle(occupied.getsockname()[1])


def test_memory_must_recover(monkeypatch):
    baseline = environment.MemorySnapshot(8, 6000)
    monkeypatch.setattr(environment, "memory_snapshot", lambda: environment.MemorySnapshot(4, 3000))
    with pytest.raises(RuntimeError, match="baseline"):
        environment.wait_for_memory(baseline, lambda _: None, timeout=0)


def test_fingerprint_tracks_relevant_settings_and_files(tmp_path):
    model, exe = tmp_path / "model.gguf", tmp_path / "llama-server.exe"
    model.write_bytes(b"GGUF")
    exe.write_bytes(b"runtime")
    profile = RuntimeProfile(str(model))
    hardware = HardwareInfo("Windows", "11", "AMD64", "CPU", 16, "GPU", 8)
    memory = environment.MemorySnapshot(8, 6000, "driver1")
    key = lambda p=profile, h=hardware, m=memory: environment.fingerprint(p, str(exe), h, m)
    original = key()
    assert key(replace(profile, gpu_layers=24, port=18080)) == original
    assert key(replace(profile, context=32768)) != original
    assert key(replace(profile, kv_cache_k="q8_0")) != original
    assert key(h=replace(hardware, ram_gb=32)) != original
    assert key(m=replace(memory, gpu_identity="driver2")) != original
    assert key(m=replace(memory, available_ram_gb=6, free_vram_mb=5000)) == original
    (tmp_path / "ggml.dll").write_bytes(b"new-library")
    assert key() != original
    model.write_bytes(b"GGUF-new-model")
    assert key() != original


def test_owned_process_killed_and_reaped_on_startup_failure(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("llama", 8), 0]
    monkeypatch.setattr(benchmark.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(benchmark, "assert_idle", lambda _: None)
    monkeypatch.setattr(benchmark, "memory_snapshot", lambda: environment.MemorySnapshot(8, 6000))
    monkeypatch.setattr(benchmark, "wait_for_memory", lambda *_: None)
    runner = BenchmarkRunner(llama_server_path="llama")
    monkeypatch.setattr(runner, "_wait_ready", lambda *_: False)
    with pytest.raises(RuntimeError, match="ready"):
        with runner.session(RuntimeProfile("model")):
            pytest.fail("A failed server must never be yielded")
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2


@pytest.fixture
def tuning(monkeypatch, tmp_path):
    model = tmp_path / "qwen-IQ4_XS.gguf"
    model.write_bytes(b"GGUF")
    profile = RuntimeProfile(str(model), context=32768)
    hardware = HardwareInfo("Windows", "11", "AMD64", "CPU", 15.7, "GPU", 8)
    for name, implementation in {
        "assert_idle": lambda _: None,
        "detect_hardware": lambda: hardware,
        "memory_snapshot": lambda: environment.MemorySnapshot(8, 6000),
        "fingerprint": lambda *_: "identity",
        "wait_for_memory": lambda *_: None,
    }.items():
        monkeypatch.setattr(autotune, name, implementation)
    runner = AutoTuneRunner("llama")
    monkeypatch.setattr(runner.gpu, "run_many", lambda *_args, **_kwargs: [measured(12, 8), measured(20, 10)])
    monkeypatch.setattr(runner.gpu, "run_one", lambda *_args, **_kwargs: measured(20, 10))
    sessions = []
    @contextmanager
    def session(selected, parallel=1):
        sessions.append(("start", selected.gpu_layers, parallel))
        try:
            yield selected
        finally:
            sessions.append(("stop", selected.gpu_layers, parallel))
    monkeypatch.setattr(runner.gpu, "session", session)
    monkeypatch.setattr(autotune.ConcurrencyBenchmarkRunner, "run", lambda *_args, **_kwargs:
        ConcurrencyBenchmarkSummary([ConcurrencyResult(2, 10, .2, 8)], 2))
    return runner, profile, sessions


def test_auto_tune_caps_unsafe_context_to_hardware_recommendation(tuning, monkeypatch):
    runner, profile, _ = tuning
    seen_contexts = []

    def run_many(candidate_profile, *_args, **_kwargs):
        seen_contexts.append(candidate_profile.context)
        return [measured(12, 8), measured(20, 10)]

    monkeypatch.setattr(runner.gpu, "run_many", run_many)
    result = runner.run(replace(profile, context=65536))

    assert seen_contexts == [32768]
    assert result.profile["context"] == 32768


def test_quick_uses_reduced_candidate_set(monkeypatch, tmp_path):
    model = tmp_path / "qwen-IQ4_XS.gguf"
    model.write_bytes(b"GGUF")
    profile = RuntimeProfile(str(model), context=32768)
    hardware = HardwareInfo("Windows", "11", "AMD64", "CPU", 15.7, "GPU", 7.96)
    monkeypatch.setattr(autotune, "assert_idle", lambda _: None)
    monkeypatch.setattr(autotune, "detect_hardware", lambda: hardware)
    monkeypatch.setattr(autotune, "memory_snapshot", lambda: environment.MemorySnapshot(8, 6000))
    monkeypatch.setattr(autotune, "fingerprint", lambda *_args, **_kwargs: "identity")
    monkeypatch.setattr(autotune, "wait_for_memory", lambda *_args, **_kwargs: None)
    runner = AutoTuneRunner("llama")
    seen = {}

    def run_many(_profile, candidates, **kwargs):
        seen["candidates"] = candidates
        seen["quick"] = kwargs["quick"]
        return [measured(candidates[0], 8), measured(candidates[-1], 10)]

    monkeypatch.setattr(runner.gpu, "run_many", run_many)
    monkeypatch.setattr(runner.gpu, "run_one", lambda *_args, **_kwargs: measured(24, 10))
    @contextmanager
    def session(selected, parallel=1):
        yield selected
    monkeypatch.setattr(runner.gpu, "session", session)
    monkeypatch.setattr(autotune.ConcurrencyBenchmarkRunner, "run", lambda *_args, **_kwargs:
        ConcurrencyBenchmarkSummary([ConcurrencyResult(2, 10, .2, 8)], 2))

    result = runner.run(profile, quick=True)

    assert seen == {"candidates": [16, 20, 24], "quick": True}
    assert result.status == "QUICK READY"


def test_full_auto_tune_uses_winner_for_workers(tuning):
    runner, profile, sessions = tuning
    result = runner.run(profile)
    assert result.status == "VERIFIED"
    assert result.profile["gpu_layers"] == 20
    assert result.workers["recommended_concurrency"] == 2
    assert sessions == [("start", 20, 4), ("stop", 20, 4)]
    assert profile.gpu_layers == 20


def test_worker_failure_cleans_up_and_does_not_return_profile(tuning, monkeypatch):
    runner, profile, sessions = tuning
    def fail(*_args, **_kwargs):
        raise TimeoutError("worker timeout")
    monkeypatch.setattr(autotune.ConcurrencyBenchmarkRunner, "run", fail)
    with pytest.raises(TimeoutError):
        runner.run(profile)
    assert sessions[-1] == ("stop", 20, 4)


def test_quick_returns_provisional_ready_status(tuning):
    runner, profile, _ = tuning
    assert runner.run(profile, quick=True).status == "QUICK READY"


def test_cancel_does_not_return_success(tuning):
    import threading
    runner, profile, _ = tuning
    runner.cancelled = threading.Event()
    runner.cancelled.set()
    with pytest.raises(RuntimeError, match="cancelled"):
        runner.run(profile)
