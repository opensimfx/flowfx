# User Guide

## Install

Preferences, Get Extensions, dropdown at the top right, Install from Disk, choose `flowfx-0.1.0.zip`. FlowFX needs Blender 5.2.0
or newer. The extension asks for file access only to read and write caches and presets. Set the cache folder under
Preferences, Add-ons, FlowFX (default `//flowfx_cache/`, next to the .blend; save the file first).

## The panel

3D Viewport, press N, tab **FlowFX**.

| Panel | Use |
|---|---|
| FlowFX | List of bodies; Remove; Validate |
| Presets | Category and preset; readout of derived physics (Hs, Froude, front speed, breaker type); name; **Create Water Body** at the 3D cursor; Apply to Active; Save as user preset |
| Body | Target Hs and Calibrate (spectral); build information |
| Roles and Coupling | Assign roles to selected objects; wavemaker; floater |
| Shading and Output | Water variant, material, depth volume, compositing template |
| Cache and Bake | Estimate, stage, Bake, Cancel, Free Cache, Export Report |
| Diagnostics | Issues from Validate |

## Surface presets (Spectral)

Pond, Small Waves, Lake, Windy Lake, Ocean Swell, Moderate, Rough, Choppy Waves, Storm, Custom use the Ocean modifier.
Create the body and play the timeline (time comes from a driver, not a handler).

**Wave height.** Preset targets are physical significant wave heights (Hs). Blender's `wave_scale` is not a height, so FlowFX
measures the evaluated surface and fits it. It measures six seeds, picks the one closest to the ensemble average, and
fits that seed, so the surface you see matches the target when averaged over time. Instantaneous Hs still fluctuates a few
percent, and different seeds differ by 10 to 25 percent; this is a property of waves on a finite tile, not an error.
Change **Target Hs** and press **Calibrate** to refit. A preset at its default settings uses a calibration measured
when FlowFX was built (`presets/calibration.json`), so it appears in a fraction of a second; any change to the
wave settings, the target height or the Blender minor version is calibrated live (a few seconds).

**Layers.** Extra spectra (for example swell plus wind chop) can be stacked as further Ocean modifiers in Displace mode
(script: `ctx.overrides["extra_layers"]`; no panel yet).

**Bake.** `Bake` writes `flowfx_disp_####.exr` for the scene frame range (R,G horizontal displacement, B height, A foam) under
`<cache>/<uid>/spectral/`, for use in other tools. It is optional; the live modifier already renders.

**Tile size.** Ocean waves repeat every `extent_m` metres. Use `repeat_x/y` on the modifier or a larger extent to hide tiling.

## Still water and wakes (Interaction)

`still_water` and `boat_wake` create a Dynamic Paint Waves canvas. Boat Wake also builds a stand-in hull that crosses the
canvas at the preset speed (6 m/s): an 8 m motorboat whose hull makes the wake and paints a white wash that fades
behind it. To use your own boat, give it the Obstacle role, copy the hull's Dynamic Paint brush settings, and delete
the stand-in. Select
objects, **Roles and Coupling, Obstacle**: each becomes a brush. Play the timeline from the first frame; Dynamic Paint
solves the waves frame by frame and caches itself. Save the file before rendering a still frame: with an unsaved
file the cache lives in memory, which the renderer cannot read, and the canvas renders flat (animation renders
solve it themselves). Light air never leaves water perfectly flat: still and calm water
shows patches of ripple (catspaws) between glassy areas, fading into uniform chop by 4 m/s of wind.

## Heightfield presets

River (Calm), Flash Flood, Tsunami Bore solve the shallow-water equations. **Bake** runs the solver for the frame range
(Esc cancels), writes surface and flow EXR sequences under `<cache>/<uid>/heightfield/`, and adds a Displace modifier that reads
the surface sequence. Surface elevation includes the terrain; dry cells sit on the bed. The flow sequence stores velocity, depth
and a foam mask for shading. Grids are small (100 x 100 or less) because the NumPy solver does 34 to 68 steps per second at
256 x 256 on one core.

## Fluid presets (Mantaflow)

