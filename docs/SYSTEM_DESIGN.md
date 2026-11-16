# System Design

This describes what 0.1.0 does. Differences from the original design document are listed at the end.

## Layers

```
ui/, ops/, props/            Blender classes: panels, operators, PropertyGroups, preferences
  core/orchestrator.py       body lifecycle: create, rebuild, remove, query
    core/                    presets, schema, theory, scale, calibration, jobs, issues (pure Python)
    engines/                 spectral, fluid, heightfield, interaction, gn_flip (probe), external (detection)
    services/                water_query, floaters, cache, estimate, impulses, imageio
    builders/                datablock writers: common (tagging), shading, volume, compositing, obstacles, whitewater, shoreline
    bindings/                every Blender identifier string, each with a CONTRACT table
```

Rules:

- `core/`, `services/water_query.py`, `services/floaters.py`, `services/cache.py`, `services/impulses.py` and
  `engines/heightfield/solver.py` import no `bpy`. They run under plain pytest.
- Only `bindings/` holds Blender identifier strings; `tests/api_contract` checks them against the running Blender.
- No app handlers in the playback path. Time uses drivers, heightfield output uses EXR image sequences, floaters are
  F-curves, Dynamic Paint and Mantaflow use Blender's own caches.

## Water body

A **body** is one logical water volume. Its state lives in `scene.flowfx.bodies` (a `FlowFXBody` PropertyGroup:
uid, title, preset id, engine, overrides JSON, build info JSON, calibration fields). Every datablock FlowFX creates carries
an ID property `flowfx = {body, role, ...}`; objects live in `FlowFX/<name> [<uid>]` collections. `common.remove_body(uid)`
deletes everything tagged with a uid. Roles: `SURFACE`, `DOMAIN`, `OBSTACLE`, `TERRAIN`, `SOURCE`, `SINK`, `BLOCK`,
`WAVEMAKER`, `FLOATER`, `OUTPUT`, `MATERIAL`, `COLLECTION`.

## Engine interface

```python
class Engine(ABC):
    id: str
    capabilities: frozenset            # SURFACE_HEIGHT, VELOCITY, FOAM_MASK, COLLISION, GUIDE_OUT, GUIDE_IN, BAKE
    def build(ctx) -> BuildResult      # create datablocks
    def validate(ctx) -> list[Issue]
    def estimate(ctx, frames) -> CostEstimate
    def update(ctx, changed) / bake(ctx, stage) / query(ctx) / teardown(ctx)
```

`BuildContext` = scene, uid, name, preset dict, overrides, cache root, location. Engines register with
`@register`. `orchestrator.create_body` runs `validate`, then `build`, then stores results on the body.

### Spectral

One Ocean object, GENERATE layer first; extra layers are further Ocean modifiers in DISPLACE mode (verified additive).
`wave_scale` and `random_seed` come from calibration. Time = driver `max(0, (frame - start) * base / fps * speed) + offset`,
a simple expression (no Python auto-run needed). Foam attribute `flowfx_foam`. Bake: FlowFX evaluates the surface per frame
and writes `flowfx_disp_####.exr` (R, G = horizontal displacement, B = height, A = foam) at render resolution.
`query.build_query` returns a `GridHeightQuery` from the evaluated mesh (translation-only objects, one tile).
Open-sea presets (tag `ocean`) repeat the tile an odd number of times out to about 2 km and a `FlowFX Tiles`
Geometry Nodes modifier shifts the grid so the original tile stays centred; `bindings.ocean.single_tile` switches
both off whenever FlowFX evaluates the surface (queries, floaters, bake, calibration), so every measurement is of
the simulated tile. A flat `FAR_SEA` plane one Hs below mean level, sharing the material, carries the sea to the
horizon. Foam coverage is calibrated after Hs (`calibrate.calibrate_foam`). `presets/calibration.json`
(written by `tools/precalibrate.py`) stores the result for each preset at its defaults under a key hashing every
input (Ocean parameters, target, seeds, tolerance, sample times, wind, Blender major.minor, cache version); a body
whose key matches skips calibration (`calibration_source: precomputed`), any other is measured live.

### Heightfield

