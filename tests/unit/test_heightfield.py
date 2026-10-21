"""Numerical validation of the shallow-water solver (design doc section 14.4)."""
import math

import numpy as np
import pytest

from flowfx.core import theory
from flowfx.engines.heightfield.outputs import foam_mask, froude_field
from flowfx.engines.heightfield.solver import Boundary, ShallowWater, SWEConfig


def _strip(nx, ny, dx, **kw):
    kw.setdefault("bottom", Boundary.periodic())
    kw.setdefault("top", Boundary.periodic())
    return SWEConfig(nx, ny, dx, dx, **kw)


def test_lake_at_rest_over_uneven_bed_with_dry_island():
    nx, ny, dx = 100, 6, 0.5
    x = (np.arange(nx) + 0.5) * dx
    bed = np.tile(0.6 * np.exp(-((x - 12) / 3) ** 2) + 1.2 * np.exp(-((x - 35) / 4) ** 2), (ny, 1))
    sw = ShallowWater(_strip(nx, ny, dx), bed=bed, h=np.maximum(1.0 - bed, 0.0))
    sw.run(30.0)
    u, v = sw.velocity()
    assert np.abs(u).max() < 1e-8 and np.abs(v).max() < 1e-8


def test_mass_conservation_closed_domain():
    nx, ny = 100, 50
    h = np.ones((ny, nx))
    h[:, :30] += 0.5
    sw = ShallowWater(SWEConfig(nx, ny, 1.0, 1.0), h=h)
    v0 = sw.total_volume()
    sw.run(20.0)
    assert abs(sw.total_volume() - v0) / v0 < 1e-9


def test_pulse_travels_at_shallow_wave_speed():
    nx, dx, h0 = 800, 0.5, 1.0
    x = (np.arange(nx) + 0.5) * dx - 200
    h = np.tile(h0 + 0.01 * np.exp(-(x / 4) ** 2), (3, 1))
    sw = ShallowWater(_strip(nx, 3, dx, left=Boundary.open(), right=Boundary.open()), h=h)
    T = 40.0
    sw.run(T)
    eta, m = sw.h[0] - h0, x > 0
    centroid = (x[m] * eta[m]).sum() / eta[m].sum()
    assert centroid / T == pytest.approx(theory.shallow_speed(h0), rel=0.03)


def test_dry_bed_dam_break_matches_ritter():
    nx, dx, ny = 400, 0.25, 4
    x = (np.arange(nx) + 0.5) * dx - 50.0
    h = np.tile(np.where(x < 0, 1.0, 0.0), (ny, 1))
    sw = ShallowWater(_strip(nx, ny, dx, left=Boundary.wall(), right=Boundary.open(), h_dry=1e-6), h=h)
    sw.run(2.0)
    ana = np.array([theory.ritter_depth(xi, sw.t, 1.0) for xi in x])
    m = np.abs(x) < 20
    err = np.sqrt(np.mean((sw.h[0][m] - ana[m]) ** 2)) / np.sqrt(np.mean(ana[m] ** 2))
    assert err < 0.05


def test_uniform_flow_matches_manning():
    n_man, slope, h0 = 0.035, 0.001, 1.0
    cfg = SWEConfig(8, 4, 1.0, 1.0, manning_n=n_man, slope_x=slope, left=Boundary.periodic(),
                    right=Boundary.periodic(), bottom=Boundary.periodic(), top=Boundary.periodic())
    sw = ShallowWater(cfg, h=np.full((4, 8), h0))
    sw.run(900.0)
    u, _ = sw.velocity()
    assert u.mean() == pytest.approx(theory.manning_velocity(slope, n_man, h0), rel=0.05)


def test_inflow_boundary_fills_domain():
    cfg = _strip(50, 3, 1.0, left=Boundary.inflow(1.0, 1.0), right=Boundary.open(), h_dry=1e-6)
    sw = ShallowWater(cfg, h=np.zeros((3, 50)))
    sw.run(30.0)
    assert sw.h[:, 0].min() > 0.5  # inflow side wet
    assert sw.total_volume() > 0.0


def test_blocked_cells_stay_dry_and_deflect():
    nx, ny = 60, 30
    block = np.zeros((ny, nx), dtype=bool)
    block[12:18, 20:24] = True
    cfg = SWEConfig(nx, ny, 1.0, 1.0, left=Boundary.inflow(1.0, 1.0), right=Boundary.open(),
                    bottom=Boundary.wall(), top=Boundary.wall())
    sw = ShallowWater(cfg, h=np.ones((ny, nx)), block=block)
    sw.run(20.0)
    assert float(sw.h[block].max()) == 0.0 and np.isfinite(sw.h).all()


def test_supercritical_flow_marks_foam():
    h = np.full((10, 10), 0.5)
    u = np.full((10, 10), 3.0)  # Fr = 3 / sqrt(9.81 * 0.5) = 1.35
    assert froude_field(h, u, np.zeros_like(u))[0, 0] == pytest.approx(1.354, abs=0.01)
    assert foam_mask(h, u, np.zeros_like(u), 1.0, 1.0).min() > 0.99


def test_cfl_positive_and_finite_for_random_state():
    rng = np.random.default_rng(1)
    sw = ShallowWater(SWEConfig(64, 64, 1.0, 1.0), h=1.0 + 0.2 * rng.random((64, 64)))
    sw.run(5.0)
    assert np.isfinite(sw.h).all() and sw.h.min() >= 0.0 and not math.isnan(sw.t)
