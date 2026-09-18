from agentfoundry.hardware import HardwareInfo
from agentfoundry.self_setup import ConcurrencyResult, build_self_setup_plan, recommend_model, select_concurrency


def machine(ram: float = 32, vram: float = 12) -> HardwareInfo:
    return HardwareInfo("Windows", "11", "AMD64", "CPU", ram, "GPU", vram)


def test_model_recommendation_scales_with_memory() -> None:
    assert recommend_model(machine(32, 12)).parameter_class == "14B"
    assert recommend_model(machine(16, 6)).parameter_class == "8B"
    assert recommend_model(machine(8, 4)).parameter_class == "3B"


def test_concurrency_selector_finds_two_slot_sweet_spot() -> None:
    results = [
        ConcurrencyResult(1, 5.65, 0.177, 5.64),
        ConcurrencyResult(2, 4.62, 0.433, 4.62),
        ConcurrencyResult(4, 9.09, 0.440, 9.02),
    ]
    assert select_concurrency(results) == 2


def test_setup_plan_stays_paper_only() -> None:
    plan = build_self_setup_plan(machine())
    assert plan.paper_only is True
    assert plan.recommended_concurrency == 1
