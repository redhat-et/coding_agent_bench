"""Queue-driven restoration, endpoint changes, and repeated resume coverage."""

import asyncio
import json
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import tomllib
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from coding_agent_bench import api
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.resume import update_endpoint, update_parent


@pytest.fixture
def store(tmp_path, monkeypatch):
    database = api.JobStore(tmp_path / "queue.db")
    monkeypatch.setattr(api, "job_store", database)
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_job_event", asyncio.Event())
    monkeypatch.setattr(api, "_nebius", object())
    return database


@pytest.mark.parametrize("new_url,api_url", [
    ("http://203.0.113.20:9000", "http://203.0.113.20:9000/v1"),
    ("https://new-domain.example.com/api/v1", "https://new-domain.example.com/api/v1"),
    ("http://[2001:db8::2]:8000/", "http://[2001:db8::2]:8000/v1"),
])
def test_transport_changes_update_all_metadata_but_not_artifacts(tmp_path, new_url, api_url):
    old_url = "http://198.51.100.10:8000/v1"
    opencode = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {"vllm": {"options": {"baseURL": old_url, "apiKey": "NONE"}}},
        "mcp": {"tool": {"url": old_url}},
    }
    agent = {"name": "opencode", "env": {
        "OPENAI_BASE_URL": old_url, "ANTHROPIC_BASE_URL": old_url,
        "HOSTED_VLLM_API_BASE": old_url, "DOCS_URL": old_url,
        "OPENCODE_CONFIG_CONTENT": json.dumps(opencode),
    }}
    environment = {"kwargs": {"persistent_env": {"HARBOR_PARENT": "old", "KEEP": "yes"}}}
    trial = {"agent": agent, "environment": environment}
    result = {"config": trial, "agent_result": {"url": old_url, "score": 1}}
    task = tmp_path / "task__123"
    (task / "agent").mkdir(parents=True)
    documents = {
        tmp_path / "config.json": {"agents": [agent], "environment": environment},
        tmp_path / "lock.json": {"trials": [trial]},
        tmp_path / "result.json": {"trial_results": [result]},
        task / "config.json": trial, task / "lock.json": trial,
        task / "result.json": result,
    }
    for path, data in documents.items():
        path.write_text(json.dumps(data))
    artifact = task / "agent/trace.json"
    artifact.write_text(json.dumps({"url": old_url}))
    original_artifact = artifact.read_bytes()

    update_parent(tmp_path, "new-parent")
    update_endpoint(tmp_path, new_url)

    loaded = {path: json.loads(path.read_text()) for path in documents}
    configs = [
        loaded[tmp_path / "config.json"],
        loaded[tmp_path / "lock.json"]["trials"][0],
        loaded[tmp_path / "result.json"]["trial_results"][0]["config"],
        loaded[task / "config.json"], loaded[task / "lock.json"],
        loaded[task / "result.json"]["config"],
    ]
    for config in configs:
        assert config["environment"]["kwargs"]["persistent_env"] == {"HARBOR_PARENT": "new-parent", "KEEP": "yes"}
        env = (config["agent"] if "agent" in config else config["agents"][0])["env"]
        assert env["OPENAI_BASE_URL"] == api_url
        assert env["HOSTED_VLLM_API_BASE"] == api_url
        assert env["ANTHROPIC_BASE_URL"] == new_url.rstrip("/")
        assert env["DOCS_URL"] == old_url
        embedded = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        assert embedded["provider"]["vllm"]["options"] == {"baseURL": api_url, "apiKey": "NONE"}
        assert embedded["mcp"]["tool"]["url"] == old_url
        assert embedded["$schema"] == opencode["$schema"]
    assert loaded[task / "result.json"]["agent_result"] == result["agent_result"]
    assert artifact.read_bytes() == original_artifact
    first = {path: path.read_bytes() for path in documents}
    update_parent(tmp_path, "new-parent")
    update_endpoint(tmp_path, new_url)
    assert {path: path.read_bytes() for path in documents} == first


