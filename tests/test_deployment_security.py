"""Deployment security regression tests."""

from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

from coding_agent_bench import api
from coding_agent_bench.job import OpenshiftJob


DEPLOYMENT_PATHS = (
    Path(__file__).parents[1] / "deploy" / "job-queue" / "base" / "deployment.yaml",
    Path(__file__).parents[1] / "deploy" / "job-queue" / "base" / "service.yaml",
    Path(__file__).parents[1] / "deploy" / "job-queue" / "base" / "route.yaml",
)
INTAKE_CRONJOB_PATH = (
    Path(__file__).parents[1] / "deploy" / "intake-poller" / "base" / "cronjob.yaml"
)


def _deployment_objects() -> dict[str, dict]:
    """Return queue manifest objects indexed by Kubernetes kind."""
    objects = []
    for path in DEPLOYMENT_PATHS:
        with path.open() as manifest:
            objects.extend(yaml.safe_load_all(manifest))
    return {obj["kind"]: obj for obj in objects}


def _intake_cronjob() -> dict:
    """Return the intake CronJob object from its (multi-document) manifest."""
    with INTAKE_CRONJOB_PATH.open() as manifest:
        objects = list(yaml.safe_load_all(manifest))
    return next(obj for obj in objects if obj["kind"] == "CronJob")


def test_queue_manifest_encrypts_service_and_route():
    """Serve queue traffic with application TLS and an OpenShift reencrypt Route."""
    objects = _deployment_objects()
    deployment = objects["Deployment"]
    service = objects["Service"]
    route = objects["Route"]

    container = deployment["spec"]["template"]["spec"]["containers"][0]
    command = container["args"][0]
    assert "--port 8443" in command
    assert "--ssl-certfile /etc/job-queue/tls/tls.crt" in command
    assert "--ssl-keyfile /etc/job-queue/tls/tls.key" in command
    assert service["metadata"]["annotations"][
        "service.beta.openshift.io/serving-cert-secret-name"
    ] == "job-queue-tls"
    assert service["spec"]["ports"][0]["port"] == 443
    assert service["spec"]["ports"][0]["targetPort"] == 8443
    assert route["spec"]["tls"]["termination"] == "reencrypt"

    container_security = container["securityContext"]
    assert container_security["runAsNonRoot"] is True
    assert container_security["allowPrivilegeEscalation"] is False
    assert container_security["capabilities"]["drop"] == ["ALL"]
    assert container_security["seccompProfile"]["type"] == "RuntimeDefault"


def test_managed_worker_endpoint_must_be_public():
    """Revalidate provider-generated endpoints before launching a worker pod."""
    assert api._worker_server_url_errors(
        "http://93.184.216.34:8000", managed_endpoint=True
    ) == []
    errors = api._worker_server_url_errors(
        "http://169.254.169.254:8000", managed_endpoint=True
    )
    assert errors
    assert "private" in errors[0] or "reserved" in errors[0]


def test_intake_cronjob_uses_a_dedicated_poller_secret():
    """Keep poller settings separate from the queue service secret."""
    cronjob = _intake_cronjob()
    container = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
    env = {entry["name"]: entry for entry in container["env"]}

    poller_only_keys = {
        "GOOGLE_SHEET_ID",
        "JOB_QUEUE_URL",
        "AUTO_APPROVE",
    }
    for key in poller_only_keys:
        assert env[key]["valueFrom"]["secretKeyRef"]["name"] == "intake-poller-secret"

    assert env["API_KEY"]["valueFrom"]["secretKeyRef"]["name"] == "job-queue-secret"


@pytest.mark.parametrize("overlay", ["stage", "prod"])
def test_deployed_workers_use_the_queue_image(overlay, monkeypatch):
    cli = shutil.which("oc") or shutil.which("kubectl")
    if cli is None:
        pytest.skip("oc or kubectl is required to render deployment overlays")
    path = DEPLOYMENT_PATHS[0].parents[1] / "overlays" / overlay
    rendered = subprocess.run(
        [cli, "kustomize", str(path)], check=True, capture_output=True,
        text=True, timeout=30,
    ).stdout
    deployment = next(obj for obj in yaml.safe_load_all(rendered) if obj["kind"] == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    env = {entry["name"]: entry.get("value") for entry in container["env"]}
    assert env["CODING_AGENT_BENCH_IMAGE"] == container["image"]
    monkeypatch.setenv("CODING_AGENT_BENCH_IMAGE", env["CODING_AGENT_BENCH_IMAGE"])
    job = OpenshiftJob("benchmark")
    for spec in (job._job_spec(["harbor", "run"]), job._resume_job_spec("resume")):
        assert spec["spec"]["template"]["spec"]["containers"][0]["image"] == container["image"]
