"""
Numerical trajectory solver for the Liftoff simulator (PHYSICS.md sections 2, 4, 6).

    simulate_trajectory(payload_mass, wind_speed) -> pandas DataFrame

Integrates the equations of motion with scipy.integrate.solve_ivp:

    state y = [x, h, vx, vy, m]   ->   [m, m, m/s, m/s, kg]      (see constants.py)

    dx/dt  = vx
    dh/dt  = vy
    dvx/dt = (T cos(theta) + Dx) / m
    dvy/dt = (T sin(theta) + Dy) / m - g
    dm/dt  = -m_dot while burning, 0 after burnout

Forces come from forces.py and the air properties from atmosphere.py. This file only
adds the guidance (thrust direction theta), the burnout switch, and the integration.

Flight phases
    1. Powered: first stage burns until its ascent propellant is gone (MECO).
       Guidance is the gravity turn from PHYSICS.md section 4.
    2. Coast: no thrust. Runs until ground impact or t_end, whichever is first.

Assumptions (PHYSICS.md section 5): single stage (the upper stage and payload are carried
as dead mass and never ignite), flat non-rotating Earth, point mass, constant C_D.

Wind: PHYSICS.md assumes still air. Here wind_speed is a constant horizontal wind along
the downrange axis (positive = tailwind). It only changes the air-relative velocity used
for drag.
"""

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

from .atmosphere import atmosphere
from .forces import drag_force, dynamic_pressure, gravity, mass_flow_rate, reference_area, thrust

# Falcon 9 first stage carrying the upper stage (approximate public values).
FALCON9 = {
    "thrust_sl": 7.607e6,          # sea-level thrust, 9 Merlin 1D [N]
    "thrust_vac": 8.227e6,         # vacuum thrust, 9 Merlin 1D [N]
    "isp_vac": 311.0,              # vacuum specific impulse [s]
    "stage1_dry_mass": 22_200.0,   # first stage without propellant [kg]
    "stage1_prop_mass": 395_700.0, # first-stage propellant [kg]
    "landing_reserve_mass": 0.0,   # propellant kept back for landing, never burned in ascent [kg]
    "throttle": 1.0,               # average throttle during the burn, 0-1 [-]
    "upper_stage_mass": 111_500.0, # fuelled second stage, carried as dead mass [kg]
    "diameter": 3.66,              # body diameter [m]
    "cd": 0.3,                     # constant drag coefficient [-]
}

# Gravity-turn guidance (PHYSICS.md section 4). These are fitted values, not physics.
KICK_START_S = 10.0     # end of the vertical rise [s]
KICK_DURATION_S = 10.0  # length of the pitch-kick ramp [s]
KICK_ANGLE_DEG = 2.0    # how far the thrust tilts from vertical during the kick [deg]

OUTPUT_COLUMNS = ["time_sec", "altitude_km", "downrange_km", "velocity_mps"]


def _thrust_angle(t, vx, vy, kick_start, kick_duration, kick_angle):
    """Thrust direction theta [rad] above the horizontal (PHYSICS.md section 4)."""
    if t < kick_start:
        return np.pi / 2
    if t < kick_start + kick_duration:
        return np.pi / 2 - kick_angle * (t - kick_start) / kick_duration
    return np.arctan2(vy, vx)


def _derivatives(t, y, burning, vehicle, ref_area, m_dot, wind_speed, guidance,
                 atmosphere_model, gravity_model):
    """Right-hand side f(t, y) -> dy/dt of the equations of motion."""
    _, h, vx, vy, m = y
    _, p, rho, _ = atmosphere(h, atmosphere_model)

    # Drag acts on the velocity relative to the air, so subtract the wind.
    drag_x, drag_y = drag_force(vx - wind_speed, vy, rho, vehicle["cd"], ref_area)
    ax, ay = drag_x / m, drag_y / m - gravity(h, gravity_model)

    if not burning:
        return [vx, vy, ax, ay, 0.0]

    force = vehicle["throttle"] * thrust(p, vehicle["thrust_sl"], vehicle["thrust_vac"])
    theta = _thrust_angle(t, vx, vy, *guidance)
    return [vx, vy, ax + force * np.cos(theta) / m, ay + force * np.sin(theta) / m, -m_dot]


