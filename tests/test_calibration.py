"""
Checks for the delay model's Platt calibration in src/models/train_model.py.

Run from the repo root, either way:
    python -m tests.test_calibration    (no pytest needed)
    python -m pytest tests/             (if pytest is installed)
"""

import math

import numpy as np
import pandas as pd

from src.models import train_model as tm


def close(a, b, abs_=1e-6):
    return math.isclose(a, b, abs_tol=abs_)


def test_platt_identity():
    # Slope 1, intercept 0 leaves the score unchanged.
    scores = np.array([0.01, 0.2, 0.5, 0.9])
    assert np.allclose(tm.platt(scores, 1.0, 0.0), scores)


def test_fit_platt_recovers_known_curve():
    # Labels drawn from a known calibration curve; the fit should land near it.
    rng = np.random.default_rng(0)
    scores = rng.uniform(0.02, 0.98, 20_000)
    labels = rng.uniform(size=scores.size) < tm.platt(scores, 0.5, -1.5)
    slope, intercept = tm.fit_platt(scores, labels)
    assert abs(slope - 0.5) < 0.05
    assert abs(intercept + 1.5) < 0.05


def test_fit_platt_matches_base_rate_without_signal():
    # Scores unrelated to the label: slope ~0 and the output ~the base rate.
    rng = np.random.default_rng(1)
    scores = rng.uniform(0.02, 0.98, 20_000)
    labels = rng.uniform(size=scores.size) < 0.1
    slope, intercept = tm.fit_platt(scores, labels)
    assert abs(slope) < 0.05
    assert abs(tm.platt(scores, slope, intercept).mean() - labels.mean()) < 0.01


def test_fit_platt_needs_both_outcomes():
    try:
        tm.fit_platt(np.array([0.2, 0.4]), np.array([0, 0]))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_predict_delay_probability_applies_calibration():
    rng = np.random.default_rng(2)
    n = 200
    df = pd.DataFrame({
        "temperature_2m": rng.normal(20, 5, n),
        "wind_speed_10m": rng.uniform(0, 40, n),
        "precipitation": rng.uniform(0, 2, n),
        "cloud_cover": rng.uniform(0, 100, n),
        "payload_mass_kg": rng.uniform(1000, 17000, n),
        "rocket_type": "Falcon 9",
    })
    df["is_delayed"] = (df["wind_speed_10m"] + rng.normal(0, 10, n) > 30).astype(int)
    categories = ["Falcon 9"]
    booster = tm.train(df, "is_delayed", categories)
    saved = {
        "rocket_categories": categories,
        "models": {"delay": {"booster": booster,
                             "calibration": {"slope": 0.5, "intercept": -2.0}}},
    }
    raw = tm.predict_probability(booster, df, categories)
    calibrated = tm.predict_delay_probability(saved, df)
    assert np.allclose(calibrated, tm.platt(raw, 0.5, -2.0))
    # A positive slope keeps the order of the raw scores.
    assert (np.argsort(raw, kind="stable") == np.argsort(calibrated, kind="stable")).all()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS  {name}")
    print(f"\nAll {len(tests)} checks passed.")
