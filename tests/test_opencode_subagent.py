"""OpenCode reviewer configuration across local, queue, and resume paths."""

import asyncio
import json
import os
import shlex
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner
from fastapi import HTTPException

from coding_agent_bench.agents.configs import OpenCodeAgentConfig
from coding_agent_bench.agents.opencode import OpenCodeSubagentConfig
from coding_agent_bench.api import CreateJobRequest, build_cli_command
from coding_agent_bench import api
from coding_agent_bench.builder import HarborCommandBuilder
from coding_agent_bench.cli import app
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.resume import _update_agent_endpoint, update_parent


@pytest.fixture
def worker_queue(tmp_path, monkeypatch):
    store = api.JobStore(tmp_path / "jobs.db")
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_job_event", asyncio.Event())
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return store


def configure(subagent=None, **kwargs):
    return OpenCodeAgentConfig().configure(
        model_name="primary",
        server_url="http://primary:8000/v1",
        model_max_len=10000,
        opencode_subagent=subagent,
        **kwargs,
    )


def config(result):
    return json.loads(result.agent_env["OPENCODE_CONFIG_CONTENT"])


def request(**kwargs):
    return CreateJobRequest(
        job_name="reviewer-test",
        agent=kwargs.pop("agent", "opencode"),
        dataset="example/dataset",
        model_name="primary",
        server_url="https://primary.example.com/v1",
        **kwargs,
    )


def test_existing_experiments_unchanged():
    result = configure()
    cfg = config(result)
    assert result.model == cfg["model"] == "vllm/primary"
    assert cfg["provider"]["vllm"]["models"]["primary"]["limit"] == {
        "context": 7500,
        "output": 2500,
    }
    assert "agent" not in cfg
    assert set(cfg["provider"]) == {"vllm"}
    assert set(result.agent_env) == {"OPENCODE_CONFIG_CONTENT"}
    assert request().opencode_subagent is None
    assert "--opencode-subagent" not in build_cli_command(request())


@pytest.mark.parametrize("reviewer_model", ["stronger", "primary"])
def test_independent_models_and_limits(reviewer_model):
    cfg = config(
        configure(
            {
                "model_name": reviewer_model,
                "server_url": "https://reviewer.example.com/",
                "model_max_len": 4000,
                "description": "Ask when stuck",
                "prompt": "Review carefully",
            }
        )
    )
    assert cfg["model"] == "vllm/primary"
    assert cfg["provider"]["vllm"]["options"]["baseURL"] == "http://primary:8000/v1"
    provider = cfg["provider"]["reviewer"]
    assert provider["options"] == {"baseURL": "https://reviewer.example.com/v1"}
    assert provider["models"][reviewer_model]["limit"] == {
        "context": 3000,
        "output": 1000,
    }
    reviewer = cfg["agent"]["reviewer"]
    assert reviewer["mode"] == "subagent"
    assert reviewer["model"] == f"reviewer/{reviewer_model}"
    assert reviewer["description"] == "Ask when stuck"
    assert reviewer["prompt"] == "Review carefully"
    assert reviewer["permission"] == {"edit": "deny", "bash": "deny", "task": "deny"}
    assert cfg["agent"]["build"]["permission"]["task"]["reviewer"] == "allow"


@pytest.mark.parametrize("endpoint", [None, "https://reviewer.example.com"])
def test_resume_updates_only_inherited_reviewer_endpoint(endpoint):
    result = configure({"model_name": "stronger", "server_url": endpoint})
    agent = {
        "env": result.agent_env,
        "extra_allowed_hosts": ["primary", "docs.example.com"],
    }
    _update_agent_endpoint(agent, "http://new-primary:9000")
    cfg = json.loads(agent["env"]["OPENCODE_CONFIG_CONTENT"])
    assert cfg["provider"]["vllm"]["options"]["baseURL"] == "http://new-primary:9000/v1"
    expected = "http://new-primary:9000/v1" if endpoint is None else endpoint + "/v1"
    assert cfg["provider"]["reviewer"]["options"]["baseURL"] == expected
    expected_hosts = (
        ["docs.example.com", "new-primary"]
        if endpoint is None
        else ["primary", "docs.example.com"]
    )
    assert agent["extra_allowed_hosts"] == expected_hosts