River Rapids, Stream, Flow Around Obstacle, Waterfall, Dam Break, Breaking Surf build a domain plus starter scenery:

- the inflow velocity is computed from depth, slope and roughness (Manning);
- many rocks are merged into **one** effector;
- rivers and streams start flowing at their normal depth on the first frame, fed by an inflow across the whole
  channel; the waterfall starts with water on the cliff top, a nappe already falling on its ballistic path and a
  plunge pool kept at its level by an outflow;
- the surf tank has a piston wavemaker keyframed from wave theory and a 1:10 beach.

**Quality** (Cache and Bake): Standard bakes the preset's grid, High a 1.5x finer one (about 4x the bake time),
Cinematic a 2x finer one (about 9x). Finer grids resolve thin sheets, jets and small splashes; changing it
rebuilds the domain, so bake again. Check **Cache and Bake, Estimate** first (heuristic RAM and disk). Choose a stage (All, Data, Mesh, Particles) and Bake; Blender runs
its own bake. Spray, foam and bubbles render as small instanced meshes once the particles are baked. A Mantaflow
domain ends in a vertical cut where the river enters: frame it out or place scenery over it, as with any simulation
domain.

## Roles

Select objects, choose a role:

| Role | Fluid body | Spectral body |
|---|---|---|
| Obstacle, Terrain | Effector (Collision), planar flag set for open meshes | Dynamic Paint brush (obstacle) |
| Source | Flow Inflow with the velocity you enter | not available |
| Sink | Flow Outflow | not available |
| Block | Flow Geometry (initial volume) | not available |
| Floater | tag | tag |

**Wavemaker** (fluid bodies): wave height, period and depth give the piston stroke from the Biesel transfer function.

**Floater**: select an object, set its mass, **Bake Floater**. FlowFX integrates a 6-DOF body floating on the active body (the Ocean
surface for spectral bodies, flat water otherwise) and keys location and rotation for the frame range. No collisions between objects.

## Shading and compositing

Six water variants: clear, lake, murky, ocean, ocean dark, turbulent, each built for how the water is bounded. Open water
(ocean, lake) is a dark body colour under a Fresnel reflection with wind chop and sun glitter set from the wind; heightfield rivers
refract their riverbed; baked Mantaflow liquids refract and absorb light by the measured absorption coefficients. Foam comes from the
`flowfx_foam` attribute, calibrated to the whitecap share for the wind and broken into wind-blown streaks, with an AOV of the same
name. Ocean presets reach the horizon on their own (tiled waves plus a far-sea plane). Baked heightfield rivers and
floods carry ripples that drift with the current and white water where the flow is fast or converging; muddy
variants hide their bed. Mantaflow spray, foam and bubbles render as small instanced droplets and flecks (bake the
particles stage, or All); the instance meshes are the hidden `FlowFX Spray/Foam/Bubbles Instance` objects, so
editing their material changes every body's white water. **Add Depth Volume** puts an absorbing box under the surface. **Build Compositing Template** creates a
compositor node group (`scene.compositing_node_group`) with the foam AOV and a Viewer.

## Cost, validation, reports

- **Estimate** shows RAM and disk and warns when free disk is short.
- **Validate** checks every body (target Hs above the fully developed limit, flows outside the domain box, RAM over budget).
- **Export Report** writes JSON with preset, derived physics, build info, estimate and issues.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Waves too small or large | Press Calibrate; check Target Hs; remember the tile and seed |
| Heightfield displacement missing | Bake first; the Displace modifier appears only after a bake |
| Spray / foam toggles odd in the domain | A 5.2.2 setter quirk; FlowFX sets them safely (docs/VALIDATION.md, spike S10) |
| Fluid bake aborts | Report it with the log; the headless test build aborts too (S8) |
| Cache path error | Save the .blend or set an absolute cache folder in preferences; unsaved files bake into the system temp folder |
| Caches missing after moving the project | Caches are stored relative to the .blend: move the `flowfx_cache` folder with it |
| A 0.2 scene's river shows water on dry banks | Bake it again: 1.0 adds the riverbed on open, and the new bake writes the wet mask |
