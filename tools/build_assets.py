"""Build flowfx/assets/flowfx_assets.blend: one asset-marked water material per variant.

Run with the bpy module:  python tools/build_assets.py
The materials come from the same builder the add-on uses at runtime, so the library never drifts.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pkg  # noqa: E402

_pkg.load()
import bpy  # noqa: E402

from flowfx.builders import shading  # noqa: E402

OUT = _pkg.EXT / "assets" / "flowfx_assets.blend"


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = set()
    for variant in shading.variant_names():
        mat = shading.build_water_material(f"FlowFX Water {variant.replace('_', ' ').title()}", variant)
        mat.asset_mark()
        mat.asset_data.description = f"FlowFX water shader, {variant} variant (IOR 1.333, volume absorption)"
        mat.asset_data.tags.new("FlowFX", skip_if_exists=True)
        mat.use_fake_user = True
        mats.add(mat)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(OUT), mats, fake_user=True)
    print(f"wrote {len(mats)} materials to {OUT} ({OUT.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
