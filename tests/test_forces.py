"""
Sample-value checks for src/physics/forces.py.

Run from the repo root, either way:
    python -m tests.test_forces      (no pytest needed)
    python -m pytest tests/          (if pytest is installed)
"""

import math

import numpy as np

from src.physics import forces
from src.physics.constants import G0, P0

# Falcon 9 first stage (published approx.): 9 Merlin 1D
T_SL = 7.607e6   # N
T_VAC = 8.227e6  # N
D_F9 = 3.66      # m


def close(a, b, rel=1e-9, abs_=1e-9):
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


# ---- gravity ----
def test_gravity_constant_default():
    assert forces.gravity(0) == G0
    assert forces.gravity(100_000) == G0  # default model ignores altitude


def test_gravity_inverse_square():
    assert close(forces.gravity(0, "inverse_square"), G0)
    assert close(forces.gravity(100_000, "inverse_square"), 9.505897, rel=1e-6)


def test_gravity_bad_model():
    try:
        forces.gravity(0, "flat")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# ---- thrust ----
def test_thrust_endpoints():
    assert close(forces.thrust(P0, T_SL, T_VAC), T_SL)
    assert close(forces.thrust(0.0, T_SL, T_VAC), T_VAC)


def test_thrust_midpoint():
    assert close(forces.thrust(P0 / 2, T_SL, T_VAC), 7.917e6, rel=1e-9)


def test_exit_area():
    assert close(forces.nozzle_exit_area(T_SL, T_VAC), 6.118924, rel=1e-6)


def test_thrust_rejects_vac_below_sl():
    try:
        forces.thrust(P0, T_VAC, T_SL)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_mass_flow_rate():
    # 8.227 MN / (9.80665 * 311 s) ~= 2697.5 kg/s
    assert close(forces.mass_flow_rate(T_VAC, 311.0), T_VAC / (G0 * 311.0))


# ---- drag ----
def test_reference_area():
    assert close(forces.reference_area(D_F9), 10.520880, rel=1e-6)


def test_dynamic_pressure():
    assert close(forces.dynamic_pressure(1.225, 100.0), 6125.0)


def test_drag_vertical():
    a = forces.reference_area(D_F9)
    dx, dy = forces.drag_force(0.0, 100.0, 1.225, 0.5, a)
    assert dx == 0.0
    assert close(dy, -32220.19389, rel=1e-6)


def test_drag_zero_velocity_no_nan():
    dx, dy = forces.drag_force(0.0, 0.0, 1.225, 0.5, 10.0)
    assert dx == 0.0 and dy == 0.0


def test_drag_opposes_velocity():
    dx, dy = forces.drag_force(100.0, 100.0, 1.225, 0.5, 10.0)
    assert dx < 0 and dy < 0 and close(dx, dy)


def test_drag_scales_with_v_squared():
    d1 = np.hypot(*forces.drag_force(30.0, 40.0, 1.0, 0.3, 2.0))
    d2 = np.hypot(*forces.drag_force(60.0, 80.0, 1.0, 0.3, 2.0))
    assert close(d2 / d1, 4.0)


def test_drag_magnitude_equals_q_cd_a():
    q = forces.dynamic_pressure(0.5, 250.0)
    d = np.hypot(*forces.drag_force(150.0, 200.0, 0.5, 0.4, 3.0))
    assert close(d, q * 0.4 * 3.0)


def test_cd_from_mach_interp_and_clamp():
    m, cd = [0.0, 1.0, 2.0], [0.3, 0.6, 0.4]
    assert close(forces.cd_from_mach(0.5, m, cd), 0.45)
    assert close(forces.cd_from_mach(-1.0, m, cd), 0.3)
    assert close(forces.cd_from_mach(5.0, m, cd), 0.4)


def test_vectorised_inputs():
    h = np.array([0.0, 50_000.0, 100_000.0])
    assert forces.gravity(h).shape == (3,)
    assert forces.thrust(np.array([P0, 0.0]), T_SL, T_VAC).shape == (2,)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS  {name}")
    print(f"\nAll {len(tests)} checks passed.")
