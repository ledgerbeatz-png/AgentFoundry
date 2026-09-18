from __future__ import annotations

import hashlib
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class DownloadProgress:
    downloaded: int
    total: int
    speed_bps: float
    state: str = "downloading"

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(max(self.downloaded / self.total, 0.0), 1.0)


def human_bytes(value: float) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def filename_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    name = Path(urllib.parse.unquote(path)).name
    return name or "model.gguf"


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class DownloadCancelled(Exception):
    pass


class ResumableDownloader:
    def __init__(
        self,
        progress: Callable[[DownloadProgress], None] | None = None,
        log: Callable[[str], None] | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> None:
        self.progress = progress or (lambda _progress: None)
        self.log = log or (lambda _message: None)
        self.chunk_size = chunk_size
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def reset(self) -> None:
        self._cancel.clear()

    def download(
        self,
        url: str,
        destination: Path,
        expected_sha256: str = "",
        retries: int = 3,
    ) -> Path:
        self.reset()
        destination = destination.expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(destination.suffix + ".part")

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                result = self._download_once(url, destination, partial)
                if expected_sha256.strip():
                    self.progress(DownloadProgress(result.stat().st_size, result.stat().st_size, 0.0, "verifying"))
                    actual = sha256_file(result)
                    expected = expected_sha256.strip().lower()
                    if actual.lower() != expected:
                        raise ValueError(
                            f"SHA256 mismatch. Expected {expected}, got {actual}."
                        )
                    self.log("[Downloads] SHA256 verified.")
                self.progress(DownloadProgress(result.stat().st_size, result.stat().st_size, 0.0, "complete"))
                return result
            except DownloadCancelled:
                self.log("[Downloads] Download cancelled. Partial file kept for resume.")
                raise
            except Exception as exc:
                last_error = exc
                self.log(f"[Downloads] Attempt {attempt}/{retries} failed: {exc}")
                if attempt < retries:
                    time.sleep(min(2 ** (attempt - 1), 5))

        assert last_error is not None
        raise last_error

    def _download_once(self, url: str, destination: Path, partial: Path) -> Path:
        existing = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "AgentFoundry/0.1"}
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"
            self.log(f"[Downloads] Resuming at {human_bytes(existing)}.")

        request = urllib.request.Request(url, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and existing > 0:
                partial.replace(destination)
                return destination
            raise

        status = getattr(response, "status", response.getcode())
        content_length = int(response.headers.get("Content-Length") or 0)
        accepts_resume = status == 206

        if existing > 0 and not accepts_resume:
            self.log("[Downloads] Server ignored Range request; restarting safely.")
            existing = 0
            mode = "wb"
        else:
            mode = "ab" if existing > 0 else "wb"

        total = existing + content_length if content_length else 0
        downloaded = existing
        started = time.perf_counter()
        window_started = started
        window_bytes = downloaded

        with response, partial.open(mode) as handle:
            while True:
                if self._cancel.is_set():
                    raise DownloadCancelled()

                chunk = response.read(self.chunk_size)
                if not chunk:
                    break

                handle.write(chunk)
                downloaded += len(chunk)

                now = time.perf_counter()
                elapsed = now - window_started
                if elapsed >= 0.25:
                    speed = (downloaded - window_bytes) / elapsed
                    self.progress(DownloadProgress(downloaded, total, speed))
                    window_started = now
                    window_bytes = downloaded

            handle.flush()
            os.fsync(handle.fileno())

        self.progress(DownloadProgress(downloaded, total or downloaded, 0.0))
        partial.replace(destination)
        self.log(f"[Downloads] Completed: {destination}")
        return destination