`engines/heightfield/solver.py` is the shallow-water solver (see `PHYSICS.md`). Scenarios (`river_reach`, `flood_plain`,
`tsunami_pulse`) build bed, initial state and boundaries from a preset. Bake writes two EXR sequences per frame:
`flowfx_hf_surface_####.exr` (R=G=B=water surface elevation; dry cells sit on the bed) and `flowfx_hf_flow_####.exr`
(u, v, depth, foam). The surface sequence's alpha is a wet mask (depth / 2 cm); dry cells sit 2 cm below the bed and
the water shader turns them transparent over the `TERRAIN` riverbed object built from the scenario's bed. Data EXRs are
channel-packed (RGB and A independent). A grid mesh with vertices at cell centres and UVs at pixel centres is displaced
by a Displace modifier reading the surface sequence (texture alpha off), so displaced vertices equal baked pixels
(tested). Bake is a generator
(`bake_iter`), run modal in the UI with cancel, or synchronously from scripts.

### Fluid

`domain.py` derives Mantaflow settings from the preset and `scale.py` (resolution from target voxel size divided by the
body's quality factor, `domain.QUALITY`: standard 1, high 1.5, cinematic 2; cache layout,
secondary particles, borders). `scenarios.py` builds starter scenery: channel (sloped bed, rocks merged into one effector,
Manning-velocity inflow across the full width, an initial slab at normal depth on the sloping bed, outflow),
cylinder pier, waterfall (cliff-top stream from a wall inflow, plunge pool with an outflow at its level), dam break, wave tank (beach wedge, still-water block, keyframed
piston from the Biesel transfer function). `roles.py` assigns Effector / Flow roles, setting the planar flag for open
meshes. `guides.py` enables guiding. `bake.py` calls `bpy.ops.fluid.bake_*` (UI session). **Not exercised by a bake in tests.**

### Interaction

Dynamic Paint Waves canvas on a cell-centre grid plus brush objects (`still_water`, `boat_wake`). `boat_wake`
builds a stand-in motorboat whose hull is the brush, keyframed linearly across the canvas at `hull_speed_mps`;
the canvas `wave_speed` is set so the wave speed is a third of the boat's (Kelvin half-angle), and a second
canvas surface (PAINT, dissolving) records the wash in the `flowfx_foam` colour layer the water material reads.

### gn_flip and external

`gn_flip` reports whether the node types a GN FLIP backend needs exist (they do not in 5.2.2). `external.flipfluids`
detects the FLIP Fluids add-on by name; conversion raises `NotImplementedError`.

## Services

- **WaterQuery** (height, normal, velocity, depth): `FlatWater`, `GridHeightQuery` (bilinear, choppy-displacement inversion).
- **Floater solver**: 6-DOF rigid body, sampled-volume buoyancy, linear and quadratic drag, angular damping, optional added
  mass, semi-implicit Euler at 240 Hz, quaternion orientation. `bake_to_fcurves` writes keyframes.
- **Cache**: per-body directories under the cache root, manifest with a parameter hash for stale detection, free, disk check.
- **Estimates**: heuristic RAM and disk (constants in `core/scale.py`, to be calibrated against measured Mantaflow runs).
- **Impulses**: bus for RainFX / BlastFX style events; `gaussian_bump` adds a conserved water volume to a depth array.
  Nothing consumes impulses inside an engine yet.

## Build pipeline

`validate` (issues with severity) then `build` (single undo step per operator) then results stored. Rebuild
(`orchestrator.rebuild_body`) tears down by uid and builds again with the same uid and name. Cost estimate and disk check
before a bake; bakes are generators with progress and cooperative cancel (`core/jobs.py`).

## Differences from the original design document

| Design document | Built | Reason |
|---|---|---|
| Layers via a Geometry Nodes composite using Sample UV Surface | Stacked Ocean modifiers (GENERATE then DISPLACE) | Verified additive and far simpler |
| Ocean bake through `bpy.ops.object.ocean_bake` | Own EXR bake | The operator is a background job that writes nothing headless |
| Calibrate `wave_scale` on 3 seeds | Representative-seed selection plus fit | Seed-to-seed spread up to 25 percent |
| 10 steps/s at 1024 squared | 1.8 steps/s (single core) | NumPy limits; compiled core deferred |
| `builders/sources.py`, `composite.py`, `shoreline` in Geometry Nodes | Roles module, no composite, Python KD-tree shoreline mask | Smaller and testable; GN proximity later |
| Tank absorbing end | Not implemented | No documented sponge layer in Mantaflow |
| Impulse consumption by engines | Bus only | Scheduled for M5 |
| Fluid, guides, FLIP Fluids adapter validated | Configuration only | No headless Mantaflow in the test environment |

