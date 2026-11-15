# Contributing

1. Set up the environment from `docs/DEVELOPMENT.md` (Python 3.13 and the `bpy` module).
2. Add behaviour with a test. Pure physics goes in `tests/unit`; anything touching Blender goes in
   `tests/integration` (or `tests/integration_fluid` if it creates a Mantaflow domain).
3. Blender identifier strings belong in `flowfx/bindings/` only, each with a row in its `CONTRACT` dict.
4. No app handlers in the playback path. Use drivers, image sequences, F-curves or Blender caches.
5. New claims about physics need a source or a measured test; tag textbook values `[T]` in docstrings.
6. Run `python tools/run_tests.py`, `ruff check .`, `python tools/validate_presets.py`, then
   `python tools/build_extension.py` before opening a pull request.
7. Presets are data: edit `tools/gen_presets.py`, run it, and commit the generated JSON.
8. Do not add third-party assets without a licence entry in `docs/REFERENCES.md`.

## Repository conventions

Shared by every OpenSimFX add-on (BlastFX, RainFX, FlowFX, AtmosFX), so the repositories read the same.

```
README.md  CHANGELOG.md  CONTRIBUTING.md  LICENSE  pyproject.toml
.github/logo.png   the add-on's icon, shown in the README heading
<addon>/           the add-on; this folder is exactly what the extension zip contains
docs/              the same nine docs in every add-on (below)
docs/img/          README and documentation renders
tests/             pytest suites (pure Python) and headless Blender checks
tools/             build_extension.py, render_preview.py, gen_preset_docs.py, ...
examples/          example scenes or scripts (optional)
```

- **Naming:** in sentences, the Blender UI, READMEs, docs and the website, write the names in mixed case:
  **OpenSimFX**, **BlastFX**, **RainFX**, **FlowFX**, **AtmosFX**. Lowercase is only for the wordmark beside a logo
  (`opensimfx`) and for identifiers: repositories, Python packages, zip files, URLs and property names
  (`blastfx`, `dist/blastfx-0.2.0.zip`, `github.com/opensimfx`). The AtmosFX repository is `atomsfx` but its package
  and zip are `atmosfx`.
- **Build:** `python tools/build_extension.py` writes `dist/<addon>-<version>.zip`. `dist/` is never committed;
  release zips go on GitHub Releases.
- **Docs:** every add-on has exactly these nine, with these titles, listed in this order in the README:

  | File | Title | Contents |
  |---|---|---|
  | `USER_GUIDE.md` | User Guide | install, first use, every panel |
  | `PRESETS.md` | Presets | the preset library (generated) |
  | `PHYSICS.md` | Physics | the models and equations |
  | `SYSTEM_DESIGN.md` | System Design | architecture, data flow, public API, decisions |
  | `DEVELOPMENT.md` | Development and Testing | environment, test suites, build and release, renders |
  | `VALIDATION.md` | Validation | what was measured, what is not verified |
  | `REFERENCES.md` | References and Licensing | sources, licences, provenance |
  | `ROADMAP.md` | Roadmap | history and next steps |
  | `UI_STYLE.md` | OpenSimFX UI conventions | shared panel layout (identical everywhere) |

  New material goes into one of these, not a new file. Generated docs say so on their first lines; a generated part
  of a hand-written doc sits between `<!-- generated:<name> start/end -->` markers. Neither is edited by hand.
- **README sections, in order:** Features, Install, Quick start, Verification status (read this), Repository layout,
  Develop, Documentation, License. Renders go under the tagline with a caption that says how they were made.
- **Private notes:** research about third-party or commercial add-ons, notes on how research was done, and
  development leftovers go in `private/` (ignored by git), never in the published docs.
- **UI:** sidebar panels follow [docs/UI_STYLE.md](docs/UI_STYLE.md), identical in every add-on.
- **Changelog:** newest first, with an `## Unreleased` section on top.
- **Licence:** GPL-3.0-or-later. Original work only: no code, shaders, node groups, textures or data copied from
  other add-ons, including ones you own a licence for.
