"""Uncertain provisioning is reconciled before any unrelated job starts."""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from coding_agent_bench import api, nebius_utils
from coding_agent_bench.nebius_utils import NebiusCommandTimeout, NebiusInstanceManager
from tests.test_nebius_regions import RegionalManager, regional, seed_vm


class LostStartReply(RegionalManager):
    def __init__(self):
        super().__init__()
        self.lost = {"start": True, "delete": False}

    async def get_instance(self, name):
        if (self._parent_id, name) not in self.cloud:
            raise RuntimeError("NotFound")
        return await super().get_instance(name)

    async def start_instance(self, name):
        notify = getattr(self, "_mutation_callback", None)
        if notify:
            notify("inflight", "start")
        await super().start_instance(name)
        if self._parent_id == "primary" and self.lost["start"]:
            self.lost["start"] = False
            raise NebiusCommandTimeout("VM is RUNNING, but its start response was lost")
        if notify:
            notify("settled", "start")

    async def delete_instance(self, name):
        notify = getattr(self, "_mutation_callback", None)
        if notify:
            notify("inflight", "delete")
        await super().delete_instance(name)
        if self.lost["delete"]:
            self.lost["delete"] = False
            raise NebiusCommandTimeout("VM is gone, but its deletion response was lost")
        if notify:
            notify("settled", "delete")


@pytest.fixture
def guarded(tmp_path, monkeypatch):
    store = api.JobStore(tmp_path / "guard.db")
    manager = LostStartReply()
    # A different GPU request must also be blocked by the same pool guard.
    original_discovery = manager.discover_locations

    async def discovery(gpu_config, *args):
        return [{**item, "gpu_config": gpu_config or "h200"}
                for item in await original_discovery(gpu_config, *args)]

    manager.discover_locations = discovery
    pool = regional(manager)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_nebius", pool)
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_job_event", asyncio.Event())
    monkeypatch.setattr(api, "_active_job", None)
    monkeypatch.setattr(api, "_shutting_down", False)
    monkeypatch.setattr(api, "CLEANUP_RETRY_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(api.OpenshiftJob, "_get_job", AsyncMock(return_value=None))
    monkeypatch.setattr(api.OpenshiftJob, "_delete_job", AsyncMock())
    ran = []

    async def run(job_id, *args, **kwargs):
        ran.append(job_id)
        store.update_status(job_id, api.JobStatus.COMPLETED)

    monkeypatch.setattr(api, "_run_job", run)
    return store, manager, pool, ran


def enqueue(store, name, endpoint):
    command = ["coding-agent-bench", "run"]
    store.insert(name, name, "opencode", "org/bench", "model", endpoint, command)
    queued = api.QueuedJob(name, command, endpoint, "model")
    api._job_queue.append(queued)
    return queued


def due(store, name):
    with store._connect() as conn:
        conn.execute("UPDATE jobs SET nebius_retry_at = 0 WHERE job_id = ?", (name,))


@pytest.mark.parametrize("mode", ["regional", "single"])
def test_lost_start_blocks_different_hardware_until_owner_runs(guarded, monkeypatch, mode):
    store, manager, pool, ran = guarded
    if mode == "single":
        monkeypatch.setattr(api, "_nebius", api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600))
    first = enqueue(store, "A", "nebius-h200")
    second = enqueue(store, "B", "nebius-b200")
    external = enqueue(store, "external", "https://external.example")
    asyncio.run(api._process_queued_job(first))
    assert store.nebius_guard()["job_id"] == "A"
    assert len(manager.cloud) == 1
    before = list(manager.events)
    asyncio.run(api._process_queued_job(second))
    assert manager.events == before
    assert store.get("B")["status"] == "queued"
    assert store.get("B")["nebius_retry_attempts"] == 0
    asyncio.run(api._process_queued_job(external))
    assert ran == []
    assert store.get("external")["status"] == "queued"
    assert store.get("external")["nebius_retry_attempts"] == 0
    due(store, "A")
    asyncio.run(api._process_queued_job(first))
    assert ran == ["A"]
    assert store.nebius_guard() is None
    assert manager.events.count(("create", "primary")) == 1
    asyncio.run(api._process_queued_job(external))
    assert ran == ["A", "external"]
    asyncio.run(api._process_queued_job(second))
    assert ran[-1] == "B"
    assert len(manager.cloud) == 1


