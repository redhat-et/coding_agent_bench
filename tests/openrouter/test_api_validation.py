"""API-level negative tests for OpenRouter job creation.

These exercise the full FastAPI app via TestClient rather than just the unit
helpers in `providers.py` / `agents/configs.py`, to confirm `POST /jobs`
actually returns clean 400s for the two OpenRouter validation cases handled
in `create_job` (unsupported agent and missing OPENROUTER_API_KEY) instead of
falling through to HarborCommandBuilder().build(), which could write the real
key to a generated agent configuration.

Env vars that gate app import-time and lifespan behavior (JOB_STORE_PATH,
API_KEY) must be set BEFORE `coding_agent_bench.api` is imported, since
`job_store = JobStore(db_path)` runs at module import time. NEBIUS_ENABLED is
left unset so lifespan startup does not require Nebius credentials or
network access.
"""

import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="cab-openrouter-api-test-")
os.environ["JOB_STORE_PATH"] = os.path.join(_tmp_dir, "jobs.db")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.pop("OPENROUTER_API_KEY", None)
os.environ.pop("NEBIUS_ENABLED", None)

import pytest
from fastapi.testclient import TestClient  # noqa: E402

from coding_agent_bench.api import CreateJobRequest, app, build_cli_command  # noqa: E402
from coding_agent_bench.providers import ModelProvider  # noqa: E402

HEADERS = {"X-API-Key": os.environ["API_KEY"]}


def test_openai_cli_command_uses_provider_without_server_url():
    request = CreateJobRequest(
        job_name="openai-test",
        agent="codex",
        dataset="some-dataset",
        model_name="gpt-5",
        model_provider=ModelProvider.OPENAI,
    )
    command = build_cli_command(request)
    assert command[command.index("--model-provider") + 1] == "openai"
    assert "--server-url" not in command


def test_openrouter_cli_command_uses_provider_without_server_url():
    request = CreateJobRequest(
        job_name="openrouter-test",
        agent="codex",
        dataset="some-dataset",
        model_name="openai/gpt-5",
        model_provider=ModelProvider.OPENROUTER,
    )
    command = build_cli_command(request)
    assert command[command.index("--model-provider") + 1] == "openrouter"
    assert "--server-url" not in command


@pytest.fixture(scope="module")
def client():
    # Module-scoped: api.py keeps its job queue/worker state (including a
    # module-level asyncio.Event) as globals set up once at import time.
    # Entering/exiting the TestClient's lifespan context more than once binds
    # that Event to a second, different event loop and raises
    # "Event object is bound to a different event loop" on teardown. A single
    # TestClient for the whole module avoids that.
    with TestClient(app) as c:
        yield c


def test_create_job_openrouter_unsupported_agent_returns_400(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    resp = client.post(
        "/jobs",
        headers=HEADERS,
        json={
            "job_name": "test-oracle-openrouter",
            "agent": "oracle",
            "dataset": "some-dataset",
            "model_name": "openai/gpt-4o",
            "model_provider": "openrouter",
        },
    )
    assert resp.status_code == 400, resp.text
    assert "openrouter" in resp.text.lower()


def test_create_job_openrouter_missing_key_returns_400(client, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    resp = client.post(
        "/jobs",
        headers=HEADERS,
        json={
            "job_name": "test-openrouter-missing-key",
            "agent": "codex",
            "dataset": "some-dataset",
            "model_name": "openai/gpt-4o",
            "model_provider": "openrouter",
        },
    )
    assert resp.status_code == 400, resp.text
    assert "OPENROUTER_API_KEY" in resp.text


def test_resume_openrouter_job_is_allowed(client, monkeypatch):
    # Resuming an OpenRouter job restores its explicit provider and key.
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    from coding_agent_bench.api import JobStatus, job_store

    job_id = "resume-openrouter-test"
    job_store.insert(
        job_id, "or-job", "codex", "some-dataset", "openai/gpt-4o",
        ModelProvider.OPENROUTER, "", ["sh", "-c", "echo hi"],
    )
    job_store.update_status(job_id, JobStatus.COMPLETED)

    resp = client.post(f"/jobs/{job_id}/resume", headers=HEADERS)
    assert resp.status_code == 200, resp.text
    assert "not supported" not in resp.text.lower()
