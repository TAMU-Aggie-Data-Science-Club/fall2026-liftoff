"""
Force models for the Liftoff trajectory simulator (PHYSICS.md section 3).

Frame: 2D flat, non-rotating Earth (see constants.py).
    x  downrange from the pad [m]
    h  geometric altitude above mean sea level, up positive [m]

All functions are pure: no state, no I/O, no Streamlit. Inputs and outputs are SI.
Scalars return floats; numpy arrays are accepted and return arrays (handy for plots/tests).

Atmospheric state (density rho, ambient pressure p) is passed IN as an argument rather
than computed here, so these functions work with any atmosphere model (US76 or the
exponential hand-check model) and do not depend on the atmosphere module.

Assumptions (PHYSICS.md section 5):
    - Point mass, zero angle of attack -> no lift, drag acts along -v_hat
    - No wind: velocity relative to the air == velocity in the ground frame
    - Thrust direction (guidance) and burnout switching are handled by the caller
"""

import numpy as np

from .constants import EARTH_RADIUS_M, G0, P0

GRAVITY_MODELS = ("constant", "inverse_square")


def _out(arr):
    """Return a Python float for 0-d results, otherwise the numpy array."""
    arr = np.asarray(arr, dtype=float)
    return float(arr) if arr.ndim == 0 else arr


# --------------------------------------------------------------------------- #
# Gravity (PHYSICS.md 3.1)
# --------------------------------------------------------------------------- #
def gravity(h, model="constant"):
    """
    Gravitational acceleration magnitude, acting in -h [m/s^2].

    Parameters
    ----------
    h : float or array   altitude above mean sea level [m]
    model : str
        "constant"        g = G0                          (default; matches flat Earth)
        "inverse_square"  g = G0 * (R_E / (R_E + h))^2    (~3% lower at 100 km)

    Note: inverse_square on a flat Earth is a partial correction only; it is most
    meaningful once the round-Earth frame (v2) exists.
    """
    h = np.asarray(h, dtype=float)
    if model == "constant":
        g = np.full_like(h, G0)
    elif model == "inverse_square":
        if np.any(h <= -EARTH_RADIUS_M):
            raise ValueError("altitude must be above the centre of the Earth")
        g = G0 * (EARTH_RADIUS_M / (EARTH_RADIUS_M + h)) ** 2
    else:
        raise ValueError(f"unknown gravity model {model!r}; use one of {GRAVITY_MODELS}")
    return _out(g)


# --------------------------------------------------------------------------- #
# Thrust and mass flow (PHYSICS.md 3.2, 3.3)
# --------------------------------------------------------------------------- #
def nozzle_exit_area(thrust_sl, thrust_vac):
    """
    Effective nozzle exit area A_e = (T_vac - T_sl) / P0 [m^2].

    Derived from the sea-level / vacuum thrust pair, not a user input.
    """
    if thrust_sl <= 0 or thrust_vac <= 0:
        raise ValueError("thrust values must be positive")
    if thrust_vac < thrust_sl:
        raise ValueError("vacuum thrust must be >= sea-level thrust")
    return (thrust_vac - thrust_sl) / P0


def thrust(p_ambient, thrust_sl, thrust_vac):
    """
    Altitude-dependent engine thrust magnitude [N] while burning.

        T(p) = T_vac - p * A_e,   A_e = (T_vac - T_sl) / P0

    So T = T_sl at p = P0 (sea level) and T = T_vac at p = 0 (vacuum).
    Assumes fixed nozzle exit pressure and full throttle (no max-Q throttle-down).
    Returns the magnitude only; direction (theta) and T = 0 after burnout are the
    caller's job.

    Parameters
    ----------
    p_ambient : float or array   ambient static pressure [Pa] (from the atmosphere model)
    thrust_sl, thrust_vac : float  sea-level and vacuum thrust [N]
    """
    p = np.asarray(p_ambient, dtype=float)
    if np.any(p < 0):
        raise ValueError("ambient pressure cannot be negative")
    a_e = nozzle_exit_area(thrust_sl, thrust_vac)
    return _out(thrust_vac - p * a_e)


def mass_flow_rate(thrust_vac, isp_vac):
    """
    Propellant mass flow rate m_dot = T_vac / (G0 * Isp_vac) [kg/s].

    Set by the engine, independent of altitude. The EOM uses dm/dt = -m_dot while
    m > m_dry and 0 after burnout.
    """
    if thrust_vac <= 0 or isp_vac <= 0:
        raise ValueError("thrust_vac and isp_vac must be positive")
    return thrust_vac / (G0 * isp_vac)


# --------------------------------------------------------------------------- #
# Aerodynamic drag (PHYSICS.md 3.4)
# --------------------------------------------------------------------------- #
def reference_area(diameter):
    """Frontal reference area A_ref = pi d^2 / 4 [m^2] from body diameter [m]."""
    if diameter <= 0:
        raise ValueError("diameter must be positive")
    return np.pi * diameter**2 / 4.0


def dynamic_pressure(rho, speed):
    """Dynamic pressure q = 0.5 * rho * V^2 [Pa]. rho [kg/m^3], speed [m/s]."""
    rho = np.asarray(rho, dtype=float)
    speed = np.asarray(speed, dtype=float)
    return _out(0.5 * rho * speed**2)


def cd_from_mach(mach, mach_table, cd_table):
    """
    Drag coefficient from a C_D(Mach) table by linear interpolation [-].

    Values outside the table are clamped to the end values (np.interp behaviour).
    mach_table must be strictly increasing.
    """
    mach_table = np.asarray(mach_table, dtype=float)
    cd_table = np.asarray(cd_table, dtype=float)
    if mach_table.shape != cd_table.shape or mach_table.size < 2:
        raise ValueError("mach_table and cd_table must be the same length (>= 2)")
    if np.any(np.diff(mach_table) <= 0):
        raise ValueError("mach_table must be strictly increasing")
    return _out(np.interp(mach, mach_table, cd_table))


def drag_force(vx, vy, rho, cd, ref_area):
    """
    Aerodynamic drag force vector (Dx, Dy) [N].

        D_vec = -0.5 * rho * C_D * A_ref * V * v_vec

    Written with V * v_vec instead of D * v_vec / V, so there is no division by V
    and the result is exactly (0, 0) on the pad (V = 0) instead of NaN.
    Acts along -v_hat (zero angle of attack, no wind).

    Parameters
    ----------
    vx, vy : float or array   velocity components [m/s]
    rho : float or array      air density [kg/m^3] (from the atmosphere model)
    cd : float or array       drag coefficient [-] (constant or cd_from_mach(...))
    ref_area : float          reference area [m^2]
    """
    vx = np.asarray(vx, dtype=float)
    vy = np.asarray(vy, dtype=float)
    speed = np.hypot(vx, vy)
    k = -0.5 * np.asarray(rho, dtype=float) * cd * ref_area * speed
    return _out(k * vx), _out(k * vy)
