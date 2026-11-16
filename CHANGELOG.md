# Changelog

## 1.0.0 - 2026-11-16

First stable release. Scenes made with 0.2 are upgraded once when they are opened (water materials, open-sea
horizon and foam, riverbeds, Mantaflow white water); heightfield bodies need a new bake for dry ground, ripples
and white water, and Mantaflow bodies a new mesh bake for the smoother surface.

### Water that looks real (research in `docs/PHYSICS.md`, *Look*)

- Open water reflects the sky: ocean and lake surfaces carried an absorption volume on an open sheet, which made
  Cycles count the camera as underwater and absorb every ray, so the sea rendered as a dark matte plane (or washed
  out). Water is now built for how it is bounded: *deep* (open water: a dark body colour under a Fresnel water
  reflection), *shallow* (heightfield rivers over their bed: refraction tinted by the water colour) and *closed*
  (baked Mantaflow liquids: refraction plus the measured Beer-Lambert absorption volume).
- Foam follows the wind: Blender's foam coverage was set by eye and drew foam over 78 % (Ocean Moderate) to 90 %
  (Storm) of the sea. It is now calibrated per preset, like the wave height, to the measured whitecap fraction
  W = 3.84e-6 U^3.41 (Monahan and O'Muircheartaigh 1980): 1.8 % at 12 m/s, 22 % at 25 m/s. Foam is broken into
  patches and wind-blown streaks.
- Short waves and sun glitter: the simulated mesh carries the long waves, so open water gets a chop bump and
  roughness that together give the mean-square slope measured by Cox and Munk for the preset's wind
  (0.003 + 5.12e-3 U).
- Open sea reaches the horizon: ocean presets tile their wave patch out to about 2 km, centred on the body, and a
  flat far-sea plane carries the water to the horizon. Queries, floaters, bakes and calibration still measure
  the one simulated tile.
- Rivers and floods have ground: heightfield bodies build their riverbed as its own object, and the baked
  surface carries a wet mask, so dry banks and ground show earth instead of a sheet of water, with a soft
  shoreline.
- Rivers and floods move: heightfield water carries ripples that drift downstream with the solved velocity (a
  flow map: two advected copies cross-faded so the pattern never stretches), stronger where the water is faster,
  and white water where the flow is near critical or converging (the solver's foam mask, broken up by the same
  ripples). Shallow water is as opaque as its variant: muddy flood and tsunami water hide their bed, a clear
  stream shows it.
- Mantaflow white water renders: the spray, foam and bubble particles were halos, which Cycles does not draw.
  They are now instanced meshes sized by the voxel (spray as fine white droplets, foam as flat flecks, bubbles
  as clear spheres), so dam breaks, rapids, waterfalls and surf show their spray and foam.
- Mantaflow surfaces are smoothed (3 positive, 2 negative passes instead of 1 and 1), which removes the voxel
  facets without thinning jets and sheets; rocks, cliffs, piers and beds get a ground material.
- Boat wakes: Dynamic Paint brushes never made waves. FlowFX left each brush modifier's type on CANVAS (the
  panel tab sets it in the UI) and Dynamic Paint only collects BRUSH modifiers, so obstacles on Still Water and
  Boat Wake canvases did nothing. Fixed; Boat Wake now also builds the boat its description promised: an 8 m
  deep-V motorboat (lofted hull with antifouling, topsides and deck, and a console with a windscreen) crossing
  the canvas at the preset speed. The wave speed is set from the boat's speed so the wake opens at the Kelvin
  angle (measured 18.7 deg against 19.47 deg), and the hull paints a white wash on a second canvas layer that
  fades over 8 s behind the stern.
- Still and calm water is no longer a perfect mirror: light air ruffles it in patches (catspaws) with glassy
  water between, using the Cox-Munk slope for the wind; the patches merge into uniform chop by 4 m/s.
- Rivers and streams (Mantaflow) flow at their normal depth from the first frame, fed by an inflow across the full
  channel: no dry start and no block of held water with side walls at the inlet. The waterfall starts with water
  running to its lip and a plunge pool held at its level by an outflow, so the curtain is falling within a second;
  its domain is cut to what the fall needs (10 x 7 x 9 m) with 7 cm cells, so the 0.3 m stream over the lip is
  four cells deep instead of three and runs smooth instead of breaking into blobs.
- Mantaflow quality: Standard (the preset's grid), High (1.5x finer, 4.0x the bake time) and Cinematic (2x finer,
  9.2x), in Cache and Bake. Measured on the dam break, 48 frames: 23 s, 90 s, 209 s.
- Fix: white water could crash Blender. At Mantaflow's default emission Flow Around Obstacle carried 14.7 million
  spray, foam and bubble particles at frame 40 (10 M bubbles inside the liquid), and on a finer grid the count
  overflowed Blender's particle array on load. Trapped-air emission (the bubbles) is cut to a tenth and divided by
  the growth in cell count; wave-crest emission (spray and foam) keeps Mantaflow's default at Standard and is
  divided by the grid refinement at High and Cinematic.
- River and flood turbulence scales with the flow: surface slope grows with the square of the speed, and the
  largest boils grow with the body (up to 1/30 of it), so a tsunami run-up seen from the air shows structure and
  a calm river seen from its bank shows fine ripples. Tsunami run-up water is turbid.
- Presets appear at once: the calibration of every spectral preset at its defaults is measured when FlowFX is
  built (`tools/precalibrate.py`, `presets/calibration.json`), so creating Ocean Moderate takes 0.3 s instead of
  5 s and Storm 0.3 s instead of 12.5 s. Any change to a preset's inputs is calibrated live as before.
- Changing the water variant keeps the open-water chop, the far-sea plane and a heightfield bake's wet mask and
  flow shading (it used to drop them).
- Storm, Rough and Choppy seas no longer fold their crests into rolled tubes (choppiness at most 1.2); storm
  foam is fine lace and long streaks along the wind instead of patches.

### Reliability

- Fix: heightfield and spectral EXRs lost their data wherever alpha was below 1 (Blender premultiplied on save
  and divided on load); data EXRs are now channel-packed and round-trip exactly.
- Caches are referenced relative to the saved .blend (Mantaflow cache folder, heightfield sequence), so a moved
  project or a render farm finds them. Unsaved files bake into the system temp folder (with a warning) instead
  of Blender's working directory, which is "/" when Blender starts from the macOS Dock.
- Fluid tests run one process per test instead of forking (Windows has no fork; on macOS a forked `bpy`
  process crashed).
- Continuous integration: every test on Linux, Windows and macOS with the `bpy` module; a Linux job with Blender
  5.2.3 and 5.2.4 builds and validates the zip, installs it in a clean profile and drives all 21 presets through
  the panels, bakes the dam break in Mantaflow against Ritter's solution and renders the sea in Cycles.
- New tests: `tests/integration/test_look_and_hardening.py` (tiling, far sea, foam, chop, material modes,
  riverbed and wet mask, flow detail, shallow opacity, EXR round trip, cache paths, driver), a Mantaflow test for
  white water, smoothing and scenery and `tests/integration/test_upgrade.py` (a scene
  saved by 0.2.0-alpha). New `tools/render_look.py` renders the look bench and the README images.

## 0.2.0-alpha.1 - 2026-11-16

- `docs/REFERENCES.md` covers what FlowFX ships and its licences; working research notes are no longer published.
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
