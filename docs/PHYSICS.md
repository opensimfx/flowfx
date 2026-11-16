# Physics

All quantities are SI: metres, seconds, kilograms. Gravity 9.81 m/s^2 (Blender's default scene gravity).
Tags: **[T]** textbook or standard engineering value, **[V]** read from a source during research,
**[M]** measured in this repository (see `VALIDATION.md`).

## Wave heights and spectra

- Significant wave height from surface elevation: `Hs = 4 sigma`. [T] (`core/calibration.py`)
- Fully developed sea (Pierson-Moskowitz), U at 19.5 m: `Hs = 0.21 U^2 / g`. U = 12 gives 3.08 m. [T]
- Fetch-limited sea: `Hs = 0.0016 U sqrt(F / g)`. U = 6 m/s, F = 3000 m gives 0.17 m. [T]
- Peak period (Pierson-Moskowitz): `omega_p = 0.877 g / U`. [T]
- Linear dispersion: `omega^2 = g k tanh(k h)`. Deep `c = sqrt(g / k)`, shallow `c = sqrt(g h)`. [T] FlowFX solves the
  inverse by Newton iteration (`theory.wavenumber_from_omega`).
- Hs of one random seed differs from the ensemble Hs; FlowFX selects a representative seed. [M]

## Shallow-water and rivers

- Saint-Venant equations with bed elevation `b`, depth `h`, momentum `hu`, `hv`. [T]
- Scheme: first-order finite volume, HLL flux, hydrostatic reconstruction (well balanced, dry-front safe), semi-implicit
  Manning friction `1 + dt g n^2 |u| / h^(4/3)`. CFL 0.45. [T]
- Froude `Fr = u / sqrt(g h)`; supercritical above 1 (hydraulic jumps, foam). [T]
- Manning: `u = R^(2/3) S^(1/2) / n`, natural channels n = 0.03 to 0.07. [T]
- Dry-bed dam break (Ritter): front `2 sqrt(g h0)`, profile `h = (2 c0 - x/t)^2 / (9 g)` for `-c0 t <= x <= 2 c0 t`. [T]
- Mantaflow dam break (desktop Blender, FLIP, 0.1 m cells): front 5.96 m/s against 6.26 m/s, 4.9 percent. The leading
  splash sheet is thinner than a cell and outruns the bulk front, so the mesh edge is not the Ritter front after the
  collapse. [M] (`docs/VALIDATION.md (Mantaflow validation)`)

## Tsunami

- Speed `c = sqrt(g d)`; 4,600 m depth gives 212 m/s, about 765 km/h; NOAA quotes almost 475 mph. [V]
- Open-ocean amplitude is small (under about 1 m); speed falls to 30 to 50 km/h near shore while height and currents grow. [V]
- The `tsunami_bore` preset is a leading bore on a 1:20 beach, not a full wave train. [design decision]

## Surf and tanks

- Piston wavemaker: `H / S = 2 (cosh 2kh - 1) / (sinh 2kh + 2kh)` (Biesel). [T]
- Iribarren number `xi = tan(beta) / sqrt(H / L0)`, `L0 = g T^2 / 2 pi`: spilling below 0.5, plunging 0.5 to 3.3, surging above. [T]

## Objects in water

- Floater: buoyant force per sample `rho g dV s_i`, submerged fraction `s_i` ramps over one sample cell height. Box draft
  `m / (rho A)` and heave period `2 pi sqrt(m / (rho g A))` reproduced to 0.00 percent and 0.01 percent. [M]
- Wake half-angle `arcsin(1/3) = 19.47 degrees`. Cylinder wake `f = St u / D`, `St ~ 0.2` for 300 < Re < 2e5. [T]
- Scale cheating (Froude similarity): to make a simulation of size `L_sim` read as `L_target`, set `s = L_target / L_sim` and
  `time_scale = 1 / sqrt(s)`. s = 20 gives 0.224. [T]

## Look

- Whitecap coverage: `W = 3.84e-6 U10^3.41` (Monahan and O'Muircheartaigh 1980): 1 % at 10 m/s, 22 % at 25 m/s. [V]
  FlowFX bisects the Ocean modifier's foam coverage until the mean foam at render resolution matches it. [M]
- Sea-surface slopes: mean-square slope `0.003 + 5.12e-3 U` (Cox and Munk 1954, U at 12.5 m). [V] The simulated mesh
  carries the long waves; 70 % of this slope variance goes to a world-space chop bump (Noise, 0.35 /m, 4 octaves)
  and 30 % to the microfacet roughness (`alpha^2`), which spreads the sun into a glitter path. [design decision]
- Deep-water colour: clear open ocean reflects a few percent, peaking in the blue (ocean-colour remote sensing). [V]
  Deep water is drawn as an opaque body colour of 10 % of the variant tint under the Fresnel reflection (IOR 1.333).
- Volume absorption is used only on closed liquid meshes: on an open sheet Cycles cannot tell inside from outside.
  [M] (`docs/VALIDATION.md`, 1.0)
- Foam streaks: wind-blown foam lies in streaks from Beaufort force 7; the foam pattern (2.5 features per metre,
  6 octaves) is stretched 8 x along the wind. [V for the Beaufort description, design decision for the factor]
- Flowing water (heightfield): ripples drift with the solved depth-averaged velocity through a flow map: two copies
  of a noise advected over a 1.2 s cycle, half a cycle apart, cross-faded by a triangle weight so neither copy is
  shown stretched. The surface mean-square slope is 0.002 + 0.002 u^2 (u in m/s, at most 0.06), following the
  velocity head; the noise amplitude that gives it uses the measured noise slope (0.44 per unit, two cross-faded
  copies keep 2/3). The largest boils are 7 m, or 1/30 of a body larger than 200 m. [design decision] White water is the solver's
  foam mask (Froude number 0.8 to 1.2 plus converging flow, `engines/heightfield/outputs.py`). [M]
- Light air: below 4 m/s water roughens in patches (catspaws) with glassy water between; the chop strength is
  modulated by a 30 m noise down to 12 % at zero wind. [design decision; Beaufort 1 "ripples with the appearance
  of scales"]
- Boat wake (Dynamic Paint): the waves are non-dispersive, so a brush moving at U leaves a cone of half-angle
  asin(c / U). FlowFX sets c = U / 3, which opens the cone at the Kelvin angle, 19.47 deg, of a real deep-water
  wake; the wave pattern inside the cone is not the Kelvin pattern. [M: 18.7 deg]
- Turbidity: shallow open water returns part of the light from suspended sediment and bubbles instead of showing
  its bed; each variant carries an opacity (clear 0, lake 0.2, turbulent 0.5, ocean_dark 0.6, murky 0.8; the
  tsunami run-up uses murky).
  [design decision, guided by the appearance of flood and river water]
- Mantaflow white water: spray, foam and bubble particles are instanced meshes sized by the voxel (spray 0.12,
  foam 0.3, bubbles 0.06 of the preset's voxel at every quality); trapped-air emission is a tenth of Mantaflow's
  default divided by the cell-count growth, wave-crest emission the default divided by the grid refinement;
  spray is mostly diffuse white because each particle stands for a cloud of
  much smaller droplets, which scatters white. [design decision] The liquid mesh is smoothed with 3 positive and 2
  negative passes. [M: removes the voxel facets at preset resolutions without thinning jets]

## Optics

- Index of refraction 1.333. [T]
- Pure-water absorption (1/m): R 0.35, G 0.065, B 0.01. [T] Mapped to Cycles Volume Absorption with
  `density = max(sigma)`, `color = 1 - sigma / density`. Verified by render: transmittance equals `exp(-sigma d)`. [M]
