"""Cross-path ownership checks enforce one running VM, including legacy recovery."""

import asyncio
from copy import deepcopy
import json

import pytest

from coding_agent_bench import api
from tests.test_nebius_pool_guard import due, enqueue, LostStartReply
from tests.test_nebius_pool_guard import guarded as guarded
from tests.test_nebius_regions import capacity, regional, seed_vm


def resume_owner(store, name, signal):
    """Create recovery metadata without a saved location, as in an older DB."""
    queued = enqueue(store, name, "nebius-h200")
    if signal == "resume":
        queued.command = ["bash", "-c", f"harbor jobs resume --path /app/jobs/{name}"]
        with store._connect() as conn:
            conn.execute("UPDATE jobs SET command = ? WHERE job_id = ?", (json.dumps(queued.command), name))
    elif signal == "checkpoint":
        with store._connect() as conn:
            conn.execute("UPDATE jobs SET pause_checkpointed = 1 WHERE job_id = ?", (name,))
    elif signal == "paused":
        store.update_status(name, api.JobStatus.PAUSED)
    return queued


@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("mode", ["single", "regional"])
@pytest.mark.parametrize("dispatch", ["allocate", "recover"])
@pytest.mark.parametrize("signal", ["resume", "checkpoint", "paused", "saved"])
@pytest.mark.parametrize("state", ["RUNNING", "STARTING", "STOPPED", "missing", "unreadable"])
def test_owner_state_checked_before_allocation_or_recovery(guarded, monkeypatch, restart, mode, dispatch, signal, state):
    store, manager, regional_pool, ran = guarded
    manager.lost["start"] = False
    pool = regional_pool if mode == "regional" else api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
    monkeypatch.setattr(api, "_nebius", pool)
    resume_owner(store, "A", signal)
    selected = (regional_pool._named(manager.locations[1]) if signal == "saved"
                else api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600).configured_location("h200"))
    if signal == "saved":
        store.record_nebius_location("A", selected)
    key = selected["project_id"], selected["instance_name"]
    if state != "missing":
        seed_vm(manager, selected)
        manager.cloud[key]["status"]["state"] = state if state != "unreadable" else "RUNNING"
    original_get = LostStartReply.get_instance

    async def get_instance(self, name):
        if state == "unreadable" and (self.project_id, name) == key:
            raise RuntimeError("Nebius API unavailable")
        return await original_get(self, name)

    monkeypatch.setattr(LostStartReply, "get_instance", get_instance)
    second = enqueue(store, "B", "nebius-h200" if dispatch == "recover" else "nebius-b200")
    if dispatch == "recover":
        target = regional_pool._named(manager.locations[0]) if mode == "regional" else pool.configured_location("h200")
        if (target["project_id"], target["instance_name"]) != key:
            seed_vm(manager, target)
        store.record_nebius_location("B", target)
        store.update_status("B", api.JobStatus.PAUSED)

        async def recover(self, name):
            # Exercise the actual provider mutation, without stabilization sleeps.
            await self._manager.start_instance(name)

        monkeypatch.setattr(api.NebiusOrchestrator, "recover_stopped_instance", recover)
    if restart:
        store = api.JobStore(store._db_path)
        monkeypatch.setattr(api, "job_store", store)
        pool = regional(manager) if mode == "regional" else api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
        monkeypatch.setattr(api, "_nebius", pool)
        asyncio.run(api._restore_jobs())
    before = deepcopy(manager.cloud)
    asyncio.run(api._process_queued_job(second))
    allowed = state in ("STOPPED", "missing") and (mode == "regional" or signal == "saved")
    if allowed:
        assert ran == ["B"]
    else:
        assert not ran
        assert store.get("B")["status"] == ("paused" if dispatch == "recover" else "queued")
        assert manager.cloud == before
        assert not any(event in ("create", "start", "delete") for event, _ in manager.events)
    assert sum(vm["status"]["state"] == "RUNNING" for vm in manager.cloud.values()) <= 1
    assert store.get("B")["nebius_retry_attempts"] == 0
    assert store.nebius_guard() is None
    if key in before:
        assert manager.cloud[key] == before[key]  # Never steal/delete A's retained VM.


