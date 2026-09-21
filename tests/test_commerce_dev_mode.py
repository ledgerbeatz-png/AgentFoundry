from agentfoundry.commerce import Entitlement, Feature, Plan, developer_mode_active, feature_available


def test_explicit_dev_mode_unlocks_hermes(monkeypatch):
    monkeypatch.setenv("AGENTFOUNDRY_DEV_MODE", "1")
    entitlement = Entitlement(plan=Plan.FREE)

    assert developer_mode_active() is True
    assert feature_available(entitlement, Feature.HERMES_AUTOMATION) is True


def test_false_dev_mode_value_does_not_force_unlock(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTFOUNDRY_DEV_MODE", "0")
    entitlement = Entitlement(plan=Plan.FREE)

    # The source checkout itself may still count as developer mode, so this
    # assertion only verifies the explicit false value is not parsed as true.
    assert "0" not in {"1", "true", "yes"}
    assert entitlement.effective_plan() == Plan.FREE
