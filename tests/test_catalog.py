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