@pytest.mark.parametrize("mode", ["single", "regional"])
@pytest.mark.parametrize("signal", ["resume", "checkpoint", "paused", "saved"])
@pytest.mark.parametrize("cleanup", ["startup", "terminal", "guarded"])
@pytest.mark.parametrize("restart", [False, True])
def test_cleanup_preserves_the_same_recovery_owners(guarded, monkeypatch, mode, signal, cleanup, restart):
    store, manager, regional_pool, _ = guarded
    pool = regional_pool if mode == "regional" else api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
    monkeypatch.setattr(api, "_nebius", pool)
    selected = (regional_pool._named(manager.locations[1]) if mode == "regional" and signal == "saved"
                else api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600).configured_location("h200"))
    resume_owner(store, "A", signal)
    if signal == "saved":
        store.record_nebius_location("A", selected)
    seed_vm(manager, selected)
    if cleanup != "startup":
        enqueue(store, "B", "nebius-h200")
        if cleanup == "guarded":
            store.claim_nebius_guard("B")
        store.record_nebius_location("B", selected)
        store.update_status("B", api.JobStatus.CANCELLING)
    if cleanup == "guarded":
        store.update_nebius_guard("B", "settled", "observe")
        store.update_nebius_guard("B", "inflight", "start")
    if restart:
        store = api.JobStore(store._db_path)
        monkeypatch.setattr(api, "job_store", store)
        pool = regional(manager) if mode == "regional" else api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
        monkeypatch.setattr(api, "_nebius", pool)
        asyncio.run(api._restore_jobs())
    asyncio.run(api._nebius_pool().cleanup("startup" if cleanup == "startup" else "B"))
    assert len(manager.cloud) == 1
    assert not any(event == "delete" for event, _ in manager.events)
    if cleanup == "guarded":
        assert store.nebius_guard()["job_id"] == "B"
        assert store.get("B")["status"] == "cancelling"


@pytest.mark.parametrize("mode", ["single", "regional"])
def test_cancellation_alone_never_authorizes_legacy_deletion(guarded, monkeypatch, mode):
    store, manager, pool, _ = guarded
    legacy = api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600).configured_location("h200")
    if mode == "single":
        monkeypatch.setattr(api, "_nebius", api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600))
    enqueue(store, "fresh", "nebius-h200")
    store.update_status("fresh", api.JobStatus.CANCELLING)
    seed_vm(manager, legacy)
    asyncio.run(api._nebius_pool().cleanup("fresh"))
    assert len(manager.cloud) == 1
    assert manager.events == []


@pytest.mark.parametrize("status", [api.JobStatus.QUEUED, api.JobStatus.PAUSED])
def test_single_region_config_change_cannot_replace_recovery_placement(guarded, monkeypatch, status):
    store, manager, regional_pool, ran = guarded
    first = enqueue(store, "A", "nebius-h200")
    selected = regional_pool._named(manager.locations[1])
    seed_vm(manager, selected)
    manager.cloud[selected["project_id"], selected["instance_name"]]["status"]["state"] = "RUNNING"
    store.record_nebius_location("A", selected)
    store.update_status("A", status)
    monkeypatch.setattr(api, "_nebius", api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600))
    asyncio.run(api._process_queued_job(first))
    assert not ran
    assert manager.events == []
    assert json.loads(store.get("A")["nebius_location"]) == selected
    assert store.nebius_guard() is None


def test_single_region_config_change_cannot_hide_completed_jobs_running_vm(guarded, monkeypatch):
    store, manager, pool, ran = guarded
    manager.lost["start"] = False
    first = enqueue(store, "A", "nebius-h200")
    asyncio.run(api._process_queued_job(first))
    assert ran == ["A"]
    previous = store.last_nebius_location()
    monkeypatch.setattr(api, "_nebius", api.NebiusOrchestrator(manager.for_project("secondary"), "subnet-secondary", "queue", 600))
    second = enqueue(store, "B", "nebius-h200")
    manager.events.clear()
    asyncio.run(api._process_queued_job(second))
    assert ran == ["A"]
    assert store.get("B")["status"] == "queued"
    assert store.last_nebius_location() == previous
    assert not any(event in ("create", "start", "delete") for event, _ in manager.events)
    assert len(manager.cloud) == 1


