"""Run every test suite in the right process layout.

  python tools/run_tests.py            unit + api_contract + integration + fluid (forked)
  python tools/run_tests.py --all      also the slow validation tests
Fluid tests run with pytest-forked: once a Mantaflow domain exists in a headless `bpy` session, the next scene
reset aborts the interpreter (docs/spikes.md S8).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(*args) -> int:
    cmd = [PY, "-m", "pytest", *args]
    print("$", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    rc = run("tests/unit", "tests/api_contract", "tests/integration", "-q")
    rc |= run("tests/integration_fluid", "--forked", "-q", "-p", "no:cacheprovider")
    if "--all" in sys.argv:
        rc |= run("tests/validation", "-m", "slow", "-q")
    return rc


if __name__ == "__main__":
    sys.exit(main())
