"""Full Apollo orchestration; quality decisions are deterministic Python rules."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
import math
import re

from .benchmark import BenchmarkRunner, BenchmarkResult, ConcurrencyBenchmarkRunner, select_best_result
from .benchmark_environment import assert_idle, fingerprint, memory_snapshot, wait_for_memory
from .hardware import detect_hardware, recommend_runtime


def confidence(results, verification, quick, telemetry_complete, previous=None, fingerprint_value=""):
    best = select_best_result(results)
    if best is None or verification is None or not verification.stable:
        return "RETEST REQUIRED", "No valid winner confirmation."
    if any(not math.isfinite(item.tokens_per_second) or item.tokens_per_second <= 0
           or not math.isfinite(item.variability_pct)
           or any(not math.isfinite(sample) or sample <= 0 for sample in item.samples)
           for item in [*results, verification] if item.stable):
        return "RETEST REQUIRED", "Invalid measurement values."
    if any(not item.stable for item in results):
        return "UNCERTAIN", "Some GPU candidates failed; the comparison is incomplete."
    if any(item.variability_pct > 20 for item in [*results, verification]):
        return "UNCERTAIN", "Repeated measurements vary by more than 20%."
    if abs(verification.tokens_per_second / best.tokens_per_second - 1) > .20:
        return "UNCERTAIN", "Winner confirmation differs by more than 20%."
    if (previous and previous.get("fingerprint") == fingerprint_value
            and previous.get("gpu_layers") == best.gpu_layers and previous.get("tokens_per_second", 0) > 0
            and abs(best.tokens_per_second / previous["tokens_per_second"] - 1) > .30):
        return "UNCERTAIN", "Throughput differs by more than 30% from the matching saved measurement."
    if quick or any(len(item.samples) < 3 for item in [*results, verification]):
        return "UNCERTAIN", "Quick Tune is provisional. Run Deep Benchmark to verify."
    if not telemetry_complete:
        return "UNCERTAIN", "Hardware or memory telemetry is incomplete."
    return "VERIFIED", "Stable repeated measurements and independent winner confirmation."


@dataclass
class AutoTuneResult:
    status: str
    reason: str
    fingerprint: str
    profile: dict
    gpu_results: list[dict]
    verification: dict | None
    workers: dict | None
    quick: bool
    memory: dict


class AutoTuneRunner:
    def __init__(self, executable="", log=None, cancelled=None):
        self.log = log or (lambda message: None)
        self.cancelled = cancelled
        self.gpu = BenchmarkRunner(log=self.log, llama_server_path=executable, startup_timeout=180,
                                   request_timeout=180)
        self.gpu.check_cancel = self.check_cancel

    def check_cancel(self):
        if self.cancelled is not None and self.cancelled.is_set():
            raise RuntimeError("Auto-Tune cancelled. Current profile preserved.")

    def run(self, profile, quick=False, candidates=None, previous=None, progress=None):
        self.check_cancel()
        self.log("Hardware preflight · checking other servers and benchmark port")
        assert_idle(self.gpu.test_port)
        hardware = detect_hardware()
        baseline = memory_snapshot()
        if baseline.available_ram_gb is not None and baseline.available_ram_gb < 1:
            raise RuntimeError("Less than 1 GB RAM available. Close other applications before tuning.")
        if hardware.vram_gb and baseline.free_vram_mb is not None and baseline.free_vram_mb < 512:
            raise RuntimeError("Less than 512 MB VRAM available. Close GPU workloads before tuning.")
        model = Path(profile.model_path)
        if not model.is_file() or model.suffix.lower() != ".gguf":
            raise ValueError("Select an existing GGUF model before tuning.")
        with model.open("rb") as stream:
            if stream.read(4) != b"GGUF":
                raise ValueError("The selected model is not a GGUF file.")
        if profile.context < 512:
            raise ValueError("Benchmark context must be at least 512 tokens.")
        executable = self.gpu._find_llama_server()
        key = fingerprint(profile, executable, hardware, baseline)
        self.gpu.baseline = baseline
        self.log(f"Hardware analyzed · {hardware.summary}")
        self.log(f"Model detected · {model.name} · {model.stat().st_size / 1024 ** 3:.2f} GB")
        quant = re.search(r"(?:IQ|Q)\d[A-Z0-9_]*", model.stem.upper())
        self.log("Quantization (filename hint): " + (quant.group() if quant else "unknown; exact file identity recorded"))
        self.log(f"Available RAM {baseline.available_ram_gb} GB · VRAM {baseline.free_vram_mb} MiB")
        if candidates is None:
            center = recommend_runtime(hardware).gpu_layers
            candidates = sorted({max(0, center + offset) for offset in (-8, -4, 0, 4)}) if center else [0]
        if not candidates or any(type(value) is not int or not 0 <= value <= 200 for value in candidates):
            raise ValueError("GPU candidates must be between 0 and 200.")
        results = self.gpu.run_many(profile, list(dict.fromkeys(candidates)), progress=progress, quick=quick)
        best = select_best_result(results)
        verification = workers = None
        selected = profile
        if best is not None:
            selected = replace(profile, gpu_layers=best.gpu_layers)
            self.log("Verify configuration · reloading and confirming the winner")
            verification = self.gpu.run_one(selected, best.gpu_layers, max_tokens=96 if quick else 192,
                                             measured_runs=1 if quick else 3)
            if verification.stable:
                self.log("AI worker optimization · temporary runtime with selected GPU settings")
                with self.gpu.session(selected) as temporary:
                    workers = ConcurrencyBenchmarkRunner(request_timeout=300, log=self.log,
                        check_cancel=self.check_cancel).run(temporary, quick=quick)
        self.check_cancel()
        wait_for_memory(baseline, self.log)
        assert_idle(self.gpu.test_port)
        if fingerprint(profile, executable) != key:
            raise RuntimeError("Hardware, model or runtime changed during tuning. Retest required.")
        telemetry = (hardware.ram_gb > 0 and baseline.available_ram_gb is not None
                     and (hardware.vram_gb == 0 or baseline.free_vram_mb is not None)
                     and hardware.gpu != "Unknown")
        status, reason = confidence(results, verification, quick, telemetry, previous, key)
        if workers is None:
            status, reason = "RETEST REQUIRED", "GPU/worker optimization did not complete."
        elif workers.variability_pct > 20:
            status, reason = "UNCERTAIN", "Worker throughput varies by more than 20%."
        self.log(f"{status} · {reason}")
        return AutoTuneResult(status, reason, key, asdict(selected), [asdict(item) for item in results],
                              asdict(verification) if verification else None,
                              asdict(workers) if workers else None, quick, asdict(baseline))
