"""Capacity-starved intake retries without losing jobs or blocking the worker."""

import asyncio
import sqlite3
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from coding_agent_bench import api, nebius_utils
from coding_agent_bench.nebius_utils import (
    NebiusCapacityError, NebiusCommandError, NebiusCommandTimeout, NebiusInstanceManager,
)


def capacity_error():
    return NebiusCapacityError(["compute", "v1", "instance", "create"], 1, "", "Not enough resources")


@pytest.fixture
def store(tmp_path, monkeypatch):
    database = api.JobStore(tmp_path / "queue.db")
    monkeypatch.setattr(api, "job_store", database)
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_job_event", asyncio.Event())
    monkeypatch.setattr(api, "_active_job", None)
    monkeypatch.setattr(api, "_shutting_down", False)
    monkeypatch.setattr(api, "NEBIUS_CAPACITY_RETRY_SECONDS", 60)
    return database


def enqueue(store, job_id="waiting", server="nebius-h200", token=None):
    command = ["coding-agent-bench", "run", "--server-url", server]
    store.insert(job_id, job_id, "opencode", "org/bench", "model", server, command,
                 github_token_required=token is not None)
    queued = api.QueuedJob(job_id, command, server, "model", github_token=token)
    api._job_queue.append(queued)
    return queued


class FakeNebius:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def get_instance_states(self):
        return []

    async def acquire_instance(self, *args, **kwargs):
        self.calls.append(time.time())
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return "worker-0", "http://203.0.113.1:8000"

    async def mark_job_started(self, _name):
        pass

    async def mark_job_completed(self, _name):
        pass


@pytest.mark.parametrize("failure", [capacity_error(), NebiusCommandTimeout("timed out")])
def test_transient_allocation_failure_stays_queued_with_durable_retry(store, monkeypatch, failure):
    queued = enqueue(store)
    neb = FakeNebius([failure])
    monkeypatch.setattr(api, "_nebius", neb)
    run = AsyncMock()
    monkeypatch.setattr(api, "_run_job", run)
    start = time.time()
    asyncio.run(api._process_queued_job(queued))
    row = store.get(queued.job_id)
    assert row["status"] == "queued"
    assert row["nebius_retry_at"] >= start + 60
    assert row["nebius_retry_attempts"] == 1
    assert "Waiting for Nebius" in row["error"]
    assert "retrying in 60s" in row["error"]
    run.assert_not_awaited()

    # A duplicate dispatcher visit must not trigger an early allocation.
    asyncio.run(api._process_queued_job(queued))
    assert len(neb.calls) == 1
    restored = api.JobStore(store._db_path).get(queued.job_id)
    assert restored["nebius_retry_at"] == row["nebius_retry_at"]


@pytest.mark.parametrize("message", ["quota exceeded", "permission denied", "invalid model configuration"])
def test_permanent_provisioning_errors_fail_instead_of_retrying(store, monkeypatch, message):
    queued = enqueue(store)
    monkeypatch.setattr(api, "_nebius", FakeNebius([RuntimeError(message)]))
    asyncio.run(api._process_queued_job(queued))
    row = store.get(queued.job_id)
    assert row["status"] == "failed"
    assert message in row["error"]
    assert row["nebius_retry_at"] == 0


def test_capacity_wait_is_not_limited_by_preemption_resume_budget(store, monkeypatch):
    queued = enqueue(store)
    neb = FakeNebius([capacity_error() for _ in range(5)] + [True])
    monkeypatch.setattr(api, "_nebius", neb)
    monkeypatch.setattr(api, "MAX_PREEMPT_RESUMES", 3)
    monkeypatch.setattr(api, "_run_job", AsyncMock())
    clock = [time.time()]
    monkeypatch.setattr(api.time, "time", lambda: clock[0])
    for _ in range(5):
        asyncio.run(api._process_queued_job(queued))
        assert store.get(queued.job_id)["status"] == "queued"
        clock[0] += 61
    asyncio.run(api._process_queued_job(queued))
    row = store.get(queued.job_id)
    assert row["nebius_retry_attempts"] == 5
    assert row["preempt_attempts"] == 0
    assert row["nebius_retry_at"] == 0
    assert row["error"] is None
    api._run_job.assert_awaited_once()


