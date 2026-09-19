from agentfoundry.runtime import RuntimeController, RuntimeProfile


def test_reference_profile_builds_expected_llama_args():
    profile = RuntimeProfile(
        model_path=r"C:\models\qwen.gguf",
        context=65536,
        gpu_layers=20,
        kv_cache_k="q4_0",
        kv_cache_v="q4_0",
        rope_scale=2.0,
        yarn_orig_ctx=40960,
        reasoning="off",
        reasoning_budget=0,
    )

    args = RuntimeController().build_llama_args(profile)

    assert args[:2] == ["-m", r"C:\models\qwen.gguf"]
    assert ["-c", "65536"] == args[2:4]
    assert "--no-kv-offload" in args
    assert "q4_0" in args
    assert "--reasoning" in args
    assert "off" in args
    assert "--port" in args
    assert "8080" in args


def test_runtime_can_force_parallel_worker_slots():
    profile = RuntimeProfile(model_path=r"C:\\models\\qwen.gguf")

    args = RuntimeController().build_llama_args(profile, parallel=2)

    index = args.index("--parallel")
    assert args[index:index + 2] == ["--parallel", "2"]


def test_runtime_gpu_fallback_retries_lower_layers(monkeypatch):
    controller = RuntimeController()
    profile = RuntimeProfile(model_path=r"C:\models\qwen.gguf", gpu_layers=24)
    started = []

    def fake_start(candidate, parallel=None):
        started.append(candidate.gpu_layers)
        controller.server_process = object()

    def fake_wait(candidate, timeout=120):
        return candidate.gpu_layers == 20

    monkeypatch.setattr(controller, "start_server", fake_start)
    monkeypatch.setattr(controller, "wait_for_server", fake_wait)
    monkeypatch.setattr(controller, "stop_server", lambda: None)
    monkeypatch.setattr("agentfoundry.runtime.time.sleep", lambda _seconds: None)

    result = controller.start_server_with_gpu_fallback(profile, parallel=1, step=4, max_fallbacks=3)

    assert started == [24, 20]
    assert result.gpu_layers == 20
    assert profile.gpu_layers == 24