def test_reviewer_openrouter_credentials_and_remote_secret(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-reviewer-key")
    reviewer = {"model_name": "provider/stronger", "server_url": "openrouter"}
    cfg = config(configure(reviewer))
    assert "apiKey" not in cfg["provider"]["vllm"]["options"]
    assert cfg["provider"]["reviewer"]["options"] == {
        "baseURL": "https://openrouter.ai/api/v1",
        "apiKey": "test-reviewer-key",
    }
    command = build_cli_command(request(opencode_subagent=reviewer))
    assert "test-reviewer-key" not in " ".join(command)
    spec = OpenshiftJob("test")._job_spec(command)
    env = spec["spec"]["template"]["spec"]["containers"][0]["env"]
    assert any(item["name"] == "OPENROUTER_API_KEY" for item in env)


def test_missing_reviewer_key_fails(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        configure({"model_name": "stronger", "server_url": "openrouter"})


def test_inherited_openrouter_endpoint_and_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    cfg = config(
        OpenCodeAgentConfig().configure(
            model_name="primary",
            server_url="openrouter",
            opencode_subagent={"model_name": "stronger"},
        )
    )
    assert cfg["provider"]["reviewer"]["options"] == cfg["provider"]["vllm"]["options"]


@pytest.mark.parametrize("primary_url", ["openrouter", "nebius-h200"])
def test_api_validates_reviewer_even_when_primary_skips_builder(
    primary_url, monkeypatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    req = request(
        opencode_subagent={"model_name": "stronger", "server_url": "openrouter"}
    )
    req.server_url = primary_url
    with patch.object(HarborCommandBuilder, "build") as build:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(api.create_job(req))
    assert exc.value.status_code == 400
    assert "OPENROUTER_API_KEY" in exc.value.detail
    build.assert_not_called()


def test_api_validates_explicit_reviewer_url(monkeypatch):
    req = request(
        opencode_subagent={
            "model_name": "stronger",
            "server_url": "https://reviewer.example.com",
        }
    )
    monkeypatch.setattr(
        api, "validate_server_url", lambda url: ["Invalid reviewer endpoint"]
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.create_job(req))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid reviewer endpoint"


def test_local_reviewer_does_not_receive_openrouter_secret():
    command = build_cli_command(request(opencode_subagent={"model_name": "stronger"}))
    spec = OpenshiftJob("test")._job_spec(command)
    env = spec["spec"]["template"]["spec"]["containers"][0]["env"]
    assert all(item["name"] != "OPENROUTER_API_KEY" for item in env)


@pytest.mark.parametrize("equals_form", [False, True])
@pytest.mark.parametrize("endpoint", ["openrouter", " openrouter "])
def test_remote_secret_normalizes_cli_option(equals_form, endpoint):
    value = json.dumps({"model_name": "stronger", "server_url": endpoint})
    option = (
        ["--opencode-subagent=" + value]
        if equals_form
        else ["--opencode-subagent", value]
    )
    command = ["coding-agent-bench", "run", *option]
    spec = OpenshiftJob("test")._job_spec(command)
    env = spec["spec"]["template"]["spec"]["containers"][0]["env"]
    assert any(item["name"] == "OPENROUTER_API_KEY" for item in env)


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"model_name": " "},
        {"model_name": "stronger", "model_max_len": 0},
        {"model_name": "stronger", "model_max_len": "100"},
        {"model_name": "stronger", "server_url": "nebius-h200"},
        {"model_name": "stronger", "server_url": ""},
        {"model_name": "stronger", "server_url": "https://reviewer.example.com:bogus"},
        {"model_name": "stronger", "server_url": "https://reviewer.example.com:70000"},
        {"model_name": "stronger", "server_url": "https://reviewer.example.com:0"},
        {"model_name": "stronger", "description": ""},
        {"model_name": "stronger", "unexpected": True},
    ],
)
def test_invalid_reviewer_config_rejected(value):
    with pytest.raises(ValidationError):
        OpenCodeSubagentConfig.model_validate(value)


@pytest.mark.parametrize("agent", ["oracle", "codex", "pi", "claude-code", "openclaw"])
def test_other_harnesses_reject_option(agent):
    with pytest.raises(ValueError, match="only supported for OpenCode"):
        request(agent=agent, opencode_subagent={"model_name": "stronger"})
    with pytest.raises(ValueError, match="only supported for OpenCode"):
        HarborCommandBuilder().build(
            agent=agent,
            dataset="example/dataset",
            model_name="primary",
            server_url="http://primary:8000",
            environment="docker",
            opencode_subagent={"model_name": "stronger"},
        )