def test_worker_allows_other_jobs_and_keeps_token_until_retry_succeeds(store, monkeypatch):
    token = SecretStr("volatile-token-never-save")
    waiting = enqueue(store, token=token)
    enqueue(store, "external", "https://external.example")
    neb = FakeNebius([capacity_error(), True])
    monkeypatch.setattr(api, "_nebius", neb)
    monkeypatch.setattr(api, "NEBIUS_CAPACITY_RETRY_SECONDS", 0.02)
    ran = []

    async def scenario():
        done = asyncio.Event()

        async def run(job_id, *args, **kwargs):
            ran.append(job_id)
            if job_id == "external":
                assert waiting.github_token is token
                assert store.get("waiting")["status"] == "queued"
            else:
                assert waiting.github_token is token
                assert store.get(job_id)["nebius_retry_at"] == 0
                assert store.get(job_id)["error"] is None
            store.update_status(job_id, api.JobStatus.COMPLETED)
            if job_id == "waiting":
                done.set()

        monkeypatch.setattr(api, "_run_job", run)
        api._job_event.set()
        worker = asyncio.create_task(api._worker())
        try:
            await asyncio.wait_for(done.wait(), 2)
        finally:
            monkeypatch.setattr(api, "_shutting_down", True)
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(scenario())
    assert ran == ["external", "waiting"]
    assert len(neb.calls) == 2
    assert neb.calls[1] - neb.calls[0] >= 0.02
    assert waiting.github_token is None
    assert b"volatile-token-never-save" not in store._db_path.read_bytes()


def test_cancel_waiting_job_drops_token_and_prevents_more_allocation(store, monkeypatch):
    queued = enqueue(store, token=SecretStr("private-token"))
    neb = FakeNebius([capacity_error()])
    monkeypatch.setattr(api, "_nebius", neb)
    asyncio.run(api._process_queued_job(queued))
    asyncio.run(api.delete_job(queued.job_id))
    assert store.get(queued.job_id)["status"] == "cancelled"
    assert api._job_queue == []
    assert queued.github_token is None
    assert len(neb.calls) == 1
    assert store.get(queued.job_id)["nebius_retry_at"] == 0


def test_new_enqueue_interrupts_capacity_timer_without_retrying_waiter_early(store, monkeypatch):
    queued = enqueue(store)
    neb = FakeNebius([capacity_error()])
    monkeypatch.setattr(api, "_nebius", neb)

    async def scenario():
        attempted, external_done = asyncio.Event(), asyncio.Event()
        acquire = neb.acquire_instance

        async def signal_attempt(*args, **kwargs):
            attempted.set()
            return await acquire(*args, **kwargs)

        neb.acquire_instance = signal_attempt

        async def run(job_id, *args, **kwargs):
            assert job_id == "external"
            store.update_status(job_id, api.JobStatus.COMPLETED)
            external_done.set()

        monkeypatch.setattr(api, "_run_job", run)
        api._job_event.set()
        worker = asyncio.create_task(api._worker())
        try:
            await asyncio.wait_for(attempted.wait(), 1)
            enqueue(store, "external", "https://external.example")
            api._job_event.set()
            await asyncio.wait_for(external_done.wait(), 1)
            assert len(neb.calls) == 1
            assert store.get(queued.job_id)["status"] == "queued"
            assert len([item for item in api._job_queue if item.job_id == queued.job_id]) == 1
        finally:
            monkeypatch.setattr(api, "_shutting_down", True)
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(scenario())


def test_capacity_error_cannot_resurrect_concurrently_cancelled_job(store, monkeypatch):
    queued = enqueue(store)

    async def acquire(*args, **kwargs):
        store.update_status(queued.job_id, api.JobStatus.CANCELLED)
        raise capacity_error()

    monkeypatch.setattr(api, "_nebius", SimpleNamespace(acquire_instance=acquire))
    asyncio.run(api._process_queued_job(queued))
    assert store.get(queued.job_id)["status"] == "cancelled"
    assert store.get(queued.job_id)["nebius_retry_attempts"] == 0


