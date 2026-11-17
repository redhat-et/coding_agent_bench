"""New terminal-job resumes prefer a VM without reserving it before dispatch."""

import asyncio
import json

import pytest

from coding_agent_bench import api
from tests.test_nebius_pool_guard import due, enqueue
from tests.test_nebius_pool_guard import guarded as guarded
from tests.test_nebius_regions import regional, seed_vm


def backend(manager, mode):
    return (api.NebiusOrchestrator(manager, "subnet-primary", "queue", 600)
            if mode == "single" else regional(manager))


def queued(job_id):
    return next(item for item in api._job_queue if item.job_id == job_id)


@pytest.mark.parametrize("mode", ["single", "regional"])
@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("saved", [False, True])
def test_two_terminal_resumes_run_sequentially_without_claiming_vm_at_submission(guarded, monkeypatch, mode, restart, saved):
    store, manager, _, _ = guarded
    manager.lost["start"] = False
    monkeypatch.setattr(api, "_nebius", backend(manager, mode))
    asyncio.run(api._process_queued_job(enqueue(store, "original", "nebius-h200")))
    location = json.loads(store.get("original")["nebius_location"])
    if not saved:
        with store._connect() as conn:
            conn.execute("UPDATE jobs SET nebius_location = NULL WHERE job_id = 'original'")
    api._job_queue.clear()
    ids = [asyncio.run(api.resume_job("original"))["job_id"] for _ in range(2)]
    for job_id in ids:
        row = store.get(job_id)
        assert row["nebius_location"] is None
        assert api.JobResponse(**row).nebius_location_hint == (location if saved else {})
        assert not api.NebiusJobOwnership.from_job(row).claimed
    assert store.nebius_guard() is None
    if restart:
        monkeypatch.setattr(api, "job_store", api.JobStore(store._db_path))
        monkeypatch.setattr(api, "_nebius", backend(manager, mode))
        asyncio.run(api._restore_jobs())

    async def scenario():
        done = asyncio.Event()
        order = []
        active = []

        async def run(job_id, *args, **kwargs):
            assert not active
            active.append(job_id)
            row = store.get(job_id)
            assert row["nebius_location_hint"] is None
            assert api.NebiusJobOwnership.from_job(row).claimed
            assert store.nebius_guard() is None  # Preparation finished; worker still serial.
            store.update_status(job_id, api.JobStatus.RUNNING)
            await asyncio.sleep(0)
            assert active == [job_id]
            if job_id == ids[0]:
                assert not api.NebiusJobOwnership.from_job(store.get(ids[1])).claimed
            order.append(job_id)
            store.update_status(job_id, api.JobStatus.COMPLETED)
            active.pop()
            if len(order) == 2:
                done.set()

        monkeypatch.setattr(api, "_run_job", run)
        api._job_event.set()
        task = asyncio.create_task(api._worker())
        try:
            await asyncio.wait_for(done.wait(), timeout=2)
        finally:
            monkeypatch.setattr(api, "_shutting_down", True)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert order == ids

    asyncio.run(scenario())
    assert all(store.get(job_id)["status"] == "completed" for job_id in ids)
    assert manager.events.count(("create", "primary")) == 1
    assert len(manager.cloud) == 1


@pytest.mark.parametrize("restart", [False, True])
def test_cancel_unselected_resume_does_not_delete_the_preferred_vm(guarded, monkeypatch, restart):
    store, manager, _, ran = guarded
    manager.lost["start"] = False
    asyncio.run(api._process_queued_job(enqueue(store, "original", "nebius-h200")))
    first_id = asyncio.run(api.resume_job("original"))["job_id"]
    second_id = asyncio.run(api.resume_job("original"))["job_id"]
    if restart:
        monkeypatch.setattr(api, "job_store", api.JobStore(store._db_path))
        monkeypatch.setattr(api, "_nebius", regional(manager))
        asyncio.run(api._restore_jobs())
    first = queued(first_id)
    asyncio.run(api.delete_job(first_id))
    if store.get(first_id)["status"] == "cancelling":
        asyncio.run(api._process_queued_job(first))
    assert store.get(first_id)["status"] == "cancelled"
    assert manager.cloud and not any(event == "delete" for event, _ in manager.events)
    asyncio.run(api._process_queued_job(queued(second_id)))
    assert ran == ["original", second_id]


