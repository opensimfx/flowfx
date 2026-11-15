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

## Optics

- Index of refraction 1.333. [T]
- Pure-water absorption (1/m): R 0.35, G 0.065, B 0.01. [T] Mapped to Cycles Volume Absorption with
  `density = max(sigma)`, `color = 1 - sigma / density`. Verified by render: transmittance equals `exp(-sigma d)`. [M]