def test_guard_survives_restart_and_reuses_the_confirmed_owner_vm(guarded, monkeypatch):
    store, manager, pool, ran = guarded
    first = enqueue(store, "A", "nebius-h200")
    enqueue(store, "B", "nebius-b200")
    asyncio.run(api._process_queued_job(first))
    original_guard = store.nebius_guard()
    reopened = api.JobStore(store._db_path)
    assert reopened.nebius_guard() == original_guard
    monkeypatch.setattr(api, "job_store", reopened)
    monkeypatch.setattr(api, "_nebius", regional(manager))
    asyncio.run(api._restore_jobs())
    due(reopened, "A")
    asyncio.run(api._process_queued_job(api._job_queue[0]))
    assert ran == ["A"]
    assert reopened.nebius_guard() is None
    assert len(manager.cloud) == 1
    assert manager.events.count(("create", "primary")) == 1


def test_cancel_keeps_guard_until_deletion_is_confirmed(guarded):
    store, manager, pool, ran = guarded
    first = enqueue(store, "A", "nebius-h200")
    second = enqueue(store, "B", "nebius-b200")
    asyncio.run(api._process_queued_job(first))
    manager.lost["delete"] = True
    asyncio.run(api.delete_job("A"))
    assert store.get("A")["status"] == "cancelling"
    asyncio.run(api._process_queued_job(first))
    assert manager.cloud == {}
    assert store.nebius_guard()["job_id"] == "A"
    before = list(manager.events)
    asyncio.run(api._process_queued_job(second))
    assert manager.events == before
    due(store, "A")
    asyncio.run(api._process_queued_job(first))
    assert store.nebius_guard() is None
    assert store.get("A")["status"] == "cancelled"
    asyncio.run(api._process_queued_job(second))
    assert ran == ["B"]
    assert len(manager.cloud) == 1


def test_unconfirmed_notfound_never_starts_a_second_create(guarded, monkeypatch):
    store, manager, pool, ran = guarded

    async def hidden_create(self, name, subnet, gpu_config):
        self.events.append(("create", self._parent_id))
        notify = getattr(self, "_mutation_callback", None)
        if notify:
            notify("inflight", "create")
        raise NebiusCommandTimeout("create is pending and not yet visible")

    monkeypatch.setattr(LostStartReply, "create_instance", hidden_create)
    first = enqueue(store, "A", "nebius-h200")
    second = enqueue(store, "B", "nebius-b200")
    asyncio.run(api._process_queued_job(first))
    for _ in range(2):
        due(store, "A")
        asyncio.run(api._process_queued_job(first))
        asyncio.run(api._process_queued_job(second))
    assert manager.events.count(("create", "primary")) == 1
    assert ("create", "secondary") not in manager.events
    assert store.nebius_guard()["job_id"] == "A"
    asyncio.run(api.delete_job("A"))
    asyncio.run(api._process_queued_job(first))
    assert store.get("A")["status"] == "cancelling"
    assert store.nebius_guard() is not None
    selected = json.loads(store.nebius_guard()["location"])
    seed_vm(manager, selected)
    due(store, "A")
    asyncio.run(api._process_queued_job(first))
    assert store.get("A")["status"] == "cancelled"
    assert store.nebius_guard() is None
    assert not manager.cloud


def test_idle_and_startup_cleanup_do_not_retire_unknown_request(guarded):
    store, manager, pool, _ = guarded
    first = enqueue(store, "A", "nebius-h200")
    asyncio.run(api._process_queued_job(first))
    selected = json.loads(store.nebius_guard()["location"])
    child = pool.provisioning_child(selected)
    child._instances[selected["instance_name"]].last_job_completed_at = time.time() - 9999
    before = list(manager.events)
    asyncio.run(child.cleanup_idle_instances())
    asyncio.run(api._delete_recovered_nebius("startup"))
    assert manager.events == before
    assert store.nebius_guard() is not None


