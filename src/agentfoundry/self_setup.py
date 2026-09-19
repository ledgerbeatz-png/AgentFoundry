from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .hardware import HardwareInfo, RuntimeRecommendation, recommend_runtime


@dataclass(frozen=True)
class ModelRecommendation:
    family: str
    parameter_class: str
    quantization: str
    reason: str


@dataclass(frozen=True)
class ConcurrencyResult:
    concurrency: int
    wall_seconds: float
    throughput_rps: float
    average_latency_seconds: float


@dataclass(frozen=True)
class SelfSetupPlan:
    model: ModelRecommendation
    runtime: RuntimeRecommendation
    recommended_concurrency: int
    paper_only: bool = True


def recommend_model(info: HardwareInfo, model_path: str = "") -> ModelRecommendation:
    """Recommend a model class, preferring an existing local GGUF as a benchmark candidate."""
    path = Path(model_path).expanduser() if model_path else None
    if path and path.is_file():
        size_gb = path.stat().st_size / (1024 ** 3)
        name = path.name.lower()
        parameter_class = "existing GGUF"
        for marker in ("32b", "14b", "8b", "7b", "3b", "1.5b"):
            if marker in name:
                parameter_class = marker.upper()
                break
        quant = "detected GGUF"
        for marker in ("iq4_xs", "q4_k_m", "q4_k_s", "q4_0", "q5_k_m", "q8_0"):
            if marker in name:
                quant = marker.upper()
                break
        combined_memory = info.ram_gb + info.vram_gb
        if size_gb <= combined_memory * 0.55:
            return ModelRecommendation(
                family="Existing local model",
                parameter_class=parameter_class,
                quantization=quant,
                reason=(
                    f"Existing {size_gb:.1f} GB GGUF detected. It fits the conservative combined "
                    f"RAM+VRAM candidate envelope; Apollo benchmark required before final recommendation."
                ),
            )

    combined_memory = info.ram_gb + info.vram_gb
    if combined_memory >= 30 and info.vram_gb >= 8:
        size, quant = "14B", "Q4-class"
    elif combined_memory >= 20 and info.vram_gb >= 6:
        size, quant = "8B", "Q4-class"
    elif info.ram_gb >= 12:
        size, quant = "7B", "Q4-class"
    else:
        size, quant = "3B", "Q4-class"
    return ModelRecommendation(
        family="Qwen-compatible instruct model",
        parameter_class=size,
        quantization=quant,
        reason=(
            f"Candidate selected from {info.ram_gb:.1f} GB RAM + {info.vram_gb:.1f} GB VRAM. "
            "Apollo benchmark is required before treating it as the final profile."
        ),
    )


def select_concurrency(results: list[ConcurrencyResult], max_latency_multiplier: float = 1.5) -> int:
    """Choose throughput sweet spot while preventing latency blow-ups."""
    valid = [r for r in results if r.concurrency > 0 and r.wall_seconds > 0 and r.throughput_rps > 0]
    if not valid:
        return 1
    baseline = min(valid, key=lambda r: r.concurrency)
    latency_limit = baseline.average_latency_seconds * max_latency_multiplier
    eligible = [r for r in valid if r.average_latency_seconds <= latency_limit]
    if not eligible:
        return baseline.concurrency
    return max(eligible, key=lambda r: (r.throughput_rps, -r.average_latency_seconds)).concurrency


def build_self_setup_plan(
    info: HardwareInfo,
    model_path: str = "",
    concurrency_results: list[ConcurrencyResult] | None = None,
) -> SelfSetupPlan:
    model = recommend_model(info, model_path)
    runtime = recommend_runtime(info, model_path)
    concurrency = select_concurrency(concurrency_results or [])
    return SelfSetupPlan(model=model, runtime=runtime, recommended_concurrency=concurrency, paper_only=True)


def model_present(model_path: str) -> bool:
    return bool(model_path and Path(model_path).expanduser().is_file())