def test_queue_cli_builder_round_trip():
    req = request(opencode_subagent={"model_name": "stronger"})
    command = build_cli_command(req)
    with patch.object(
        HarborCommandBuilder,
        "build",
        return_value=(["harbor", "run"], Path("jobs/test")),
    ) as build:
        result = CliRunner().invoke(app, [*command[1:], "--dry-run"])
    assert result.exit_code == 0, result.output
    reviewer = build.call_args.kwargs["opencode_subagent"]
    assert reviewer == req.opencode_subagent
    harbor, _ = HarborCommandBuilder().build(
        **{key: value for key, value in build.call_args.kwargs.items()}
    )
    env = next(arg for arg in harbor if arg.startswith("OPENCODE_CONFIG_CONTENT="))
    assert (
        json.loads(env.split("=", 1)[1])["agent"]["reviewer"]["model"]
        == "reviewer/stronger"
    )


@pytest.mark.parametrize(
    "agent,reviewer",
    [
        ("opencode", "{broken"),
        ("opencode", "{}"),
        ("oracle", '{"model_name":"stronger"}'),
    ],
)
def test_cli_rejects_invalid_configuration_before_launch(agent, reviewer):
    with patch.object(OpenshiftJob, "run") as launch:
        result = CliRunner().invoke(
            app,
            [
                "run",
                "--agent",
                agent,
                "--dataset",
                "example/dataset",
                "--model-name",
                "primary",
                "--server-url",
                "https://primary.example.com",
                "--environment",
                "openshift",
                "--remote",
                "--opencode-subagent",
                reviewer,
            ],
        )
    assert result.exit_code != 0
    launch.assert_not_called()


def test_example_configuration_loads():
    path = Path(__file__).parents[1] / "examples/opencode-subagent.json"
    req = CreateJobRequest.model_validate_json(path.read_text())
    assert req.agent == "opencode"
    assert req.model_name != req.opencode_subagent.model_name


