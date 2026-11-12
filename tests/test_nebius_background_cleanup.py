"""Background deletion owns the same durable slot as benchmark provisioning."""

import asyncio
import json
import time

import pytest

from coding_agent_bench import api
from coding_agent_bench.nebius_utils import NebiusCommandTimeout
from tests.test_nebius_pool_guard import enqueue
from tests.test_nebius_pool_guard import guarded as guarded
from tests.test_nebius_regions import regional, seed_vm


def expired_vm(pool, manager, mode):
    if mode == "single":
        location = pool.configured_location("h200")
        child = pool
    else:
        location = pool._named(manager.locations[0])
        child = pool._child(location)
    seed_vm(manager, location)
    child._instances[location["instance_name"]] = api.NebiusInstanceState(
        location["instance_name"], "h200", last_job_completed_at=time.time() - 700,
    )
    return location


@pytest.mark.parametrize("mode", ["single", "regional"])
@pytest.mark.parametrize("outcome", ["timeout_before", "timeout_after", "cancelled"])
def test_background_delete_blocks_dispatch_and_recovers_after_restart(guarded, monkeypatch, mode, outcome):
    store, manager, pool, ran = guarded
    if mode == "single":
        pool = api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
        monkeypatch.setattr(api, "_nebius", pool)
    location = expired_vm(pool, manager, mode)
    managed = enqueue(store, "B", "nebius-b200")
    external = enqueue(store, "external", "https://external.example")
    original = type(manager).delete_instance

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        monkeypatch.setattr(api, "_nebius_cleanup_event", asyncio.Event())

        async def interrupted_delete(self, name):
            guard = store.nebius_guard()
            assert guard["job_id"] == api.NEBIUS_CLEANUP_OWNER
            assert guard["state"] == "inflight" and guard["operation"] == "delete"
            assert json.loads(guard["location"]) == location
            entered.set()
            await release.wait()
            if outcome == "timeout_after":
                await original(self, name)
            raise NebiusCommandTimeout("Lost delete response")

        monkeypatch.setattr(type(manager), "delete_instance", interrupted_delete)
        task = asyncio.create_task(api._nebius_pool().cleanup_background())
        await entered.wait()
        guard = store.nebius_guard()
        assert not api._nebius_pool().begin("B", "b200")
        await api._process_queued_job(managed)
        await api._process_queued_job(external)
        assert not ran
        assert store.nebius_guard() == guard
        request = api.ResolveNebiusAbsentRequest(
            operator="alice", reason="checked", confirmed_absent=True, expected_revision=guard["revision"],
        )
        with pytest.raises(api.HTTPException) as error:
            await api.resolve_nebius_absent(api.NEBIUS_CLEANUP_OWNER, request)
        assert error.value.status_code == 409
        if outcome == "cancelled":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            release.set()
            await task
        assert store.nebius_guard() is not None
        assert not pool.cleanup_active
        monkeypatch.setattr(type(manager), "delete_instance", original)

        # Lose every in-memory backend cache and restore the queue from SQLite.
        monkeypatch.setattr(api, "job_store", api.JobStore(store._db_path))
        recovered = (api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
                     if mode == "single" else regional(manager))
        monkeypatch.setattr(api, "_nebius", recovered)
        await api._restore_jobs()
        assert store.nebius_guard()["job_id"] == api.NEBIUS_CLEANUP_OWNER
        api._job_event.clear()
        loop = asyncio.create_task(api._nebius_cleanup_loop(startup=False))
        await api._job_event.wait()  # First automatic maintenance pass completed.
        loop.cancel()
        with pytest.raises(asyncio.CancelledError):
            await loop
        assert store.nebius_guard() is None
        assert not manager.cloud
        await api._process_queued_job(external)
        assert ran == ["external"]

    asyncio.run(scenario())


def test_startup_discovery_rechecks_worker_before_deleting(guarded, monkeypatch):
    store, manager, pool, _ = guarded
    location = expired_vm(pool, manager, "regional")

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        original = manager.discover_locations

        async def discovery(*args):
            entered.set()
            await release.wait()
            return await original(*args)

        monkeypatch.setattr(manager, "discover_locations", discovery)
        task = asyncio.create_task(api._nebius_pool().cleanup_background(startup=True))
        await entered.wait()
        assert store.nebius_guard() is None
        # A worker may dispatch while discovery is still read-only.
        monkeypatch.setattr(api, "_active_job", ("B", None))
        release.set()
        await task
        assert (location["project_id"], location["instance_name"]) in manager.cloud
        assert not any(event == "delete" for event, _ in manager.events)
        assert store.nebius_guard() is None

    asyncio.run(scenario())


def test_startup_journals_every_target_and_protects_new_owner(guarded, monkeypatch):
    store, manager, pool, _ = guarded
    targets = [pool._legacy, *(pool._named(item) for item in manager.locations)]
    for location in targets:
        seed_vm(manager, location)
    original = type(manager).delete_instance
    deleted = []

    async def delete(self, name):
        guard = store.nebius_guard()
        assert guard["job_id"] == api.NEBIUS_CLEANUP_OWNER
        location = json.loads(guard["location"])
        assert (location["project_id"], location["instance_name"]) == (self.project_id, name)
        assert guard["operation"] == "delete" and guard["state"] == "inflight"
        deleted.append(location)
        if len(deleted) == 1:
            enqueue(store, "paused", "nebius-h200")
            store.record_nebius_location("paused", targets[-1])
            store.update_status("paused", api.JobStatus.PAUSED)
        await original(self, name)

    monkeypatch.setattr(type(manager), "delete_instance", delete)
    asyncio.run(api._nebius_pool().cleanup_background(startup=True))
    assert deleted == targets[:-1]
    assert store.nebius_guard() is None
    assert list(manager.cloud) == [(targets[-1]["project_id"], targets[-1]["instance_name"])]


def test_operator_can_inspect_retry_and_resolve_inactive_cleanup_guard(guarded, monkeypatch):
    store, manager, pool, _ = guarded
    monkeypatch.setattr(api, "_nebius_cleanup_event", asyncio.Event())
    location = expired_vm(pool, manager, "regional")
    owner = api.NEBIUS_CLEANUP_OWNER
    assert store.claim_nebius_guard(owner)
    assert store.record_nebius_idle_cleanup(owner, location)
    store.update_nebius_guard(owner, "inflight", "delete")
    inspected = asyncio.run(api.get_nebius_pool())
    assert inspected["owner_kind"] == "cleanup"
    assert inspected["location"] == location
    asyncio.run(api.request_nebius_reconciliation(owner))
    assert api._nebius_cleanup_event.is_set()
    assert store.nebius_guard() is not None
    manager.cloud.clear()
    asyncio.run(api.resolve_nebius_absent(owner, api.ResolveNebiusAbsentRequest(
        operator="alice", reason="Provider confirmed deletion", confirmed_absent=True,
        expected_revision=inspected["revision"],
    )))
    assert store.nebius_guard() is None
    assert not api._job_queue  # Maintenance is not a fake benchmark job.
    with store._connect() as conn:
        assert conn.execute("SELECT job_id FROM nebius_pool_resolutions").fetchone()[0] == owner
