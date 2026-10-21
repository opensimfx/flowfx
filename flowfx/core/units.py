"""SI constants used across FlowFX. All lengths in metres, time in seconds."""

G = 9.81  # m/s^2, matches Blender's default scene gravity (0, 0, -9.81)
RHO_WATER = 1000.0  # kg/m^3 (fresh water, simplification)
RHO_SEAWATER = 1025.0

# Pure-water absorption coefficients (1/m) at roughly 650 / 550 / 450 nm.
# [T] textbook order of magnitude, not retrieved in the design research.
ABSORPTION_CLEAR_RGB = (0.35, 0.065, 0.01)
IOR_WATER = 1.333
