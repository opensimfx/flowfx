"""Load flowfx/ as the `flowfx` package for tools and tests that run outside Blender's add-on loader."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "flowfx"


def load():
    if "flowfx" in sys.modules:
        return sys.modules["flowfx"]
    spec = importlib.util.spec_from_file_location("flowfx", EXT / "__init__.py",
                                                  submodule_search_locations=[str(EXT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flowfx"] = mod
    spec.loader.exec_module(mod)
    return mod
