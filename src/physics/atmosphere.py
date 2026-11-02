"""
Standard atmosphere models for the Liftoff trajectory simulator (PHYSICS.md 3.5).

    atmosphere(h, model="us76") -> AtmosphereState(T, p, rho, a)

    h    geometric altitude above mean sea level [m]   (same h as the state vector)
    T    static temperature [K]
    p    static pressure [Pa]          -> forces.thrust(p, ...)
    rho  density [kg/m^3]              -> forces.drag_force(..., rho, ...)
    a    speed of sound [m/s]          -> Mach = V / a -> forces.cd_from_mach(...)

The result unpacks like a tuple (T, p, rho, a = atmosphere(h)) or by name (atm.rho).
Scalars give floats; numpy arrays give arrays.

Models
------
"us76" (default)
    U.S. Standard Atmosphere 1976, seven layers from 0 to 84.852 km geopotential.
    Layers are defined in geopotential altitude z = r0 h / (r0 + h). Base temperatures
    and pressures are built from T0, P0 and the lapse rates, so T and p are continuous
    at every layer boundary (no jumps for solve_ivp).
    Above 84.852 km: temperature held at 186.946 K, pressure decays isothermally.
    Real US76 differs above 86 km, but q is ~0 there, so the effect on drag is negligible.
    Below sea level the first layer is extended (fine for pads a few hundred m below MSL).

"exponential" (hand-check / teaching only)
    rho = RHO0 exp(-h/H), p = P0 exp(-h/H), T = T0 (constant).
    Mach and C_D(M) are WRONG at altitude in this mode (T never drops).

Assumptions: dry air, no weather or day-of-launch variation, no wind.
"""

from typing import NamedTuple

import numpy as np

from .constants import (
    G0,
    GAMMA_AIR,
    P0,
    R_AIR,
    RHO0,
    SCALE_HEIGHT_M,
    T0,
    US76_EARTH_RADIUS_M,
)

ATMOSPHERE_MODELS = ("us76", "exponential")


class AtmosphereState(NamedTuple):
    T: "float | np.ndarray"    # temperature [K]
    p: "float | np.ndarray"    # pressure [Pa]
    rho: "float | np.ndarray"  # density [kg/m^3]
    a: "float | np.ndarray"    # speed of sound [m/s]


def _out(arr):
    """Return a Python float for 0-d results, otherwise the numpy array."""
    arr = np.asarray(arr, dtype=float)
    return float(arr) if arr.ndim == 0 else arr


# --------------------------------------------------------------------------- #
# US76 layer table (geopotential altitude). The last entry is the top of the
# model; above it we use an isothermal layer (lapse 0).
# --------------------------------------------------------------------------- #
_Z_BASE = np.array([0.0, 11_000.0, 20_000.0, 32_000.0, 47_000.0, 51_000.0, 71_000.0, 84_852.0])
_LAPSE = np.array([-0.0065, 0.0, 0.0010, 0.0028, 0.0, -0.0028, -0.0020, 0.0])  # [K/m]

US76_TOP_Z = _Z_BASE[-1]  # [m] geopotential


def _layer_pressure(p_b, T_b, lapse, dz):
    """Pressure at dz above a layer base (hydrostatic + ideal gas)."""
    if lapse == 0.0:
        return p_b * np.exp(-G0 * dz / (R_AIR * T_b))
    T = T_b + lapse * dz
    return p_b * (T / T_b) ** (-G0 / (R_AIR * lapse))


def _build_bases():
    T_b = [T0]
    p_b = [P0]
    for i in range(len(_Z_BASE) - 1):
        dz = _Z_BASE[i + 1] - _Z_BASE[i]
        p_b.append(_layer_pressure(p_b[i], T_b[i], _LAPSE[i], dz))
        T_b.append(T_b[i] + _LAPSE[i] * dz)
    return np.array(T_b), np.array(p_b)


_T_BASE, _P_BASE = _build_bases()


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #
def geopotential_altitude(h):
    """Geometric altitude h [m] -> geopotential altitude z = r0 h / (r0 + h) [m]."""
    h = np.asarray(h, dtype=float)
    return _out(US76_EARTH_RADIUS_M * h / (US76_EARTH_RADIUS_M + h))


def speed_of_sound(T):
    """Speed of sound a = sqrt(gamma R T) [m/s] for temperature T [K]."""
    T = np.asarray(T, dtype=float)
    if np.any(T <= 0):
        raise ValueError("temperature must be positive")
    return _out(np.sqrt(GAMMA_AIR * R_AIR * T))


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
def us76(h):
    """U.S. Standard Atmosphere 1976 at geometric altitude h [m]. See module docstring."""
    h = np.asarray(h, dtype=float)
    if np.any(h <= -US76_EARTH_RADIUS_M / 2):
        raise ValueError("altitude is far below sea level")
    z = US76_EARTH_RADIUS_M * h / (US76_EARTH_RADIUS_M + h)

    # Which layer each altitude is in (below 0 -> layer 0, above top -> last layer)
    i = np.clip(np.searchsorted(_Z_BASE, z, side="right") - 1, 0, len(_Z_BASE) - 1)
    T_b, p_b, L = _T_BASE[i], _P_BASE[i], _LAPSE[i]
    dz = z - _Z_BASE[i]

    T = T_b + L * dz
    isothermal = L == 0.0
    L_safe = np.where(isothermal, 1.0, L)  # avoid divide-by-zero in the unused branch
    p_grad = p_b * (T / T_b) ** (-G0 / (R_AIR * L_safe))
    p_iso = p_b * np.exp(-G0 * dz / (R_AIR * T_b))
    p = np.where(isothermal, p_iso, p_grad)

    rho = p / (R_AIR * T)
    a = np.sqrt(GAMMA_AIR * R_AIR * T)
    return AtmosphereState(_out(T), _out(p), _out(rho), _out(a))


def exponential(h):
    """Exponential atmosphere at altitude h [m]. Hand-check mode; T fixed at T0."""
    h = np.asarray(h, dtype=float)
    decay = np.exp(-h / SCALE_HEIGHT_M)
    T = np.full_like(h, T0)
    return AtmosphereState(
        _out(T),
        _out(P0 * decay),
        _out(RHO0 * decay),
        _out(np.sqrt(GAMMA_AIR * R_AIR * T)),
    )


def atmosphere(h, model="us76"):
    """
    Atmospheric state at geometric altitude h [m].

    model: "us76" (default) or "exponential" (hand checks only).
    Returns AtmosphereState(T [K], p [Pa], rho [kg/m^3], a [m/s]).
    """
    if model == "us76":
        return us76(h)
    if model == "exponential":
        return exponential(h)
    raise ValueError(f"unknown atmosphere model {model!r}; use one of {ATMOSPHERE_MODELS}")
