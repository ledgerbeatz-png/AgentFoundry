from datetime import datetime, timedelta, timezone

from agentfoundry.commerce import (
    Entitlement,
    Feature,
    Plan,
    feature_available,
    start_trial,
)


def test_free_plan_has_only_free_features() -> None:
    entitlement = Entitlement(plan=Plan.FREE)

    assert feature_available(entitlement, Feature.HARDWARE_SCAN)
    assert feature_available(entitlement, Feature.BASIC_RUNTIME)
    assert not feature_available(entitlement, Feature.BENCHMARKS)
    assert not feature_available(entitlement, Feature.HERMES_AUTOMATION)


def test_trial_unlocks_pro_features() -> None:
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    entitlement = Entitlement(plan=Plan.FREE)
    start_trial(entitlement, now=now)

    assert entitlement.effective_plan(now) == Plan.TRIAL
    assert feature_available(entitlement, Feature.BENCHMARKS, now=now)
    assert feature_available(entitlement, Feature.RESUMABLE_DOWNLOADS, now=now)


def test_expired_trial_falls_back_to_free() -> None:
    started = datetime(2026, 9, 1, tzinfo=timezone.utc)
    now = started + timedelta(days=15)
    entitlement = Entitlement(
        plan=Plan.TRIAL,
        trial_started_at=started.isoformat(),
    )

    assert entitlement.effective_plan(now) == Plan.FREE
    assert not feature_available(entitlement, Feature.BENCHMARKS, now=now)


def test_trial_cannot_be_restarted_locally() -> None:
    started = datetime(2026, 9, 1, tzinfo=timezone.utc)
    entitlement = Entitlement(
        plan=Plan.TRIAL,
        trial_started_at=started.isoformat(),
    )

    start_trial(entitlement, now=datetime(2026, 10, 1, tzinfo=timezone.utc))

    assert entitlement.trial_started_at == started.isoformat()


def test_pro_unlocks_all_features() -> None:
    entitlement = Entitlement(plan=Plan.PRO)

    for feature in Feature:
        assert feature_available(entitlement, feature)