@pytest.mark.parametrize("name,target,filename", [
    ("codex", "/root/.codex/config.toml", "config.toml"),
    ("pi", "/root/.pi/agent/models.json", "models.json"),
])
def test_endpoint_restore_recreates_agent_mount_files(tmp_path, name, target, filename):
    source = tmp_path / "mounts" / filename
    config = {
        "agents": [{"name": name, "model_name": "vllm/org/model"}],
        "environment": {"mounts": [{"source": str(source), "target": target, "type": "bind"}]},
    }
    (tmp_path / "config.json").write_text(json.dumps(config))
    update_endpoint(tmp_path, "http://203.0.113.20:8000")
    if name == "codex":
        data = tomllib.loads(source.read_text())
        assert data["model"] == "org/model"
        assert data["model_providers"]["vllm"]["base_url"] == "http://203.0.113.20:8000/v1"
        assert data["model_providers"]["vllm"]["wire_api"] == "responses"
    else:
        provider = json.loads(source.read_text())["providers"]["vllm"]
        assert provider["baseUrl"] == "http://203.0.113.20:8000/v1"
        assert provider["models"][0]["id"] == "org/model"


def test_generated_preparation_steps_execute_with_quoted_paths(tmp_path):
    directory = tmp_path / "job with ' quotes"
    directory.mkdir()
    config = directory / "config.json"
    config.write_text(json.dumps({"agents": [{"env": {"OPENAI_BASE_URL": "http://198.51.100.10:8000/v1"}}]}))
    # Only replace uv's environment launcher; execute the actual module steps.
    shell = 'uv() { shift 4; "$TEST_PYTHON" "$@"; }; true'
    shell += api._build_parent_env_shell_step(str(directory))
    shell += api._build_url_replace_shell_step("https://new.example.com", str(directory))
    subprocess.run(["bash", "-c", shell], check=True, cwd=tmp_path, timeout=10, env={
        **os.environ, "TEST_PYTHON": sys.executable,
        "PYTHONPATH": str(Path(api.__file__).parents[1]), "HARBOR_PARENT": "new-parent",
    })
    restored = json.loads(config.read_text())
    assert restored["environment"]["kwargs"]["persistent_env"]["HARBOR_PARENT"] == "new-parent"
    assert restored["agents"][0]["env"]["OPENAI_BASE_URL"] == "https://new.example.com/v1"


@pytest.mark.parametrize("original_name", ["benchmark", "benchmark--resume"])
def test_repeated_manual_resumes_keep_the_original_artifact_prefix(store, original_name):
    store.insert("first", original_name, "oracle", "dataset", "model", "https://model.example.com", [])
    job_id = "first"
    for _ in range(3):
        store.update_status(job_id, api.JobStatus.FAILED)
        response = asyncio.run(api.resume_job(job_id))
        row = store.get(response["job_id"])
        assert row["results_job_name"] == original_name
        assert row["job_name"] == original_name + "--resume"
        assert f"s3://results/{original_name}/" in json.loads(row["command"])[2]
        assert f"s3://results/{original_name}/" in api._build_pause_resume_command(row)[2]
        job_id = response["job_id"]


def test_database_migration_recovers_legacy_artifact_paths(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY, job_name TEXT, agent TEXT, dataset TEXT, model_name TEXT, server_url TEXT, command TEXT, status TEXT, error TEXT)")
    for job_id, name, command in [
        ("normal", "real-name--resume", ["coding-agent-bench", "run", "--job-name", "real-name--resume"]),
        ("resume", "job with spaces--resume", ["bash", "-c", "uv run harbor jobs resume -p '/app/jobs/job with spaces' -f CancelledError"]),
    ]:
        connection.execute("INSERT INTO jobs VALUES (?, ?, 'oracle', 'dataset', 'model', 'nebius-h200', ?, 'paused', NULL)", (job_id, name, json.dumps(command)))
    connection.commit()
    connection.close()
    migrated = api.JobStore(path)
    assert migrated.get("normal")["results_job_name"] == "real-name--resume"
    assert migrated.get("resume")["results_job_name"] == "job with spaces"
    assert api.JobStore(path).get("resume")["results_job_name"] == "job with spaces"


def test_manual_paused_resume_reuses_row_and_cancellation_filter(store):
    store.insert("paused", "benchmark", "oracle", "dataset", "model", "nebius-h200", [])
    store.update_status("paused", api.JobStatus.PAUSED)
    response = asyncio.run(api.resume_job("paused", api.ResumeJobRequest(filter_error_types=["cancelled"])))
    assert response["job_id"] == "paused"
    assert len(store.list()) == 1
    assert not store.list_paused()
    assert len(api._job_queue) == 1
    assert api._job_queue[0].job_id == "paused"
    assert "-f CancelledError" in api._job_queue[0].command[2]


