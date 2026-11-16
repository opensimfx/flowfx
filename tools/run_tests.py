"""Run every test suite in the right process layout.

  python tools/run_tests.py            unit + api_contract + integration + fluid (forked)
  python tools/run_tests.py --all      also the slow validation tests
Fluid tests run one fresh Python process per test: once a Mantaflow domain exists in a headless `bpy`
session, the next scene reset aborts the interpreter (docs/VALIDATION.md, spike S8). A process per test is used
instead of pytest-forked: Windows has no fork, and on macOS a forked child of a process that loaded `bpy`
crashes (SIGTRAP).
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


def fluid_tests() -> list[str]:
    out = subprocess.run([PY, "-m", "pytest", "tests/integration_fluid", "--collect-only", "-q",
                          "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True).stdout
    return [line.strip() for line in out.splitlines() if "::" in line]


def main() -> int:
    rc = run("tests/unit", "tests/api_contract", "tests/integration", "-q")
    ids = fluid_tests()
    if not ids:
        print("no fluid tests collected", flush=True)
        rc |= 1
    failed = [t for t in ids if run(t, "-q", "-p", "no:cacheprovider") != 0]
    print(f"fluid tests: {len(ids) - len(failed)}/{len(ids)} passed", flush=True)
    rc |= 1 if failed else 0
    if "--all" in sys.argv:
        rc |= run("tests/validation", "-m", "slow", "-q")
    return rc


if __name__ == "__main__":
    sys.exit(main())