def test_builder_preserves_existing_positional_arguments(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    positional = HarborCommandBuilder().build(
        "opencode",
        "example/dataset",
        "primary",
        "https://primary.example.com",
        "docker",
        "task-*",
        2,
        3,
        10000,
        "my-job",
        "latest",
        4,
        ["AgentTimeoutError"],
        ["org/skills"],
        2.5,
        "high",
        ["docs.example.com"],
    )
    keyword = HarborCommandBuilder().build(
        agent="opencode",
        dataset="example/dataset",
        model_name="primary",
        server_url="https://primary.example.com",
        environment="docker",
        dataset_pattern="task-*",
        n_concurrent=2,
        n_tasks=3,
        model_max_len=10000,
        job_name="my-job",
        agent_version="latest",
        max_retries=4,
        retry_include=["AgentTimeoutError"],
        skills=["org/skills"],
        agent_timeout_multiplier=2.5,
        thinking="high",
        allow_agent_host=["docs.example.com"],
    )
    assert positional == keyword
    assert positional[1] == tmp_path / "jobs/my-job"


@pytest.mark.parametrize(
    "reviewer_url,expected_host",
    [
        ("https://reviewer.example.com:8443/api/v1", "reviewer.example.com"),
        (" openrouter ", "openrouter.ai"),
        (None, "primary.example.com"),
        ("https://93.184.216.34/v1", "93.184.216.34"),
        ("https://[2606:4700:4700::1111]:8443/v1", "2606:4700:4700::1111"),
    ],
)
@pytest.mark.parametrize("already_allowed", [False, True])
def test_reviewer_host_is_allowed_only_during_agent_phase(
    reviewer_url, expected_host, already_allowed, monkeypatch
):
    from harbor.models.task.config import NetworkMode, NetworkPolicy, TaskConfig
    from harbor.models.trial.config import AgentConfig
    from harbor.trial.network_policy import (
        resolve_agent_phase_policy,
        resolve_verifier_phase_policy,
    )

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    supplied_hosts = ["docs.example.com"] + ([expected_host] if already_allowed else [])
    original_hosts = supplied_hosts.copy()
    command, _ = HarborCommandBuilder().build(
        agent="opencode",
        dataset="example/dataset",
        model_name="primary",
        server_url="https://primary.example.com",
        environment="docker",
        opencode_subagent={"model_name": "stronger", "server_url": reviewer_url},
        allow_agent_host=supplied_hosts,
    )
    hosts = [
        command[index + 1]
        for index, item in enumerate(command)
        if item == "--allow-agent-host"
    ]
    assert hosts == ["docs.example.com", expected_host]
    assert supplied_hosts == original_hosts
    assert "--allow-environment-host" not in command
    baseline = NetworkPolicy(
        network_mode=NetworkMode.ALLOWLIST, allowed_hosts=["primary.example.com"]
    )
    agent_policy = resolve_agent_phase_policy(
        TaskConfig(), AgentConfig(name="opencode", extra_allowed_hosts=hosts), baseline
    )
    assert set(agent_policy.allowed_hosts) == {
        "primary.example.com",
        "docs.example.com",
        expected_host,
    }
    assert agent_policy.network_mode == NetworkMode.ALLOWLIST
    verifier_policy = resolve_verifier_phase_policy(
        TaskConfig(), None, baseline=baseline
    )
    assert verifier_policy == baseline


def test_queue_reviewer_host_is_added_without_an_explicit_allowlist():
    command = build_cli_command(
        request(
            opencode_subagent={
                "model_name": "stronger",
                "server_url": "https://reviewer.example.com:8443/v1",
            }
        )
    )
    result = CliRunner().invoke(app, [*command[1:], "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "--allow-agent-host reviewer.example.com" in result.output


def test_worker_revalidates_reviewer_after_dns_changes(worker_queue, monkeypatch):
    address = "93.184.216.34"
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
        ],
    )
    req = request(
        opencode_subagent={
            "model_name": "stronger",
            "server_url": "https://reviewer.example.com",
        }
    )
    req.server_url = "openrouter"
    created = asyncio.run(api.create_job(req))
    address = "169.254.169.254"
    with patch.object(
        OpenshiftJob, "_run_oc_command", new_callable=AsyncMock
    ) as launch:
        asyncio.run(
            api._run_job(created.job_id, created.command, server_url="openrouter")
        )
    launch.assert_not_awaited()
    row = worker_queue.get(created.job_id)
    assert row["status"] == api.JobStatus.FAILED.value
    assert "Reviewer URL validation failed" in row["error"]
    assert "private or reserved" in row["error"]


@pytest.mark.parametrize(
    "endpoint", ["http://93.184.216.34", "https://127.0.0.1", "https://169.254.169.254"]
)
def test_managed_primary_does_not_relax_reviewer_url_policy(endpoint, worker_queue):
    req = request(opencode_subagent={"model_name": "stronger", "server_url": endpoint})
    command = build_cli_command(req)
    worker_queue.insert(
        "test-job",
        "test",
        "opencode",
        req.dataset,
        req.model_name,
        req.server_url,
        command,
    )
    with patch.object(
        OpenshiftJob, "_run_oc_command", new_callable=AsyncMock
    ) as launch:
        asyncio.run(
            api._run_job(
                "test-job",
                command,
                server_url="http://93.184.216.34",
                managed_endpoint=True,
            )
        )
    launch.assert_not_awaited()
    row = worker_queue.get("test-job")
    assert row["status"] == api.JobStatus.FAILED.value
    assert "Reviewer URL validation failed" in row["error"]


@pytest.mark.parametrize(
    "endpoint", ["https://93.184.216.34:8443/v1", " openrouter ", None]
)
def test_worker_launches_valid_reviewer_config(endpoint, worker_queue, monkeypatch):
    req = request(opencode_subagent={"model_name": "stronger", "server_url": endpoint})
    command = build_cli_command(req)
    worker_queue.insert(
        "test-job",
        "test",
        "opencode",
        req.dataset,
        req.model_name,
        req.server_url,
        command,
    )
    monkeypatch.setattr(api, "_retry_terminal_job", AsyncMock())
    with (
        patch.object(OpenshiftJob, "_run_oc_command", new_callable=AsyncMock) as launch,
        patch.object(OpenshiftJob, "_wait_for_job_pod_ready", new_callable=AsyncMock),
        patch.object(
            OpenshiftJob,
            "_get_job",
            new_callable=AsyncMock,
            return_value={
                "status": {"conditions": [{"type": "Complete", "status": "True"}]},
            },
        ),
    ):
        asyncio.run(api._run_job("test-job", command, server_url="openrouter"))
    launch.assert_awaited_once()
    assert launch.call_args.args[0] == ["apply", "-f", "-"]


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://*.example.com",
        "https://reviewer*.example.com",
        "https://%2A.example.com",
        "https://reviewer.%2a.example.com",
    ],
)
@pytest.mark.parametrize("inherited", [False, True])
def test_wildcard_reviewer_hosts_rejected_before_command_generation(
    endpoint, inherited
):
    reviewer = {"model_name": "stronger"}
    if not inherited:
        reviewer["server_url"] = endpoint
    with patch.object(HarborCommandBuilder, "_build_command") as build:
        with pytest.raises(ValueError, match="wildcard hostname"):
            HarborCommandBuilder().build(
                agent="opencode",
                dataset="example/dataset",
                model_name="primary",
                server_url=endpoint if inherited else "https://primary.example.com",
                environment="docker",
                opencode_subagent=reviewer,
            )
    build.assert_not_called()


