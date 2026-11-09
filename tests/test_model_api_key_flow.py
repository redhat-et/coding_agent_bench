import asyncio
import json

import pytest
from pydantic import SecretStr

from coding_agent_bench.builder import HarborCommandBuilder


def test_model_api_key_is_passed_as_agent_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    command, _ = HarborCommandBuilder().build(
        agent="claude-code",
        dataset="example-dataset",
        model_name="example-model",
        server_url="https://model.example.com",
        environment="docker",
        api_key="model-key",
    )

    ae_values = [command[index + 1] for index, value in enumerate(command) if value == "--ae"]
    assert "CAB_MODEL_API_KEY=model-key" in ae_values


def test_cleanup_deletes_only_inactive_queue_owned_secrets(monkeypatch):
    from coding_agent_bench import api

    class Store:
        def list(self):
            return [{"job_id": "active-job", "status": api.JobStatus.RUNNING.value}]

    secrets = {
        "items": [
            {"metadata": {"name": "queue-old", "labels": {
                "coding-agent-bench-owner": "queue",
                "coding-agent-bench-job": "old-job",
            }}},
            {"metadata": {"name": "queue-active", "labels": {
                "coding-agent-bench-owner": "queue",
                "coding-agent-bench-job": "active-job",
            }}},
            {"metadata": {"name": "cli-old", "labels": {
                "coding-agent-bench-job": "old-job",
            }}},
        ]
    }
    deleted = []

    async def run_oc(command, **_kwargs):
        if command[:4] == ["get", "secrets", "-l", "coding-agent-bench-purpose=model-api-key"]:
            return json.dumps(secrets)
        deleted.append(command)
        return ""

    monkeypatch.setattr(api, "job_store", Store())
    monkeypatch.setattr(api, "_run_oc", run_oc)

    asyncio.run(api._cleanup_model_api_key_secrets())

    assert deleted == [["delete", "secret", "queue-old", "--ignore-not-found"]]


@pytest.mark.parametrize("status", [
    "completing", "failing", "cancelling", "pausing",
])
def test_adopt_existing_reconciles_transitional_state_without_model_key(monkeypatch, status):
    from coding_agent_bench import api

    class Store:
        row = {
            "status": status,
            "command": "[]",
            "server_url": "https://model.example",
            "model_name": "model",
            "model_api_key_required": 1,
            "error": None,
        }

        def get(self, _job_id):
            return self.row

    calls = []

    class Job:
        model_api_key_secret_name = "secret"

        async def delete_model_api_key_secret(self):
            pass

    async def terminal(*_args, **_kwargs):
        calls.append("terminal")

    async def cancellation(*_args, **_kwargs):
        calls.append("cancellation")

    async def pause(*_args, **_kwargs):
        calls.append("pause")

    monkeypatch.setattr(api, "job_store", Store())
    monkeypatch.setattr(api, "OpenshiftJob", lambda **_kwargs: Job())
    monkeypatch.setattr(api, "_retry_terminal_job", terminal)
    monkeypatch.setattr(api, "_retry_cancellation", cancellation)
    monkeypatch.setattr(api, "_retry_pause_finalize", pause)

    asyncio.run(api._process_queued_job(
        api.QueuedJob("job", [], "https://model.example", "model", adopt_existing=True)
    ))

    assert calls == [{
        "completing": "terminal", "failing": "terminal",
        "cancelling": "cancellation", "pausing": "pause",
    }[status]]


def test_failed_paused_recovery_retains_model_api_key_secret(monkeypatch):
    from coding_agent_bench import api

    class Store:
        row = {
            "status": api.JobStatus.PAUSED.value,
            "command": "[]",
            "server_url": "https://model.example",
            "model_name": "model",
            "model_api_key_required": 1,
            "error": None,
        }

        def get(self, _job_id):
            return self.row

    class Job:
        model_api_key_secret_name = "secret"
        deleted = False

        async def model_api_key_secret_exists(self):
            return True

        async def delete_model_api_key_secret(self):
            self.deleted = True

    job = Job()
    monkeypatch.setattr(api, "job_store", Store())
    monkeypatch.setattr(api, "OpenshiftJob", lambda **_kwargs: job)

    async def run_false(_row):
        return False

    monkeypatch.setattr(api, "_recover_paused_job", run_false)
    asyncio.run(api._process_queued_job(
        api.QueuedJob("job", [], "https://model.example", "model", adopt_existing=True)
    ))

    assert not job.deleted


def test_shutdown_retains_model_api_key_secret_for_recovery(monkeypatch):
    from coding_agent_bench import api

    class Store:
        row = {
            "status": api.JobStatus.RUNNING.value,
            "command": "[]",
            "server_url": "https://model.example",
            "model_name": "model",
            "model_api_key_required": 1,
            "error": None,
        }

        def get(self, _job_id):
            return self.row

    class Job:
        model_api_key_secret_name = "secret"
        deleted = False

        async def create_model_api_key_secret(self, _key, **_kwargs):
            pass

        async def delete_model_api_key_secret(self):
            self.deleted = True

    async def cancelled(*_args, **_kwargs):
        raise asyncio.CancelledError

    job = Job()
    monkeypatch.setattr(api, "job_store", Store())
    monkeypatch.setattr(api, "OpenshiftJob", lambda **_kwargs: job)
    monkeypatch.setattr(api, "_run_job", cancelled)
    monkeypatch.setattr(api, "_shutting_down", True)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(api._process_queued_job(
            api.QueuedJob(
                "job", [], "https://model.example", "model",
                model_api_key=SecretStr("key"),
            )
        ))

    assert not job.deleted
