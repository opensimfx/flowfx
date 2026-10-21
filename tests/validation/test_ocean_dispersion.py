"""Measures how closely the Ocean modifier follows linear dispersion omega^2 = g k tanh(k h).

Method: evaluate the surface over time, FFT each frame, and take the temporal spectrum of the strongest
Fourier modes. Blender's Ocean produces standing-wave modes, so phase tracking does not work.
Results are recorded in docs/validation_report.md; only the well-resolved cases are asserted.
"""
import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from flowfx.bindings import ocean  # noqa: E402
from flowfx.core import theory  # noqa: E402

L, N = 100.0, 144


def measure(depth, spectrum, wind=10.0, seed=2, duration=40.0, dt=0.1, modes=6):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = bpy.data.objects.new("O", bpy.data.meshes.new("g"))
    bpy.context.scene.collection.objects.link(obj)
    mod = ocean.add_modifier(obj)
    ocean.apply_params(mod, dict(spatial_size=int(L), resolution=12, viewport_resolution=12, choppiness=0.0,
                                 wind_velocity=wind, wave_alignment=1.0, damping=0.0, depth=depth,
                                 spectrum=spectrum, wave_scale=1.0, random_seed=seed))
    times = np.arange(0.0, duration, dt)
    spectra = []
    for t in times:
        mod.time = float(t)
        d = ocean.evaluate(obj)
        n = int(round(len(d["co"]) ** 0.5))
        ix = np.rint(d["uv"][:, 0] * (n - 1)).astype(int)
        iy = np.rint(d["uv"][:, 1] * (n - 1)).astype(int)
        z = np.zeros((n, n))
        z[iy, ix] = d["co"][:, 2]
        spectra.append(np.fft.fft2(z[: n - 1, : n - 1]))
    F = np.array(spectra)
    mag = np.abs(F).mean(axis=0)
    mag[0, 0] = 0.0
    k_axis = np.fft.fftfreq(N, d=L / N) * 2 * np.pi
    w_axis = 2 * np.pi * np.fft.fftfreq(len(times) * 8, d=dt)
    rows = []
    for jy, jx in np.dstack(np.unravel_index(np.argsort(mag.ravel())[::-1][: 2 * modes], mag.shape))[0][::2]:
        k = float(np.hypot(k_axis[jx], k_axis[jy]))
        sig = F[:, jy, jx] - F[:, jy, jx].mean()
        spec_t = np.abs(np.fft.fft(sig * np.hanning(len(sig)), n=len(times) * 8))
        w_meas = float(abs(w_axis[np.argmax(spec_t)]))
        w_th = theory.omega_dispersion(k, depth)
        rows.append((k, w_meas, w_th, abs(w_meas - w_th) / w_th))
    return np.array(rows)


@pytest.mark.slow
@pytest.mark.parametrize("depth,spectrum", [(200.0, "JONSWAP"), (3.0, "TEXEL_MARSEN_ARSLOE")])
def test_dispersion_matches_theory_for_resolved_modes(depth, spectrum):
    rows = measure(depth, spectrum)
    assert np.median(rows[:, 3]) < 0.02, rows
