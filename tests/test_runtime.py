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
