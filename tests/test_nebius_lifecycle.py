"""Public lifecycle boundaries, readiness deadlines, and operator reconciliation."""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from coding_agent_bench import api, nebius_utils
from coding_agent_bench.nebius_utils import NebiusCommandError, NebiusInstanceManager, PoolPhase, ProvisioningRecord
from tests.test_nebius_pool_guard import enqueue, due
from tests.test_nebius_pool_guard import guarded as guarded


@pytest.mark.parametrize("operation,successful,known", [
    ("create", True, True), ("start", True, True), ("stop", True, True),
    ("delete", True, False), ("start", False, True),
])
def test_persisted_transition_retains_cleanup_knowledge(tmp_path, operation, successful, known):
    store = api.JobStore(tmp_path / "state.db")
    assert store.claim_nebius_guard("A")
    store.update_nebius_guard("A", PoolPhase.CONFIRMED, "observe")
    store.update_nebius_guard("A", PoolPhase.REQUEST_PENDING, operation)
    store.update_nebius_guard("A", PoolPhase.CONFIRMED if successful else PoolPhase.REJECTED, operation)
    record = ProvisioningRecord.from_row(store.nebius_guard())
    assert record.vm_known is known
    reopened = api.JobStore(store._db_path)
    assert reopened.nebius_guard() == store.nebius_guard()


def test_invalid_transition_cannot_corrupt_durable_owner(tmp_path):
    store = api.JobStore(tmp_path / "state.db")
    store.claim_nebius_guard("A")
    before = store.nebius_guard()
    with pytest.raises(ValueError):
        store.update_nebius_guard("A", "arbitrary-state", "create")
    assert store.nebius_guard() == before
    assert store.claim_nebius_guard("B") is False


@pytest.mark.parametrize("owner,deadline,status,expected,delay", [
    (None, 200, "queued", 0, 0),  # Another due job overtakes a capacity waiter.
    ("A", 200, "queued", None, 100),
    ("A", 90, "queued", 1, 0),
    ("A", 200, "cancelling", None, 100),
    ("A", 90, "cancelling", 1, 0),
    (None, 200, "cancelling", 0, 0),
])
def test_dispatch_policy_is_independent_of_endpoint_hardware(owner, deadline, status, expected, delay):
    rows = [
        {"job_id": "external", "status": "queued", "nebius_retry_at": 0},
        {"job_id": "A", "status": status, "nebius_retry_at": deadline},
    ]
    guard = {"job_id": owner} if owner else None
    assert api._next_dispatch(rows, guard, 100) == (expected, delay)


