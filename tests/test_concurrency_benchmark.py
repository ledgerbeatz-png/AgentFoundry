from agentfoundry.benchmark import ConcurrencyBenchmarkSummary
from agentfoundry.self_setup import ConcurrencyResult, select_concurrency


def test_observed_qwen_profile_recommends_two_workers() -> None:
    results = [
        ConcurrencyResult(1, 5.65, 0.177, 5.64),
        ConcurrencyResult(2, 4.62, 0.433, 4.62),
        ConcurrencyResult(4, 9.09, 0.440, 9.02),
    ]
    summary = ConcurrencyBenchmarkSummary(results, select_concurrency(results))
    assert summary.recommended_concurrency == 2
