"""Generate procedural 128x128 preview swatches for every preset into flowfx/assets/previews.

Run with the bpy module:  python tools/gen_previews.py
The swatch shades a synthetic wave height field with the preset's water variant tint; swell size follows Hs
for surface presets, streak direction follows flow for river/event presets.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pkg  # noqa: E402

_pkg.load()
import bpy  # noqa: E402

from flowfx.builders.shading import VARIANTS  # noqa: E402
from flowfx.core import presets  # noqa: E402

OUT = _pkg.EXT / "assets" / "previews"
N = 128


def field(p):
    y, x = np.mgrid[0:N, 0:N] / N
    amp = {"surface": 0.5, "flow": 0.8, "event": 1.0}[p["category"]]
    if "hs_m" in p.get("targets", {}):
        amp = min(1.0, 0.25 + 0.2 * np.log10(1 + 10 * p["targets"]["hs_m"]))
    z = np.zeros((N, N))
    rng = np.random.default_rng(abs(hash(p["id"])) % 2**32)
    for i in range(6):
        k = 3 + 4 * i
        ang = rng.uniform(-0.4, 0.4) if p["category"] != "surface" else rng.uniform(0, 6.28)
        z += amp * np.sin(2 * np.pi * k * (x * np.cos(ang) + y * np.sin(ang)) + rng.uniform(0, 6.28)) / (i + 1)
    if p["engine"] in ("fluid", "heightfield"):
        z += 0.6 * np.exp(-((x - 0.5) ** 2 + (y - 0.5) ** 2) / 0.02)  # obstacle / bore bump
    return z


def render(p):
    z = field(p)
    gy, gx = np.gradient(z)
    g = (-gx - gy)
    g = g / (g.std() + 1e-9)  # normalise so every swatch has the same contrast
    shade = np.clip(0.62 + 0.18 * g, 0.2, 1.0)
    tint = np.array(VARIANTS[p["shading"]["material"]]["tint"])
    sky = np.linspace(1.0, 0.6, N)[:, None]
    rgb = tint[None, None, :] * 1.5 * (0.55 + 0.7 * shade[:, :, None]) * sky[:, :, None]
    spec = np.clip((g - 1.8) * 0.35, 0, 0.5)[:, :, None]
    rgb = np.clip(rgb + spec, 0, 1) ** (1 / 2.2)
    return np.dstack([rgb, np.ones((N, N))]).astype(np.float32)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for p in presets.load_all():
        img = bpy.data.images.new(f"prev_{p['id']}", N, N, alpha=True)
        img.pixels.foreach_set(render(p).ravel())
        img.filepath_raw = str(OUT / f"{p['id']}.png")
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)
    print(f"wrote {len(list(OUT.glob('*.png')))} previews to {OUT}")


if __name__ == "__main__":
    main()