def restored_reviewer(endpoint):
    """Build a saved agent, allowing tests to simulate changed legacy metadata."""
    result = configure(
        {"model_name": "stronger", "server_url": "https://reviewer.example.com"}
    )
    opencode = config(result)
    opencode["provider"]["reviewer"]["options"]["baseURL"] = endpoint
    result.agent_env["OPENCODE_CONFIG_CONTENT"] = json.dumps(opencode)
    return {"name": "opencode", "env": result.agent_env}


@pytest.mark.parametrize("location", ["root", "trial", "lock", "result"])
def test_resume_rechecks_explicit_reviewer_after_dns_changes(
    tmp_path, monkeypatch, location
):
    address = "93.184.216.34"
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
        ],
    )
    agent = restored_reviewer("https://reviewer.example.com/v1")
    root = tmp_path / "config.json"
    root.write_text(
        json.dumps({"agents": [agent]} if location == "root" else {"agents": []})
    )
    if location == "trial":
        trial = tmp_path / "trial"
        trial.mkdir()
        (trial / "config.json").write_text(json.dumps({"agent": agent}))
    elif location == "lock":
        (tmp_path / "lock.json").write_text(json.dumps({"trials": [{"agent": agent}]}))
    elif location == "result":
        (tmp_path / "result.json").write_text(
            json.dumps({"trial_results": [{"config": {"agent": agent}}]})
        )

    update_parent(tmp_path, "first-parent")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    address = "169.254.169.254"
    with pytest.raises(
        ValueError, match="Reviewer URL validation failed.*private or reserved"
    ):
        update_parent(tmp_path, "second-parent")
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize(
    "endpoint,error",
    [
        ("http://93.184.216.34/v1", "https scheme"),
        ("https://127.0.0.1/v1", "private or reserved"),
        ("https://*.example.com/v1", "wildcard hostname"),
        (None, "reviewer has no endpoint"),
    ],
)
def test_resume_rejects_invalid_saved_reviewer_endpoint(tmp_path, endpoint, error):
    (tmp_path / "config.json").write_text(
        json.dumps({"agents": [restored_reviewer(endpoint)]})
    )
    with pytest.raises(ValueError, match=error):
        update_parent(tmp_path, "new-parent")


@pytest.mark.parametrize("kind", ["inherited", "other-harness", "no-reviewer"])
def test_resume_reviewer_validation_leaves_other_configurations_compatible(
    tmp_path, monkeypatch, kind
):
    agent = restored_reviewer("http://127.0.0.1/v1")
    if kind == "inherited":
        agent["env"]["CAB_OPENCODE_SUBAGENT_INHERIT_ENDPOINT"] = "1"
    elif kind == "other-harness":
        agent["name"] = "pi"
    else:
        agent = {"name": "opencode", "env": configure().agent_env}
    (tmp_path / "config.json").write_text(json.dumps({"agents": [agent]}))
    with patch.object(socket, "getaddrinfo") as dns:
        update_parent(tmp_path, "new-parent")
    dns.assert_not_called()
    updated = json.loads((tmp_path / "config.json").read_text())
    assert (
        updated["environment"]["kwargs"]["persistent_env"]["HARBOR_PARENT"]
        == "new-parent"
    )
    assert updated["agents"] == [agent]


@pytest.mark.parametrize(
    "endpoint,allowed",
    [
        ("https://93.184.216.34/v1", True),
        ("https://169.254.169.254/v1", False),
    ],
)
def test_resume_preparation_checks_reviewer_before_starting_harbor(
    tmp_path, endpoint, allowed
):
    (tmp_path / "config.json").write_text(
        json.dumps({"agents": [restored_reviewer(endpoint)]})
    )
    marker = tmp_path / "harbor-started"
    shell = 'uv() { shift 4; "$TEST_PYTHON" "$@"; }; true'
    shell += api._build_parent_env_shell_step(str(tmp_path))
    shell += " && " + shlex.join(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('harbor-started').touch()",
        ]
    )
    result = subprocess.run(
        ["bash", "-c", shell],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        env={
            **os.environ,
            "TEST_PYTHON": sys.executable,
            "HARBOR_PARENT": "new-parent",
            "PYTHONPATH": str(Path(api.__file__).parents[1]),
        },
    )
    assert (result.returncode == 0) == allowed, result.stderr
    assert marker.exists() == allowed
    if not allowed:
        assert "Reviewer URL validation failed" in result.stderr
