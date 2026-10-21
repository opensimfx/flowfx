"""Validate every preset JSON against the schema and print derived physics. Exit code 1 on any error."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pkg  # noqa: E402

_pkg.load()
import json  # noqa: E402

from flowfx.core import presets  # noqa: E402
from flowfx.core.schema import validate_preset  # noqa: E402

bad = 0
for f in sorted((_pkg.EXT / "presets").glob("*/*.json")):
    p = json.loads(f.read_text(encoding="utf-8"))
    errors = validate_preset(p) + ([] if f.stem == p.get("id") else ["file name does not match id"])
    status = "ok" if not errors else "; ".join(errors)
    bad += bool(errors)
    derived = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in presets.derive(p).items()}
    print(f"{p.get('id', '?'):22s} {status}  {derived}")
sys.exit(1 if bad else 0)
