"""Generate flowfx/presets/*.json from the catalogue below.

The JSON files are the source of truth after generation; this script documents the
physical reasoning for each seed value and keeps them reproducible.
Run: python tools/gen_presets.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "flowfx" / "presets"


def surface(pid, name, desc, wind, depth, extent, hs, spectrum, chop, align, damp, foam,
            res, vres, fetch=None, sharpen=None, spray=False, material="lake", use_foam=True, tags=()):
    physical = {"wind_speed_mps": wind, "depth_m": depth, "extent_m": extent}
    if fetch is not None:
        physical["fetch_m"] = fetch
    mapping = {"spectrum": spectrum, "choppiness": chop, "wave_alignment": align, "damping": damp,
               "foam_coverage": foam, "resolution": res, "viewport_resolution": vres,
               "use_foam": use_foam, "use_spray": spray, "layers": 1}
    if sharpen is not None:
        mapping["sharpen_peak_jonswap"] = sharpen
    return {"schema": 1, "id": pid, "name": name, "category": "surface", "engine": "spectral",
            "description": desc, "physical": physical, "targets": {"hs_m": hs}, "mapping": mapping,
            "calibrate": {"method": "hs", "seeds": [1, 2, 3, 4, 5, 6], "tolerance": 0.10},
            "shading": {"material": material}, "tags": list(tags)}


def fluid(pid, name, cat, desc, physical, scenario, method, voxel, material, sec=(True, True, True),
          borders=None, flip_ratio=0.97, tags=(), cache="MODULAR", **extra):
    mapping = {"scenario": scenario, "method": method, "voxel_m": voxel, "flip_ratio": flip_ratio,
               "particle_number": 2, "use_fractions": True, "fractions_distance": 0.5, "mesh_scale": 2,
               "secondary": {"spray": sec[0], "foam": sec[1], "bubbles": sec[2]},
               "cache": {"type": cache, "data_format": "OPENVDB", "compress": "BLOSC"},
               "borders": borders or {"x": False, "y": True, "z_bottom": True, "z_top": False}}
    mapping.update(extra)
    return {"schema": 1, "id": pid, "name": name, "category": cat, "engine": "fluid", "description": desc,
            "physical": physical, "targets": {}, "mapping": mapping, "calibrate": {},
            "shading": {"material": material}, "tags": list(tags)}


def heightfield(pid, name, cat, desc, physical, scenario, cell, duration, material, tags=(), **extra):
    mapping = {"scenario": scenario, "cell_m": cell, "duration_s": duration, "cfl": 0.45}
    mapping.update(extra)
    return {"schema": 1, "id": pid, "name": name, "category": cat, "engine": "heightfield",
            "description": desc, "physical": physical, "targets": {}, "mapping": mapping, "calibrate": {},
            "shading": {"material": material}, "tags": list(tags)}


def interaction(pid, name, cat, desc, physical, mapping, material, tags=()):
    return {"schema": 1, "id": pid, "name": name, "category": cat, "engine": "interaction",
            "description": desc, "physical": physical, "targets": {}, "mapping": mapping, "calibrate": {},
            "shading": {"material": material}, "tags": list(tags)}


PRESETS = [
    interaction("still_water", "Still Water", "surface",
                "Flat water plane with micro-ripple shading. Dynamic Paint Waves reacts to objects entering the water.",
                {"extent_m": 50.0, "depth_m": 2.0},
                {"canvas": True, "wave_speed": 1.0, "wave_damping": 0.05, "wave_timescale": 1.0,
                 "wave_spring": 0.2, "wave_smoothness": 1.0, "grid_cells": 128}, "clear", ["calm", "interaction"]),
    surface("pond", "Pond Ripples", "Sheltered pond; faint wind ripples.", 1.5, 1.5, 20, 0.02,
            "TEXEL_MARSEN_ARSLOE", 0.1, 0.3, 0.8, -1.0, 12, 8, material="clear", use_foam=False,
            tags=["calm", "shallow"]),
    surface("small_waves", "Small Waves", "Light chop on a small water body.", 4.0, 3.0, 50, 0.10,
            "TEXEL_MARSEN_ARSLOE", 0.4, 0.6, 0.7, -0.5, 14, 8, material="lake", use_foam=False,
            tags=["calm", "shallow"]),
    surface("lake", "Lake", "Fetch-limited lake sea, 6 m/s wind over 3 km.", 6.0, 8.0, 100, 0.17,
            "TEXEL_MARSEN_ARSLOE", 0.6, 0.5, 0.6, -0.2, 16, 8, fetch=3000, material="lake",
            tags=["lake", "shallow"]),
    surface("lake_windy", "Windy Lake", "Fetch-limited lake sea, 10 m/s wind over 8 km.", 10.0, 12.0, 150, 0.46,
            "TEXEL_MARSEN_ARSLOE", 1.0, 0.6, 0.5, 0.1, 16, 8, fetch=8000, material="lake",
            tags=["lake", "wind"]),
    surface("ocean_swell", "Ocean Swell", "Long established swell, developing sea.", 8.0, 200.0, 200, 0.8,
            "JONSWAP", 0.8, 0.9, 0.7, 0.0, 18, 9, material="ocean", tags=["ocean", "swell"]),
    surface("ocean_moderate", "Ocean Moderate", "Moderate sea, Pierson-Moskowitz spectrum.", 12.0, 200.0, 200, 2.0,
            "PIERSON_MOSKOWITZ", 1.0, 0.7, 0.5, 0.2, 18, 9, material="ocean", tags=["ocean"]),
    surface("ocean_rough", "Ocean Rough", "Rough sea, JONSWAP with sharp peaks.", 16.0, 200.0, 300, 4.0,
            "JONSWAP", 1.3, 0.6, 0.4, 0.4, 20, 10, sharpen=0.5, material="ocean", tags=["ocean", "rough"]),
    surface("choppy_waves", "Choppy Waves", "Steep short-crested turbulent sea with heavy foam.", 14.0, 200.0, 100, 1.2,
            "PHILLIPS", 1.8, 0.2, 0.2, 0.5, 18, 9, material="ocean", tags=["ocean", "choppy"]),
    surface("storm", "Storm Sea", "Storm sea with spray map.", 25.0, 200.0, 400, 8.0,
            "JONSWAP", 1.5, 0.6, 0.3, 0.8, 22, 11, sharpen=0.7, spray=True, material="ocean_dark",
            tags=["ocean", "storm"]),
    heightfield("river_calm", "River (Calm)", "flow",
                "Lowland river reach: shallow-water solver, Manning friction, subcritical flow.",
                {"depth_m": 2.0, "slope": 0.0003, "manning_n": 0.035, "extent_m": [200.0, 40.0]},
                "river_reach", 1.0, 60.0, "murky", ["river", "heightfield"]),
    fluid("river_rapids", "River Rapids", "flow",
          "Steep rocky reach, supercritical flow with hydraulic jumps and whitewater.",
          {"depth_m": 0.5, "slope": 0.05, "manning_n": 0.05, "extent_m": [30.0, 10.0, 6.0]},
          "channel", "APIC", 0.1, "turbulent", tags=["river", "whitewater"]),
    fluid("stream_creek", "Stream / Creek", "flow", "Small shallow creek over rocks.",
          {"depth_m": 0.15, "slope": 0.015, "manning_n": 0.04, "extent_m": [8.0, 4.0, 2.0]},
          "channel", "APIC", 0.05, "clear", tags=["river", "small"]),
    fluid("flow_around_obstacle", "Flow Around Obstacle", "flow",
          "Current past a circular pier; wake and vortex shedding.",
          {"depth_m": 2.0, "velocity_mps": 2.0, "cylinder_d_m": 1.0, "extent_m": [20.0, 10.0, 4.0]},
          "cylinder", "APIC", 0.1, "murky", tags=["obstacle", "wake"]),
    fluid("waterfall", "Waterfall", "flow", "Inflow over a drop; impact, spray and bubbles.",
          {"drop_m": 6.0, "inflow_depth_m": 0.3, "inflow_velocity_mps": 2.0, "extent_m": [10.0, 10.0, 12.0]},
          "waterfall", "FLIP", 0.1, "turbulent", tags=["waterfall", "spray"]),
    fluid("dam_break", "Dam Break", "event", "Dry-bed dam break; front speed checks against Ritter.",
          {"h0_m": 1.0, "extent_m": [20.0, 5.0, 5.0]},
          "dam_break", "FLIP", 0.1, "clear", sec=(True, True, False),
          borders={"x": True, "y": True, "z_bottom": True, "z_top": False}, tags=["event", "validation"]),
    heightfield("flash_flood", "Flash Flood", "event",
                "Inflow flood front over sloping terrain with wet/dry fronts.",
                {"inflow_depth_m": 1.5, "inflow_velocity_mps": 2.0, "terrain_slope": 0.002,
                 "extent_m": [500.0, 500.0]},
                "flood_plain", 5.0, 120.0, "murky", ["event", "flood"]),
    heightfield("tsunami_bore", "Tsunami Bore", "event",
                "Leading wave only: shallow-water far field with a bore running up a 1:20 beach.",
                {"offshore_depth_m": 10.0, "bore_height_m": 5.0, "beach_slope": 0.05, "extent_m": [2000.0, 500.0]},
                "tsunami_pulse", 10.0, 120.0, "ocean_dark", ["event", "tsunami"]),
    fluid("surf_breaking", "Breaking Surf", "event",
          "Piston-driven wave train shoaling and breaking on a 1:10 beach.",
          {"wave_height_m": 1.5, "period_s": 8.0, "depth_m": 4.0, "beach_slope": 0.1,
           "extent_m": [120.0, 8.0, 10.0]},
          "wave_tank", "FLIP", 0.2, "ocean", borders={"x": True, "y": True, "z_bottom": True, "z_top": False},
          tags=["event", "surf", "tank"]),
    interaction("boat_wake", "Boat Wake", "event",
                "Moving hull over a Dynamic Paint Waves canvas; Kelvin wake angle check.",
                {"hull_speed_mps": 6.0, "extent_m": 100.0, "depth_m": 10.0},
                {"canvas": True, "wave_speed": 1.0, "wave_damping": 0.02, "wave_timescale": 1.0,
                 "wave_spring": 0.1, "wave_smoothness": 1.0, "grid_cells": 256}, "lake",
                ["event", "wake", "interaction"]),
    surface("custom", "Custom Ocean", "Blank spectral surface for manual tuning.", 10.0, 200.0, 100, 1.0,
            "JONSWAP", 1.0, 0.5, 0.5, 0.0, 16, 8, material="ocean", tags=["custom"]),
]


def main():
    for old in OUT.glob("*/*.json"):
        old.unlink()
    for p in PRESETS:
        d = OUT / p["category"]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{p['id']}.json").write_text(json.dumps(p, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(PRESETS)} presets to {OUT}")


if __name__ == "__main__":
    main()
