from pathlib import Path

from agentfoundry.downloads import DownloadProgress, filename_from_url, human_bytes


def test_filename_from_url_decodes_name() -> None:
    assert filename_from_url("https://example.com/models/Qwen%203.gguf") == "Qwen 3.gguf"


def test_filename_from_url_has_fallback() -> None:
    assert filename_from_url("https://example.com/") == "model.gguf"


def test_download_progress_fraction() -> None:
    progress = DownloadProgress(downloaded=50, total=100, speed_bps=1024)
    assert progress.fraction == 0.5


def test_human_bytes() -> None:
    assert human_bytes(1024) == "1.0 KB"
    assert human_bytes(1024 * 1024) == "1.0 MB"
