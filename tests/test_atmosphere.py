"""
Checks for src/physics/atmosphere.py against published US76 values,
plus integration checks with forces.py.

Run from the repo root, either way:
    python -m tests.test_atmosphere      (no pytest needed)
    python -m pytest tests/              (if pytest is installed)
"""

import math

import numpy as np

from src.physics import atmosphere as atm
from src.physics import forces
from src.physics.constants import P0, RHO0, T0, US76_EARTH_RADIUS_M


def close(a, b, rel=1e-9, abs_=0.0):
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


def geometric(z):
    """Geopotential z -> geometric h (inverse of geopotential_altitude)."""
    return US76_EARTH_RADIUS_M * z / (US76_EARTH_RADIUS_M - z)


# ---- sea level -------------------------------------------------------------
def test_sea_level():
    T, p, rho, a = atm.atmosphere(0.0)
    assert T == T0 and p == P0
    assert close(rho, RHO0, rel=1e-6)
    assert close(a, 340.294, rel=1e-5)


# ---- published US76 values (geometric altitude) ----------------------------
# h [m]: (T [K], p [Pa], rho [kg/m^3])  from the US Standard Atmosphere 1976 tables
US76_TABLE = {
    10_000: (223.252, 26_499.9, 0.41351),
    30_000: (226.509, 1_197.0, 1.8410e-2),
    50_000: (270.65, 79.779, 1.0269e-3),
    80_000: (198.639, 1.0524, 1.8458e-5),
}


def test_matches_us76_tables():
    for h, (T_ref, p_ref, rho_ref) in US76_TABLE.items():
        s = atm.atmosphere(h)
        assert close(s.T, T_ref, rel=1e-4), (h, s.T, T_ref)
        assert close(s.p, p_ref, rel=1e-3), (h, s.p, p_ref)
        assert close(s.rho, rho_ref, rel=1e-3), (h, s.rho, rho_ref)


def test_layer_bases_match_physics_md():
    # PHYSICS.md 3.5 table: base z [m] -> (T_b [K], p_b [Pa])
    bases = {
        11_000: (216.65, 22_632.06),
        20_000: (216.65, 5_474.889),
        32_000: (228.65, 868.0187),
        47_000: (270.65, 110.9063),
        51_000: (270.65, 66.93887),
        71_000: (214.65, 3.956420),
    }
    for z, (T_b, p_b) in bases.items():
        s = atm.atmosphere(geometric(z))
        assert close(s.T, T_b, rel=1e-9, abs_=1e-6), (z, s.T)
        assert close(s.p, p_b, rel=1e-4), (z, s.p)


def test_continuous_at_layer_boundaries():
    for z in [11_000, 20_000, 32_000, 47_000, 51_000, 71_000, 84_852]:
        h = geometric(z)
        lo, hi = atm.atmosphere(h - 1e-3), atm.atmosphere(h + 1e-3)
        assert close(lo.T, hi.T, rel=1e-6)
        assert close(lo.p, hi.p, rel=1e-6)


def test_above_top_isothermal_and_positive():
    for h in [90_000, 150_000, 300_000]:
        s = atm.atmosphere(h)
        assert close(s.T, 186.946, rel=1e-6)
        assert s.p > 0 and s.rho > 0


def test_pressure_density_decrease_with_altitude():
    h = np.linspace(0, 150_000, 3001)
    s = atm.atmosphere(h)
    assert np.all(np.diff(s.p) < 0)
    assert np.all(np.diff(s.rho) < 0)


def test_ideal_gas_and_speed_of_sound_consistent():
    h = np.array([0.0, 5_000.0, 25_000.0, 60_000.0])
    s = atm.atmosphere(h)
    assert np.allclose(s.p, s.rho * 287.05287 * s.T)
    assert np.allclose(s.a, atm.speed_of_sound(s.T))


def test_geopotential_altitude():
    assert atm.geopotential_altitude(0.0) == 0.0
    assert close(atm.geopotential_altitude(geometric(11_000)), 11_000, rel=1e-12)


def test_below_sea_level_ok():
    s = atm.atmosphere(-100.0)
    assert s.T > T0 and s.p > P0


def test_exponential_model():
    s = atm.atmosphere(8_500.0, model="exponential")
    assert close(s.rho, RHO0 / math.e)
    assert close(s.p, P0 / math.e)
    assert s.T == T0


def test_bad_model():
    try:
        atm.atmosphere(0.0, model="isa")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_scalar_and_array_types():
    assert isinstance(atm.atmosphere(1000.0).p, float)
    assert atm.atmosphere(np.array([0.0, 1000.0])).p.shape == (2,)


# ---- integration with forces.py --------------------------------------------
T_SL, T_VAC = 7.607e6, 8.227e6  # Falcon 9 stage 1 (approx.)


def test_thrust_at_sea_level_is_t_sl():
    assert close(forces.thrust(atm.atmosphere(0.0).p, T_SL, T_VAC), T_SL)


def test_thrust_approaches_vacuum():
    T = forces.thrust(atm.atmosphere(100_000.0).p, T_SL, T_VAC)
    assert T_SL < T <= T_VAC and close(T, T_VAC, rel=1e-6)


def test_drag_and_mach_pipeline():
    # F9-sized body at 10 km, 400 m/s straight up
    s = atm.atmosphere(10_000.0)
    mach = 400.0 / s.a
    cd = forces.cd_from_mach(mach, [0.0, 0.8, 1.0, 1.2, 3.0], [0.3, 0.35, 0.6, 0.55, 0.35])
    dx, dy = forces.drag_force(0.0, 400.0, s.rho, cd, forces.reference_area(3.66))
    q = forces.dynamic_pressure(s.rho, 400.0)
    assert 1.2 < mach < 1.4
    assert dx == 0.0 and dy < 0
    assert close(-dy, q * cd * forces.reference_area(3.66))


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS  {name}")
    print(f"\nAll {len(tests)} checks passed.")