@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("mode", ["single", "regional"])
def test_confirmed_vacancy_does_not_reserve_legacy_vm(guarded, monkeypatch, restart, mode):
    store, manager, _, ran = guarded
    pool = regional(manager) if mode == "regional" else api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
    monkeypatch.setattr(api, "_nebius", pool)
    manager.locations = manager.locations[:1]
    first = resume_owner(store, "A", "resume")
    manager.failures["primary"].append(capacity())
    asyncio.run(api._process_queued_job(first))
    assert store.get("A")["nebius_vacant"]
    if restart:
        store = api.JobStore(store._db_path)
        monkeypatch.setattr(api, "job_store", store)
        pool = regional(manager) if mode == "regional" else api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
        monkeypatch.setattr(api, "_nebius", pool)
        asyncio.run(api._restore_jobs())
    legacy = api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600).configured_location("h200")
    seed_vm(manager, legacy)
    manager.cloud["primary", "queue-0"]["status"]["state"] = "RUNNING"
    manager.lost["start"] = False
    second = enqueue(store, "B", "nebius-h200")
    asyncio.run(api._process_queued_job(second))
    assert ran == ["B"]
    assert list(manager.cloud) == [("primary", "queue-0")]


@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("lost_delete,cancel", [(False, False), (True, False), (True, True)])
def test_recovery_retires_other_regions_idle_vm_first(guarded, monkeypatch, restart, lost_delete, cancel):
    store, manager, pool, ran = guarded
    manager.lost["start"] = False
    first = enqueue(store, "A", "nebius-h200")
    selected = pool._named(manager.locations[1])
    seed_vm(manager, selected)
    store.record_nebius_location("A", selected)
    store.update_status("A", api.JobStatus.PAUSED)
    second = enqueue(store, "B", "nebius-h200")
    asyncio.run(api._process_queued_job(second))
    assert ran == ["B"]
    idle = store.last_nebius_location()
    assert idle["project_id"] == "primary"
    if restart and not lost_delete:
        store = api.JobStore(store._db_path)
        monkeypatch.setattr(api, "job_store", store)
        pool = regional(manager)
        monkeypatch.setattr(api, "_nebius", pool)
        asyncio.run(api._restore_jobs())
    manager.events.clear()
    async def recover(self, name):
        assert not any(vm["status"]["state"] == "RUNNING" for vm in manager.cloud.values())
        await self._manager.start_instance(name)

    monkeypatch.setattr(api.NebiusOrchestrator, "recover_stopped_instance", recover)
    manager.lost["delete"] = lost_delete
    asyncio.run(api._process_queued_job(first))
    if lost_delete:
        assert store.get("A")["status"] == "paused"
        assert json.loads(store.get("A")["nebius_location"]) == selected
        assert json.loads(store.nebius_guard()["location"]) == idle
        assert not any(event == "start" for event, _ in manager.events)
        external = enqueue(store, "external", "https://example.com")
        asyncio.run(api._process_queued_job(external))
        assert ran == ["B"]
        if cancel:
            asyncio.run(api.delete_job("A"))
        if restart:
            store = api.JobStore(store._db_path)
            monkeypatch.setattr(api, "job_store", store)
            monkeypatch.setattr(api, "_nebius", regional(manager))
            asyncio.run(api._restore_jobs())
            first = next(item for item in api._job_queue if item.job_id == "A")
        due(store, "A")
        asyncio.run(api._process_queued_job(first))
    if cancel:
        assert ran == ["B"]
        assert store.get("A")["status"] == "cancelled"
        assert not manager.cloud
        assert not any(event == "start" for event, _ in manager.events)
    else:
        assert ran == ["B", "A"]
        assert len(manager.cloud) == 1
        assert manager.events.index(("delete", "primary")) < manager.events.index(("start", "secondary"))
    assert store.nebius_guard() is None
