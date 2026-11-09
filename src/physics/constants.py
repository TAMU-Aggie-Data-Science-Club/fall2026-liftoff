"""
Physical constants and reference coordinate frame for Liftoff trajectory simulator.

2D flat earth, non rotating coordinate frame

(0,0) is the launchpad

x: is how far rocket has traveled accross the ground from the launchpad, in meters

h: is the height above sea level, in meters (up is positive)

SI units used, angles are in RADIANS
"""

# Mean radius of the Earth [m]
EARTH_RADIUS_M = 6_371_000.0

# Standard gravitational acceleration at Earth's surface [m/s^2]
G0 = 9.80665

# Static pressure at sea level, standard atmosphere [Pa]
# Used for altitude-dependent thrust: A_e = (T_vac - T_SL) / P0
P0 = 101_325.0

# Air density at sea level, standard atmosphere [kg/m^3]
RHO0 = 1.225

# Atmospheric scale height for the exponential model rho(h) = RHO0 * exp(-h / H) [m]
SCALE_HEIGHT_M = 8_500.0

# Coordinate system used
COORDINATE_SYSTEM = "2D Cartesian"

# Is the Earth rotating?
EARTH_ROTATING = False

# Order of the values in the state vector
STATE_VECTOR_ORDER = ["x", "h", "v_x", "v_y", "m"]

# Units used for simulation (SI units)
UNITS = {
    "length_unit": "m",
    "time_unit": "s",
    "mass_unit": "kg",
    "velocity_unit": "m/s",
    "acceleration_unit": "m/s^2",
    "force_unit": "N",
    "pressure_unit": "Pa",
    "temperature_unit": "K",
    "angle_unit": "rad"
}