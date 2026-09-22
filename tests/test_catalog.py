from agentfoundry.catalog import load_model_manifests


def test_reference_manifest_is_available() -> None:
    manifests = load_model_manifests()
    reference = next(
        manifest for manifest in manifests
        if manifest.id == "qwen3-14b-abliterated-iq4-xs"
    )

    assert reference.quantization == "IQ4_XS"
    assert reference.download_url.startswith("https://huggingface.co/")
    assert reference.filename.endswith(".gguf")
    assert reference.default_profile["context"] == 65536
    assert reference.default_profile["gpu_layers"] == 20


def test_bonsai_manifest_requires_prism_runtime() -> None:
    manifests = load_model_manifests()
    bonsai = next(
        manifest for manifest in manifests
        if manifest.id == "bonsai-2-27b-ptq1-0"
    )

    assert bonsai.quantization == "PTQ1_0"
    assert bonsai.filename == "Ternary-Bonsai-2-27B-PTQ1_0.gguf"
    assert bonsai.runtime["requires_custom_build"] is True
    assert bonsai.runtime["variant"] == "PrismML-Eng/llama.cpp"
    assert bonsai.default_profile["context"] == 32768
