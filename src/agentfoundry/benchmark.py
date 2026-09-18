from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .runtime import RuntimeController, RuntimeProfile


@dataclass
class BenchmarkResult:
    gpu_layers: int
    stable: bool
    latency_seconds: float = 0.0
    completion_tokens: int = 0
    tokens_per_second: float = 0.0
    error: str = ""

    @property
    def status(self) -> str:
        return "stable" if self.stable else "failed"


def select_best_result(results: list[BenchmarkResult]) -> BenchmarkResult | None:
    stable = [result for result in results if result.stable]
    if not stable:
        return None
    return max(stable, key=lambda item: (item.tokens_per_second, -item.latency_seconds))


class BenchmarkRunner:
    def __init__(
        self,
        log: Callable[[str], None] | None = None,
        test_port: int = 18080,
        startup_timeout: float = 90.0,
        request_timeout: float = 90.0,
        llama_server_path: str = "",
    ) -> None:
        self.log = log or (lambda _message: None)
        self.test_port = test_port
        self.startup_timeout = startup_timeout
        self.request_timeout = request_timeout
        self.llama_server_path = llama_server_path

    def _find_llama_server(self) -> str:
        executable = self.llama_server_path or shutil.which("llama-server") or shutil.which("llama-server.exe")
        if not executable:
            raise FileNotFoundError("llama-server was not found in PATH.")
        return executable

    @staticmethod
    def _post_json(url: str, payload: dict, timeout: float) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _wait_ready(self, process: subprocess.Popen[str], base_url: str) -> bool:
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(f"{base_url}/models", timeout=2) as response:
                    if response.status == 200:
                        return True
            except Exception:
                time.sleep(1)
        return False

    def run_one(
        self,
        profile: RuntimeProfile,
        gpu_layers: int,
        prompt: str = "Reply with exactly: benchmark ready",
        max_tokens: int = 48,
    ) -> BenchmarkResult:
        model = Path(profile.model_path)
        if not model.is_file():
            return BenchmarkResult(gpu_layers=gpu_layers, stable=False, error=f"Model not found: {model}")

        executable = self._find_llama_server()
        test_profile = RuntimeProfile(
            model_path=profile.model_path,
            context=profile.context,
            gpu_layers=gpu_layers,
            kv_cache_k=profile.kv_cache_k,
            kv_cache_v=profile.kv_cache_v,
            rope_scaling=profile.rope_scaling,
            rope_scale=profile.rope_scale,
            yarn_orig_ctx=profile.yarn_orig_ctx,
            host="127.0.0.1",
            port=self.test_port,
            reasoning=profile.reasoning,
            reasoning_budget=profile.reasoning_budget,
        )
        args = RuntimeController().build_llama_args(test_profile)
        command = [executable, *args]

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        process: subprocess.Popen[str] | None = None

        try:
            self.log(f"[Apollo] Testing {gpu_layers} GPU layers…")
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=creationflags,
            )
            if not self._wait_ready(process, test_profile.base_url):
                error = "server failed to become ready"
                if process.poll() is not None:
                    error = f"server exited with code {process.returncode}"
                self.log(f"[Apollo] {gpu_layers} layers failed: {error}")
                return BenchmarkResult(gpu_layers=gpu_layers, stable=False, error=error)

            models = RuntimeController().get_models(test_profile)
            model_id = models[0] if models else profile.model_path

            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0,
            }

            started = time.perf_counter()
            response = self._post_json(
                f"{test_profile.base_url}/chat/completions",
                payload,
                timeout=self.request_timeout,
            )
            elapsed = max(time.perf_counter() - started, 0.001)

            usage = response.get("usage") or {}
            completion_tokens = int(usage.get("completion_tokens") or 0)
            tokens_per_second = completion_tokens / elapsed if completion_tokens else 0.0

            self.log(
                f"[Apollo] {gpu_layers} layers stable · {elapsed:.2f}s · "
                f"{tokens_per_second:.2f} tok/s"
            )
            return BenchmarkResult(
                gpu_layers=gpu_layers,
                stable=True,
                latency_seconds=elapsed,
                completion_tokens=completion_tokens,
                tokens_per_second=tokens_per_second,
            )
        except (urllib.error.URLError, TimeoutError, subprocess.SubprocessError, OSError, ValueError) as exc:
            self.log(f"[Apollo] {gpu_layers} layers failed: {exc}")
            return BenchmarkResult(gpu_layers=gpu_layers, stable=False, error=str(exc))
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()

    def run_many(
        self,
        profile: RuntimeProfile,
        gpu_layers_values: list[int],
        progress: Callable[[BenchmarkResult], None] | None = None,
    ) -> list[BenchmarkResult]:
        results: list[BenchmarkResult] = []
        for layers in gpu_layers_values:
            result = self.run_one(profile, layers)
            results.append(result)
            if progress:
                progress(result)
        return results
