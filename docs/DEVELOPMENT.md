# Development and Testing

## Environment

```
uv python install 3.13
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python bpy numpy pytest pytest-forked ruff
```

The `bpy` wheel is the real Blender Python module (tested with 5.2.2 LTS). It can run operators, evaluate modifiers and
render with Cycles on CPU. Its Mantaflow cannot bake (see `VALIDATION.md (Spikes)` S8). A desktop Blender 5.2.1 is still needed for
interactive checks.

## Commands

| Command | Does |
|---|---|
| `python tools/run_tests.py [--all]` | All suites in the correct process layout |
| `python tools/validate_presets.py` | Schema-check presets, print derived physics |
| `python tools/gen_presets.py` | Regenerate preset JSON from the catalogue |
| `python tools/gen_previews.py`, `build_assets.py` | Regenerate swatches and the material library |
| `python tools/gen_docs.py` | Regenerate `PRESETS.md` and `SYSTEM_DESIGN.md (Blender API bindings)` |
| `python tools/run_validation.py` | Re-measure physics and write `VALIDATION.md` |
| `python tools/build_extension.py` | Validate and build `dist/flowfx-<version>.zip` |

Desktop Blender can run the same suites: `blender -b --python-expr "import pytest, sys; sys.exit(pytest.main(['tests/integration']))"`
with pytest installed in Blender's Python.

## Desktop checks

These need the desktop Blender binary, because the `bpy` module cannot bake with Mantaflow. Run them with the
project Python: they start desktop Blender themselves, one process per preset, so a Mantaflow domain cannot take the
next preset down with it.

```
.venv/bin/python tools/desktop_check.py                     # every preset through the panel surface
.venv/bin/python tools/zip_check.py                         # the same from the installed zip
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python tools/fluid_validation.py -- dam_break 40      # bake and measure one preset
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python tools/render_preview.py -- choppy_waves docs/img/choppy_waves.png 32
```

They write a JSON report (`docs/desktop_check_report.json`, `docs/zip_check_report.json`,
`docs/fluid_validation_<preset>.json`). The Blender profile (config, scripts, extensions) is redirected to a
throwaway directory, but on macOS the user preferences file is still the real one, so `zip_check.py` leaves the
extension enabled in the user preferences.

## Test layout

- `tests/unit`: no Blender (theory, scale, presets, solver, floaters, query).
- `tests/api_contract`: every identifier in `bindings/` against the running Blender.
- `tests/integration`: register the package, drive operators, build presets, bake EXR.
- `tests/integration_fluid`: Mantaflow domains; one forked process per test (`pytest --forked`).
- `tests/validation`: slow physical checks (Cycles render, dispersion time series). Marked `slow`.

The pytest `conftest.py` exits with `os._exit` after the summary when `bpy` is loaded, because the module can segfault at
interpreter shutdown.

## Conventions

- Python 3.13, type hints on public functions, line length 120 (`ruff`).
- Relative imports inside the package. The extension id is `flowfx`; `props/prefs.ADDON_ID` derives the top-level package name.
- Blender 5.2 API: `scene.compositing_node_group`, no `material.use_nodes`, GN inputs through `modifier.properties.inputs`.
- Never evaluate the depsgraph in fluid tests; never reset the file in the same process after creating a domain.
- Fluid boolean setters for secondary particles must go through `engines/fluid/secondary.py`.

## Adding a preset

Add an entry to `tools/gen_presets.py` (physical inputs in SI, derived values come from `core/theory.py`), run it,
run `tools/validate_presets.py`, add a preview with `tools/gen_previews.py`, regenerate docs.

## Releasing

1. Update `core/version.py`, `flowfx/blender_manifest.toml` and `CHANGELOG.md`.
2. `python tools/run_tests.py --all`, `python tools/run_validation.py`, `python tools/gen_docs.py`.
3. `python tools/build_extension.py`; test the zip in desktop Blender.

## Preview renders

Real Cycles renders made in desktop Blender 5.2.3 by `tools/render_preview.py`, one per engine. Open water (ocean,
river) is filmed from the near end of the body looking along it; the baked dam-break liquid from a three-quarter view. They are the add-on's own
output: the preset is built by the FlowFX operators, the water is shaded with the FlowFX water material, and the flow
boxes, terrain and obstacles are hidden because they are simulation helpers.

| Engine | Preset | What it shows |
|---|---|---|
| Spectral | `choppy_waves` | The Ocean modifier surface with the calibrated wave field |
| Fluid (Mantaflow) | `dam_break` | The baked liquid after the reservoir collapses, as a refracting volume |
| Heightfield | `river_calm` | The baked shallow-water solve, displaced into the surface |

![choppy waves](img/choppy_waves.png)

![dam break](img/dam_break.png)

![river calm](img/river_calm.png)

Regenerate one of them (the fluid preset bakes first, so it takes a minute):

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        --python tools/render_preview.py -- choppy_waves docs/img/choppy_waves.png 32

Set `FLOWFX_SAVE_BLEND` to a path to save the scene as well; `examples/flowfx_demo.blend` is the result for `choppy_waves`.
