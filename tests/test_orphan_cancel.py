"""Cancellation must distinguish an absent parent from checkpointing or API failure."""

import asyncio

from fastapi import HTTPException
import pytest

from coding_agent_bench import api


@pytest.fixture
def orphan(tmp_path, monkeypatch):
    store = api.JobStore(tmp_path / "jobs.db")
    store.insert("orphan", "benchmark", "codex", "dataset", "model", "nebius-h200", [])
    store.update_status("orphan", api.JobStatus.PAUSING)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_job_event", asyncio.Event())
    monkeypatch.setattr(api, "_nebius", None)
    monkeypatch.setattr(api, "CLEANUP_RETRY_INTERVAL_SECONDS", 0)

    class Job:
        existing = None
        inspected = 0
        deleted = 0

        async def _get_job(self):
            self.inspected += 1
            return self.existing

        async def _delete_job(self):
            self.deleted += 1

    job = Job()
    monkeypatch.setattr(api, "OpenshiftJob", lambda *_args, **_kwargs: job)
    return store, job


def test_orphan_cancellation_survives_restart_and_cleans_up(orphan, monkeypatch):
    store, job = orphan
    assert asyncio.run(api._pause_commit("orphan", job)) is False
    response = asyncio.run(api.delete_job("orphan"))
    assert response["message"] == "Job cancelling"
    assert store.get("orphan")["status"] == "cancelling"
    assert store.get("orphan")["pause_checkpointed"] == 0
    assert "checkpoint unconfirmed" in store.get("orphan")["error"]
    assert api._job_event.is_set()
    queued = api._job_queue[0]
    assert queued.adopt_existing
    # Repeated cancellation doesn't enqueue a second cleanup.
    asyncio.run(api.delete_job("orphan"))
    assert len(api._job_queue) == 1
    restarted = api.JobStore(store._db_path)
    assert [row["job_id"] for row in restarted.list_recoverable()] == ["orphan"]
    monkeypatch.setattr(api, "job_store", restarted)
    asyncio.run(api._process_queued_job(queued))
    assert restarted.get("orphan")["status"] == "cancelled"
    assert restarted.get("orphan")["pause_checkpointed"] == 0
    assert restarted.list_paused() == []
    assert job.deleted == 1


def test_failed_parent_can_be_cancelled_without_checkpoint(orphan):
    store, job = orphan
    job.existing = {
        "status": {"conditions": [{"type": "Failed", "status": "True"}]}
    }

    response = asyncio.run(api.delete_job("orphan"))

    assert response["message"] == "Job cancelling"
    assert store.get("orphan")["status"] == "cancelling"
    assert store.get("orphan")["pause_checkpointed"] == 0
    assert "terminally failed" in store.get("orphan")["error"]
    assert api._job_event.is_set()
    assert api._job_queue[0].adopt_existing


@pytest.mark.parametrize("checkpointed", [False, True])
def test_retained_or_checkpointed_parent_cannot_be_cancelled(orphan, checkpointed):
    store, job = orphan
    if checkpointed:
        store.mark_pause_checkpointed("orphan")
    else:
        job.existing = {"status": {"conditions": []}}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.delete_job("orphan"))
    assert exc.value.status_code == (409 if checkpointed else 400)
    assert store.get("orphan")["status"] == "pausing"
    assert job.deleted == 0
    assert api._job_queue == []


def test_parent_lookup_failure_does_not_allow_cancellation(orphan, monkeypatch):
    store, job = orphan

    async def unavailable():
        raise RuntimeError("OpenShift unreachable")

    monkeypatch.setattr(job, "_get_job", unavailable)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.delete_job("orphan"))
    assert exc.value.status_code == 503
    assert store.get("orphan")["status"] == "pausing"
    assert api._job_queue == []


@pytest.mark.parametrize("winner", ["checkpoint", "running", "paused"])
def test_cancellation_cannot_overwrite_checkpoint_or_state_race(orphan, monkeypatch, winner):
    store, job = orphan

    async def raced_lookup():
        if winner == "checkpoint":
            store.mark_pause_checkpointed("orphan")
        else:
            store.update_status("orphan", api.JobStatus(winner))
        return None

    monkeypatch.setattr(job, "_get_job", raced_lookup)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.delete_job("orphan"))
    assert exc.value.status_code == 409
    assert store.get("orphan")["status"] == ("pausing" if winner == "checkpoint" else winner)
    assert api._job_queue == []
