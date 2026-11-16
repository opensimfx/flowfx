# Roadmap

Status as of 1.0.0 (2026-11-16): the three engines, coupling, shading and caches are stable; the Geometry Nodes FLIP backend and the FLIP Fluids adapter stay internal (probe and detection only, not in the panel; M6). Sizes: S under 1 week, M 2 to 3 weeks, L 4 to 6 weeks (one developer).

| Milestone | Scope | Status | Remaining |
|---|---|---|---|
| M0 Spikes | S1 to S9 | Mostly done | S1, S3, S4 (moving domain), S9 need a desktop Blender with Mantaflow and FLIP Fluids; see `VALIDATION.md (Spikes)` |
| M1 Spectral MVP | Extension, bindings, spectral engine, calibration, 10 surface presets, shading, EXR bake, previews, API contract test | **Done** | Real preview renders; panel for extra layers; EEVEE check |
| M2 Fluid core | Domain builder, roles, obstacles, caches, six fluid presets, whitewater path | **Bakes validated** | Real bakes done: dam-break front within 4.9% of Ritter, river inflow at the design depth. Spray and foam render as instanced meshes (1.0). Left: calibrate estimates against real bakes, secondary particles to Point Clouds |
| M3 Tank and events | Wavemaker, beach, guided up-res, surf, compositing, EEVEE | Partial | Guides (S1, S3); absorbing end; tsunami FLIP region; EEVEE parity |
| M4 Heightfield | Solver, boundaries, rivers, flood, tsunami far field | **Solver and bake done** | Hand-off to a FLIP region; larger grids (compiled core). Shading from the flow sequence done in 1.0 |
| M5 Coupling | Floaters, interaction, wake, Impulse API | Partial | Engines consuming impulses; floater collisions. Wake angle validated in 1.0 (18.7 deg against 19.47 deg) |
| M6 Release | Docs, FLIP Fluids adapter, performance, wheel, submission | **1.0 released**: docs, CI, upgrade path, look pass | Adapter, compiled core, extension platform submission, GN backend when Blender ships the nodes |

## Next steps in order

1. ~~Open `dist/flowfx-0.1.0.zip` in desktop Blender 5.2.1; run each preset; fix whatever the UI shows~~ **Done**:
   the zip installs with Blender's own extension CLI and all 21 presets run through the whole panel surface from the
   installed extension (`docs/zip_check_report.json`), the same from the source tree (`docs/desktop_check_report.json`).
2. ~~Run real Mantaflow bakes of `dam_break` and `river_rapids`; compare to `docs/PHYSICS.md`~~ **Done**: the
   dam-break front is within 4.9% of Ritter's 6.26 m/s and the river inflow delivers the designed cross-section
   (`docs/VALIDATION.md (Mantaflow validation)`). The flow emission band was fixed on the way: the reservoir was 28% too large.
3. ~~Decide on a compiled core (C++ or Numba wheel) based on target grid sizes~~ **Done**: the budget of 10 steps/s at
   1024 x 1024 is met by NumPy (14.3 steps/s) and the presets use grids of 100 x 100 to 200 x 50, so the solver stays in
   NumPy (`docs/SYSTEM_DESIGN.md (decision record 0006)`).
4. Impulse consumption in heightfield and interaction engines (M5).
5. ~~Real preview renders and a demo scene~~ **Done**: Cycles renders of one preset per engine and a demo scene
   (`docs/DEVELOPMENT.md (Preview renders)`, `examples/flowfx_demo.blend`).
6. Close the spikes that a desktop bake unblocked: S1 (an Ocean-displaced mesh as an Effector Guide) and S3
   (domain-to-domain guide up-res).