## Public API

### Public API for sibling add-ons

```python
import flowfx.api as fx          # in an installed extension: bl_ext.<repo>.flowfx.api

fx.API_VERSION                   # 1
fx.add_impulse(kind="DROP", position=(x, y, z), radius=0.05, energy_j=0.002, t=0.0, body="nearest")
fx.subscribe(handler)            # handler(impulse) called for each impulse
q = fx.get_water_query(body_uid) # WaterQuery or KeyError / NotImplementedError
```

Kinds: `DROP`, `SPLASH`, `EXPLOSION`, `WAKE`. RainFX would send `DROP`; BlastFX `EXPLOSION`. Impulses are queued and
delivered to subscribers; engine consumption is not implemented in 0.1.0. `services.impulses.gaussian_bump` adds a conserved
volume (m^3) to a depth array for heightfield use.

`WaterQuery` methods: `height(xy, t)`, `normal(xy, t)`, `velocity(xyz, t)`, `depth(xy, t)`; positions are numpy arrays.
Available for spectral bodies; `FlatWater` and `GridHeightQuery` can be constructed directly.

### Preset schema (version 1)

```json
{
  "schema": 1, "id": "lake", "name": "Lake", "category": "surface", "engine": "spectral",
  "description": "...",
  "physical": {"wind_speed_mps": 6.0, "depth_m": 8.0, "extent_m": 100, "fetch_m": 3000},
  "targets": {"hs_m": 0.17},
  "mapping": {"spectrum": "TEXEL_MARSEN_ARSLOE", "choppiness": 0.6, "wave_alignment": 0.5, "damping": 0.6,
              "foam_coverage": -0.2, "resolution": 16, "viewport_resolution": 8, "use_foam": true, "use_spray": false},
  "calibrate": {"method": "hs", "seeds": [1, 2, 3, 4, 5, 6], "tolerance": 0.10},
  "shading": {"material": "lake"},
  "tags": ["lake", "shallow"]
}
```

Required mapping keys per engine: spectral (`spectrum`, `resolution`, `viewport_resolution`, `choppiness`), fluid
(`scenario`, `method`, `voxel_m`, `secondary`, `cache`), heightfield (`scenario`, `cell_m`, `duration_s`, `cfl`),
interaction (`canvas`, `grid_cells`). Validation: `core/schema.py`; check all files with `tools/validate_presets.py`.
User presets are saved as `<config>/flowfx_presets/<category>/user_<name>.json` and appear in the dropdown.
`docs/PRESETS.md` lists every shipped preset.

### Engine contract

See `docs/SYSTEM_DESIGN.md`. To add an engine: subclass `engines.base.Engine`, decorate with `@register`, import it in
`engines/registry.load_builtin`, add its id to `core/schema.ENGINES` and `REQUIRED`.

### Operators

`flowfx.body_create`, `body_remove`, `preset_apply`, `preset_save`, `role_assign`, `role_clear`, `wavemaker_add`,
`floater_bake`, `calibrate`, `estimate`, `validate`, `bake`, `bake_cancel`, `cache_free`, `shading_build`, `volume_build`,
`compositing_build`, `export_report`. All except `estimate`, `validate`, `bake_cancel` are undoable or confirm.
`flowfx.bake` runs a modal job from the UI (Esc cancels) and synchronously via `EXEC_DEFAULT`.

### Blender identifiers

`docs/SYSTEM_DESIGN.md (Blender API bindings)` lists every identifier, type and default; `tests/api_contract` verifies them.

## Decision records

Architecture decisions, oldest first.

### 0001 Ship as a Blender Extension

Status: accepted.

Context: Blender 4.2 introduced extensions (`blender_manifest.toml`); 5.2 is the target. Older water add-ons still use
legacy `bl_info` registration.