def test_restart_restores_capacity_wait_without_allocation_before_due(store, monkeypatch):
    queued = enqueue(store)
    store.defer_nebius(queued.job_id, time.time() + 600, "Waiting for Nebius capacity")
    monkeypatch.setattr(api, "_nebius", FakeNebius([]))
    assert asyncio.run(api._restore_jobs()) is True
    assert len(api._job_queue) == 1
    restored = api._job_queue[0]
    assert restored.job_id == queued.job_id
    asyncio.run(api._process_queued_job(restored))
    assert api._nebius.calls == []
    assert store.get(queued.job_id)["status"] == "queued"


def test_due_capacity_wait_can_start_after_queue_service_restart(store, monkeypatch):
    queued = enqueue(store)
    store.defer_nebius(queued.job_id, time.time() - 1, "Waiting for Nebius capacity")
    monkeypatch.setattr(api, "_nebius", FakeNebius([True]))
    monkeypatch.setattr(api.OpenshiftJob, "_get_job", AsyncMock(return_value=None))
    run = AsyncMock()
    monkeypatch.setattr(api, "_run_job", run)
    asyncio.run(api._restore_jobs())
    asyncio.run(api._process_queued_job(api._job_queue[0]))
    run.assert_awaited_once()
    assert run.call_args.kwargs["adopt_existing"] is False
    assert store.get(queued.job_id)["nebius_retry_at"] == 0
    assert store.get(queued.job_id)["error"] is None


