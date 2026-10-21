import math

import pytest

from flowfx.core import theory as T


def test_hs_fully_developed_matches_design_table():
    assert T.hs_fully_developed(12) == pytest.approx(3.083, abs=0.01)
    assert T.hs_fully_developed(16) == pytest.approx(5.48, abs=0.01)
    assert T.hs_fully_developed(25) == pytest.approx(13.38, abs=0.01)


def test_hs_fetch_limited():
    assert T.hs_fetch_limited(6, 3000) == pytest.approx(0.168, abs=0.002)
    assert T.hs_fetch_limited(10, 8000) == pytest.approx(0.457, abs=0.002)


def test_dispersion_limits():
    k = 0.5
    assert T.phase_speed(k, 1e4) == pytest.approx(math.sqrt(T.G / k), rel=1e-6)  # deep
    assert T.phase_speed(1e-3, 2.0) == pytest.approx(T.shallow_speed(2.0), rel=1e-3)  # shallow


def test_wavenumber_roundtrip():
    for depth in (0.5, 4.0, 200.0):
        k = 0.3
        w = T.omega_dispersion(k, depth)
        assert T.wavenumber_from_omega(w, depth) == pytest.approx(k, rel=1e-9)


def test_tsunami_speed_matches_noaa_example():
    c = T.shallow_speed(4600.0)
    assert c == pytest.approx(212.4, abs=0.2)
    assert c * 3.6 == pytest.approx(765.0, abs=1.0)


def test_manning_and_froude_for_presets():
    u = T.manning_velocity(0.0003, 0.035, 2.0)
    assert u == pytest.approx(0.786, abs=0.005)
    assert T.froude(u, 2.0) == pytest.approx(0.177, abs=0.005)
    assert T.flow_regime(T.froude(2.817, 0.5)) == "supercritical"


def test_breaker_classification():
    xi = T.iribarren(0.1, 1.5, 8.0)
    assert xi == pytest.approx(0.816, abs=0.01)
    assert T.breaker_type(xi) == "plunging"
    assert T.breaker_type(0.2) == "spilling"
    assert T.breaker_type(4.0) == "surging"


def test_dam_break_and_free_fall():
    assert T.dam_break_front_speed(1.0) == pytest.approx(6.264, abs=0.01)
    assert T.free_fall_speed(6.0) == pytest.approx(10.85, abs=0.01)


def test_ritter_profile_limits():
    assert T.ritter_depth(-100, 2.0, 1.0) == 1.0
    assert T.ritter_depth(100, 2.0, 1.0) == 0.0
    # at x = 0 depth is 4 c0^2 / (9 g) = 4 h0 / 9
    assert T.ritter_depth(0.0, 2.0, 1.0) == pytest.approx(4.0 / 9.0)


def test_kelvin_angle_and_strouhal():
    assert T.kelvin_half_angle_deg() == pytest.approx(19.47, abs=0.01)
    assert T.strouhal_frequency(2.0, 1.0) == pytest.approx(0.4)


def test_look_scale():
    assert T.look_scale_time_scale(20.0) == pytest.approx(0.2236, abs=1e-3)


def test_piston_stroke_deep_limit():
    # In deep water H/S -> 2, so S -> H/2 for a deep tank.
    assert T.biesel_piston_ratio(1.0, 50.0) == pytest.approx(2.0, rel=1e-6)
    assert T.piston_stroke(1.0, 4.0, 50.0) == pytest.approx(0.5, rel=1e-3)


def test_absorption_conversion_roundtrip():
    sigma = (0.35, 0.065, 0.01)
    color, density = T.absorption_to_color_density(sigma)
    for s, c in zip(sigma, color):
        assert density * (1.0 - c) == pytest.approx(s)
    assert all(0.0 <= c <= 1.0 for c in color)