Decision: package as an extension with schema 1.0.0, `blender_version_min = "5.2.0"`, GPL-3.0-or-later, one permission
(`files`, for caches and presets). Build with Blender's own `blender_ext.py` so validation matches Blender's rules.

Consequences: relative imports only; the package name differs by install (`flowfx` in tests, `bl_ext.<repo>.flowfx` installed),
so preferences derive their id from `__name__`. Compiled wheels, if added, require `platforms` and `wheels`.

### 0002 Three engines behind one orchestrator

Status: accepted.

Context: the Ocean modifier is a deep-water spectral model; Mantaflow is the only liquid solver in 5.2 and is too expensive at
river or tsunami scale; Blender 5.2 has no Geometry Nodes fluid solver (verified: no Points-to-Grid, no Poisson node).

Decision: Spectral (Ocean modifier), Fluid (Mantaflow), Heightfield (own shallow-water solver), plus a Dynamic Paint
interaction engine, all behind `Engine` and a preset layer. A GN FLIP backend is a probe-only stub.

Consequences: presets choose an engine; large-scale shallow flows do not pay for FLIP; a future GN solver is one more engine.

### 0003 Isolate Blender identifiers in bindings/

Status: accepted.

Context: 5.0 and 5.2 changed Python APIs (compositor node groups, Geometry Nodes modifier inputs, materials without `use_nodes`),
and fluid properties behave in version-specific ways (secondary particle toggles).

Decision: every identifier string lives in `bindings/` with a `CONTRACT` table; a test asserts type and default against the running
Blender. Quirk workarounds live next to the binding they fix.

Consequences: API drift is a one-folder fix, and the contract test fails loudly on a new Blender.

### 0008 Water is shaded for how it is bounded; one upgrade pass on load

Status: accepted (1.0).

Decision: `builders/shading.py` builds deep (open water: opaque body colour, Fresnel, Cox-Munk chop), shallow
(heightfield over a bed: transmission, no volume) and closed (Mantaflow liquid: transmission plus Beer-Lambert volume)
materials. `services/upgrade.py` adds the one application handler, on `load_post`, which upgrades 0.x bodies once
(marked `flowfx_version` in their info) and never runs during playback, so decision 0004 still holds.

### 0004 No application handlers in the playback path

Status: accepted.

Decision: Ocean time is a driver with a simple expression; heightfield results are EXR image sequences read by a Displace modifier;
floaters are baked F-curves; Dynamic Paint and Mantaflow use Blender's caches.

Consequences: results render identically in the UI, in background renders and on a farm without extra setup. Tradeoff: heightfield
and floaters need a bake step before playback.

### 0005 Own surface bake and representative-seed calibration

Status: accepted.

Context: `bpy.ops.object.ocean_bake` is a background job that writes nothing in a headless session, and does not expose horizontal
displacement for custom use. Ocean `wave_scale` is linear in height but not a height, and the Hs of a single seed on a finite tile
differs from the ensemble by up to about 25 percent.

Decision: bake by evaluating the surface per frame into float EXR; calibrate by measuring six seeds once, choosing the seed closest to
the ensemble, and fitting `wave_scale` to that seed, then verifying on other time samples.

Consequences: tests can run headless; per-preset seed and residual are stored on the body; tolerance is 10 percent (time-averaged).

### 0006 Keep the heightfield core in NumPy

Status: accepted.

Context: the heightfield engine solves shallow water itself, in pure NumPy, so a compiled core (a C++ extension or a Numba
wheel) was on the roadmap as a decision to be taken from the target grid sizes. The design budget is 10 solver steps per
second at 1024 x 1024 (docs/VALIDATION.md, spike S6). That budget is machine dependent: the spike measured 2.8 steps/s at 1024 x 1024
on the machine it ran on, while the same measurement on this machine gives 14.3 (and 902, 257 and 62 at 128 x 128,
256 x 256 and 512 x 512). The three shipped heightfield presets use far smaller grids than that: `flash_flood` 100 x 100
(cell 5 m), `tsunami_bore` 200 x 50 (cell 10 m) and `river_calm` 200 x 40 (cell 1 m), so at most 20,000 cells.

Decision: the solver stays in NumPy. No compiled wheel, no Numba runtime, no `platforms` entry in the extension manifest.
A compiled core would only pay off on grids one to two orders of magnitude finer than any preset asks for, and at
1024 x 1024 the answer would depend on the machine rather than on the solver.

