"""API-level negative tests for OpenRouter job creation.

These exercise the full FastAPI app via TestClient rather than just the unit
helpers in `providers.py` / `agents/configs.py`, to confirm `POST /jobs`
uses OpenRouter's hostname as an ordinary server URL.

Env vars that gate app import-time and lifespan behavior (JOB_STORE_PATH,
API_KEY) must be set BEFORE `coding_agent_bench.api` is imported, since
`job_store = JobStore(db_path)` runs at module import time. NEBIUS_ENABLED is
left unset so lifespan startup does not require Nebius credentials or
network access.
"""

import os
import tempfile
import json

_tmp_dir = tempfile.mkdtemp(prefix="cab-openrouter-api-test-")
os.environ["JOB_STORE_PATH"] = os.path.join(_tmp_dir, "jobs.db")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.pop("NEBIUS_ENABLED", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from coding_agent_bench.api import app  # noqa: E402

HEADERS = {"X-API-Key": os.environ["API_KEY"]}


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


def test_create_job_openrouter_uses_hostname(client):
    resp = client.post(
        "/jobs",
        headers={**HEADERS, "X-Model-API-Key": "sk-or-test"},
        json={
            "job_name": "test-oracle-openrouter",
            "agent": "codex",
            "dataset": "some-dataset",
            "model_name": "openai/gpt-4o",
            "server_url": "https://openrouter.ai/api",
        },
    )
    assert resp.status_code == 200, resp.text


def test_create_job_rejects_the_removed_openrouter_sentinel(client):
    resp = client.post(
        "/jobs",
        headers=HEADERS,
        json={
            "job_name": "test-openrouter-missing-key",
            "agent": "codex",
            "dataset": "some-dataset",
            "model_name": "openai/gpt-4o",
            "server_url": "openrouter",
        },
    )
    assert resp.status_code == 400, resp.text
    assert "https" in resp.text.lower()


def test_resume_openrouter_job_is_allowed(client):
    # Resuming an OpenRouter job uses the same URL rewrite path as other
    # explicitly configured endpoints.
    from coding_agent_bench.api import JobStatus, job_store

    job_id = "resume-openrouter-test"
    job_store.insert(
        job_id, "or-job", "codex", "some-dataset", "openai/gpt-4o",
        "https://openrouter.ai/api", ["sh", "-c", "echo hi"],
    )
    job_store.update_status(job_id, JobStatus.COMPLETED)

    resp = client.post(f"/jobs/{job_id}/resume", headers={**HEADERS, "X-Model-API-Key": "sk-or-test"})
    assert resp.status_code == 200, resp.text
    assert "not supported" not in resp.text.lower()
    row = job_store.get(resp.json()["job_id"])
    assert row["model_api_key_required"] == 1
    assert "sk-or-test" not in json.dumps(row)