def simulate_trajectory(
    payload_mass,
    wind_speed=0.0,
    *,
    vehicle=None,
    kick_angle_deg=KICK_ANGLE_DEG,
    kick_start_s=KICK_START_S,
    kick_duration_s=KICK_DURATION_S,
    site_altitude=0.0,
    t_end=500.0,
    dt=1.0,
    atmosphere_model="us76",
    gravity_model="constant",
):
    """
    Simulate a launch from the pad (t=0, x=0, vx=0, vy=0) and return the flight path.

    Parameters
    ----------
    payload_mass : float   payload mass [kg]
    wind_speed : float     constant horizontal wind along downrange [m/s], + = tailwind
    vehicle : dict         rocket parameters; defaults to FALCON9 (same keys required)
    kick_angle_deg, kick_start_s, kick_duration_s : gravity-turn pitch kick
    site_altitude : float  pad altitude above mean sea level [m]
    t_end : float          last output time [s]
    dt : float             spacing of the output rows [s]
    atmosphere_model : "us76" or "exponential"
    gravity_model : "constant" or "inverse_square"

    Returns
    -------
    DataFrame with one row every dt seconds and columns
        time_sec, altitude_km, downrange_km, velocity_mps
    The rows stop early if the vehicle hits the ground before t_end. Flight events are
    in df.attrs["events"]: burnout_time_s, max_q_time_s, max_q_pa, apogee_time_s,
    apogee_km, impact_time_s (None when that event did not happen before t_end).

    Raises ValueError for bad inputs or if thrust/weight <= 1 on the pad.
    """
    vehicle = FALCON9 if vehicle is None else vehicle
    if payload_mass < 0:
        raise ValueError("payload_mass cannot be negative")
    if t_end <= 0 or dt <= 0:
        raise ValueError("t_end and dt must be positive")

    throttle = vehicle["throttle"]
    burned_mass = vehicle["stage1_prop_mass"] - vehicle["landing_reserve_mass"]
    if not 0 < throttle <= 1:
        raise ValueError("throttle must be in (0, 1]")
    if burned_mass <= 0:
        raise ValueError("landing_reserve_mass must be smaller than stage1_prop_mass")

    # Mass at burnout: everything except the propellant burned on the way up.
    m_dry = (vehicle["stage1_dry_mass"] + vehicle["landing_reserve_mass"]
             + vehicle["upper_stage_mass"] + payload_mass)
    m0 = m_dry + burned_mass
    m_dot = throttle * mass_flow_rate(vehicle["thrust_vac"], vehicle["isp_vac"])
    t_burn = burned_mass / m_dot
    ref_area = reference_area(vehicle["diameter"])

    # Pad hold (PHYSICS.md section 2): a rocket that cannot lift off is an input error.
    pad_thrust = throttle * thrust(atmosphere(site_altitude, atmosphere_model).p,
                                   vehicle["thrust_sl"], vehicle["thrust_vac"])
    if pad_thrust <= m0 * gravity(site_altitude, gravity_model):
        raise ValueError("thrust-to-weight ratio on the pad is <= 1; the vehicle cannot lift off")

    guidance = (kick_start_s, kick_duration_s, np.radians(kick_angle_deg))
    args = (vehicle, ref_area, m_dot, wind_speed, guidance, atmosphere_model, gravity_model)
    times = np.arange(0.0, t_end + dt / 2, dt)
    options = {"rtol": 1e-8, "atol": 1e-6, "max_step": 1.0}

    def ground_impact(t, y, *_):
        return y[1] - site_altitude
    ground_impact.terminal = True
    ground_impact.direction = -1

    def apogee(t, y, *_):
        return y[3]
    apogee.direction = -1

    # Phase 1: powered flight up to burnout. m_dot is constant, so burnout (m = m_dry)
    # happens at exactly t_burn and no event search is needed.
    t_stop = min(t_burn, t_end)
    powered = solve_ivp(_derivatives, (0.0, t_stop), [0.0, site_altitude, 0.0, 0.0, m0],
                        dense_output=True, events=[ground_impact],
                        args=(True, *args), **options)
    if not powered.success:
        raise RuntimeError(f"powered-flight integration failed: {powered.message}")
    crashed = powered.t_events[0].size > 0  # flew into the ground with the engines on
    t_out = times[times <= powered.t[-1]]
    y_out = powered.sol(t_out)
    events = {"burnout_time_s": t_burn if t_burn <= t_end and not crashed else None,
              "apogee_time_s": None, "apogee_km": None,
              "impact_time_s": float(powered.t_events[0][0]) if crashed else None}

    # Phase 2: coast with thrust off, starting from the burnout state. A second
    # solve_ivp call handles the jump in the equations at burnout more cleanly than
    # one call (PHYSICS.md section 6.3).
    if t_burn < t_end and not crashed:
        coast = solve_ivp(_derivatives, (t_burn, t_end), powered.y[:, -1],
                          dense_output=True, events=[apogee, ground_impact],
                          args=(False, *args), **options)
        if not coast.success:
            raise RuntimeError(f"coast integration failed: {coast.message}")
        t_coast = times[(times > t_burn) & (times <= coast.t[-1])]
        t_out = np.concatenate([t_out, t_coast])
        y_out = np.concatenate([y_out, coast.sol(t_coast)], axis=1)
        if coast.t_events[0].size:
            events["apogee_time_s"] = float(coast.t_events[0][0])
            events["apogee_km"] = float(coast.y_events[0][0][1]) / 1000.0
        if coast.t_events[1].size:
            events["impact_time_s"] = float(coast.t_events[1][0])

    x, h, vx, vy = y_out[0], y_out[1], y_out[2], y_out[3]
    speed = np.hypot(vx, vy)
    q = dynamic_pressure(atmosphere(h, atmosphere_model).rho, np.hypot(vx - wind_speed, vy))
    ascent = t_out <= t_burn  # max-Q of the climb, not of the fall back into the air
    events["max_q_time_s"] = float(t_out[ascent][np.argmax(q[ascent])])
    events["max_q_pa"] = float(np.max(q[ascent]))

    df = pd.DataFrame({
        "time_sec": t_out,
        "altitude_km": h / 1000.0,
        "downrange_km": x / 1000.0,
        "velocity_mps": speed,
    })
    df.attrs["events"] = events
    return df


if __name__ == "__main__":
    flight = simulate_trajectory(payload_mass=10_000, wind_speed=0.0)
    print(flight.iloc[::25].to_string(index=False))
    print(flight.attrs["events"])