def test_worker_prioritizes_reconciliation_over_external_work(guarded, monkeypatch):
    store, manager, _, ran = guarded
    first = enqueue(store, "A", "nebius-h200")
    monkeypatch.setattr(api, "NEBIUS_CAPACITY_RETRY_SECONDS", 0.02)
    asyncio.run(api._process_queued_job(first))
    enqueue(store, "external", "https://external.example")

    async def scenario():
        owner_running = asyncio.Event()
        finish_owner = asyncio.Event()
        external_finished = asyncio.Event()

        async def run(job_id, *args, **kwargs):
            ran.append(job_id)
            if job_id == "A":
                assert store.nebius_guard() is None
                store.update_status(job_id, api.JobStatus.RUNNING)
                owner_running.set()
                await finish_owner.wait()
            store.update_status(job_id, api.JobStatus.COMPLETED)
            if job_id == "external":
                external_finished.set()

        monkeypatch.setattr(api, "_run_job", run)
        api._job_event.set()
        task = asyncio.create_task(api._worker())
        try:
            await asyncio.wait_for(owner_running.wait(), 1)
            assert ran == ["A"]
            assert store.get("external")["status"] == "queued"
            finish_owner.set()
            await asyncio.wait_for(external_finished.wait(), 1)
        finally:
            monkeypatch.setattr(api, "_shutting_down", True)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(scenario())
    assert ran == ["A", "external"]
    assert manager.events.count(("create", "primary")) == 1
    assert store.get("external")["nebius_retry_attempts"] == 0


def test_guard_claim_is_atomic_between_jobs(tmp_path):
    store = api.JobStore(tmp_path / "claims.db")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(store.claim_nebius_guard, ["A", "B"]))
    assert results.count(True) == 1
    assert store.nebius_guard()["job_id"] in ("A", "B")


def test_mutating_cli_transport_error_keeps_request_unsettled(tmp_path, monkeypatch):
    store = api.JobStore(tmp_path / "request.db")
    store.claim_nebius_guard("A")
    manager = object.__new__(NebiusInstanceManager)
    manager.set_mutation_observer(lambda state, operation: store.update_nebius_guard("A", state, operation))
    process = SimpleNamespace(returncode=1, communicate=AsyncMock(return_value=(b"", b"rpc error: DeadlineExceeded")))

    async def create(*args, **kwargs):
        assert store.nebius_guard()["state"] == "inflight"
        return process

    monkeypatch.setattr(nebius_utils.asyncio, "create_subprocess_exec", create)
    with pytest.raises(NebiusCommandTimeout):
        asyncio.run(manager.mutate_instance("create", ["compute", "v1", "instance", "create"]))
    assert store.nebius_guard()["state"] == "inflight"
    assert store.nebius_guard()["operation"] == "create"


def test_lost_preemption_restart_reply_also_holds_shared_pool(guarded, monkeypatch):
    store, manager, pool, ran = guarded
    first = enqueue(store, "A", "nebius-h200")
    second = enqueue(store, "B", "nebius-b200")
    selected = pool._named(manager.locations[0])
    seed_vm(manager, selected)
    store.record_nebius_location("A", selected)
    store.update_status("A", api.JobStatus.PAUSED)
    asyncio.run(api._process_queued_job(first))
    assert store.get("A")["status"] == "paused"
    assert store.nebius_guard()["job_id"] == "A"
    assert manager.events.count(("start", "primary")) == 1
    before = list(manager.events)
    asyncio.run(api._process_queued_job(second))
    assert manager.events == before
    monkeypatch.setattr(pool.provisioning_child(selected), "recover_stopped_instance", AsyncMock())
    due(store, "A")
    asyncio.run(api._process_queued_job(first))
    assert ran == ["A"]
    assert store.nebius_guard() is None
    assert len(manager.cloud) == 1