Consequences: the shipped presets cost seconds to bake on any machine. A 1024 x 1024 bake of 250 frames costs about three
minutes on this machine and about a quarter of an hour on the slower one. Revisit if a preset needs a cell finer than
1 m over a 2 km extent (more than 4M cells), where NumPy is memory-bound and drops below one step per second. Numba is
then the cheapest escape hatch, since it needs no build toolchain, but it would add a runtime dependency and
per-platform wheels.


<!-- generated:bindings start -->

## Blender API bindings

Every Blender identifier FlowFX uses lives in `flowfx/bindings/`. `tests/api_contract/` asserts each row against the running Blender (verified on 5.2.2). Generated by `tools/gen_docs.py`.

### OceanModifier

| Identifier | RNA type | Default |
|---|---|---|
| `geometry_mode` | ENUM | GENERATE |
| `repeat_x` | INT | 1 |
| `repeat_y` | INT | 1 |
| `resolution` | INT | 7 |
| `viewport_resolution` | INT | 7 |
| `spatial_size` | INT | 50 |
| `size` | FLOAT | 1.0 |
| `depth` | FLOAT | 200.0 |
| `random_seed` | INT | 0 |
| `time` | FLOAT | 1.0 |
| `use_normals` | BOOLEAN | False |
| `wave_scale` | FLOAT | 1.0 |
| `wave_scale_min` | FLOAT | 0.01 |
| `choppiness` | FLOAT | 1.0 |
| `wind_velocity` | FLOAT | 30.0 |
| `wave_alignment` | FLOAT | 0.0 |
| `wave_direction` | FLOAT | 0.0 |
| `damping` | FLOAT | 0.5 |
| `spectrum` | ENUM | PHILLIPS |
| `fetch_jonswap` | FLOAT | 120.0 |
| `sharpen_peak_jonswap` | FLOAT | 0.0 |
| `use_foam` | BOOLEAN | False |
| `foam_layer_name` | STRING |  |
| `foam_coverage` | FLOAT | 0.0 |
| `use_spray` | BOOLEAN | False |
| `spray_layer_name` | STRING |  |
| `invert_spray` | BOOLEAN | False |
| `filepath` | STRING |  |
| `frame_start` | INT | 1 |
| `frame_end` | INT | 250 |
| `bake_foam_fade` | FLOAT | 0.98 |
| `is_cached` | BOOLEAN | False |

### FluidDomainSettings