@pytest.mark.parametrize("winner", [api.JobStatus.QUEUED, api.JobStatus.CANCELLED])
def test_manual_resume_refuses_a_lost_state_transition(store, monkeypatch, winner):
    store.insert("paused", "benchmark", "oracle", "dataset", "model", "nebius-h200", [])
    store.update_status("paused", api.JobStatus.PAUSED)
    original = store.resume_paused

    def race(*args, **kwargs):
        store.update_status("paused", winner)
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "resume_paused", race)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.resume_job("paused"))
    assert exc.value.status_code == 409
    assert store.get("paused")["status"] == winner.value
    assert api._job_queue == []


def test_manual_resume_wins_while_automatic_recovery_is_waiting(store, monkeypatch):
    store.insert("paused", "benchmark", "oracle", "dataset", "model", "nebius-h200", [])
    store.update_status("paused", api.JobStatus.PAUSED)

    class StopLoop(Exception):
        pass

    class Nebius:
        def has_busy_instance(self):
            return False

        async def adopt_paused_instance(self, *_args):
            return "vm"

        async def recover_stopped_instance(self, _name):
            await api.resume_job("paused", api.ResumeJobRequest(server_url="https://manual.example.com"))

    sleeps = 0

    async def sleep(_seconds):
        nonlocal sleeps
        sleeps += 1
        if sleeps > 1:
            raise StopLoop

    monkeypatch.setattr(api, "_nebius", Nebius())
    monkeypatch.setattr(api, "_active_job", None)
    monkeypatch.setattr(api, "_shutting_down", False)
    monkeypatch.setattr(api.asyncio, "sleep", sleep)
    with pytest.raises(StopLoop):
        asyncio.run(api._resume_paused_jobs_loop())
    assert len(api._job_queue) == 1
    assert api._job_queue[0].server_url == "https://manual.example.com"
    assert store.get("paused")["server_url"] == "https://manual.example.com"


@pytest.mark.parametrize("legacy", [False, True])
def test_registered_model_resume_uses_only_resume_pod_spec(store, monkeypatch, legacy):
    if legacy:
        command = ["bash", "-c", "uv run harbor jobs resume -p /app/jobs/benchmark -f RuntimeError"]
    else:
        command = ["bash", "-c", api._build_resume_shell_command("benchmark", "attempt", ["RuntimeError"], None)]
    store.insert("id", "benchmark--resume", "oracle", "dataset", "known", "nebius-h200", command, results_job_name="benchmark")
    specs = []

    class Nebius:
        async def acquire_instance(self, *_args, **_kwargs):
            return "vm", "http://203.0.113.20:8000"

        async def mark_job_started(self, _name):
            pass

        async def mark_job_completed(self, _name):
            pass

    class Job(OpenshiftJob):
        def _job_spec(self, *_args, **_kwargs):
            raise AssertionError("A resume must never use the ordinary direct-upload wrapper")

        async def _run_oc_command(self, _command, **kwargs):
            specs.append(json.loads(kwargs["stdin_data"]))
            return "", ""

        async def _wait_for_job_pod_ready(self):
            pass

        async def _get_job(self):
            return {"status": {"conditions": [{"type": "Complete", "status": "True"}]}}

        async def _delete_job(self):
            pass

    monkeypatch.setattr(api, "_nebius", Nebius())
    monkeypatch.setattr(api, "OpenshiftJob", Job)
    monkeypatch.setattr(api, "MODEL_REGISTRY", {"known": SimpleNamespace(model_max_len=2048)})
    monkeypatch.setattr(api, "_worker_server_url_errors", lambda *_args, **_kwargs: [])
    asyncio.run(api._process_queued_job(api.QueuedJob("id", command, "nebius-h200", "known")))
    assert len(specs) == 1
    shell = specs[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]
    assert "--model-max-len" not in shell
    assert "s3 cp --recursive /app/jobs/ s3://results/" not in shell
    assert "-f RuntimeError" in shell
    assert "coding_agent_bench.resume endpoint /app/jobs/benchmark http://203.0.113.20:8000" in shell
    assert shlex.split(shell)[0] == "export"
