from agentfoundry.hardware import HardwareInfo, recommend_runtime


def test_recommendation_for_6gb_gpu_and_16gb_ram() -> None:
    info = HardwareInfo(
        os_name="Windows",
        os_version="11",
        architecture="AMD64",
        cpu="Test CPU",
        ram_gb=16.0,
        gpu="GTX 1060",
        vram_gb=6.0,
    )

    recommendation = recommend_runtime(info)

    assert recommendation.context == 65536
    assert recommendation.gpu_layers == 20
    assert recommendation.kv_cache_k == "q4_0"
    assert recommendation.kv_cache_v == "q4_0"


def test_recommendation_falls_back_to_cpu() -> None:
    info = HardwareInfo(
        os_name="Linux",
        os_version="test",
        architecture="x86_64",
        cpu="Test CPU",
        ram_gb=8.0,
        gpu="Unknown",
        vram_gb=0.0,
    )

    recommendation = recommend_runtime(info)

    assert recommendation.context == 16384
    assert recommendation.gpu_layers == 0