| Identifier | RNA type | Default |
|---|---|---|
| `domain_type` | ENUM | GAS |
| `resolution_max` | INT | 32 |
| `time_scale` | FLOAT | 1.0 |
| `use_adaptive_timesteps` | BOOLEAN | True |
| `cfl_condition` | FLOAT | 2.0 |
| `timesteps_min` | INT | 1 |
| `timesteps_max` | INT | 4 |
| `gravity` | FLOAT |  |
| `use_collision_border_left` | BOOLEAN | False |
| `use_collision_border_right` | BOOLEAN | False |
| `use_collision_border_top` | BOOLEAN | False |
| `use_collision_border_bottom` | BOOLEAN | False |
| `use_collision_border_front` | BOOLEAN | False |
| `use_collision_border_back` | BOOLEAN | False |
| `simulation_method` | ENUM | FLIP |
| `flip_ratio` | FLOAT | 0.97 |
| `particle_radius` | FLOAT | 1.0 |
| `particle_number` | INT | 2 |
| `particle_min` | INT | 8 |
| `particle_max` | INT | 16 |
| `particle_randomness` | FLOAT | 0.1 |
| `particle_band_width` | FLOAT | 3.0 |
| `use_fractions` | BOOLEAN | False |
| `fractions_distance` | FLOAT | 0.5 |
| `fractions_threshold` | FLOAT | 0.05 |
| `use_mesh` | BOOLEAN | True |
| `mesh_scale` | INT | 2 |
| `mesh_generator` | ENUM | IMPROVED |
| `mesh_smoothen_pos` | INT | 1 |
| `mesh_smoothen_neg` | INT | 1 |
| `mesh_concave_lower` | FLOAT | 0.4 |
| `mesh_concave_upper` | FLOAT | 3.5 |
| `use_speed_vectors` | BOOLEAN | False |
| `use_spray_particles` | BOOLEAN | False |
| `use_foam_particles` | BOOLEAN | False |
| `use_bubble_particles` | BOOLEAN | False |
| `sndparticle_combined_export` | ENUM | OFF |
| `sndparticle_boundary` | ENUM | DELETE |
| `sndparticle_life_min` | FLOAT | 10.0 |
| `sndparticle_life_max` | FLOAT | 25.0 |
| `sndparticle_potential_min_wavecrest` | FLOAT | 2.0 |
| `sndparticle_potential_max_wavecrest` | FLOAT | 8.0 |
| `sndparticle_potential_min_trappedair` | FLOAT | 5.0 |
| `sndparticle_potential_max_trappedair` | FLOAT | 20.0 |
| `sndparticle_potential_min_energy` | FLOAT | 1.0 |
| `sndparticle_potential_max_energy` | FLOAT | 5.0 |
| `sndparticle_potential_radius` | INT | 2 |
| `sndparticle_update_radius` | INT | 2 |
| `sndparticle_sampling_wavecrest` | INT | 200 |
| `sndparticle_sampling_trappedair` | INT | 40 |
| `sndparticle_bubble_buoyancy` | FLOAT | 0.5 |
| `sndparticle_bubble_drag` | FLOAT | 0.6 |
| `use_viscosity` | BOOLEAN | False |
| `viscosity_value` | FLOAT | 0.05 |
| `viscosity_base` | FLOAT | 1.0 |
| `viscosity_exponent` | INT | 6 |
| `use_diffusion` | BOOLEAN | False |
| `surface_tension` | FLOAT | 0.0 |
| `cache_directory` | STRING |  |
| `cache_type` | ENUM | REPLAY |
| `cache_frame_start` | INT | 1 |
| `cache_frame_end` | INT | 250 |
| `cache_data_format` | ENUM | OPENVDB |
| `cache_mesh_format` | ENUM | UNI |
| `cache_particle_format` | ENUM | OPENVDB |
| `cache_resumable` | BOOLEAN | False |
| `openvdb_cache_compress_type` | ENUM | BLOSC |
| `use_guide` | BOOLEAN | False |
| `guide_source` | ENUM | DOMAIN |
| `guide_parent` | POINTER |  |
| `guide_vel_factor` | FLOAT | 2.0 |
| `guide_alpha` | FLOAT | 2.0 |
| `guide_beta` | INT | 5 |

### FluidFlowSettings

| Identifier | RNA type | Default |
|---|---|---|
| `flow_type` | ENUM |  |
| `flow_behavior` | ENUM |  |
| `flow_source` | ENUM |  |
| `use_inflow` | BOOLEAN |  |
| `use_initial_velocity` | BOOLEAN |  |
| `velocity_factor` | FLOAT |  |
| `velocity_normal` | FLOAT |  |
| `velocity_coord` | FLOAT |  |
| `surface_distance` | FLOAT |  |
| `use_plane_init` | BOOLEAN |  |
| `subframes` | INT |  |

### FluidEffectorSettings

| Identifier | RNA type | Default |
|---|---|---|
| `effector_type` | ENUM |  |
| `guide_mode` | ENUM |  |
| `use_effector` | BOOLEAN |  |
| `use_plane_init` | BOOLEAN |  |
| `surface_distance` | FLOAT |  |
| `subframes` | INT |  |
| `velocity_factor` | FLOAT |  |

### DynamicPaintSurface (wave)

| Identifier | RNA type | Default |
|---|---|---|
| `wave_damping` | FLOAT |  |
| `wave_speed` | FLOAT |  |
| `wave_timescale` | FLOAT |  |
| `wave_spring` | FLOAT |  |
| `wave_smoothness` | FLOAT |  |
| `use_wave_open_border` | BOOLEAN |  |

### Operators

`bpy.ops.fluid.` `bake_data`, `bake_mesh`, `bake_particles`, `bake_noise`, `bake_guides`, `bake_all`, `free_data`, `free_mesh`, `free_particles`, `free_noise`, `free_guides`, `free_all`, `pause_bake`

<!-- generated:bindings end -->
