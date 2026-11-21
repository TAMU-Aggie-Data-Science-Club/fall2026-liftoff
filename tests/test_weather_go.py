"""
Checks for the weather-go forecast parser in src/data/weather_go.py.

Run from the repo root, either way:
    python -m tests.test_weather_go     (no pytest needed)
    python -m pytest tests/             (if pytest is installed)
"""

import numpy as np
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


# --- low_weather_go model input (src/models/train_model.py) ---

def ts(text):
    return pd.Timestamp(text, tz="UTC")


def test_flag_threshold_and_blank():
    from src.models.train_model import low_weather_go_flag

    assert low_weather_go_flag(30) == 1.0
    assert low_weather_go_flag(50) == 0.0  # 50% GO is not "low"
    assert low_weather_go_flag(90) == 0.0
    assert np.isnan(low_weather_go_flag(None))


def test_cutoff_is_target_or_first_move():
    from src.models.train_model import forecast_cutoff

    baseline = pd.DataFrame(
        {"target": [ts("2025-01-10"), ts("2025-02-10")],
         "created_on": [ts("2025-01-01"), ts("2025-02-01")]},
        index=pd.Index(["kept", "moved"], name="launch_id"),
    )
    schedule = pd.DataFrame({
        "launch_id": ["kept", "kept", "moved", "moved"],
        "created_on": [ts("2025-01-01"), ts("2025-01-05"), ts("2025-02-01"), ts("2025-02-08")],
        # "kept": a later note repeats the target (within an hour) -> not a move.
        # "moved": a later note pushes the target two days -> cutoff at that note.
        "target": [ts("2025-01-10"), ts("2025-01-10 00:30"), ts("2025-02-10"), ts("2025-02-12")],
    })
    cutoff = forecast_cutoff(baseline, schedule)
    assert cutoff["kept"] == ts("2025-01-10")
    assert cutoff["moved"] == ts("2025-02-08")


def test_by_launch_ignores_forecasts_after_cutoff():
    from src.models.train_model import low_weather_go_by_launch

    updates = pd.DataFrame({
        "launch_id": ["a", "a", "b"],
        "created_on": ["2025-01-08T00:00Z", "2025-01-09T12:00Z", "2025-01-08T00:00Z"],
        "comment": ["Updated launch weather, 80% GO.", "Updated launch weather, 20% GO.",
                    "Weather 40%"],
    })
    cutoff = pd.Series({"a": ts("2025-01-09"), "b": ts("2025-01-09"), "c": ts("2025-01-09")})
    flags = low_weather_go_by_launch(updates, cutoff)
    assert flags["a"] == 0.0  # the 20% note came after the cutoff
    assert flags["b"] == 1.0
    assert np.isnan(flags["c"])  # no forecast -> blank, launch is kept


def test_optional_input_not_dropped():
    from src.models.train_model import usable_launches

    launches = pd.DataFrame({
        "launch_timestamp_utc": [ts("2025-01-01"), ts("2025-01-02")],
        "is_delayed": [0.0, 1.0],
        "wind_speed_10m": [10.0, None],
        "low_weather_go": [np.nan, 1.0],
    })
    kept = usable_launches(launches, "is_delayed", ["wind_speed_10m", "low_weather_go"])
    # Blank low_weather_go is kept; blank wind (a required input) is dropped.
    assert len(kept) == 1 and kept["wind_speed_10m"].iloc[0] == 10.0


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS  {name}")
    print(f"\nAll {len(tests)} checks passed.")
