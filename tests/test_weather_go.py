"""
Checks for the weather-go forecast parser in src/data/weather_go.py.

Run from the repo root, either way:
    python -m tests.test_weather_go     (no pytest needed)
    python -m pytest tests/             (if pytest is installed)
"""

import pandas as pd

from src.data.weather_go import latest_weather_go, parse_weather_go


def test_parse_common_phrasings():
    assert parse_weather_go("Updated launch weather, 55% GO.") == 55
    assert parse_weather_go("Updated launch weather, >95% GO.") == 95
    assert parse_weather_go("Weather 80%") == 80
    assert parse_weather_go("Updating Weather POG to 40%") == 40
    assert parse_weather_go("Updated launch weather, 90% at start of window (75% at end).") == 90


def test_parse_ignores_non_forecasts():
    assert parse_weather_go("Hold at T-00:27 due to launch site weather.") is None
    assert parse_weather_go("Payload fairing 100% integrated.") is None  # not about weather
    assert parse_weather_go("Weather forecast per https://x.io/Falcon%209%20Crew.pdf") is None
    assert parse_weather_go(None) is None


def test_latest_respects_as_of():
    updates = pd.DataFrame({
        "launch_id": ["a", "a", "a", "b"],
        "created_on": ["2025-01-01T00:00Z", "2025-01-02T00:00Z", "2025-01-03T00:00Z", "2025-01-02T00:00Z"],
        "comment": ["Updated launch weather, 70% GO.", "Now targeting Jan 5",
                    "Updated launch weather, 30% GO.", "Weather 90%"],
    })
    # The 30% note is after as_of, so the 70% one is the latest known value.
    assert latest_weather_go(updates, "a", pd.Timestamp("2025-01-02T12:00Z")) == 70
    assert latest_weather_go(updates, "a", pd.Timestamp("2025-01-04T00:00Z")) == 30
    assert latest_weather_go(updates, "a", pd.Timestamp("2024-12-31T00:00Z")) is None
    assert latest_weather_go(updates, "c", pd.Timestamp("2025-01-04T00:00Z")) is None


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS  {name}")
    print(f"\nAll {len(tests)} checks passed.")
