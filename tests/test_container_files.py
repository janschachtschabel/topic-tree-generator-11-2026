"""Static checks of the container setup (no Docker in the test environment; the CI builds the image)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_is_multi_stage_non_root_and_runs_gunicorn() -> None:
    text = (ROOT / "Dockerfile").read_text()
    assert sum(line.startswith("FROM ") for line in text.splitlines()) == 2
    assert "USER 10001" in text
    assert 'CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.main:app"]' in text
    assert "EXPOSE 8000 9000" in text
    assert "--no-dev" in text
    assert "fastapi dev" not in text and "fastapi run" not in text


def test_dockerignore_keeps_tests_docs_and_secrets_out() -> None:
    entries = set((ROOT / ".dockerignore").read_text().split())
    assert {".venv", ".git", "tests", "docs", ".env", "deploy"} <= entries
    # Prompt files are markdown and must stay in the image.
    assert not any(e.endswith("*.md") for e in entries)


def test_compose_publishes_both_ports_and_mounts_tmp() -> None:
    text = (ROOT / "compose.yml").read_text()
    assert '"8000:8000"' in text and '"9000:9000"' in text
    assert "read_only: true" in text and "/tmp" in text
