from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import statistics
import concurrent.futures
import math
import tempfile
from contextlib import contextmanager
from dataclasses import replace
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .self_setup import ConcurrencyResult, select_concurrency

from .runtime import RuntimeController, RuntimeProfile
from .benchmark_environment import assert_idle, memory_snapshot, wait_for_memory


@dataclass
class BenchmarkResult:
    gpu_layers: int
    stable: bool
    latency_seconds: float = 0.0
    completion_tokens: int = 0
    tokens_per_second: float = 0.0
    error: str = ""
    variability_pct: float = 0.0
    samples: tuple[float, ...] = ()

    @property
    def status(self) -> str:
        return "stable" if self.stable else "failed"


def select_best_result(results: list[BenchmarkResult]) -> BenchmarkResult | None:
    stable = [result for result in results if result.stable and math.isfinite(result.tokens_per_second)
              and result.tokens_per_second > 0]
    if not stable:
        return None
    return max(stable, key=lambda item: (item.tokens_per_second, -item.latency_seconds))


def validate_completion(response: dict, expected_tokens: int) -> int:
    tokens = (response.get("usage") or {}).get("completion_tokens")
    if response.get("error") or not response.get("choices") or type(tokens) is not int or tokens != expected_tokens:
        raise ValueError("Incomplete benchmark response or unsupported fixed-token workload")
    return tokens


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
        self.baseline = None
        self.check_cancel = lambda: None

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
            self.check_cancel()
            if process.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(f"{base_url}/models", timeout=2) as response:
                    if response.status == 200:
                        return True
            except Exception:
                time.sleep(1)
        return False

    @contextmanager
    def session(self, profile: RuntimeProfile, parallel: int = 1):
        """One owned server, captured diagnostics and confirmed cleanup on every exit."""
        assert_idle(self.test_port)
        if self.baseline is None:
            self.baseline = memory_snapshot()
        wait_for_memory(self.baseline, self.log)
        self.check_cancel()
        assert_idle(self.test_port)
        test_profile = replace(profile, host="127.0.0.1", port=self.test_port)
        command = [
            self._find_llama_server(),
            *RuntimeController().build_llama_args(test_profile),
            "--parallel", str(max(1, parallel)),
        ]
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as output:
            process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                self.log(
                    f"Loading model · GPU {profile.gpu_layers} · context {profile.context:,} · "
                    f"parallel {max(1, parallel)}"
                )
                if not self._wait_ready(process, test_profile.base_url):
                    raise RuntimeError("Benchmark server failed to become ready")
                if process.poll() is not None:
                    raise RuntimeError("Benchmark server exited during startup")
                snapshot = memory_snapshot()
                self.log(f"Runtime ready · RAM free {snapshot.available_ram_gb} GB · VRAM free {snapshot.free_vram_mb} MiB")
                if snapshot.available_ram_gb is not None and snapshot.available_ram_gb < 1:
                    raise RuntimeError("Runtime leaves less than 1 GB RAM available. Reduce context before retesting.")
                yield test_profile
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=8)
                output.seek(0, 2)
                size = output.tell()
                output.seek(max(0, size - 16000))
                self.log("[Apollo server diagnostics]\n" + output.read())
                wait_for_memory(self.baseline, self.log)

    def run_one(
        self,
        profile: RuntimeProfile,
        gpu_layers: int,
        prompt: str = (
            "You are a local trading research analyst. Given a hypothetical token with strong short-term "
            "momentum but moderate holder concentration, produce a concise risk assessment with evidence, "
            "counterarguments, and a final PAPER-RESEARCH action. Use roughly 120 words."
        ),
        max_tokens: int = 192,
        measured_runs: int = 3,
    ) -> BenchmarkResult:
        model = Path(profile.model_path)
        if not model.is_file():
            return BenchmarkResult(gpu_layers=gpu_layers, stable=False, error=f"Model not found: {model}")

        try:
            with self.session(replace(profile, gpu_layers=gpu_layers), parallel=1) as test_profile:
                models = RuntimeController().get_models(test_profile)
                if not models:
                    raise ValueError("Benchmark endpoint has no model")
                payload = {
                    "model": models[0],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0,
                    "seed": 42,
                    "ignore_eos": True,
                    "cache_prompt": False,
                }
                self.log(f"GPU {gpu_layers} · warming up")
                self._post_json(f"{test_profile.base_url}/chat/completions",
                                dict(payload, max_tokens=24), self.request_timeout)
                elapsed_runs, token_runs, run_tps = [], [], []
                for index in range(max(1, measured_runs)):
                    self.check_cancel()
                    self.log(f"GPU {gpu_layers} · Run {index + 1}/{measured_runs}")
                    started = time.perf_counter()
                    response = self._post_json(f"{test_profile.base_url}/chat/completions",
                                               payload, self.request_timeout)
                    elapsed = max(time.perf_counter() - started, 0.001)
                    tokens = validate_completion(response, max_tokens)
                    elapsed_runs.append(elapsed)
                    token_runs.append(tokens)
                    run_tps.append(tokens / elapsed)
                    self.log(f"GPU {gpu_layers} · Run {index + 1}/{measured_runs} · {run_tps[-1]:.2f} end-to-end tok/s")
                tps = statistics.median(run_tps)
                variability = (max(run_tps) - min(run_tps)) / tps * 100 if len(run_tps) > 1 else 0
                return BenchmarkResult(gpu_layers, True, statistics.median(elapsed_runs),
                                       round(statistics.median(token_runs)), tps,
                                       variability_pct=variability, samples=tuple(run_tps))
        except (urllib.error.URLError, TimeoutError, subprocess.SubprocessError, OSError, ValueError) as exc:
            self.log(f"[Apollo] {gpu_layers} layers failed: {exc}")
            return BenchmarkResult(gpu_layers=gpu_layers, stable=False, error=str(exc))

    def run_many(
        self,
        profile: RuntimeProfile,
        gpu_layers_values: list[int],
        progress: Callable[[BenchmarkResult], None] | None = None,
        quick: bool = False,
    ) -> list[BenchmarkResult]:
        results: list[BenchmarkResult] = []
        for layers in gpu_layers_values:
            result = self.run_one(
                profile,
                layers,
                max_tokens=48 if quick else 192,
                measured_runs=1 if quick else 3,
            )
            results.append(result)
            if progress:
                progress(result)
        return results


