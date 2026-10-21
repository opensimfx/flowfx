"""2D shallow-water solver (pure NumPy, no bpy).

Finite volume, first order, HLL flux with hydrostatic reconstruction (well balanced,
positivity preserving for CFL <= 0.5), Manning friction applied semi-implicitly, optional
body slope force for uniform-flow tests. Arrays are shaped (ny, nx); +x is axis 1, +y axis 0.

State: h (depth), hu, hv (momentum). Bed elevation b. Water surface = b + h.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ...core.units import G

WALL, OPEN, PERIODIC, INFLOW = "wall", "open", "periodic", "inflow"


@dataclass
class Boundary:
    kind: str = WALL
    h: float = 0.0  # inflow depth
    u: float = 0.0  # inflow normal velocity (positive = into the domain)

    @staticmethod
    def wall():
        return Boundary(WALL)

    @staticmethod
    def open():
        return Boundary(OPEN)

    @staticmethod
    def periodic():
        return Boundary(PERIODIC)

    @staticmethod
    def inflow(h: float, u: float):
        return Boundary(INFLOW, h, u)


@dataclass
class SWEConfig:
    nx: int
    ny: int
    dx: float
    dy: float
    manning_n: float = 0.0
    cfl: float = 0.45
    h_dry: float = 1e-5
    g: float = G
    slope_x: float = 0.0  # body-force slope (uniform-flow tests)
    slope_y: float = 0.0
    left: Boundary = field(default_factory=Boundary.wall)
    right: Boundary = field(default_factory=Boundary.wall)
    bottom: Boundary = field(default_factory=Boundary.wall)
    top: Boundary = field(default_factory=Boundary.wall)


class ShallowWater:
    def __init__(self, cfg: SWEConfig, bed=None, h=None, hu=None, hv=None, manning_map=None, block=None):
        self.cfg = cfg
        shape = (cfg.ny, cfg.nx)
        self.b = np.zeros(shape) if bed is None else np.array(bed, dtype=np.float64)
        self.h = np.zeros(shape) if h is None else np.array(h, dtype=np.float64)
        self.hu = np.zeros(shape) if hu is None else np.array(hu, dtype=np.float64)
        self.hv = np.zeros(shape) if hv is None else np.array(hv, dtype=np.float64)
        self.n_map = None if manning_map is None else np.array(manning_map, dtype=np.float64)
        # Boolean mask of blocked cells (obstacles): treated as bed raised to infinity-like wall.
        self.block = None if block is None else np.array(block, dtype=bool)
        for name in ("b", "h", "hu", "hv"):
            if getattr(self, name).shape != shape:
                raise ValueError(f"{name} must have shape {shape}")
        self.t = 0.0
        self.steps = 0
        self._clean()

    # ------------------------------------------------------------------ helpers
    def _clean(self):
        c = self.cfg
        self.h[self.h < 0.0] = 0.0
        dry = self.h < c.h_dry
        self.hu[dry] = 0.0
        self.hv[dry] = 0.0
        if self.block is not None:
            self.h[self.block] = 0.0
            self.hu[self.block] = 0.0
            self.hv[self.block] = 0.0

    def velocity(self):
        wet = self.h > self.cfg.h_dry
        safe = np.where(wet, self.h, 1.0)
        return np.where(wet, self.hu / safe, 0.0), np.where(wet, self.hv / safe, 0.0)

    def surface(self):
        return self.b + self.h

    def total_volume(self) -> float:
        return float(self.h.sum() * self.cfg.dx * self.cfg.dy)

    def max_dt(self) -> float:
        c = self.cfg
        u, v = self.velocity()
        cw = np.sqrt(c.g * self.h)
        sx = float(np.max(np.abs(u) + cw))
        sy = float(np.max(np.abs(v) + cw))
        rate = max(sx / c.dx, sy / c.dy, 1e-12)
        return c.cfl / rate

    # ------------------------------------------------------------------ ghost cells
    def _padded(self):
        c = self.cfg
        pad = lambda a: np.pad(a, 1, mode="edge")  # noqa: E731
        B, H, HU, HV = pad(self.b), pad(self.h), pad(self.hu), pad(self.hv)
        if self.block is not None:
            # blocked cells act as high walls: raise bed so reconstruction yields zero flux
            wallz = float(self.b.max() + self.h.max() + 1e3)
            Bm = np.pad(self.block, 1, mode="edge")
            B = np.where(Bm, wallz, B)
        self._apply_bc(B, H, HU, HV, c.left, "left")
        self._apply_bc(B, H, HU, HV, c.right, "right")
        self._apply_bc(B, H, HU, HV, c.bottom, "bottom")
        self._apply_bc(B, H, HU, HV, c.top, "top")
        return B, H, HU, HV

    def _apply_bc(self, B, H, HU, HV, bc: Boundary, side: str):
        sl = {"left": (slice(None), 0), "right": (slice(None), -1),
              "bottom": (0, slice(None)), "top": (-1, slice(None))}[side]
        inner = {"left": (slice(None), 1), "right": (slice(None), -2),
                 "bottom": (1, slice(None)), "top": (-2, slice(None))}[side]
        opp = {"left": (slice(None), -2), "right": (slice(None), 1),
               "bottom": (-2, slice(None)), "top": (1, slice(None))}[side]
        normal_is_x = side in ("left", "right")
        sign = 1.0 if side in ("left", "bottom") else -1.0  # inward normal direction
        if bc.kind == PERIODIC:
            B[sl], H[sl], HU[sl], HV[sl] = B[opp], H[opp], HU[opp], HV[opp]
        elif bc.kind == OPEN:
            B[sl], H[sl], HU[sl], HV[sl] = B[inner], H[inner], HU[inner], HV[inner]
        elif bc.kind == WALL:
            B[sl], H[sl] = B[inner], H[inner]
            if normal_is_x:
                HU[sl], HV[sl] = -HU[inner], HV[inner]
            else:
                HU[sl], HV[sl] = HU[inner], -HV[inner]
        elif bc.kind == INFLOW:
            B[sl] = B[inner]
            H[sl] = bc.h
            qn = sign * bc.u * bc.h
            if normal_is_x:
                HU[sl], HV[sl] = qn, 0.0
            else:
                HU[sl], HV[sl] = 0.0, qn
        else:
            raise ValueError(f"unknown boundary kind {bc.kind}")

    # ------------------------------------------------------------------ flux
    def _hll(self, bL, hL, qnL, qtL, bR, hR, qnR, qtR):
        """HLL flux across x-normal faces with hydrostatic reconstruction.

        Returns (F_h, F_qn, F_qt, hL*, hR*) where * are reconstructed depths.
        qn is the normal momentum, qt the transverse momentum.
        """
        c = self.cfg
        g = c.g
        bs = np.maximum(bL, bR)
        hLs = np.maximum(0.0, hL + bL - bs)
        hRs = np.maximum(0.0, hR + bR - bs)
        wetL, wetR = hL > c.h_dry, hR > c.h_dry
        uL = np.where(wetL, qnL / np.where(wetL, hL, 1.0), 0.0)
        uR = np.where(wetR, qnR / np.where(wetR, hR, 1.0), 0.0)
        vL = np.where(wetL, qtL / np.where(wetL, hL, 1.0), 0.0)
        vR = np.where(wetR, qtR / np.where(wetR, hR, 1.0), 0.0)
        cL, cR = np.sqrt(g * hLs), np.sqrt(g * hRs)
        # wave speed estimates (Einfeldt / Davis) with dry-front handling
        sL = np.where(hLs <= c.h_dry, uR - 2.0 * cR, np.minimum(uL - cL, uR - cR))
        sR = np.where(hRs <= c.h_dry, uL + 2.0 * cL, np.maximum(uL + cL, uR + cR))
        UL = np.stack([hLs, hLs * uL, hLs * vL])
        UR = np.stack([hRs, hRs * uR, hRs * vR])
        FL = np.stack([hLs * uL, hLs * uL * uL + 0.5 * g * hLs * hLs, hLs * uL * vL])
        FR = np.stack([hRs * uR, hRs * uR * uR + 0.5 * g * hRs * hRs, hRs * uR * vR])
        denom = np.where(sR - sL == 0.0, 1.0, sR - sL)
        Fh = (sR * FL - sL * FR + sL * sR * (UR - UL)) / denom
        F = np.where(sL >= 0.0, FL, np.where(sR <= 0.0, FR, Fh))
        return F[0], F[1], F[2], hLs, hRs

    # ------------------------------------------------------------------ step
    def step(self, dt: float | None = None) -> float:
        c = self.cfg
        if dt is None:
            dt = min(self.max_dt(), 1.0)
        B, H, HU, HV = self._padded()
        g = c.g

        # x-faces: between padded columns i and i+1, for interior rows
        sl_rows = slice(1, -1)
        bL, bR = B[sl_rows, :-1], B[sl_rows, 1:]
        hL, hR = H[sl_rows, :-1], H[sl_rows, 1:]
        Fh, Fqn, Fqt, hLs, hRs = self._hll(bL, hL, HU[sl_rows, :-1], HV[sl_rows, :-1],
                                           bR, hR, HU[sl_rows, 1:], HV[sl_rows, 1:])
        FqnL = Fqn + 0.5 * g * (hL * hL - hLs * hLs)  # flux seen by the left cell
        FqnR = Fqn + 0.5 * g * (hR * hR - hRs * hRs)  # flux seen by the right cell
        dh = -(Fh[:, 1:] - Fh[:, :-1]) / c.dx
        dhu = -(FqnL[:, 1:] - FqnR[:, :-1]) / c.dx
        dhv = -(Fqt[:, 1:] - Fqt[:, :-1]) / c.dx

        # y-faces: swap roles of (hu, hv)
        sl_cols = slice(1, -1)
        bB, bT = B[:-1, sl_cols], B[1:, sl_cols]
        hB, hT = H[:-1, sl_cols], H[1:, sl_cols]
        Gh, Gqn, Gqt, hBs, hTs = self._hll(bB, hB, HV[:-1, sl_cols], HU[:-1, sl_cols],
                                           bT, hT, HV[1:, sl_cols], HU[1:, sl_cols])
        GqnB = Gqn + 0.5 * g * (hB * hB - hBs * hBs)
        GqnT = Gqn + 0.5 * g * (hT * hT - hTs * hTs)
        dh += -(Gh[1:, :] - Gh[:-1, :]) / c.dy
        dhv += -(GqnB[1:, :] - GqnT[:-1, :]) / c.dy
        dhu += -(Gqt[1:, :] - Gqt[:-1, :]) / c.dy

        self.h = self.h + dt * dh
        self.hu = self.hu + dt * dhu
        self.hv = self.hv + dt * dhv
        if c.slope_x or c.slope_y:
            self.hu += dt * g * self.h * c.slope_x
            self.hv += dt * g * self.h * c.slope_y
        self._clean()
        self._friction(dt)
        self.t += dt
        self.steps += 1
        return dt

    def _friction(self, dt: float):
        c = self.cfg
        if self.n_map is None and c.manning_n <= 0.0:
            return
        n = self.n_map if self.n_map is not None else c.manning_n
        wet = self.h > c.h_dry
        h = np.where(wet, self.h, 1.0)
        speed = np.sqrt(self.hu ** 2 + self.hv ** 2) / h
        factor = 1.0 + dt * c.g * n * n * speed / np.power(h, 4.0 / 3.0)
        self.hu = np.where(wet, self.hu / factor, 0.0)
        self.hv = np.where(wet, self.hv / factor, 0.0)

    def run(self, duration: float, callback=None) -> int:
        """Advance by `duration` seconds with adaptive dt. Returns number of steps."""
        end = self.t + duration
        n = 0
        while self.t < end - 1e-12:
            dt = min(self.max_dt(), end - self.t)
            self.step(dt)
            n += 1
            if callback is not None and callback(self) is False:
                break
        return n
