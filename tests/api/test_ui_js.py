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


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("script", sorted(p.name for p in (_ROOT / "app" / "ui" / "static").glob("*.js")))
def test_ui_script_parses(script: str) -> None:
    # Regression: an unescaped quote in i18n.js broke the whole page while every unit test stayed green.
    path = _ROOT / "app" / "ui" / "static" / script
    proc = subprocess.run(["node", "--check", str(path)], check=False, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
