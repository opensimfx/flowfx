# Changelog

## Unreleased

- The list of third-party reference files studied during design moved out of `docs/REFERENCES.md` into a local,
  ignored `private/` folder; the published references keep what FlowFX ships and its licences.
- Repository layout shared by the four OpenSimFX add-ons (CONTRIBUTING.md, Repository conventions): the docs
  and `CONTRIBUTING.md` are now published, under the shared upper-case names (`user_guide.md` -> `USER_GUIDE.md`,
  `presets_reference.md` -> `PRESETS.md`, `theory.md` -> `PHYSICS.md`, `design.md` -> `SYSTEM_DESIGN.md`,
  `development.md` -> `DEVELOPMENT.md`, `roadmap.md` -> `ROADMAP.md`, and the rest upper-cased); README renders
  moved to `docs/img/`, the demo scene to `examples/`. Generated JSON reports stay local (`docs/*.json`).
- The same nine docs as every add-on: the API, decision records and generated Blender bindings moved into
  `SYSTEM_DESIGN.md`; the validation report, Mantaflow validation and spikes into the new `VALIDATION.md` (the
  report tools now write their own marked sections, `tools/_docsection.py`); preview notes into `DEVELOPMENT.md`;
  asset provenance into the new `REFERENCES.md`. The docs index was dropped (the README lists the docs).
- Fix: `tools/render_preview.py` framed the whole water body from outside (an ocean tile read as a small sheet on
  the floor, a river as a thin far-away strip); the camera now stands at the near end of the body's long axis, a
  little above the surface, looking along it 20 degrees down (baked Mantaflow liquids keep the three-quarter
  view). README renders re-made.
- UI follows the shared OpenSimFX conventions (`docs/UI_STYLE.md`, identical in all four add-ons):
  preset category, preset, name and a large *Create Water Body* now open the main panel above the
  body list, with *Remove Water Body* separated at the bottom; the preset's derived values moved
  to *Readout*, *Apply to Active* / *Save* to *Preset Files*, and *Free Cache* sits at the bottom
  of *Cache and Bake*. Every panel uses Blender's label-left property layout. No properties or
  operators changed.

## 0.1.0-alpha - 2026-10-21

First public alpha: the working MVP, plus Mantaflow bakes validated against theory in desktop Blender.

- Extension manifest (schema 1.0.0, Blender 5.2.0+), validated and built with Blender's extension CLI.
- 21 presets in SI units with derived physics readouts (Hs, Froude, breaker type, front speed, wave speed).
- Spectral engine: Ocean modifier surfaces, representative-seed Hs calibration, stacked layers, time driver
  (no handlers), own EXR displacement bake, WaterQuery with choppiness inversion.
- Heightfield engine: first-order HLL shallow-water solver with hydrostatic reconstruction, wet/dry fronts,
  Manning friction; EXR sequence cache displayed through a Displace modifier.
- Fluid engine: Mantaflow domain builder, scenery (channel with merged rocks, cylinder, waterfall, dam break,
  wave tank with Biesel piston), roles, secondary particles, guides, cost estimates. Bake wrappers (UI session only).
- Interaction engine: Dynamic Paint Waves canvas and brushes.
- Floater solver with sampled-volume buoyancy and F-curve baking.
- Shading (six variants), depth volume, compositing node group with foam AOV.
- Operators and panels; preferences; user presets; JSON report export.
- Public API: impulses and WaterQuery for sibling add-ons.
- Tests: unit, API contract, integration, forked fluid, validation. Reports in `docs/`.
- Mantaflow bakes now run from a script: the bake operator is invoked synchronously when Blender runs in
  background mode, and the job is invoked from the UI as before.
- Fixed the flow emission band. Blender's default 1.5 m band was added to the object volume, which made the
  dam-break reservoir 28% larger than its depth said and the river inflow 3 m deep instead of 0.5 m.
- Real Mantaflow bakes in desktop Blender 5.2.1 (`tools/fluid_validation.py`, `docs/FLUID_VALIDATION.md`):
  the dam-break front runs at 5.96 m/s against Ritter's 6.26 m/s, the river inflow holds the designed depth.
- New `tools/desktop_check.py` and `tools/zip_check.py`: every preset is driven through the whole panel surface in
  desktop Blender, from the source tree and from the installed zip (`docs/desktop_check_report.json`,
  `docs/zip_check_report.json`).
- New `tools/render_preview.py`: real Cycles renders, one per engine, plus a demo scene (`docs/PREVIEWS.md`).
- The heightfield core stays in NumPy: the design budget of 10 steps/s at 1024 x 1024 is met, and the presets use
  grids of 100 x 100 to 200 x 50 (`docs/adr/0006-numpy-heightfield-core.md`).
- Repository layout: the add-on package lives in `flowfx/` at the repository root, next to `tests/`, `tools/`,
  `docs/` and `dist/`. The old `flowfx/extension/` wrapper is gone.
- The packaged zip no longer carries `.DS_Store` files (excluded in `blender_manifest.toml`).

Known limits are listed in README.md Status and `docs/SPIKES.md`.
