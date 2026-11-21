"""
Checks for the low_weather_go input in src/models/train_random_forest.py.

Run from the repo root, either way:
    python -m tests.test_random_forest   (no pytest needed)
    python -m pytest tests/              (if pytest is installed)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# train_random_forest imports train_model as a top-level module (it is run as a script).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "models"))
import train_random_forest as rf  # noqa: E402


def ts(text):
    return pd.Timestamp(text, tz="UTC")


def test_flag_threshold_and_blank():
    assert rf.low_weather_go_flag(30) == 1.0
    assert rf.low_weather_go_flag(50) == 0.0  # 50% GO is not "low"
    assert np.isnan(rf.low_weather_go_flag(None))


def test_forecast_after_target_move_is_ignored():
    launches = pd.DataFrame({
        "launch_id": ["kept", "moved", "none"],
        "launch_timestamp_utc": [ts("2025-01-10"), ts("2025-02-14"), ts("2025-03-10")],
    })
    updates = pd.DataFrame({
        "launch_id": ["kept", "kept", "moved", "moved", "moved", "none"],
        "created_on": ["2025-01-01T00:00Z", "2025-01-09T00:00Z",
                       "2025-02-01T00:00Z", "2025-02-08T00:00Z", "2025-02-09T00:00Z",
                       "2025-03-01T00:00Z"],
        "comment": ["Now targeting Jan 10 at 00:00 UTC", "Updated launch weather, 30% GO.",
                    "Now targeting Feb 10 at 00:00 UTC", "Delayed to Feb 14 at 00:00 UTC",
                    "Updated launch weather, 20% GO.",  # after the move -> must not count
                    "Now targeting Mar 10 at 00:00 UTC"],
    })
    cutoff = rf.forecast_cutoff(launches, updates)
    assert cutoff["kept"] == ts("2025-01-10")
    assert cutoff["moved"] == ts("2025-02-08")

    flags = rf.add_low_weather_go(launches, updates).set_index("launch_id")["low_weather_go"]
    assert flags["kept"] == 1.0
    assert np.isnan(flags["moved"])
    assert np.isnan(flags["none"])  # no forecast -> blank


def test_rf_features_without_the_optional_column():
    df = pd.DataFrame({c: [1.0] for c in rf.RF_NUMERIC_FEATURES if c != "low_weather_go"})
    df["rocket_type"] = "Falcon 9"
    features = rf.rf_features(df, ["Falcon 9"])
    assert np.isnan(features["low_weather_go"].iloc[0])


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS  {name}")
    print(f"\nAll {len(tests)} checks passed.")