@pytest.mark.parametrize("mode", ["single", "regional"])
def test_selected_resume_retains_uncertain_ownership_across_restart(guarded, monkeypatch, mode):
    store, manager, _, ran = guarded
    manager.lost["start"] = False
    monkeypatch.setattr(api, "_nebius", backend(manager, mode))
    asyncio.run(api._process_queued_job(enqueue(store, "original", "nebius-h200")))
    first_id = asyncio.run(api.resume_job("original"))["job_id"]
    second_id = asyncio.run(api.resume_job("original"))["job_id"]
    for vm in manager.cloud.values():
        vm["status"]["state"] = "STOPPED"
    manager.lost["start"] = True
    asyncio.run(api._process_queued_job(queued(first_id)))
    assert store.nebius_guard()["job_id"] == first_id
    assert store.get(first_id)["nebius_location_hint"] is None
    assert api.NebiusJobOwnership.from_job(store.get(first_id)).claimed
    assert not api.NebiusJobOwnership.from_job(store.get(second_id)).claimed
    monkeypatch.setattr(api, "job_store", api.JobStore(store._db_path))
    monkeypatch.setattr(api, "_nebius", backend(manager, mode))
    asyncio.run(api._restore_jobs())
    before = list(manager.events)
    asyncio.run(api._process_queued_job(queued(second_id)))
    assert manager.events == before and ran == ["original"]
    due(store, first_id)
    asyncio.run(api._process_queued_job(queued(first_id)))
    asyncio.run(api._process_queued_job(queued(second_id)))
    assert ran == ["original", first_id, second_id]
    assert store.nebius_guard() is None and len(manager.cloud) == 1


@pytest.mark.parametrize("protected", [False, True])
def test_regional_preference_is_optional_and_never_overrides_a_paused_owner(guarded, protected):
    store, manager, pool, ran = guarded
    manager.lost["start"] = False
    preferred = pool._named(manager.locations[1])
    other = pool._named(manager.locations[0])
    for location in (preferred, other):
        seed_vm(manager, location)
    enqueue(store, "original", "nebius-h200")
    store.record_nebius_location("original", preferred)
    store.update_status("original", api.JobStatus.COMPLETED)
    if protected:
        enqueue(store, "paused-owner", "nebius-h200")
        store.record_nebius_location("paused-owner", preferred)
        store.update_status("paused-owner", api.JobStatus.PAUSED)
    resume_id = asyncio.run(api.resume_job("original"))["job_id"]
    asyncio.run(api._process_queued_job(queued(resume_id)))
    assert ran == [resume_id]
    actual = json.loads(store.get(resume_id)["nebius_location"])
    assert actual["project_id"] == (other if protected else preferred)["project_id"]
    assert (preferred["project_id"], preferred["instance_name"]) in manager.cloud
    if protected:
        assert manager.cloud[preferred["project_id"], preferred["instance_name"]]["status"]["state"] == "STOPPED"


def test_resume_hint_does_not_override_requested_hardware(guarded):
    store, manager, _, ran = guarded
    manager.lost["start"] = False
    asyncio.run(api._process_queued_job(enqueue(store, "original", "nebius-h200")))
    resume_id = asyncio.run(api.resume_job("original", api.ResumeJobRequest(server_url="nebius-b200")))["job_id"]
    assert json.loads(store.get(resume_id)["nebius_location_hint"])["gpu_config"] == "h200"
    asyncio.run(api._process_queued_job(queued(resume_id)))
    assert ran == ["original", resume_id]
    assert json.loads(store.get(resume_id)["nebius_location"])["gpu_config"] == "b200"
    assert len(manager.cloud) == 1
    vm = next(iter(manager.cloud.values()))
    assert vm["spec"]["resources"]["platform"] == "gpu-b200-sxm"


@pytest.mark.parametrize("placement", ["saved", "legacy", "vacant"])
def test_failed_checkpoint_resume_retains_only_real_ownership(guarded, placement):
    store, _, pool, _ = guarded
    enqueue(store, "original", "nebius-h200")
    location = pool._named(pool._manager.locations[0])
    if placement == "saved":
        store.record_nebius_location("original", location)
    with store._connect() as conn:
        conn.execute("UPDATE jobs SET pause_checkpointed = 1, nebius_vacant = ? WHERE job_id = 'original'",
                     (placement == "vacant",))
    store.update_status("original", api.JobStatus.FAILED)
    resume_id = asyncio.run(api.resume_job("original"))["job_id"]
    row = store.get(resume_id)
    ownership = api.NebiusJobOwnership.from_job(row)
    assert ownership.claimed is (placement != "vacant")
    assert store.get("original")["resumed_by_job_id"] == resume_id
    if placement == "saved":
        assert ownership.location == location
    with pytest.raises(api.HTTPException) as error:
        asyncio.run(api.resume_job("original"))
    assert error.value.status_code == 409


def test_hint_migration_preserves_old_recovery_claims(guarded):
    store, _, pool, _ = guarded
    enqueue(store, "saved", "nebius-h200")
    store.claim_nebius_guard("saved")
    store.record_nebius_location("saved", pool._legacy)
    store.update_nebius_guard("saved", "inflight", "start")
    enqueue(store, "legacy", "nebius-h200")
    with store._connect() as conn:
        conn.execute("UPDATE jobs SET command = ? WHERE job_id = 'legacy'",
                     (json.dumps(["bash", "-c", "harbor jobs resume --path /app/jobs/legacy"]),))
        conn.execute("ALTER TABLE jobs DROP COLUMN nebius_location_hint")
    before = store.nebius_guard()
    reopened = api.JobStore(store._db_path)
    for job_id in ("saved", "legacy"):
        row = reopened.get(job_id)
        assert row["nebius_location_hint"] is None
        assert api.NebiusJobOwnership.from_job(row).claimed
    assert reopened.nebius_guard() == before
