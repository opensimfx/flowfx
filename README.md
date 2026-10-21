# FlowFX

Physically based water and flow simulation for Blender 5.2+: still water, ponds, lakes, ocean seas, choppy and
storm waves, rivers, streams, flow around obstacles, waterfalls, dam breaks, floods, tsunami bores, breaking surf and
boat wakes. SI-unit presets, calibrated wave heights, three simulation engines, foam, collision, floaters,
shading and compositing templates.

Version 0.1.0 is a **working scaffold plus MVP**. This README says exactly what works, what was tested and what was not.

## Install

1. Download `flowfx-0.1.0.zip` (built by `tools/build_extension.py`, validated with Blender's own extension CLI).
2. Blender 5.2: Preferences, Get Extensions, the dropdown at the top right, Install from Disk, choose the zip.
3. Open a 3D Viewport, press N, select the **FlowFX** tab.

Not yet checked in an interactive desktop session (see Status): the install dialog and panel layout. The add-on
registers, runs every operator and builds every preset under the real `bpy` 5.2.2 module in CI, and every preset was
driven through the whole panel surface in desktop Blender 5.2.1, from the source tree and from the installed zip.

## Quick start

1. FlowFX tab, Presets: pick a category and a preset (for example *Lake*), press **Create Water Body**.
2. Spectral presets build an Ocean surface calibrated to the preset wave height and animate with a driver. Play the timeline.
3. Fluid presets build a Mantaflow domain with scenery, sources, sinks and obstacles. Bake from **Cache and Bake**.
4. Heightfield presets: **Bake** solves the shallow-water equations and writes EXR sequences that drive a Displace modifier.
5. **Roles and Coupling** adds obstacles, sources, sinks, a piston wavemaker and floating objects.

See `docs/user_guide.md`.

## Status

| Area | State | Evidence |
|---|---|---|
| Extension packaging | Built and validated | `blender_ext.py validate` and `build`; `dist/flowfx-0.1.0.zip` |
| Spectral engine (Ocean modifier) | Working | 10 surface presets build, calibrate and bake EXR in tests; held-out Hs errors in `docs/validation_report.md` |
| Heightfield engine (shallow water) | Working, small to medium grids | Lake-at-rest, mass, wave speed, Ritter dam break, Manning all measured; displaced mesh equals baked pixels |
| Fluid engine (Mantaflow) | **Bakes run and match theory** | Baked in desktop Blender 5.2.1: dam-break front 5.96 m/s against Ritter 6.26 m/s (4.9%), river inflow delivers the designed 0.5 m cross-section. `docs/fluid_validation.md` |
| Floater solver | Working | Heave period 0.01% and draft 0.00% from theory; bakes keyframes |
| Dynamic Paint interaction | Builds canvas and brushes | Settings read back; not simulated |
| Shading, volume, compositing | Build | Cycles absorption verified exactly against Beer-Lambert; real renders in `docs/previews.md` |
| GN fluid backend | Capability probe only | 5.2.2 has no Points-to-Grid or Poisson node |
| FLIP Fluids adapter | Detection only | Not tested |
| Desktop UI | Driven headlessly | All 21 presets run through the whole panel surface in desktop Blender 5.2.1, from the source tree and from the installed zip; no interactive session yet |

Tested on the `bpy` 5.2.2 LTS Python module (Python 3.13) and on the desktop 5.2.1 build. 93 tests pass in the module:
76 unit, API contract and integration, 13 forked fluid, 4 slow validation. The 13 forked fluid tests abort in this
environment because the PyPI `bpy` module crashes inside Mantaflow (docs/spikes.md S8); the desktop build runs the
same bakes. `docs/validation_report.md` holds the measured numbers, `docs/fluid_validation.md` the Mantaflow ones and
`docs/previews.md` the renders.

## Layout

```
flowfx/                what is zipped: manifest, package, presets, assets
  core/               pure Python: theory, scale, presets, schema, calibration, jobs, orchestrator
  bindings/           every Blender identifier string (one place to fix API drift)
  engines/            spectral, fluid, heightfield, gn_flip (probe), external (FLIP Fluids detection)
  services/           water query, floaters, cache, estimates, impulses, EXR io
  builders/           datablock writers: tagging, shading, volume, compositing, obstacles, whitewater, shoreline
  props/ ops/ ui/     Blender classes
  api/                public API for sibling add-ons
  presets/            21 JSON presets
  assets/             preview swatches and flowfx_assets.blend (materials)
tests/                unit, api_contract, integration, integration_fluid (forked), validation
tools/                build, validate, desktop checks, fluid validation, renders, docs
docs/                 user guide, design, theory, API, spikes, roadmap, ADRs, generated reports
dist/                 prebuilt flowfx-0.1.0.zip and checksum
scenes/               demo scene and the asset library
```

## Develop

```
uv python install 3.13 && uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python bpy numpy pytest pytest-forked ruff
.venv/bin/python tools/run_tests.py          # add --all for slow validation tests
.venv/bin/python tools/build_extension.py    # writes dist/flowfx-<version>.zip
```

See `docs/development.md` and `CONTRIBUTING.md`.

## Licence

GPL-3.0-or-later (required for Blender add-ons). Reference files from the research phase carry their own licences
and are **not** included; see `docs/assets_provenance.md`.