def test_cancelled_unknown_request_is_restored_for_cleanup_after_restart(guarded, monkeypatch):
    store, manager, _, _ = guarded
    first = enqueue(store, "A", "nebius-h200")
    asyncio.run(api._process_queued_job(first))
    asyncio.run(api.delete_job("A"))
    reopened = api.JobStore(store._db_path)
    monkeypatch.setattr(api, "job_store", reopened)
    monkeypatch.setattr(api, "_nebius", regional(manager))
    asyncio.run(api._restore_jobs())
    queued = next(item for item in api._job_queue if item.job_id == "A")
    asyncio.run(api._process_queued_job(queued))
    assert reopened.get("A")["status"] == "cancelled"
    assert reopened.nebius_guard() is None
    assert not manager.cloud


def test_terminal_guard_owner_is_recovered_not_forgotten(guarded):
    store, _, _, _ = guarded
    first = enqueue(store, "A", "nebius-h200")
    asyncio.run(api._process_queued_job(first))
    store.update_status("A", api.JobStatus.FAILED, error="interrupted cleanup")
    asyncio.run(api._restore_jobs())
    assert store.get("A")["status"] == "failing"
    assert any(item.job_id == "A" for item in api._job_queue)
    assert store.nebius_guard()["job_id"] == "A"


@pytest.mark.parametrize("restart", [False, True])
def test_different_hardware_cleans_idle_vm_outside_its_eligible_regions(guarded, monkeypatch, restart):
    store, manager, pool, ran = guarded
    manager.lost["start"] = False
    first = enqueue(store, "A", "nebius-h200")
    second = enqueue(store, "B", "nebius-b200")
    asyncio.run(api._process_queued_job(first))
    assert store.nebius_guard() is None
    assert store.last_nebius_location()["project_id"] == "primary"
    if restart:
        monkeypatch.setattr(api, "_nebius", regional(manager))
    # The B200 job cannot use A's H200 region, but must not leave A's idle VM
    # running there while allocating another VM in its own eligible region.
    manager.locations = [manager.locations[1]]
    manager.events.clear()
    asyncio.run(api._process_queued_job(second))
    assert ran == ["A", "B"]
    assert len(manager.cloud) == 1
    assert next(iter(manager.cloud))[0] == "secondary"
    assert manager.events.index(("delete", "primary")) < manager.events.index(("create", "secondary"))


def test_discovery_timeout_without_mutation_does_not_lock_the_pool(guarded, monkeypatch):
    store, manager, _, ran = guarded
    first = enqueue(store, "A", "nebius-h200")
    second = enqueue(store, "B", "nebius-b200")
    discovery = manager.discover_locations
    monkeypatch.setattr(manager, "discover_locations", AsyncMock(side_effect=NebiusCommandTimeout("read-only discovery timed out")))
    asyncio.run(api._process_queued_job(first))
    assert store.nebius_guard() is None
    assert manager.cloud == {}
    assert store.get("A")["status"] == "queued"
    monkeypatch.setattr(manager, "discover_locations", discovery)
    manager.lost["start"] = False
    asyncio.run(api._process_queued_job(second))
    assert ran == ["B"]


def test_single_region_config_change_does_not_probe_the_wrong_project(guarded, monkeypatch):
    store, manager, _, _ = guarded
    first = enqueue(store, "A", "nebius-h200")
    monkeypatch.setattr(api, "_nebius", api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600))
    asyncio.run(api._process_queued_job(first))
    before = list(manager.events)
    changed = manager.for_project("secondary")
    monkeypatch.setattr(api, "_nebius", api.NebiusOrchestrator(changed, "subnet-secondary", "queue", 600))
    due(store, "A")
    asyncio.run(api._process_queued_job(first))
    assert manager.events == before
    assert store.nebius_guard()["job_id"] == "A"
    assert "single-region configuration" in store.get("A")["error"]
