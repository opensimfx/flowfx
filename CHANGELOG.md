# Changelog

## Unreleased

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
- Real Mantaflow bakes in desktop Blender 5.2.1 (`tools/fluid_validation.py`, `docs/fluid_validation.md`):
  the dam-break front runs at 5.96 m/s against Ritter's 6.26 m/s, the river inflow holds the designed depth.
- New `tools/desktop_check.py` and `tools/zip_check.py`: every preset is driven through the whole panel surface in
  desktop Blender, from the source tree and from the installed zip (`docs/desktop_check_report.json`,
  `docs/zip_check_report.json`).
- New `tools/render_preview.py`: real Cycles renders, one per engine, plus a demo scene (`docs/previews.md`).
- The heightfield core stays in NumPy: the design budget of 10 steps/s at 1024 x 1024 is met, and the presets use
  grids of 100 x 100 to 200 x 50 (`docs/adr/0006-numpy-heightfield-core.md`).
- Repository layout: the add-on package lives in `flowfx/` at the repository root, next to `tests/`, `tools/`,
  `docs/` and `dist/`. The old `flowfx/extension/` wrapper is gone.
- The packaged zip no longer carries `.DS_Store` files (excluded in `blender_manifest.toml`).

Known limits are listed in README.md Status and `docs/spikes.md`.
