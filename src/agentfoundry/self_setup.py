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


def recommend_model(info: HardwareInfo) -> ModelRecommendation:
    """Recommend a local model class without downloading or trusting a remote binary."""
    if info.ram_gb >= 28 and info.vram_gb >= 10:
        size, quant = "14B", "Q4-class"
    elif info.ram_gb >= 16:
        size, quant = "8B", "Q4-class"
    else:
        size, quant = "3B", "Q4-class"
    return ModelRecommendation(
        family="Qwen-compatible instruct model",
        parameter_class=size,
        quantization=quant,
        reason=f"Selected for {info.ram_gb:.1f} GB RAM and {info.vram_gb:.1f} GB VRAM.",
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
    model = recommend_model(info)
    runtime = recommend_runtime(info, model_path)
    concurrency = select_concurrency(concurrency_results or [])
    return SelfSetupPlan(model=model, runtime=runtime, recommended_concurrency=concurrency, paper_only=True)


def model_present(model_path: str) -> bool:
    return bool(model_path and Path(model_path).expanduser().is_file())
