"""Load the extension package as `flowfx` without Blender and tidy up bpy sessions."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "flowfx"


def _load_package():
    if "flowfx" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location("flowfx", EXT / "__init__.py",
                                                  submodule_search_locations=[str(EXT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flowfx"] = mod
    spec.loader.exec_module(mod)


_load_package()


_STATUS = {"code": 0}


def pytest_sessionfinish(session, exitstatus):
    _STATUS["code"] = int(exitstatus)


def pytest_unconfigure(config):
    # The bpy module can segfault during interpreter shutdown; exit cleanly with pytest's own status
    # after the terminal summary has been printed.
    if "bpy" in sys.modules:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_STATUS["code"])
