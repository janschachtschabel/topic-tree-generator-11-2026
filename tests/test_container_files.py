"""Static and Compose-CLI checks of the container setup."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from app.settings import Settings

ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_is_multi_stage_non_root_and_runs_gunicorn() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert sum(line.startswith("FROM ") for line in text.splitlines()) == 2
    assert "USER 10001" in text
    assert 'CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.main:app"]' in text
    assert "EXPOSE 8000 9000" in text
    assert "--no-dev" in text
    assert "fastapi dev" not in text and "fastapi run" not in text


def test_dockerignore_keeps_tests_docs_and_secrets_out() -> None:
    entries = set((ROOT / ".dockerignore").read_text(encoding="utf-8").split())
    assert {".venv", ".git", "tests", "docs", ".env", "deploy"} <= entries
    # Prompt files are markdown and must stay in the image.
    assert not any(e.endswith("*.md") for e in entries)


def test_canonical_compose_is_reverse_proxy_and_panel_compatible() -> None:
    compose_path = ROOT / "docker-compose.yml"
    assert compose_path.is_file()
    # Keep a single canonical root file so Docker Compose never warns about conflicting names.
    assert not (ROOT / "compose.yml").exists()

    text = compose_path.read_text(encoding="utf-8")
    # Plain YAML for web editors: no tabs, no anchors/merge keys, no required or nested interpolations.
    assert "\t" not in text
    assert "<<:" not in text
    assert ":?" not in text
    assert not re.search(r"\$\{[^}]*\$\{", text)

    data = yaml.safe_load(text)
    service = data["services"]["topic-tree"]
    assert "build" not in service
    assert "volumes" not in service
    # Reachable without a domain: one host port (default 18000, unlikely to be taken) on the public API port only;
    # HOST_BIND=127.0.0.1 closes it once Traefik serves a DOMAIN. The internal port is never published.
    assert service["ports"] == ["${HOST_BIND:-0.0.0.0}:${HOST_PORT:-18000}:${PUBLIC_PORT:-8000}"]
    assert service["read_only"] is True
    assert "/tmp" in service["tmpfs"]
    assert service["restart"] == "unless-stopped"
    assert "${IMAGE:-" in service["image"]

    # Optional .env so first deploy works even without any variables.
    env_files = service["env_file"]
    assert isinstance(env_files, list)
    assert any(
        isinstance(entry, dict) and entry.get("path") == ".env" and entry.get("required") is False
        for entry in env_files
    )

    # Default network is named (created if missing, shared if present), never external: true.
    default_net = data["networks"]["default"]
    assert default_net.get("external") is not True
    assert default_net["name"] == "${TRAEFIK_NETWORK:-topic-tree-web}"

    # Traefik labels route HTTPS to port 8000 without claiming ports 80/443 or exposing internal port 9000.
    labels = service["labels"]
    assert "traefik.enable=true" in labels
    assert "traefik.docker.network=${TRAEFIK_NETWORK:-topic-tree-web}" in labels
    # Router and service names are global in Traefik: a second instance on the same host needs its own name,
    # otherwise Traefik merges both containers into one load-balanced service.
    router = "${TRAEFIK_ROUTER:-topic-tree}"
    assert f"traefik.http.routers.{router}.rule=Host(`${{DOMAIN:-}}`)" in labels
    assert f"traefik.http.routers.{router}.entrypoints=${{TRAEFIK_ENTRYPOINT:-websecure}}" in labels
    assert f"traefik.http.routers.{router}.tls.certresolver=${{TRAEFIK_CERTRESOLVER:-letsencrypt}}" in labels
    assert f"traefik.http.routers.{router}.service={router}" in labels
    # Container ports follow PUBLIC_PORT / INTERNAL_PORT so a changed port in .env keeps routing and health intact.
    assert f"traefik.http.services.{router}.loadbalancer.server.port=${{PUBLIC_PORT:-8000}}" in labels
    assert "127.0.0.1:${INTERNAL_PORT:-9000}/health" in " ".join(service["healthcheck"]["test"])


def test_local_build_compose_publishes_both_ports_and_mounts_tmp() -> None:
    text = (ROOT / "docker-compose.build.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    service = data["services"]["topic-tree"]
    assert service["build"] == "."
    # Host and container side follow PUBLIC_PORT / INTERNAL_PORT (alternative ports for several APIs on one host).
    assert "${PUBLIC_PORT:-8000}:${PUBLIC_PORT:-8000}" in service["ports"]
    assert "${INTERNAL_PORT:-9000}:${INTERNAL_PORT:-9000}" in service["ports"]
    assert service["read_only"] is True
    assert "/tmp" in service["tmpfs"]


def test_env_example_is_safe_initial_env_for_first_deploy() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    # DOMAIN must start empty (no placeholder domain that would trigger ACME certificate requests).
    assert re.search(r"(?m)^DOMAIN=\s*$", text)
    settings = Settings(_env_file=ROOT / ".env.example")
    assert settings.domain is None
    assert settings.openai_api_key is None
    assert settings.b_api_dev_key is None
    assert settings.openai_base_url is None


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose.build.yml"])
def test_docker_compose_config_validates_without_env_and_with_env_example(tmp_path: Path, filename: str) -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not installed")
    compose_copy = tmp_path / filename
    compose_copy.write_text((ROOT / filename).read_text(encoding="utf-8"), encoding="utf-8")

    # 1) Without .env at all
    without_env = subprocess.run(
        ["docker", "compose", "-f", str(compose_copy), "config", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert without_env.returncode == 0, without_env.stderr

    # 2) With .env.example copied as .env
    (tmp_path / ".env").write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    with_example = subprocess.run(
        ["docker", "compose", "-f", str(compose_copy), "config", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert with_example.returncode == 0, with_example.stderr


def test_build_compose_resolves_custom_ports_from_env(tmp_path: Path) -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not installed")
    (tmp_path / "docker-compose.build.yml").write_text(
        (ROOT / "docker-compose.build.yml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / ".env").write_text("PUBLIC_PORT=8010\nINTERNAL_PORT=9010\n", encoding="utf-8")
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.build.yml", "config", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    ports = json.loads(result.stdout)["services"]["topic-tree"]["ports"]
    assert {(p["published"], p["target"]) for p in ports} == {("8010", 8010), ("9010", 9010)}


def test_canonical_compose_resolves_router_name_and_ports_per_instance(tmp_path: Path) -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not installed")
    (tmp_path / "docker-compose.yml").write_text((ROOT / "docker-compose.yml").read_text(encoding="utf-8"), "utf-8")
    (tmp_path / ".env").write_text(
        "DOMAIN=trees2.example.org\nTRAEFIK_ROUTER=topic-tree-staging\nPUBLIC_PORT=8010\nINTERNAL_PORT=9010\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "config", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    service = json.loads(result.stdout)["services"]["topic-tree"]
    labels = service["labels"]
    assert labels["traefik.http.routers.topic-tree-staging.rule"] == "Host(`trees2.example.org`)"
    assert labels["traefik.http.routers.topic-tree-staging.service"] == "topic-tree-staging"
    assert labels["traefik.http.services.topic-tree-staging.loadbalancer.server.port"] == "8010"
    assert not any(".topic-tree." in key for key in labels)
    assert "127.0.0.1:9010/health" in " ".join(service["healthcheck"]["test"])


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ("", ("0.0.0.0", "18000", 8000)),
        ("HOST_PORT=18010\nPUBLIC_PORT=8010\n", ("0.0.0.0", "18010", 8010)),
        ("DOMAIN=trees.example.org\nHOST_BIND=127.0.0.1\n", ("127.0.0.1", "18000", 8000)),
    ],
)
def test_canonical_compose_publishes_one_configurable_host_port(
    tmp_path: Path, env: str, expected: tuple[str, str, int]
) -> None:
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not installed")
    (tmp_path / "docker-compose.yml").write_text((ROOT / "docker-compose.yml").read_text(encoding="utf-8"), "utf-8")
    if env:
        (tmp_path / ".env").write_text(env, encoding="utf-8")
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "config", "--format", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    ports = json.loads(result.stdout)["services"]["topic-tree"]["ports"]
    assert [(p.get("host_ip"), p["published"], p["target"]) for p in ports] == [expected]


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose.build.yml"])
def test_compose_waits_for_running_requests_before_killing_the_container(filename: str) -> None:
    # Audit 2026-11-26: 90 s cut requests that may run up to REQUEST_TIMEOUT_SECONDS plus gunicorn's grace.
    service = yaml.safe_load((ROOT / filename).read_text(encoding="utf-8"))["services"]["topic-tree"]
    grace = int(re.fullmatch(r"(\d+)s", service["stop_grace_period"]).group(1))
    assert grace >= Settings(_env_file=None).request_timeout_seconds + 20