def test_active_provisioning_can_be_cancelled_without_scheduling_retry(store, monkeypatch):
    queued = enqueue(store, token=SecretStr("private-token"))

    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def acquire(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()

        async def finish(job_id, *args, **kwargs):
            store.update_status(job_id, api.JobStatus.CANCELLED)
            cancelled.set()
            return True

        monkeypatch.setattr(api, "_nebius", SimpleNamespace(
            get_instance_states=lambda: [], acquire_instance=acquire,
        ))
        monkeypatch.setattr(api, "_delete_recovered_nebius", AsyncMock())
        monkeypatch.setattr(api, "_finish_cancellation", finish)
        api._job_event.set()
        worker = asyncio.create_task(api._worker())
        try:
            await asyncio.wait_for(started.wait(), 1)
            await api.delete_job(queued.job_id)
            await asyncio.wait_for(cancelled.wait(), 1)
        finally:
            monkeypatch.setattr(api, "_shutting_down", True)
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(scenario())
    assert store.get(queued.job_id)["status"] == "cancelled"
    assert store.get(queued.job_id)["nebius_retry_attempts"] == 0
    assert queued.github_token is None
    assert api._job_queue == []


def test_private_source_requires_fresh_token_if_capacity_wait_restarts(store, monkeypatch):
    queued = enqueue(store, token=SecretStr("private-token"))
    store.defer_nebius(queued.job_id, time.time() - 1, "Waiting for Nebius capacity")
    monkeypatch.setattr(api, "_nebius", FakeNebius([]))
    asyncio.run(api._restore_jobs())
    asyncio.run(api._process_queued_job(api._job_queue[0]))
    row = store.get(queued.job_id)
    assert row["status"] == "failed"
    assert "fresh GitHub token" in row["error"]
    assert api._nebius.calls == []


def test_old_store_schema_migrates_retry_fields(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY, job_name TEXT, agent TEXT, dataset TEXT, "
                     "model_name TEXT, command TEXT, status TEXT, error TEXT)")
        conn.execute("INSERT INTO jobs VALUES ('one', 'job', 'opencode', 'dataset', 'model', '[]', 'queued', NULL)")
    store = api.JobStore(path)
    row = store.get("one")
    assert row["nebius_retry_at"] == 0
    assert row["nebius_retry_attempts"] == 0
    assert api.JobResponse(**row).nebius_retry_at == 0


@pytest.mark.parametrize("output, operation, expected", [
    ("Not enough resources", "create", NebiusCapacityError),
    ("INSUFFICIENT_CAPACITY", "start", NebiusCapacityError),
    ("RESOURCE_EXHAUSTED: quota exceeded; not enough resources", "create", NebiusCommandError),
    ("RESOURCE_EXHAUSTED", "create", NebiusCommandError),
    ("permission denied: not enough resources", "create", NebiusCommandError),
    ("not enough resources", "get", NebiusCommandError),
])
def test_cli_classifies_only_explicit_allocation_shortages(monkeypatch, output, operation, expected):
    process = SimpleNamespace(returncode=1, communicate=AsyncMock(return_value=(b"", output.encode())))
    monkeypatch.setattr(nebius_utils.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    manager = object.__new__(NebiusInstanceManager)
    with pytest.raises(expected) as error:
        asyncio.run(manager.exec(["compute", "v1", "instance", operation]))
    assert type(error.value) is expected
    assert error.value.stderr == output


@pytest.mark.parametrize("cancel", [False, True])
def test_cli_timeout_and_cancellation_kill_and_drain_subprocess(monkeypatch, cancel):
    manager = object.__new__(NebiusInstanceManager)
    monkeypatch.setattr(nebius_utils, "NEBIUS_CLI_TIMEOUT_SECONDS", 0.01)

    async def scenario():
        entered = asyncio.Event()

        class Process:
            returncode = None
            killed = False

            async def communicate(self):
                if self.killed:
                    return b"", b""
                entered.set()
                await asyncio.Event().wait()

            def kill(self):
                self.killed = True
                self.returncode = -9

        process = Process()
        monkeypatch.setattr(nebius_utils.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        task = asyncio.create_task(manager.exec(["compute", "instance", "start"]))
        await entered.wait()
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else NebiusCommandTimeout):
            await task
        assert process.killed

    asyncio.run(scenario())


def test_partial_create_is_reconciled_without_recreating_matching_vm(monkeypatch):
    exists = False
    details = {"spec": {"resources": {"platform": "gpu-h200-sxm", "preset": "1gpu-16vcpu-200gb"}},
               "status": {"state": "STOPPED"}}

    async def create(*args):
        nonlocal exists
        exists = True
        raise NebiusCommandTimeout("response was lost after VM creation")

    async def instance_exists(*args):
        return exists

    manager = SimpleNamespace(
        instance_exists=instance_exists, create_instance=AsyncMock(side_effect=create),
        get_instance=AsyncMock(return_value=details), delete_instance=AsyncMock(),
        start_instance=AsyncMock(), stop_model=AsyncMock(), start_model=AsyncMock(),
        get_instance_ip_address=AsyncMock(return_value="203.0.113.1"),
    )
    orchestrator = api.NebiusOrchestrator(manager, "subnet", "worker", 600)
    with pytest.raises(NebiusCommandTimeout):
        asyncio.run(orchestrator.acquire_instance("model", "h200"))
    assert asyncio.run(orchestrator.acquire_instance("model", "h200")) == ("worker-0", "http://203.0.113.1:8000")
    assert manager.create_instance.await_count == 1
    manager.delete_instance.assert_not_awaited()
    manager.start_model.assert_awaited_once()


def test_instance_exists_does_not_treat_permission_errors_as_missing(monkeypatch):
    manager = object.__new__(NebiusInstanceManager)
    monkeypatch.setattr(manager, "get_instance", AsyncMock(side_effect=RuntimeError("permission denied")))
    with pytest.raises(RuntimeError, match="permission denied"):
        asyncio.run(manager.instance_exists("worker-0"))


def test_retry_reconciles_delete_that_finished_after_cli_timeout():
    exists = True

    async def delete(*args):
        nonlocal exists
        exists = False
        raise NebiusCommandTimeout("delete completed but response was lost")

    async def instance_exists(*args):
        return exists

    manager = SimpleNamespace(
        instance_exists=instance_exists, delete_instance=AsyncMock(side_effect=delete),
        create_instance=AsyncMock(), start_instance=AsyncMock(),
        stop_model=AsyncMock(), start_model=AsyncMock(),
        get_instance_ip_address=AsyncMock(return_value="203.0.113.1"),
    )
    orchestrator = api.NebiusOrchestrator(manager, "subnet", "worker", 600)
    orchestrator._instances["worker-0"] = api.NebiusInstanceState("worker-0", "h200")
    with pytest.raises(NebiusCommandTimeout):
        asyncio.run(orchestrator.acquire_instance("model", "b200"))
    assert asyncio.run(orchestrator.acquire_instance("model", "b200"))[0] == "worker-0"
    assert manager.delete_instance.await_count == 1
    assert manager.create_instance.await_count == 1
