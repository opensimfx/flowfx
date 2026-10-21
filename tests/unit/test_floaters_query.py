import numpy as np
import pytest

from flowfx.core.units import RHO_WATER, G
from flowfx.services.floaters import FloaterSpec, simulate
from flowfx.services.water_query import FlatWater, GridHeightQuery


def _box(lin=0.0):
    return FloaterSpec(mass=2000.0, size=(2.0, 2.0, 1.0), nsamples=(6, 6, 16), linear_damping=lin)


def test_heave_period_matches_theory():
    spec = _box()
    ts, ps, _ = simulate(spec, FlatWater(0.0), 20.0, dt=1 / 480, position=(0, 0, 0.1))
    z = ps[:, 2]
    up = np.where((z[:-1] < 0) & (z[1:] >= 0))[0]
    assert len(up) >= 8
    period = (ts[up[-1]] - ts[up[0]]) / (len(up) - 1)
    expected = 2 * np.pi * np.sqrt(spec.mass / (RHO_WATER * G * 4.0))
    assert period == pytest.approx(expected, rel=0.05)


def test_equilibrium_draft_matches_archimedes():
    spec = _box(lin=8000.0)
    _, ps, _ = simulate(spec, FlatWater(0.0), 40.0, dt=1 / 480, position=(0, 0, 0.3))
    draft = 0.0 - (ps[-1, 2] - 0.5)
    assert draft == pytest.approx(spec.mass / (RHO_WATER * 4.0), rel=0.01)


def test_floater_stays_level_in_flat_water():
    spec = _box(lin=8000.0)
    _, _, qs = simulate(spec, FlatWater(0.0), 10.0, dt=1 / 240, position=(0, 0, 0.2))
    assert np.abs(qs[:, 1:]).max() < 1e-6


def test_grid_query_bilinear_and_normal():
    x = np.linspace(0, 10, 11)
    z = np.tile(0.1 * x, (11, 1))  # plane sloping in x
    q = GridHeightQuery(0, 0, 1, 1, z)
    assert q.height([[2.5, 3.0]])[0] == pytest.approx(0.25)
    n = q.normal([[5.0, 5.0]])[0]
    assert n[0] == pytest.approx(-0.1 / np.sqrt(1.01), rel=1e-3) and n[2] > 0.99


def test_grid_query_choppy_displacement_is_inverted():
    n = 65
    x = np.arange(n, dtype=float)
    X, Y = np.meshgrid(x, x)
    dx = 0.4 * np.sin(2 * np.pi * X / 32.0)
    z = np.cos(2 * np.pi * X / 32.0)  # height defined on rest coordinates
    q = GridHeightQuery(0, 0, 1, 1, z, disp_x=dx, disp_y=np.zeros_like(dx))
    for p0 in (10.0, 20.0, 40.5):
        d = 0.4 * np.sin(2 * np.pi * p0 / 32.0)
        h = q.height([[p0 + d, 8.0]])[0]
        assert h == pytest.approx(np.cos(2 * np.pi * p0 / 32.0), abs=0.02)


def test_flat_water_defaults():
    f = FlatWater(1.5, floor=-2.0)
    assert f.depth([[0, 0]])[0] == pytest.approx(3.5)
    assert f.normal([[0, 0]])[0].tolist() == [0.0, 0.0, 1.0]
