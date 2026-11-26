"""Release guarantees of the GitHub Actions workflow."""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _workflow() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # YAML 1.1 reads the key `on` as True
    return data


def test_a_release_tag_can_be_published_by_hand() -> None:
    # Regression: the v2.0.0 tag never triggered a push run, and nothing could publish it afterwards.
    data = _workflow()
    assert "workflow_dispatch" in data["on"]
    assert "workflow_dispatch" in data["jobs"]["publish"]["if"]


def test_release_tags_never_move_latest_and_never_overwrite_a_version() -> None:
    steps = _workflow()["jobs"]["publish"]["steps"]
    meta = next(s for s in steps if s.get("id") == "meta")
    assert "latest=false" in meta["with"]["flavor"]
    names = [s.get("name", "") for s in steps]
    assert names.index("Publish each release version only once") < names.index(
        "Package and push Helm chart to GHCR OCI on release tags"
    )


def test_the_lock_file_is_checked_against_pyproject() -> None:
    runs = [s.get("run", "") for s in _workflow()["jobs"]["test"]["steps"]]
    assert "uv lock --check" in runs
