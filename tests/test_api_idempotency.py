"""Tests for queue request defaults and idempotent job creation."""

import asyncio
import socket
import sqlite3

import pytest

from coding_agent_bench import api


@pytest.fixture
def isolated_queue(tmp_path, monkeypatch):
    """Replace the process-global store and queue with isolated test state."""
    previous_store = api.job_store
    previous_queue = list(api._job_queue)
    api.job_store = api.JobStore(tmp_path / "jobs.db")
    api._job_queue.clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    try:
        yield
    finally:
        api.job_store = previous_store
        api._job_queue[:] = previous_queue


def _request(key: str = "intake-test-key") -> api.CreateJobRequest:
    """Build a minimal queue request suitable for an idempotency test."""
    return api.CreateJobRequest(
        job_name="intake-test",
        agent="codex",
        dataset="swe-bench/swe-bench-verified",
        model_name="Qwen/Qwen3-32B",
        server_url="openrouter",
        idempotency_key=key,
    )


def test_job_store_enforces_unique_idempotency_keys(tmp_path):
    """Reject two persisted jobs with the same idempotency key."""
    store = api.JobStore(tmp_path / "jobs.db")
    args = (
        "job-1",
        "name",
        "oracle",
        "dataset",
        "model",
        "openrouter",
        ["command"],
    )
    store.insert(*args, idempotency_key="same-key")
    with pytest.raises(sqlite3.IntegrityError):
        store.insert("job-2", *args[1:], idempotency_key="same-key")


def test_repeated_create_request_returns_original_job(isolated_queue):
    """Return the original job and enqueue it only once on a repeated request."""
    first = asyncio.run(api.create_job(_request()))
    second = asyncio.run(api.create_job(_request()))

    assert second.job_id == first.job_id
    assert second.message == "Job already exists."
    assert len(api._job_queue) == 1


def test_omitted_queue_defaults_are_not_sent_to_harbor(isolated_queue):
    """Leave concurrency unset while inferring a known model's context length."""
    request = _request(key="defaults")
    request.model_name = "RedHatAI/Qwen3.6-27B-FP8"
    command = api.build_cli_command(request)

    assert "--n-concurrent" not in command
    max_len_index = command.index("--model-max-len")
    assert command[max_len_index + 1] == "131072"


def test_create_accepts_an_unconfigured_server_host(isolated_queue, monkeypatch):
    """Allow public model hosts without restarting for configuration changes."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )
    request = _request(key="unapproved-host")
    request.server_url = "https://new-model.example.com"

    result = asyncio.run(api.create_job(request))

    assert result.job_id


def test_nebius_resource_tokens_are_case_insensitive():
    """Normalize managed-Nebius resource tokens before looking them up."""
    assert api._parse_nebius_url("nebius-H200") == "h200"
