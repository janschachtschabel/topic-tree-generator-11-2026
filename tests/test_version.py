import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_version_matches_pyproject_version() -> None:
    with open(Path(__file__).parent.parent / "pyproject.toml", "rb") as pyproject_file:
        pyproject_version = tomllib.load(pyproject_file)["project"]["version"]

    schema = TestClient(app).get("/openapi.json").json()

    assert schema["info"]["version"] == pyproject_version
