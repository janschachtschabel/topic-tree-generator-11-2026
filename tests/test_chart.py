"""Helm chart checks: versions in sync, lint, and the rendered manifests (Leitfaden Kap. 3 and 4)."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from app.version import service_version

CHART = Path(__file__).resolve().parent.parent / "deploy" / "helm" / "topic-tree"
HELM = shutil.which("helm")
needs_helm = pytest.mark.skipif(HELM is None, reason="helm not installed")

ALL_ON = [
    "--set",
    "networkPolicy.enabled=true",
    "--set",
    "networkPolicy.publicFrom[0].namespaceSelector.matchLabels.name=b-api",
    "--set",
    "networkPolicy.internalFrom[0].namespaceSelector.matchLabels.name=monitoring",
    "--set",
    "serviceMonitor.enabled=true",
    "--set",
    "prometheusRule.enabled=true",
    "--set",
    "autoscaling.enabled=true",
    "--set",
    "ingress.enabled=true",
    "--set",
    "secrets.existingSecret=topic-tree-secrets",
]


def test_chart_version_equals_app_and_service_version() -> None:
    chart = yaml.safe_load((CHART / "Chart.yaml").read_text())
    assert chart["name"] == "topic-tree"
    assert chart["version"] == chart["appVersion"] == service_version()


def test_every_value_is_documented() -> None:
    lines = (CHART / "values.yaml").read_text().splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^[a-zA-Z]\w*:", line):
            assert any("## @param" in previous for previous in lines[max(0, i - 4) : i]), line


def render(*args: str) -> list[dict]:
    out = subprocess.run([HELM, "template", "t", str(CHART), *args], check=True, capture_output=True, text=True)
    return [doc for doc in yaml.safe_load_all(out.stdout) if doc]


def kinds(docs: list[dict]) -> dict[str, dict]:
    return {doc["kind"]: doc for doc in docs}


@needs_helm
def test_helm_lint_strict_passes() -> None:
    result = subprocess.run(
        [HELM, "lint", "--strict", str(CHART), *ALL_ON], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


@needs_helm
def test_default_render_has_two_ports_probes_and_restricted_security() -> None:
    docs = kinds(render())
    assert set(docs) == {"Deployment", "Service"}
    pod = docs["Deployment"]["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert {p["name"]: p["containerPort"] for p in container["ports"]} == {"http": 8000, "internal": 9000}
    assert container["livenessProbe"]["httpGet"] == {"path": "/health", "port": "internal"}
    assert container["readinessProbe"]["httpGet"] == {"path": "/health", "port": "http"}
    sc = container["securityContext"]
    assert sc["readOnlyRootFilesystem"] is True and sc["allowPrivilegeEscalation"] is False
    assert sc["capabilities"]["drop"] == ["ALL"]
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
    assert {"name": "tmp", "mountPath": "/tmp"} in container["volumeMounts"]
    env = {e["name"]: e.get("value") for e in container["env"]}
    assert env["SERVICE_ID"] == "topic-tree" and env["SERVICE_MODE"] == "bapi"
    assert env["UI_ENABLED"] == "false"
    assert docs["Deployment"]["spec"]["template"]["spec"]["terminationGracePeriodSeconds"] >= 290
    ports = {p["name"]: p["port"] for p in docs["Service"]["spec"]["ports"]}
    assert ports == {"http": 8000, "internal": 9000}


def test_probes_are_configurable_in_values() -> None:
    # Leitfaden Kap. 4: values.yaml maps every setting, probes included.
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    assert values["probes"]["liveness"]["httpGet"] == {"path": "/health", "port": "internal"}
    assert values["probes"]["readiness"]["httpGet"] == {"path": "/health", "port": "http"}
    template = (CHART / "templates" / "deployment.yaml").read_text(encoding="utf-8")
    assert ".Values.probes.liveness" in template and ".Values.probes.readiness" in template


@needs_helm
def test_probe_overrides_reach_the_deployment() -> None:
    docs = kinds(render("--set", "probes.readiness.periodSeconds=7", "--set", "probes.liveness.failureThreshold=5"))
    container = docs["Deployment"]["spec"]["template"]["spec"]["containers"][0]
    assert container["readinessProbe"]["periodSeconds"] == 7
    assert container["livenessProbe"]["failureThreshold"] == 5


@needs_helm
def test_optional_parts_render_when_enabled() -> None:
    docs = kinds(render(*ALL_ON))
    assert {"NetworkPolicy", "ServiceMonitor", "PrometheusRule", "HorizontalPodAutoscaler", "Ingress"} <= set(docs)
    policy = docs["NetworkPolicy"]["spec"]
    rules = {r["ports"][0]["port"]: r["from"] for r in policy["ingress"]}
    assert rules["http"][0]["namespaceSelector"]["matchLabels"]["name"] == "b-api"
    assert rules["internal"][0]["namespaceSelector"]["matchLabels"]["name"] == "monitoring"
    assert docs["ServiceMonitor"]["spec"]["endpoints"][0]["port"] == "internal"
    container = docs["Deployment"]["spec"]["template"]["spec"]["containers"][0]
    assert container["envFrom"] == [{"secretRef": {"name": "topic-tree-secrets"}}]
    alerts = [r["alert"] for g in docs["PrometheusRule"]["spec"]["groups"] for r in g["rules"]]
    assert {"TopicTreeLLMErrors", "TopicTreeSlowRequests", "TopicTreeDescribeFailures"} <= set(alerts)


@needs_helm
def test_enabled_policy_without_peers_denies_instead_of_allowing_everyone() -> None:
    # An ingress rule with an empty "from" list would match ALL sources in Kubernetes.
    policy = kinds(render("--set", "networkPolicy.enabled=true"))["NetworkPolicy"]["spec"]
    assert not policy.get("ingress")  # null or [] with policyTypes Ingress = deny all
    assert "Ingress" in policy["policyTypes"]


def test_gitlab_ci_kubeconform_job_uses_alpine_image_with_shell() -> None:
    # GitLab Runner's Docker executor invokes `sh` inside every job image; bare kubeconform tags are `FROM scratch`.
    gitlab_ci = yaml.safe_load((CHART.parents[2] / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    image = gitlab_ci["kubeconform"]["image"]
    image_name = image["name"] if isinstance(image, dict) else image
    assert image_name.startswith("ghcr.io/yannh/kubeconform:") and image_name.endswith("-alpine"), image_name


def test_large_integer_values_are_rendered_without_float_notation() -> None:
    # Audit 2026-11-26: Helm reads numbers as float64, so `| quote` turned 10485760 into "1.048576e+07",
    # which Settings cannot parse; `int64` first keeps the plain digits.
    template = (CHART / "templates" / "deployment.yaml").read_text(encoding="utf-8")
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["config"]
    large = [name for name, value in values.items() if isinstance(value, int) and value >= 1_000_000]
    assert large
    for name in large:
        assert f".Values.config.{name} | int64 | quote" in template
