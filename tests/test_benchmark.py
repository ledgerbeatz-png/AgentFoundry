from agentfoundry.benchmark import BenchmarkResult, ModelComparisonOutcome, select_best_result


def test_select_best_result_prefers_highest_throughput() -> None:
    results = [
        BenchmarkResult(gpu_layers=12, stable=True, latency_seconds=4.0, completion_tokens=20, tokens_per_second=5.0),
        BenchmarkResult(gpu_layers=20, stable=True, latency_seconds=2.5, completion_tokens=20, tokens_per_second=8.0),
        BenchmarkResult(gpu_layers=24, stable=False, error="out of memory"),
    ]

    best = select_best_result(results)

    assert best is not None
    assert best.gpu_layers == 20


def test_select_best_result_returns_none_without_stable_run() -> None:
    results = [
        BenchmarkResult(gpu_layers=20, stable=False, error="failed"),
        BenchmarkResult(gpu_layers=24, stable=False, error="failed"),
    ]

    assert select_best_result(results) is None


def test_model_comparison_outcome_reports_gibibytes() -> None:
    outcome = ModelComparisonOutcome(
        name="demo",
        result=BenchmarkResult(gpu_layers=20, stable=True, tokens_per_second=7.5),
        model_size_bytes=6 * 1024 ** 3,
        context=32768,
    )

    assert outcome.model_size_gb == 6.0
    assert outcome.context == 32768
