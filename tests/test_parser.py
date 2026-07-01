"""Unit tests for the iLMeteo box-widget HTML parser.

Run with:  python -m pytest tests/  (or just python tests/test_parser.py)
These tests have no Home Assistant dependency.
"""
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "ilmeteo")
)

from api import parse_box, wind_bearing, parse_real1, parse_day1  # noqa: E402
from const import map_condition  # noqa: E402
import location_data as _ld  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "box_b_roma.html")


def _load():
    with open(SAMPLE, encoding="utf-8") as f:
        return parse_box(f.read())


def test_city_and_date():
    data = _load()
    assert data["city"] == "Roma"
    assert data["date"] == "19/06/2026"


def test_city_url():
    data = _load()
    assert data["url"] == "https://www.ilmeteo.it/meteo/roma"


def test_hour_count():
    data = _load()
    assert len(data["hours"]) == 5


def test_first_slot_values():
    h = _load()["hours"][0]
    assert h["time"] == "11.00"
    assert h["temperature"] == 32.9
    assert h["humidity"] == 41.0
    assert h["wind_dir"] == "NW"
    assert h["wind_speed"] == 5.0
    assert h["precipitation"] == 0.0


def test_night_code_detection():
    # Last slot (23.00) carries a night sprite code (1xx)
    h = _load()["hours"][-1]
    assert h["condition_code"].startswith("10") or int(h["condition_code"]) >= 100


def test_wind_bearing():
    assert wind_bearing("N") == 0
    assert wind_bearing("WSW") == 247.5
    assert wind_bearing("O") == 270  # Italian Ovest
    assert wind_bearing(None) is None


def test_condition_day_night():
    assert map_condition("Sereno", "1") == "sunny"
    assert map_condition("Sereno", "101") == "clear-night"
    assert map_condition("Temporale", "10") == "lightning-rainy"
    assert map_condition("qualcosa di ignoto", "999") is None



# --- Location dataset tests ---


def test_dataset_regions():
    regions = _ld.get_regions()
    assert len(regions) == 20
    assert "Lombardia" in regions
    assert "Lazio" in regions


def test_dataset_resolve_roma():
    assert _ld.resolve_code("Lazio", "Roma (RM)", "Roma") == "5913"


def test_dataset_provinces_sorted():
    provs = _ld.get_provinces("Lombardia")
    assert provs == sorted(provs)
    assert "Milano (MI)" in provs


# --- real1 (real-time current conditions) parser tests ---

REAL1_SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "real1_roma.html")


def test_real1_parses_current_conditions():
    with open(REAL1_SAMPLE, encoding="utf-8") as f:
        data = parse_real1(f.read())
    assert data["condition_text"] == "Sole e caldo"
    assert data["condition_code"] == "2"
    assert data["hour"] == "12:30"
    assert data["temperature"] == 35.0
    assert data["humidity"] == 21.0
    assert data["wind_dir"] == "WNW"
    assert data["wind_speed"] == 8.0
    assert data["wind_desc"] == "debole"


def test_real1_handles_styled_temperature_tag():
    # Regression: inline-styled <b> tag, not bare <b>
    with open(REAL1_SAMPLE, encoding="utf-8") as f:
        data = parse_real1(f.read())
    assert data["temperature"] is not None


def test_real1_handles_html_entities():
    # Regression: HTML entities (&agrave; &nbsp; &deg;), not literal chars
    with open(REAL1_SAMPLE, encoding="utf-8") as f:
        data = parse_real1(f.read())
    assert data["humidity"] == 21.0  # from "Umidit&agrave;: 21%"
    assert data["wind_speed"] == 8.0  # from "8&nbsp;km/h"


def test_real1_ignores_unrelated_title_bar_link():
    # Regression: unrelated <a> earlier in the page must not be matched
    with open(REAL1_SAMPLE, encoding="utf-8") as f:
        data = parse_real1(f.read())
    assert data["condition_text"] != "Roma"
    assert data["condition_text"] == "Sole e caldo"


# --- day1 (official daily min/max) parser tests ---

DAY1_SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "day1_roma.html")


def test_day1_parses_six_days():
    with open(DAY1_SAMPLE, encoding="utf-8") as f:
        days = parse_day1(f.read())
    assert len(days) == 6


def test_day1_parses_all_fields_correctly():
    # Values verified against ilmeteo.it's live forecast for this layout
    with open(DAY1_SAMPLE, encoding="utf-8") as f:
        days = parse_day1(f.read())
    expected = [
        (19.0, 36.0, 5.0),
        (19.0, 36.0, 25.0),
        (20.0, 34.0, 10.0),
        (19.0, 34.0, 10.0),
        (19.0, 35.0, 10.0),
        (19.0, 35.0, 10.0),
    ]
    for day, (tmin, tmax, prob) in zip(days, expected):
        assert day["temp_min"] == tmin
        assert day["temp_max"] == tmax
        assert day["precipitation_probability"] == prob


def test_day1_precip_probability_not_confused_by_nested_markup():
    # Regression: nested mini-table / width=100% must not break parsing
    with open(DAY1_SAMPLE, encoding="utf-8") as f:
        days = parse_day1(f.read())
    assert days[1]["precipitation_probability"] == 25.0  # not 100.0


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
