"""Runs the Node unit tests of the test UI's pure scripts (`tests/ui_js/`); skipped where `node` is missing."""

import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_ui_js_unit_tests() -> None:
    tests = sorted(str(p) for p in (_ROOT / "tests" / "ui_js").glob("*.test.cjs"))
    assert tests, "no UI JS tests found"
    cmd = ["node", "--test", *tests]
    proc = subprocess.run(cmd, check=False, cwd=_ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
