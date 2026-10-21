"""Floater solver: 6-DOF rigid body with sampled-volume buoyancy (pure NumPy).

Blender has no documented path that lets liquid move rigid bodies, so FlowFX integrates
its own body against any WaterQuery and bakes the result to F-curves.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.units import RHO_WATER, G


def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array([aw * bw - ax * bx - ay * by - az * bz,
                     aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw])


def quat_to_matrix(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


@dataclass
class FloaterSpec:
    mass: float
    size: tuple  # box hull (sx, sy, sz) in metres
    nsamples: tuple = (8, 8, 16)
    rho: float = RHO_WATER
    linear_damping: float = 0.0  # N s / m at full submergence
    quadratic_drag_area: float = 0.0  # Cd * A_ref (m^2); drag = 0.5 rho CdA |v| v
    angular_damping: float = 0.0  # N m s at full submergence
    added_mass_fraction: float = 0.0  # fraction of displaced water mass added to linear inertia


class FloaterSolver:
    def __init__(self, spec: FloaterSpec, position=(0.0, 0.0, 0.0), quaternion=(1.0, 0.0, 0.0, 0.0)):
        self.spec = spec
        self.pos = np.array(position, dtype=np.float64)
        self.q = np.array(quaternion, dtype=np.float64)
        self.vel = np.zeros(3)
        self.omega = np.zeros(3)
        sx, sy, sz = spec.size
        nx, ny, nz = spec.nsamples
        ix, iy, iz = np.meshgrid((np.arange(nx) + 0.5) / nx - 0.5, (np.arange(ny) + 0.5) / ny - 0.5,
                                 (np.arange(nz) + 0.5) / nz - 0.5, indexing="ij")
        self.samples = np.stack([ix.ravel() * sx, iy.ravel() * sy, iz.ravel() * sz], axis=1)
        self.dv = sx * sy * sz / (nx * ny * nz)
        self.cell_h = sz / nz
        m = spec.mass
        self.inertia = np.diag([m / 12 * (sy ** 2 + sz ** 2), m / 12 * (sx ** 2 + sz ** 2), m / 12 * (sx ** 2 + sy ** 2)])
        self.t = 0.0

    def submerged(self, query, t):
        R = quat_to_matrix(self.q)
        p = self.samples @ R.T + self.pos
        wz = query.height(p[:, :2], t)
        s = np.clip((wz - (p[:, 2] - 0.5 * self.cell_h)) / self.cell_h, 0.0, 1.0)
        return p, s

    def step(self, dt: float, query, t: float | None = None):
        sp = self.spec
        t = self.t if t is None else t
        p, s = self.submerged(query, t)
        fb = sp.rho * G * self.dv * s  # buoyant force magnitude per sample (+z)
        force = np.array([0.0, 0.0, fb.sum() - sp.mass * G])
        torque = np.cross(p - self.pos, np.stack([np.zeros_like(fb), np.zeros_like(fb), fb], axis=1)).sum(axis=0)
        v_sub = s.sum() * self.dv
        frac = v_sub / (self.dv * len(s))
        vw = query.velocity(self.pos[None, :], t)[0]
        v_rel = self.vel - vw
        force += -sp.linear_damping * frac * v_rel
        force += -0.5 * sp.rho * sp.quadratic_drag_area * frac * np.linalg.norm(v_rel) * v_rel
        torque += -sp.angular_damping * frac * self.omega
        m_eff = sp.mass + sp.added_mass_fraction * sp.rho * v_sub
        self.vel = self.vel + force / m_eff * dt
        self.pos = self.pos + self.vel * dt
        R = quat_to_matrix(self.q)
        iw = R @ self.inertia @ R.T
        self.omega = self.omega + np.linalg.solve(iw, torque - np.cross(self.omega, iw @ self.omega)) * dt
        dq = 0.5 * quat_mul(np.array([0.0, *self.omega]), self.q)
        self.q = self.q + dq * dt
        self.q /= np.linalg.norm(self.q)
        self.t = t + dt


def simulate(spec: FloaterSpec, query, duration: float, dt: float = 1.0 / 240.0, position=(0.0, 0.0, 0.0),
             quaternion=(1.0, 0.0, 0.0, 0.0), sample_dt: float | None = None):
    """Integrate and return (times, positions, quaternions) sampled every `sample_dt`."""
    sample_dt = sample_dt or dt
    solver = FloaterSolver(spec, position, quaternion)
    ts, ps, qs = [0.0], [solver.pos.copy()], [solver.q.copy()]
    next_sample = sample_dt
    n = int(round(duration / dt))
    for _ in range(n):
        solver.step(dt, query)
        if solver.t + 1e-12 >= next_sample:
            ts.append(solver.t)
            ps.append(solver.pos.copy())
            qs.append(solver.q.copy())
            next_sample += sample_dt
    return np.array(ts), np.array(ps), np.array(qs)


def bake_to_fcurves(obj, times, positions, quaternions, fps: float, frame_start: int = 1):
    """Write the trajectory as location and quaternion keyframes (one per frame)."""
    obj.rotation_mode = "QUATERNION"
    for t, p, q in zip(times, positions, quaternions):
        frame = frame_start + t * fps
        obj.location = tuple(float(v) for v in p)
        obj.rotation_quaternion = tuple(float(v) for v in q)
        obj.keyframe_insert("location", frame=frame)
        obj.keyframe_insert("rotation_quaternion", frame=frame)
