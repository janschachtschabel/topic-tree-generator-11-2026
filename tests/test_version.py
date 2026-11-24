import tomllib
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

# Importing the application otherwise fetches remote vocabularies at module load time.
with patch("rdflib.Graph.parse"):
    import main


def test_openapi_version_matches_pyproject_version() -> None:
    with open(Path(__file__).parent.parent / "pyproject.toml", "rb") as pyproject_file:
        pyproject_version = tomllib.load(pyproject_file)["project"]["version"]

    schema = TestClient(main.app).get("/openapi.json").json()

    assert schema["info"]["version"] == pyproject_version
