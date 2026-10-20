"""
Physical constants and reference coordinate frame for Liftoff trajectory simulator.

2D flat earth, non rotating coordinate frame

(0,0) is the launchpad

x: is how far rocket has traveled accross the ground from the launchpad, in meters

h: is the height above sea levevl, in meters (up is positive)

SI units used, angles are in RADIANS
"""

# Mean radius of the Earth [m]
EARTH_RADIUS_M = 6_371_000.0

# Standard gravitational acceleration at Earth's surface [m/s^2]
G0 = 9.80665

# Air density at sea level, standard atmosphere [kg/m^3]
RHO0 = 1.225

# Atmospheric scale height for the exponential model rho(h) = RHO0 * exp(-h / H) [m]
SCALE_HEIGHT_M = 8_500.0