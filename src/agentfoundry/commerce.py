from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


TRIAL_DAYS = 14


class Plan(str, Enum):
    FREE = "free"
    TRIAL = "trial"
    PRO = "pro"


class Feature(str, Enum):
    HARDWARE_SCAN = "hardware_scan"
    BASIC_RUNTIME = "basic_runtime"
    BASIC_MODELS = "basic_models"
    SETUP_WIZARD = "setup_wizard"
    RESUMABLE_DOWNLOADS = "resumable_downloads"
    AUTO_TUNING = "auto_tuning"
    BENCHMARKS = "benchmarks"
    HERMES_AUTOMATION = "hermes_automation"
    PRO_UPDATES = "pro_updates"


FREE_FEATURES = {
    Feature.HARDWARE_SCAN,
    Feature.BASIC_RUNTIME,
    Feature.BASIC_MODELS,
}

PRO_FEATURES = set(Feature)


@dataclass
class Entitlement:
    plan: Plan = Plan.FREE
    trial_started_at: str = ""
    license_token: str = ""

    def trial_end(self) -> datetime | None:
        if not self.trial_started_at:
            return None
        try:
            started = datetime.fromisoformat(self.trial_started_at)
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            return started + timedelta(days=TRIAL_DAYS)
        except ValueError:
            return None

    def trial_active(self, now: datetime | None = None) -> bool:
        end = self.trial_end()
        if end is None:
            return False
        current = now or datetime.now(timezone.utc)
        return current < end

    def effective_plan(self, now: datetime | None = None) -> Plan:
        if self.plan == Plan.PRO:
            return Plan.PRO
        if self.plan == Plan.TRIAL and self.trial_active(now):
            return Plan.TRIAL
        return Plan.FREE

    def days_left(self, now: datetime | None = None) -> int:
        end = self.trial_end()
        if end is None:
            return 0
        current = now or datetime.now(timezone.utc)
        remaining = end - current
        if remaining.total_seconds() <= 0:
            return 0
        return max(1, remaining.days + (1 if remaining.seconds else 0))


def start_trial(entitlement: Entitlement, now: datetime | None = None) -> Entitlement:
    if entitlement.trial_started_at:
        return entitlement
    started = now or datetime.now(timezone.utc)
    entitlement.plan = Plan.TRIAL
    entitlement.trial_started_at = started.isoformat()
    return entitlement


def feature_available(
    entitlement: Entitlement,
    feature: Feature,
    now: datetime | None = None,
) -> bool:
    plan = entitlement.effective_plan(now)
    if plan in (Plan.PRO, Plan.TRIAL):
        return feature in PRO_FEATURES
    return feature in FREE_FEATURES
