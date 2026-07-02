"""Unit tests for alert providers (alerts.py).

Run with:  python -m pytest tests/  (or just python tests/test_alerts.py)
No Home Assistant dependency: HeuristicAlertProvider is pure, and
DpcSensorAlertProvider only needs hass.states.get(), stubbed here with a
minimal fake instead of importing homeassistant.
"""
import asyncio
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "ilmeteo")
)

from alerts import DpcSensorAlertProvider, HeuristicAlertProvider  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def _ids(alerts):
    return {a.alert_id for a in alerts}


# --- HeuristicAlertProvider ---------------------------------------------

def _coordinator_data(daily=None, days=None, current=None):
    return {"daily": daily or [], "days": days or [], "current": current or {}}


def test_no_alerts_on_empty_data():
    alerts = _run(HeuristicAlertProvider().async_get_alerts(_coordinator_data(), "1", "Roma"))
    assert alerts == []


def test_heat_thresholds_today():
    data = _coordinator_data(daily=[{"temp_max": 39}, {}])
    alerts = _run(HeuristicAlertProvider().async_get_alerts(data, "1", "Roma"))
    a = [x for x in alerts if x.alert_id == "heuristic_heat_today"]
    assert len(a) == 1
    assert a[0].severity == "orange"


def test_heat_below_threshold_no_alert():
    data = _coordinator_data(daily=[{"temp_max": 30}])
    alerts = _run(HeuristicAlertProvider().async_get_alerts(data, "1", "Roma"))
    assert not any(a.kind == "heat" for a in alerts)


def test_today_and_tomorrow_are_independent_alerts():
    data = _coordinator_data(daily=[{"temp_max": 39}, {"temp_max": 20, "temp_min": -6}])
    alerts = _run(HeuristicAlertProvider().async_get_alerts(data, "1", "Roma"))
    ids = _ids(alerts)
    assert "heuristic_heat_today" in ids
    assert "heuristic_heat_tomorrow" not in ids
    assert "heuristic_cold_tomorrow" in ids
    assert "heuristic_cold_today" not in ids


def test_current_wind_only_applies_to_today():
    # wind_speed only in "current" (real1), not in the daily summary for
    # either day: today should pick it up via fallback, tomorrow must not.
    data = _coordinator_data(
        daily=[{}, {}],
        current={"wind_speed": 70},
    )
    alerts = _run(HeuristicAlertProvider().async_get_alerts(data, "1", "Roma"))
    ids = _ids(alerts)
    assert "heuristic_wind_today" in ids
    assert "heuristic_wind_tomorrow" not in ids


def test_hail_detected_from_condition_text():
    data = _coordinator_data(days=[{"hours": [{"condition_text": "Grandine forte"}]}])
    alerts = _run(HeuristicAlertProvider().async_get_alerts(data, "1", "Roma"))
    assert "heuristic_hail_today" in _ids(alerts)


def test_storm_severity_escalation():
    mild = _coordinator_data(days=[{"hours": [{"condition_text": "Temporale"}]}])
    strong = _coordinator_data(days=[{"hours": [{"condition_text": "Temporali forti"}]}])
    mild_alerts = _run(HeuristicAlertProvider().async_get_alerts(mild, "1", "Roma"))
    strong_alerts = _run(HeuristicAlertProvider().async_get_alerts(strong, "1", "Roma"))
    mild_storm = next(a for a in mild_alerts if a.alert_id == "heuristic_storm_today")
    strong_storm = next(a for a in strong_alerts if a.alert_id == "heuristic_storm_today")
    assert mild_storm.severity == "yellow"
    assert strong_storm.severity == "orange"


def test_rain_probability_threshold():
    data = _coordinator_data(daily=[{"precipitation_probability": 85}])
    alerts = _run(HeuristicAlertProvider().async_get_alerts(data, "1", "Roma"))
    assert "heuristic_rain_today" in _ids(alerts)


def test_signature_changes_with_severity():
    from alerts import WeatherAlert
    a = WeatherAlert("x", "yellow", "heat", "t", "m", "heuristic")
    b = WeatherAlert("x", "orange", "heat", "t", "m", "heuristic")
    assert a.signature != b.signature


# --- DpcSensorAlertProvider ----------------------------------------------

class _FakeState:
    def __init__(self, state, attributes):
        self.state = state
        self.attributes = attributes


class _FakeStates:
    def __init__(self, state):
        self._state = state

    def get(self, entity_id):
        return self._state


class _FakeHass:
    def __init__(self, state):
        self.states = _FakeStates(state)


def test_dpc_missing_entity_returns_no_alerts():
    hass = _FakeHass(None)
    provider = DpcSensorAlertProvider(hass, "sensor.dpc_alert")
    alerts = _run(provider.async_get_alerts(_coordinator_data(), "1", "Roma"))
    assert alerts == []


def test_dpc_unavailable_state_returns_no_alerts():
    hass = _FakeHass(_FakeState("unavailable", {}))
    provider = DpcSensorAlertProvider(hass, "sensor.dpc_alert")
    alerts = _run(provider.async_get_alerts(_coordinator_data(), "1", "Roma"))
    assert alerts == []


def test_dpc_events_today_and_tomorrow():
    state = _FakeState("2", {
        "events_today": [
            {"risk": "Temporali", "alert": "Allerta arancione", "level": 3, "info": "info"},
        ],
        "events_tomorrow": [
            {"risk": "Idrogeologico", "alert": "Allerta gialla", "level": 2, "info": "info2"},
        ],
    })
    hass = _FakeHass(state)
    provider = DpcSensorAlertProvider(hass, "sensor.dpc_alert")
    alerts = _run(provider.async_get_alerts(_coordinator_data(), "1", "Roma"))
    ids = _ids(alerts)
    assert "dpc_temporali_events_today" in ids
    assert "dpc_idrogeologico_events_tomorrow" in ids
    today = next(a for a in alerts if a.alert_id == "dpc_temporali_events_today")
    assert today.severity == "orange"
    assert today.source == "protezione_civile"


def test_dpc_ignores_level_below_2():
    state = _FakeState("1", {
        "events_today": [{"risk": "Temporali", "alert": "Verde", "level": 1, "info": ""}],
    })
    hass = _FakeHass(state)
    provider = DpcSensorAlertProvider(hass, "sensor.dpc_alert")
    alerts = _run(provider.async_get_alerts(_coordinator_data(), "1", "Roma"))
    assert alerts == []


def test_dpc_falls_back_to_aggregate_today_tomorrow():
    # Older component versions: no events_today/events_tomorrow attributes.
    state = _FakeState("3", {"today": {"alert": "Allerta arancione", "level": 3, "info": "x"}})
    hass = _FakeHass(state)
    provider = DpcSensorAlertProvider(hass, "sensor.dpc_alert")
    alerts = _run(provider.async_get_alerts(_coordinator_data(), "1", "Roma"))
    assert _ids(alerts) == {"dpc_today"}


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    sys.exit(1 if failed else 0)
