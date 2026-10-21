"""Closed-form water physics used by the preset mapping layer.

Pure Python, no bpy. Every function is unit tested in tests/unit/test_theory.py.
Evidence tags in docs/theory.md: [T] = textbook value, not retrieved during research.
"""
from __future__ import annotations

import math

from .units import G


def hs_fully_developed(wind_mps: float) -> float:
    """Pierson-Moskowitz fully developed sea: Hs = 0.21 U^2 / g. [T]"""
    return 0.21 * wind_mps * wind_mps / G


def hs_fetch_limited(wind_mps: float, fetch_m: float) -> float:
    """Fetch-limited sea: Hs = 0.0016 U sqrt(F / g). [T]"""
    return 0.0016 * wind_mps * math.sqrt(fetch_m / G)


def hs_from_sigma(sigma: float) -> float:
    """Narrow-band Gaussian sea: Hs = 4 sigma (sigma = std of surface elevation)."""
    return 4.0 * sigma


def peak_period_pm(wind_mps: float) -> float:
    """Pierson-Moskowitz peak period, omega_p = 0.877 g / U. [T]"""
    return 2.0 * math.pi / (0.877 * G / wind_mps)


def omega_dispersion(k: float, depth_m: float) -> float:
    """Linear dispersion, omega^2 = g k tanh(k h)."""
    return math.sqrt(G * k * math.tanh(k * depth_m))


def wavenumber_from_omega(omega: float, depth_m: float, iterations: int = 60) -> float:
    """Invert the dispersion relation by Newton iteration."""
    k = omega * omega / G
    for _ in range(iterations):
        th = math.tanh(k * depth_m)
        f = G * k * th - omega * omega
        sech2 = 1.0 - th * th
        df = G * th + G * k * depth_m * sech2
        step = f / df
        k -= step
        if abs(step) < 1e-13 * max(k, 1.0):
            break
    return k


def phase_speed(k: float, depth_m: float) -> float:
    return omega_dispersion(k, depth_m) / k


def wavelength_from_period(period_s: float, depth_m: float) -> float:
    return 2.0 * math.pi / wavenumber_from_omega(2.0 * math.pi / period_s, depth_m)


def shallow_speed(depth_m: float) -> float:
    """c = sqrt(g h). Tsunami speed uses the same relation. [V NOAA]"""
    return math.sqrt(G * depth_m)


def froude(velocity_mps: float, depth_m: float) -> float:
    return velocity_mps / math.sqrt(G * depth_m)


def flow_regime(fr: float) -> str:
    if fr < 0.95:
        return "subcritical"
    if fr <= 1.05:
        return "critical"
    return "supercritical"


def manning_velocity(slope: float, manning_n: float, hydraulic_radius_m: float) -> float:
    """Manning: u = R^(2/3) S^(1/2) / n. [T]"""
    return hydraulic_radius_m ** (2.0 / 3.0) * math.sqrt(slope) / manning_n


def deep_wavelength(period_s: float) -> float:
    return G * period_s * period_s / (2.0 * math.pi)


def iribarren(beach_slope: float, wave_height_m: float, period_s: float) -> float:
    """Surf similarity xi = tan(beta) / sqrt(H / L0). [T]"""
    return beach_slope / math.sqrt(wave_height_m / deep_wavelength(period_s))


def breaker_type(xi: float) -> str:
    if xi < 0.5:
        return "spilling"
    if xi <= 3.3:
        return "plunging"
    return "surging"


def dam_break_front_speed(h0_m: float) -> float:
    """Dry-bed dam break (Ritter): front speed 2 sqrt(g h0)."""
    return 2.0 * math.sqrt(G * h0_m)


def ritter_depth(x: float, t: float, h0: float) -> float:
    """Ritter analytic depth for a dry-bed dam break, dam at x = 0, water on x < 0."""
    c0 = math.sqrt(G * h0)
    if t <= 0.0:
        return h0 if x < 0.0 else 0.0
    if x <= -c0 * t:
        return h0
    if x >= 2.0 * c0 * t:
        return 0.0
    return (2.0 * c0 - x / t) ** 2 / (9.0 * G)


def free_fall_speed(drop_m: float) -> float:
    return math.sqrt(2.0 * G * drop_m)


def kelvin_half_angle_deg() -> float:
    """Kelvin wake half-angle, arcsin(1/3) = 19.47 degrees."""
    return math.degrees(math.asin(1.0 / 3.0))


def strouhal_frequency(velocity_mps: float, diameter_m: float, strouhal: float = 0.2) -> float:
    """Cylinder wake shedding frequency, St ~ 0.2 for 300 < Re < 2e5. [T]"""
    return strouhal * velocity_mps / diameter_m


def look_scale_time_scale(look_scale: float) -> float:
    """Froude similarity: make a sim read `look_scale` times larger by slowing time."""
    return 1.0 / math.sqrt(look_scale)


def biesel_piston_ratio(k: float, depth_m: float) -> float:
    """Piston wavemaker transfer function H/S = 2 (cosh 2kh - 1) / (sinh 2kh + 2kh). [T]"""
    kh2 = 2.0 * k * depth_m
    return 2.0 * (math.cosh(kh2) - 1.0) / (math.sinh(kh2) + kh2)


def piston_stroke(wave_height_m: float, period_s: float, depth_m: float) -> float:
    """Peak-to-peak piston stroke S needed for wave height H at period T in depth h."""
    k = wavenumber_from_omega(2.0 * math.pi / period_s, depth_m)
    return wave_height_m / biesel_piston_ratio(k, depth_m)


def absorption_to_color_density(sigma_rgb):
    """Map per-channel absorption coefficients (1/m) to a Volume Absorption node.

    Assumes sigma_c = density * (1 - color_c). [U] verified by
    tests/validation/test_cycles_absorption.py when a render engine is available.
    Returns (color_rgb, density).
    """
    density = max(sigma_rgb)
    color = tuple(1.0 - s / density for s in sigma_rgb)
    return color, density