@pytest.mark.parametrize("phase", ["stop_old_model", "start_new_model"])
def test_model_readiness_timeout_cancels_task_then_cleans_owned_vm(guarded, monkeypatch, phase):
    store, manager, pool, ran = guarded
    manager.lost["start"] = False
    cancelled = []

    async def hang(self, *args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(phase)

    # Clients are shallow project-scoped copies, so patch their class methods.
    monkeypatch.setattr(type(manager), "stop_model" if phase == "stop_old_model" else "start_model", hang)
    monkeypatch.setattr(api, "NEBIUS_MODEL_START_TIMEOUT_SECONDS", 0.01)
    first = enqueue(store, "A", "nebius-h200")
    asyncio.run(api._process_queued_job(first))
    assert cancelled == [phase]
    assert ran == []
    assert store.get("A")["status"] == "failing"
    assert "startup/readiness exceeded" in store.get("A")["error"]
    assert len(manager.cloud) == 1
    assert store.nebius_guard()["job_id"] == "A"
    due(store, "A")
    first.adopt_existing = True
    asyncio.run(api._process_queued_job(first))
    assert store.get("A")["status"] == "failed"
    assert store.nebius_guard() is None
    assert not manager.cloud


@pytest.mark.parametrize("streaming", [False, True])
def test_readiness_deadline_kills_ssh_subprocess(monkeypatch, streaming):
    manager = object.__new__(NebiusInstanceManager)

    async def scenario():
        class Process:
            returncode = None
            killed = False

            @property
            def stdout(self):
                return self

            def __aiter__(self):
                return self

            async def __anext__(self):
                await asyncio.Event().wait()

            async def communicate(self):
                if not self.killed:
                    await asyncio.Event().wait()
                return b"", b""

            def kill(self):
                self.killed = True
                self.returncode = -9

        process = Process()
        monkeypatch.setattr(nebius_utils.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.01):
                if streaming:
                    await manager._ssh_stream(["ssh", "test-only"], "Available routes")
                else:
                    await manager._ssh_run(["ssh", "test-only"])
        assert process.killed

    asyncio.run(scenario())


def test_read_only_cli_does_not_change_guard(tmp_path, monkeypatch):
    store = api.JobStore(tmp_path / "state.db")
    store.claim_nebius_guard("A")
    manager = object.__new__(NebiusInstanceManager)
    manager.set_mutation_observer(lambda phase, operation: store.update_nebius_guard("A", phase, operation))
    process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(b"{}", b"")))
    monkeypatch.setattr(nebius_utils.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    before = store.nebius_guard()
    asyncio.run(manager.exec(["compute", "instance", "get-by-name", "--name", "vm"]))
    assert store.nebius_guard() == before


def test_explicit_mutation_rejection_settles_without_forgetting_owner(tmp_path, monkeypatch):
    store = api.JobStore(tmp_path / "state.db")
    store.claim_nebius_guard("A")
    manager = object.__new__(NebiusInstanceManager)
    manager.set_mutation_observer(lambda phase, operation: store.update_nebius_guard("A", phase, operation))
    monkeypatch.setattr(manager, "exec", AsyncMock(side_effect=NebiusCommandError([], 1, "", "PermissionDenied")))
    with pytest.raises(NebiusCommandError):
        asyncio.run(manager.mutate_instance("start", ["compute", "instance", "start"]))
    assert store.nebius_guard()["state"] == "rejected"
    assert store.nebius_guard()["job_id"] == "A"


def test_explicit_mutation_cancellation_keeps_durable_pending_state(tmp_path, monkeypatch):
    store = api.JobStore(tmp_path / "state.db")
    store.claim_nebius_guard("A")
    manager = object.__new__(NebiusInstanceManager)
    manager.set_mutation_observer(lambda phase, operation: store.update_nebius_guard("A", phase, operation))

    async def scenario():
        started = asyncio.Event()

        async def hang(args):
            assert store.nebius_guard()["state"] == "inflight"
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(manager, "exec", hang)
        task = asyncio.create_task(manager.mutate_instance("create", ["compute", "instance", "create"]))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert api.JobStore(store._db_path).nebius_guard()["state"] == "inflight"


@pytest.mark.parametrize("process_started", [False, True])
def test_local_launch_error_and_later_pipe_error_have_different_outcomes(tmp_path, monkeypatch, process_started):
    store = api.JobStore(tmp_path / "state.db")
    store.claim_nebius_guard("A")
    manager = object.__new__(NebiusInstanceManager)
    manager.set_mutation_observer(lambda phase, operation: store.update_nebius_guard("A", phase, operation))
    if process_started:
        process = SimpleNamespace(returncode=1, communicate=AsyncMock(side_effect=OSError("pipe read failed")))
        spawn = AsyncMock(return_value=process)
    else:
        spawn = AsyncMock(side_effect=FileNotFoundError("no CLI"))
    monkeypatch.setattr(nebius_utils.asyncio, "create_subprocess_exec", spawn)
    expected = OSError if process_started else nebius_utils.NebiusCommandNotStarted
    with pytest.raises(expected):
        asyncio.run(manager.mutate_instance("create", ["compute", "instance", "create"]))
    assert store.nebius_guard()["state"] == ("inflight" if process_started else "rejected")


def test_operator_inspection_and_retry_are_authenticated_and_do_not_unlock(guarded, monkeypatch):
    store, manager, _, _ = guarded
    first = enqueue(store, "A", "nebius-h200")
    asyncio.run(api._process_queued_job(first))
    monkeypatch.setenv("API_KEY", "test-secret")
    # No context manager: do not start background workers or Nebius on test startup.
    client = TestClient(api.app)
    assert client.get("/nebius/pool").status_code in (401, 403)
    assert client.post("/nebius/pool/reconcile/A").status_code in (401, 403)
    headers = {"X-API-Key": "test-secret"}
    before = list(manager.events)
    response = client.get("/nebius/pool", headers=headers)
    assert response.status_code == 200
    assert response.json()["blocked"] is True
    assert response.json()["owner_job_id"] == "A"
    assert response.json()["location"] == json.loads(store.nebius_guard()["location"])
    assert "command" not in response.text
    assert client.post("/nebius/pool/reconcile/B", headers=headers).status_code == 409
    assert client.post("/nebius/pool/reconcile/A", headers=headers).status_code == 200
    assert client.post("/nebius/pool/reconcile/A", headers=headers).status_code == 200
    assert len([item for item in api._job_queue if item.job_id == "A"]) == 1
    assert store.get("A")["nebius_retry_at"] == 0
    assert store.nebius_guard()["job_id"] == "A"
    assert manager.events == before  # endpoint schedules; it never mutates cloud resources.
    monkeypatch.setattr(api, "_active_job", ("A", None))
    assert client.post("/nebius/pool/reconcile/A", headers=headers).status_code == 409


def test_operator_reconciliation_recovers_cancelled_owner_through_worker(guarded):
    store, manager, _, _ = guarded
    first = enqueue(store, "A", "nebius-h200")
    asyncio.run(api._process_queued_job(first))
    asyncio.run(api.delete_job("A"))
    store.wait_nebius_guard("A", "cleanup waiting")
    assert store.get("A")["nebius_retry_at"] > time.time()
    asyncio.run(api.request_nebius_reconciliation("A"))
    assert store.get("A")["nebius_retry_at"] == 0
    asyncio.run(api._process_queued_job(first))
    assert store.get("A")["status"] == "cancelled"
    assert not manager.cloud
    assert asyncio.run(api.get_nebius_pool())["blocked"] is False


@pytest.mark.parametrize("state,allowed", [("RUNNING", False), ("STARTING", False), ("STOPPED", True)])
def test_another_paused_vm_must_be_stopped_before_allocation(guarded, state, allowed):
    from tests.test_nebius_regions import seed_vm

    store, manager, pool, ran = guarded
    manager.lost["start"] = False
    enqueue(store, "paused-owner", "nebius-h200")
    selected = pool._named(manager.locations[0])
    seed_vm(manager, selected)
    manager.cloud[selected["project_id"], selected["instance_name"]]["status"]["state"] = state
    store.record_nebius_location("paused-owner", selected)
    store.update_status("paused-owner", api.JobStatus.PAUSED)
    fresh = enqueue(store, "fresh", "nebius-b200")
    asyncio.run(api._process_queued_job(fresh))
    if allowed:
        assert ran == ["fresh"]
        assert sum(vm["status"]["state"] == "RUNNING" for vm in manager.cloud.values()) == 1
    else:
        assert not ran
        assert store.get("fresh")["status"] == "queued"
        assert store.get("fresh")["nebius_retry_attempts"] == 0
        assert len(manager.cloud) == 1
