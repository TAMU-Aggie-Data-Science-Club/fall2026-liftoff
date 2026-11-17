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

ML link (PHYSICS.md section 9): simulate_trajectory_with_risk() takes the launch-success
probability (success = launched on time, i.e. 1 - the "delay" model's output) from
models/baseline_model.pkl and the surface temperature, turns them into a
drag multiplier and an air-density multiplier, and runs the same solver with those.
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

from .atmosphere import atmosphere
from .constants import T0
from .forces import drag_force, dynamic_pressure, gravity, mass_flow_rate, reference_area, thrust

# Falcon 9 first stage carrying the upper stage (approximate public values).
FALCON9 = {
    "thrust_sl": 7.607e6,          # sea-level thrust, 9 Merlin 1D [N]
    "thrust_vac": 8.227e6,         # vacuum thrust, 9 Merlin 1D [N]
    "isp_vac": 311.0,              # vacuum specific impulse [s]
    "stage1_dry_mass": 22_200.0,   # first stage without propellant [kg]
    "stage1_prop_mass": 395_700.0, # first-stage propellant [kg]
    "landing_reserve_mass": 50_000.0,  # propellant kept back for landing, not burned in ascent [kg]
    "throttle": 0.87,              # average throttle during the burn, 0-1 [-]
    "upper_stage_mass": 111_500.0, # fuelled second stage, carried as dead mass [kg]
    "diameter": 3.66,              # body diameter [m]
    "cd": 0.3,                     # constant drag coefficient [-]
}

# landing_reserve_mass, throttle and KICK_ANGLE_DEG are fitted to real Falcon 9 telemetry
# (PHYSICS.md section 8, src/physics/validation.py). They are not published values.

# Gravity-turn guidance (PHYSICS.md section 4).
KICK_START_S = 10.0     # end of the vertical rise [s]
KICK_DURATION_S = 10.0  # length of the pitch-kick ramp [s]
KICK_ANGLE_DEG = 0.56   # how far the thrust tilts from vertical during the kick [deg]

# Lowest altitude passed to the atmosphere model (see _derivatives) [m]
MIN_ATMOSPHERE_ALTITUDE_M = -1_000.0

# Solver settings, checked by src/physics/solver_benchmark.py.
RTOL = 1e-6                     # relative tolerance [-]
ATOL = 1e-3                     # absolute tolerance [m, m/s, kg]
MAX_STEP_S = 5.0                # longest step, so thin atmosphere layers are not skipped [s]
MAX_DERIVATIVE_CALLS = 200_000  # safety stop; a normal flight needs a few thousand

# ML risk -> drag multiplier (PHYSICS.md section 9). Each row is
# (failure probability = chance of a delay, below this; risk level; drag multiplier). These are scenario
# margins chosen by the team, not measured physics.
RISK_LEVELS = [
    (0.05, "low", 1.00),
    (0.20, "medium", 1.10),
    (float("inf"), "high", 1.25),
]
DENSITY_SCALE_LIMITS = (0.85, 1.15)  # clamp on the temperature-based density multiplier
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "baseline_model.pkl"

OUTPUT_COLUMNS = ["time_sec", "altitude_km", "downrange_km", "velocity_mps"]


def _thrust_angle(phase, t, vx, vy, kick_start, kick_duration, kick_angle):
    """Thrust direction theta [rad] above the horizontal (PHYSICS.md section 4)."""
    if phase == "vertical":
        return np.pi / 2
    if phase == "kick":
        return np.pi / 2 - kick_angle * (t - kick_start) / kick_duration
    return np.arctan2(vy, vx)  # "turn": thrust along the velocity vector


def _derivatives(t, y, phase, vehicle, ref_area, m_dot, wind_speed, guidance,
                 atmosphere_model, gravity_model, density_scale, calls):
    """
    Right-hand side f(t, y) -> dy/dt of the equations of motion.

    phase is "vertical", "kick" or "turn" while the engines burn, and "coast" after.
    """
    calls[0] += 1
    if calls[0] > MAX_DERIVATIVE_CALLS:
        raise RuntimeError("trajectory integration is not converging; stopped to avoid "
                           "an endless run")
    _, h, vx, vy, m = y
    # The solver's trial steps can overshoot below the pad before the ground-impact
    # event pulls them back. Clamp so the atmosphere model never sees a deep hole.
    _, p, rho, _ = atmosphere(max(h, MIN_ATMOSPHERE_ALTITUDE_M), atmosphere_model)

    # Drag acts on the velocity relative to the air, so subtract the wind.
    drag_x, drag_y = drag_force(vx - wind_speed, vy, rho * density_scale, vehicle["cd"],
                                ref_area)
    ax, ay = drag_x / m, drag_y / m - gravity(h, gravity_model)

    if phase == "coast":
        return [vx, vy, ax, ay, 0.0]

    force = vehicle["throttle"] * thrust(p, vehicle["thrust_sl"], vehicle["thrust_vac"])
    theta = _thrust_angle(phase, t, vx, vy, *guidance)
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
    density_scale=1.0,
    drag_scale=1.0,
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
    density_scale : float  multiplier on air density at every altitude (1 = standard day)
    drag_scale : float     multiplier on the drag coefficient (1 = nominal)

    Returns
    -------
    DataFrame with one row every dt seconds and columns
        time_sec, altitude_km, downrange_km, velocity_mps
    The rows stop early if the vehicle hits the ground before t_end. Flight events are
    in df.attrs["events"]: burnout_time_s, max_q_time_s, max_q_pa, apogee_time_s,
    apogee_km, impact_time_s (None when that event did not happen before t_end).

    Raises ValueError for bad inputs (negative or non-finite numbers, no propellant to
    burn, thrust/weight <= 1 on the pad) and RuntimeError if the integration fails.
    """
    vehicle = FALCON9 if vehicle is None else vehicle
    numbers = {"payload_mass": payload_mass, "wind_speed": wind_speed,
               "kick_angle_deg": kick_angle_deg, "kick_start_s": kick_start_s,
               "kick_duration_s": kick_duration_s, "site_altitude": site_altitude,
               "t_end": t_end, "dt": dt, "density_scale": density_scale,
               "drag_scale": drag_scale}
    for name, value in numbers.items():
        if not np.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
    if payload_mass < 0:
        raise ValueError("payload_mass cannot be negative")
    if t_end <= 0 or dt <= 0:
        raise ValueError("t_end and dt must be positive")
    if kick_start_s < 0 or kick_duration_s <= 0:
        raise ValueError("kick_start_s must be >= 0 and kick_duration_s must be > 0")
    if density_scale <= 0 or drag_scale <= 0:
        raise ValueError("density_scale and drag_scale must be positive")
    vehicle = {**vehicle, "cd": vehicle["cd"] * drag_scale}

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
    calls = [0]  # shared counter of derivative evaluations (see MAX_DERIVATIVE_CALLS)
    args = (vehicle, ref_area, m_dot, wind_speed, guidance, atmosphere_model, gravity_model,
            density_scale, calls)
    times = np.arange(0.0, t_end + dt / 2, dt)
    options = {"rtol": RTOL, "atol": ATOL, "max_step": MAX_STEP_S}

    def ground_impact(t, y, *_):
        return y[1] - site_altitude
    ground_impact.terminal = True
    ground_impact.direction = -1

    def apogee(t, y, *_):
        return y[3]
    apogee.direction = -1

    # Phase 1: powered flight up to burnout. m_dot is constant, so burnout (m = m_dry)
    # happens at exactly t_burn and no event search is needed. The burn is integrated
    # in up to three pieces (vertical rise, pitch kick, gravity turn) so that no solver
    # step crosses a jump in the thrust direction.
    t_stop = min(t_burn, t_end)
    kick_end_s = kick_start_s + kick_duration_s
    segments = [("vertical", 0.0, min(kick_start_s, t_stop)),
                ("kick", kick_start_s, min(kick_end_s, t_stop)),
                ("turn", kick_end_s, t_stop)]
    state = [0.0, site_altitude, 0.0, 0.0, m0]
    t_out, y_out = np.empty(0), np.empty((5, 0))
    crashed = False  # True if the rocket flies into the ground with the engines on
    events = {"burnout_time_s": None, "apogee_time_s": None, "apogee_km": None,
              "impact_time_s": None}
    for phase, t_start, t_finish in segments:
        if t_finish <= t_start:
            continue
        powered = solve_ivp(_derivatives, (t_start, t_finish), state, dense_output=True,
                            events=[ground_impact], args=(phase, *args), **options)
        if not powered.success:
            raise RuntimeError(f"powered-flight integration failed: {powered.message}")
        after_start = times >= t_start if t_start == 0.0 else times > t_start
        t_segment = times[after_start & (times <= powered.t[-1])]
        if t_segment.size:  # a very short piece may contain no output time
            t_out = np.concatenate([t_out, t_segment])
            y_out = np.concatenate([y_out, powered.sol(t_segment).reshape(5, -1)], axis=1)
        state = powered.y[:, -1]
        if powered.t_events[0].size:
            crashed = True
            events["impact_time_s"] = float(powered.t_events[0][0])
            break
    if t_burn <= t_end and not crashed:
        events["burnout_time_s"] = t_burn

    # Phase 2: coast with thrust off, starting from the burnout state. A second
    # solve_ivp call handles the jump in the equations at burnout more cleanly than
    # one call (PHYSICS.md section 6.3).
    if t_burn < t_end and not crashed:
        coast = solve_ivp(_derivatives, (t_burn, t_end), state,
                          dense_output=True, events=[apogee, ground_impact],
                          args=("coast", *args), **options)
        if not coast.success:
            raise RuntimeError(f"coast integration failed: {coast.message}")
        t_coast = times[(times > t_burn) & (times <= coast.t[-1])]
        if t_coast.size:
            t_out = np.concatenate([t_out, t_coast])
            y_out = np.concatenate([y_out, coast.sol(t_coast).reshape(5, -1)], axis=1)
        if coast.t_events[0].size:
            events["apogee_time_s"] = float(coast.t_events[0][0])
            events["apogee_km"] = float(coast.y_events[0][0][1]) / 1000.0
        if coast.t_events[1].size:
            events["impact_time_s"] = float(coast.t_events[1][0])

    x, h, vx, vy = y_out[0], y_out[1], y_out[2], y_out[3]
    speed = np.hypot(vx, vy)
    q = dynamic_pressure(atmosphere(h, atmosphere_model).rho * density_scale,
                         np.hypot(vx - wind_speed, vy))
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


# --------------------------------------------------------------------------- #
# ML model -> solver (PHYSICS.md section 9)
# --------------------------------------------------------------------------- #
def risk_adjustments(success_probability=None, temperature_c=None):
    """
    Turn an ML prediction and the weather into solver multipliers.

    Parameters
    ----------
    success_probability : float or None
        Chance the launch goes up on time, 0-1 (1 - the "delay" model's output).
        None means no prediction is available.
    temperature_c : float or None
        Surface air temperature [deg C]. None means a standard day (15 deg C).

    Returns
    -------
    dict with
        risk_level           "low", "medium", "high", or "unknown"
        failure_probability  1 - success_probability (the chance of a delay), or None
        drag_scale           drag multiplier from RISK_LEVELS (1.0 when unknown)
        density_scale        T0 / T_surface: cold air is denser, hot air is thinner
    """
    risk_level, failure_probability, drag_scale = "unknown", None, 1.0
    if success_probability is not None:
        if not 0.0 <= success_probability <= 1.0:
            raise ValueError("success_probability must be between 0 and 1")
        failure_probability = 1.0 - float(success_probability)
        for limit, risk_level, drag_scale in RISK_LEVELS:
            if failure_probability < limit:
                break

    density_scale = 1.0
    if temperature_c is not None:
        temperature_k = temperature_c + 273.15
        if not np.isfinite(temperature_k) or temperature_k <= 0:
            raise ValueError("temperature_c must be a finite temperature above absolute zero")
        density_scale = float(np.clip(T0 / temperature_k, *DENSITY_SCALE_LIMITS))

    return {"risk_level": risk_level, "failure_probability": failure_probability,
            "drag_scale": drag_scale, "density_scale": density_scale}


def predict_success_probability(payload_mass, wind_speed, temperature_c=15.0, precipitation=0.0,
                                cloud_cover=0.0, rocket_type="Falcon 9", model_path=MODEL_PATH,
                                upper_wind_max=None):
    """
    Launch-success (on-time) probability, 1 - the saved "delay" model's output, or None
    if the model file does not exist yet (run src/models/train_model.py to create it).

    wind_speed and upper_wind_max (strongest high-altitude wind; None = unknown, passed to
    the model as missing) are in m/s here and are converted to the model's km/h. The other inputs use
    the model's own units: deg C, mm of precipitation, percent cloud cover.
    """
    model_path = Path(model_path)
    if not model_path.exists():
        return None
    # Imported here so the solver itself does not need xgboost.
    from src.models.train_model import predict_probability

    with open(model_path, "rb") as file:
        saved = pickle.load(file)
    features = pd.DataFrame([{
        "temperature_2m": temperature_c,
        "wind_speed_10m": abs(wind_speed) * 3.6,
        "upper_wind_max_kmh": np.nan if upper_wind_max is None else abs(upper_wind_max) * 3.6,
        "precipitation": precipitation,
        "cloud_cover": cloud_cover,
        "payload_mass_kg": payload_mass,
        "rocket_type": rocket_type,
    }])
    booster = saved["models"]["delay"]["booster"]
    delay_probability = float(predict_probability(booster, features, saved["rocket_categories"])[0])
    return 1.0 - delay_probability


def simulate_trajectory_with_risk(payload_mass, wind_speed=0.0, *, success_probability=None,
                                  temperature_c=None, precipitation=0.0, cloud_cover=0.0,
                                  upper_wind_max=None,
                                  rocket_type="Falcon 9", model_path=MODEL_PATH, **solver_kwargs):
    """
    simulate_trajectory() with the flight path adjusted for ML-predicted risk and weather.

    Pass success_probability if the dashboard already has the model output. Otherwise it
    is predicted here from models/baseline_model.pkl. With no prediction available the
    risk level is "unknown" and only the temperature adjustment is applied.

    Returns the same DataFrame as simulate_trajectory(). The adjustments that were used
    are in df.attrs["risk"] (see risk_adjustments), next to df.attrs["events"].
    """
    if success_probability is None:
        success_probability = predict_success_probability(
            payload_mass, wind_speed, 15.0 if temperature_c is None else temperature_c,
            precipitation, cloud_cover, rocket_type, model_path, upper_wind_max=upper_wind_max)
    risk = risk_adjustments(success_probability, temperature_c)
    df = simulate_trajectory(payload_mass, wind_speed, density_scale=risk["density_scale"],
                             drag_scale=risk["drag_scale"], **solver_kwargs)
    df.attrs["risk"] = risk
    return df


if __name__ == "__main__":
    flight = simulate_trajectory(payload_mass=10_000, wind_speed=0.0)
    print(flight.iloc[::25].to_string(index=False))
    print(flight.attrs["events"])