@dataclass
class ConcurrencyBenchmarkSummary:
    results: list[ConcurrencyResult]
    recommended_concurrency: int
    variability_pct: float = 0.0


class ConcurrencyBenchmarkRunner:
    """Measure an already-running OpenAI-compatible local endpoint at 1/2/4 workers."""

    def __init__(self, request_timeout: float = 90.0, log: Callable[[str], None] | None = None,
                 check_cancel=None) -> None:
        self.request_timeout = request_timeout
        self.log = log or (lambda _message: None)
        self.check_cancel = check_cancel or (lambda: None)

    def _one(self, base_url: str, model_id: str, prompt: str, max_tokens: int) -> float:
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "seed": 42,
            "ignore_eos": True,
            "cache_prompt": False,
        }
        started = time.perf_counter()
        response = BenchmarkRunner._post_json(f"{base_url}/chat/completions", payload, self.request_timeout)
        validate_completion(response, max_tokens)
        return max(time.perf_counter() - started, 0.001)

    def run(
        self,
        profile: RuntimeProfile,
        concurrency_values: tuple[int, ...] = (1, 2, 4),
        quick: bool = False,
    ) -> ConcurrencyBenchmarkSummary:
        models = RuntimeController().get_models(profile)
        if not models:
            raise RuntimeError("No model is available on the running local endpoint.")
        model_id = models[0]
        results: list[ConcurrencyResult] = []
        variability = 0.0
        prompt = (
            "Analyze this hypothetical paper-trading setup: momentum is rising, liquidity is adequate, "
            "holder concentration is moderate, and no hard-risk flags are present. Return a concise "
            "risk/opportunity assessment and PAPER action with reasons."
        )

        # Warm the live endpoint before comparing worker counts.
        self._one(profile.base_url, model_id, "Reply briefly: warmup", 24)
        cycles = 1 if quick else 3
        max_tokens = 32 if quick else 128
        for workers in concurrency_values:
            self.log(f"[Apollo] Testing concurrency {workers} across {cycles} cycles…")
            walls: list[float] = []
            throughputs: list[float] = []
            average_latencies: list[float] = []
            for cycle in range(cycles):
                self.check_cancel()
                self.log(f"AI workers {workers} · Cycle {cycle + 1}/{cycles}")
                wall_started = time.perf_counter()
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(self._one, profile.base_url, model_id, prompt, max_tokens) for _ in range(workers)]
                    latencies = [future.result() for future in futures]
                wall = max(time.perf_counter() - wall_started, 0.001)
                walls.append(wall)
                throughputs.append(workers / wall)
                average_latencies.append(sum(latencies) / len(latencies))
            result = ConcurrencyResult(
                concurrency=workers,
                wall_seconds=statistics.median(walls),
                throughput_rps=statistics.median(throughputs),
                average_latency_seconds=statistics.median(average_latencies),
            )
            results.append(result)
            variability = max(variability, (max(throughputs) - min(throughputs)) / result.throughput_rps * 100)
            self.log(f"[Apollo] {workers} workers · {result.throughput_rps:.3f} req/s · {result.average_latency_seconds:.2f}s avg")

        return ConcurrencyBenchmarkSummary(results=results, recommended_concurrency=select_concurrency(results),
                                           variability_pct=variability)
