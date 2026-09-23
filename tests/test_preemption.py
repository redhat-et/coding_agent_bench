import asyncio
import json

import pytest

from coding_agent_bench.job import OpenshiftJob


class StopLoop(Exception):
    """Raised from a patched asyncio.sleep to end a background loop after N passes."""


def patch_sleep(monkeypatch):
    from coding_agent_bench import api

    clock = {"t": 0.0}
    real_sleep = asyncio.sleep

    async def virtual_sleep(seconds):
        clock["t"] += seconds
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", virtual_sleep)
    monkeypatch.setattr(api, "_monotonic", lambda: clock["t"])


def patch_loop_passes(monkeypatch, passes):
    counter = {"n": 0}

    async def counting_sleep(_seconds):
        counter["n"] += 1
        if counter["n"] > passes:
            raise StopLoop

    monkeypatch.setattr(asyncio, "sleep", counting_sleep)


class FlowStore:
    """JobStore stand-in that enforces the pausing -> paused state machine."""

    def __init__(self, row):
        self.row = dict(row)
        self.status_updates = []
        self.pause_commits = []

    def get(self, _job_id):
        return dict(self.row)

    def update_status(self, _job_id, status, error=None):
        self.status_updates.append((status.value, error))
        self.row["status"] = status.value
        self.row["error"] = error

    def pause_commit(self, job_id, command, attempts, error):
        self.pause_commits.append((command, attempts, error))
        if self.row["status"] != "pausing" or not self.row.get("pause_checkpointed"):
            return False
        self.row["command"] = command
        self.row["status"] = "paused"
        self.row["preempt_attempts"] = attempts
        self.row["error"] = error
        return True

    def mark_pause_checkpointed(self, _job_id):
        if self.row["status"] != "pausing":
            return False
        self.row["pause_checkpointed"] = 1
        return True

    def update_status_if(self, _job_id, expected, status, error=None):
        if self.row["status"] != expected.value:
            return False
        self.update_status(_job_id, status, error=error)
        return True


class FlowNebius:
    def __init__(self, states=None):
        self._manager = self
        self.states = states
        self.get_calls = 0
        self.paused = []
        self.completed = []
        self.started = []

    async def get_instance(self, _name):
        self.get_calls += 1
        if not self.states:
            return {"status": {"state": "RUNNING"}}
        state = self.states[min(self.get_calls - 1, len(self.states) - 1)]
        if isinstance(state, Exception):
            raise state
        return {"status": {"state": state}}

    async def get_instance_state(self, name):
        details = await self.get_instance(name)
        return details.get("status", {}).get("state")

    async def mark_job_paused(self, name):
        self.paused.append(name)

    async def mark_job_completed(self, name):
        self.completed.append(name)

    async def mark_job_started(self, name):
        self.started.append(name)


class FlowJob:
    def __init__(self, job=None, delete_error=None, signal_exited=True):
        self._job = job
        self._delete_error = delete_error
        self._signal_exited = signal_exited
        self.applied = 0
        self.deleted = 0
        self.signals = []
        self.pauses = []
        self.ready_waits = 0

    def _job_spec(self, command, openrouter=False):
        return {}

    def _resume_job_spec(self, shell_command):
        return {}

    async def _run_oc_command(self, command, stdin_data=None):
        self.applied += 1
        return "", ""

    async def _wait_for_job_pod_ready(self, timeout_sec=300):
        self.ready_waits += 1

    async def _get_job(self):
        return self._job

    async def _signal_job_pod(self, wait_seconds=60):
        self.signals.append(wait_seconds)
        return self._signal_exited

    async def request_pause(self, reason, wait_seconds=600):
        self.pauses.append((reason, wait_seconds))
        return self._signal_exited

    async def _delete_job(self):
        self.deleted += 1
        if self._delete_error:
            raise self._delete_error


def running_job():
    return {"status": {"conditions": []}}


class CompletingJob(FlowJob):
    def __init__(self, complete_after):
        super().__init__(job=running_job())
        self._complete_after = complete_after
        self._polls = 0

    async def _get_job(self):
        self._polls += 1
        if self._polls >= self._complete_after:
            return {"status": {"conditions": [{"type": "Complete", "status": "True"}]}}
        return running_job()


def instrument(monkeypatch, api, store=None, nebius=None, oj=None, shutdown=False):
    if store is not None:
        monkeypatch.setattr(api, "job_store", store)
    if nebius is not None:
        monkeypatch.setattr(api, "_nebius", nebius)
    if oj is not None:
        monkeypatch.setattr(api, "OpenshiftJob", lambda job_name, clean_legacy_pods=False: oj)
    monkeypatch.setattr(api, "_shutting_down", shutdown)


# ---------------------------------------------------------------------------
# Detection inside the _run_job monitor loop
# ---------------------------------------------------------------------------


def test_stopped_instance_triggers_preemption(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({"job_id": "j", "status": "running", "preempt_attempts": 0, "error": None})
    nebius = FlowNebius(states=["STOPPED"])
    oj = FlowJob(job=running_job())
    instrument(monkeypatch, api, store, nebius, oj)

    with pytest.raises(api.InstancePreempted):
        asyncio.run(api._run_job("j", ["harbor", "run"], nebius_instance_name="cab-worker-0"))

    assert nebius.get_calls == 4  # 45s elapsed window: observations at 0/15/30/45s
    assert store.row["status"] == "running"  # detection must not terminalize the row


def test_transient_api_error_does_not_trigger(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({"job_id": "j", "status": "running", "preempt_attempts": 0, "error": None})
    nebius = FlowNebius(states=[RuntimeError("api blip"), "RUNNING"])
    oj = CompletingJob(complete_after=12)
    instrument(monkeypatch, api, store, nebius, oj)

    asyncio.run(api._run_job("j", ["harbor", "run"], nebius_instance_name="cab-worker-0"))

    assert store.row["status"] == "completed"
    assert nebius.get_calls == 3  # polls 3, 6, 9 checked; reset each time after the initial blip


def test_sustained_api_outage_triggers_preemption(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "NEBIUS_UNREACHABLE_TRIGGER_SECONDS", 30)
    store = FlowStore({"job_id": "j", "status": "running", "preempt_attempts": 0, "error": None})
    nebius = FlowNebius(states=[RuntimeError("api down")])
    oj = FlowJob(job=running_job())
    instrument(monkeypatch, api, store, nebius, oj)

    with pytest.raises(api.InstancePreempted):
        asyncio.run(api._run_job("j", ["harbor", "run"], nebius_instance_name="cab-worker-0"))

    assert nebius.get_calls == 3  # window opens at t=10s, fires once 30s elapsed


def test_missing_state_uses_long_unavailability_threshold(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "NEBIUS_UNREACHABLE_TRIGGER_SECONDS", 30)
    store = FlowStore({"job_id": "j", "status": "running", "preempt_attempts": 0, "error": None})
    nebius = FlowNebius(states=[None])  # payload regression: {} -> no state
    oj = FlowJob(job=running_job())
    instrument(monkeypatch, api, store, nebius, oj)

    with pytest.raises(api.InstancePreempted) as exc:
        asyncio.run(api._run_job("j", ["harbor", "run"], nebius_instance_name="cab-worker-0"))

    assert "no usable state" in str(exc.value)
    assert nebius.get_calls == 3  # error lane (30s elapsed, patched), not the 45s stopped lane


def test_transient_missing_state_does_not_trigger(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({"job_id": "j", "status": "running", "preempt_attempts": 0, "error": None})
    nebius = FlowNebius(states=[None, "RUNNING"])
    oj = CompletingJob(complete_after=9)
    instrument(monkeypatch, api, store, nebius, oj)

    asyncio.run(api._run_job("j", ["harbor", "run"], nebius_instance_name="cab-worker-0"))

    assert store.row["status"] == "completed"


def test_deleted_instance_counts_as_stopped(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({"job_id": "j", "status": "running", "preempt_attempts": 0, "error": None})
    nebius = FlowNebius(states=["DELETED"])
    oj = FlowJob(job=running_job())
    instrument(monkeypatch, api, store, nebius, oj)

    with pytest.raises(api.InstancePreempted) as exc:
        asyncio.run(api._run_job("j", ["harbor", "run"], nebius_instance_name="cab-worker-0"))

    assert "is DELETED" in str(exc.value)
    assert nebius.get_calls == 4  # fast stopped lane, not the 300s error lane


def test_non_nebius_jobs_never_probe_the_instance(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({"job_id": "j", "status": "running", "preempt_attempts": 0, "error": None})

    class ExplodingNebius(FlowNebius):
        async def get_instance(self, _name):
            raise AssertionError("non-nebius jobs must not poll Nebius")

    oj = CompletingJob(complete_after=5)
    instrument(monkeypatch, api, store, ExplodingNebius(), oj)

    asyncio.run(api._run_job("j", ["harbor", "run"]))

    assert store.row["status"] == "completed"


def test_shutdown_suppresses_detection(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({"job_id": "j", "status": "running", "preempt_attempts": 0, "error": None})

    class ExplodingNebius(FlowNebius):
        async def get_instance(self, _name):
            raise AssertionError("detection must be off while shutting down")

    oj = CompletingJob(complete_after=4)
    instrument(monkeypatch, api, store, ExplodingNebius(), oj, shutdown=True)

    asyncio.run(api._run_job("j", ["harbor", "run"], nebius_instance_name="cab-worker-0"))

    assert store.row["status"] == "completed"


# ---------------------------------------------------------------------------
# Pause engine
# ---------------------------------------------------------------------------


def test_pause_parks_job_with_resume_command_after_checkpoint_upload(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({
        "job_id": "jid", "job_name": "job-a", "agent": "a", "dataset": "d",
        "model_name": "m", "server_url": "nebius-b200", "status": "running",
        "preempt_attempts": 0, "error": None,
    })
    nebius = FlowNebius()
    oj = FlowJob(job=running_job())  # pod still running -> must be signalled
    instrument(monkeypatch, api, store, nebius, oj)

    asyncio.run(api._handle_pause("jid", oj, "cab-worker-0"))

    assert nebius.paused == ["cab-worker-0"]
    assert oj.signals == []  # Keep Harbor alive to write pending cancellations.
    assert oj.pauses[0][1] == api.PAUSE_UPLOAD_TIMEOUT_SECONDS
    assert oj.deleted == 1
    assert store.row["status"] == "paused"
    assert store.row["preempt_attempts"] == 1
    command = store.row["command"]
    assert command[0] == "bash" and command[1] == "-c"
    assert "harbor jobs resume" in command[2]
    assert "s3://results/job-a/" in command[2]
    assert "VM preempted" in store.row["error"]


def test_pause_retains_parent_when_pod_outlives_upload_budget(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({
        "job_id": "jid", "job_name": "job-a", "agent": "a", "dataset": "d",
        "model_name": "m", "server_url": "nebius-b200", "status": "running",
        "preempt_attempts": 0, "error": None,
    })
    oj = FlowJob(job=running_job(), signal_exited=False)
    instrument(monkeypatch, api, store, FlowNebius(), oj)

    asyncio.run(api._handle_pause("jid", oj, "cab-worker-0"))

    assert store.row["status"] == "pausing"
    assert "checkpoint not confirmed" in store.row["error"]
    assert oj.deleted == 0
    assert store.pause_commits == []


def test_pause_budget_exhaustion_fails_job_without_parking(monkeypatch):
    from coding_agent_bench import api

    store = FlowStore({
        "job_id": "jid", "job_name": "job-a", "agent": "a", "dataset": "d",
        "model_name": "m", "server_url": "nebius-b200", "status": "running",
        "preempt_attempts": api.MAX_PREEMPT_RESUMES, "error": None,
    })
    nebius = FlowNebius()
    oj = FlowJob(job=running_job())
    instrument(monkeypatch, api, store, nebius, oj)

    asyncio.run(api._handle_pause("jid", oj, "cab-worker-0"))

    assert store.row["status"] == "failed"
    assert "exhausted" in store.row["error"]
    assert store.pause_commits  # Save the checkpoint even after exhausting retries.
    assert store.row["pause_checkpointed"] == 1
    assert nebius.paused == ["cab-worker-0"]


def test_pause_skips_job_cancelled_during_detection(monkeypatch):
    from coding_agent_bench import api

    # A DELETE can land between detection and the pause's first write;
    # the guarded pausing update must refuse to resurrect the cancelled row.
    store = FlowStore({
        "job_id": "jid", "job_name": "job-a", "agent": "a", "dataset": "d",
        "model_name": "m", "server_url": "nebius-b200", "status": "cancelled",
        "preempt_attempts": 0, "error": None,
    })
    nebius = FlowNebius()
    oj = FlowJob(job=running_job())
    instrument(monkeypatch, api, store, nebius, oj)

    asyncio.run(api._handle_pause("jid", oj, "cab-worker-0"))

    assert store.row["status"] == "cancelled"
    assert nebius.paused == []
    assert oj.deleted == 0
    assert store.pause_commits == []


def test_pause_commit_skips_jobs_that_left_pausing(monkeypatch):
    from coding_agent_bench import api

    store = FlowStore({"job_id": "jid", "status": "cancelled", "preempt_attempts": 0})
    monkeypatch.setattr(api, "job_store", store)
    oj = FlowJob(job=None)

    assert asyncio.run(api._pause_commit("jid", oj)) is True
    assert oj.deleted == 0


def test_pause_finalize_does_not_requeue_while_cleanup_keeps_failing(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "CLEANUP_MAX_ATTEMPTS", 2)
    store = FlowStore({
        "job_id": "jid", "job_name": "job-a", "agent": "a", "dataset": "d",
        "model_name": "m", "server_url": "nebius-b200", "status": "pausing",
        "preempt_attempts": 1, "error": None, "pause_checkpointed": 1,
    })
    monkeypatch.setattr(api, "job_store", store)
    oj = FlowJob(job=None, delete_error=RuntimeError("oc api unreachable"))

    asyncio.run(api._retry_pause_finalize("jid", oj))

    assert store.row["status"] == "pausing"
    assert "cleanup failure" in store.row["error"]
    assert store.row["preempt_attempts"] == 1


@pytest.mark.parametrize("job", [None, {"status": {"conditions": [{"type": "Failed", "status": "True"}]}}])
def test_unconfirmed_checkpoint_is_never_deleted_or_parked(monkeypatch, job):
    from coding_agent_bench import api

    store = FlowStore({
        "job_id": "jid", "job_name": "job-a", "status": "pausing",
        "server_url": "nebius-b200", "preempt_attempts": 0, "error": "preempted",
    })
    oj = FlowJob(job=job)
    monkeypatch.setattr(api, "job_store", store)
    assert asyncio.run(api._pause_commit("jid", oj)) is False
    assert oj.deleted == 0
    assert not store.pause_commits
    assert store.row["status"] == "pausing"


def test_checkpoint_proof_survives_restart_after_parent_deletion(monkeypatch):
    from coding_agent_bench import api

    store = FlowStore({
        "job_id": "jid", "job_name": "job-a", "status": "pausing",
        "server_url": "nebius-b200", "preempt_attempts": 0, "error": "preempted",
        "pause_checkpointed": 1,
    })
    monkeypatch.setattr(api, "job_store", store)
    assert asyncio.run(api._pause_commit("jid", FlowJob(job=None))) is True
    assert store.row["status"] == "paused"
    assert "-f CancelledError" in store.row["command"][2]


def test_paused_resume_command_reuses_original_artifact_and_placeholder():
    from coding_agent_bench import api

    command = api._build_pause_resume_command({
        "job_id": "abc",
        "job_name": "foo--resume",
        "command": ["bash", "-c", "uv run harbor jobs resume -p /app/jobs/foo"],
        "server_url": "nebius-b200",
        "preempt_attempts": 2,
    })

    assert command[0] == "bash" and command[1] == "-c"
    shell = command[2]
    assert "harbor jobs resume" in shell
    assert "s3://results/foo/" in shell  # original artifact, not foo--resume
    assert "/app/jobs/foo" in shell
    assert "foo/abc-p2" in shell  # per-attempt staging prefix
    assert "coding_agent_bench.resume parent" in shell
    assert "coding_agent_bench.resume endpoint" not in shell  # injected after provisioning


def test_process_queued_job_routes_preemption_to_pause(monkeypatch):
    from coding_agent_bench import api

    store = FlowStore({
        "job_id": "j1", "job_name": "job-a", "agent": "a", "dataset": "d",
        "model_name": "m", "server_url": "nebius-b200", "status": "running",
        "preempt_attempts": 0, "error": None,
    })
    monkeypatch.setattr(api, "job_store", store)

    class AcquiringNebius(FlowNebius):
        async def acquire_instance(self, model_name, gpu_config):
            return "inst-0", "http://9.9.9.9:8000"

    monkeypatch.setattr(api, "_nebius", AcquiringNebius())

    handled = []

    async def fake_run_job(*args, **kwargs):
        raise api.InstancePreempted("boom")

    async def fake_handle_pause(job_id, oj, instance_name):
        handled.append((job_id, instance_name))

    monkeypatch.setattr(api, "_run_job", fake_run_job)
    monkeypatch.setattr(api, "_handle_pause", fake_handle_pause)

    queued = api.QueuedJob("j1", ["harbor", "run", "--agent", "pi"], "nebius-b200", "m")
    asyncio.run(api._process_queued_job(queued))

    assert handled == [("j1", "inst-0")]
    assert all(s != "failed" for s, _ in store.status_updates)


def test_pausing_restart_survives_nebius_outage(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    store = FlowStore({
        "job_id": "j1", "job_name": "job-a", "agent": "a", "dataset": "d",
        "model_name": "m", "server_url": "nebius-b200", "status": "pausing",
        "preempt_attempts": 1, "error": "VM preempted",
        "command": json.dumps(["harbor", "run", "--agent", "pi"]),
    })
    nebius = FlowNebius(states=[RuntimeError("api down")])  # adoption re-raises
    oj = FlowJob(job=running_job())
    instrument(monkeypatch, api, store, nebius, oj)

    queued = api.QueuedJob("j1", ["harbor", "run", "--agent", "pi"], "nebius-b200", "m")
    asyncio.run(api._process_queued_job(queued))  # must not raise

    # Finalization needs no Nebius: the pause completes untracked, and the
    # recovery loop re-adopts once the API answers again.
    assert store.row["status"] == "paused"


def test_worker_survives_crashing_job(monkeypatch):
    from coding_agent_bench import api

    store = FlowStore({"job_id": "j1", "status": "queued"})
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_job_queue", [
        api.QueuedJob("j1", ["harbor", "run"], "http://x:8000", "m"),
    ])

    class OnceEvent:
        def __init__(self):
            self.waits = 0

        def clear(self):
            pass

        def set(self):
            pass

        async def wait(self):
            self.waits += 1
            if self.waits > 1:
                raise StopLoop

    monkeypatch.setattr(api, "_job_event", OnceEvent())

    async def crasher(_queued):
        raise RuntimeError("boom")

    monkeypatch.setattr(api, "_process_queued_job", crasher)

    with pytest.raises(StopLoop):  # not RuntimeError: the dispatcher survived
        asyncio.run(api._worker())


# ---------------------------------------------------------------------------
# Paused-job recovery loop
# ---------------------------------------------------------------------------


class LoopStore:
    def __init__(self, rows):
        self._rows = rows
        self.status_updates = []

    def list_paused(self):
        return [dict(r) for r in self._rows if r.get("status") == "paused"]

    def list_pausing(self):
        return [dict(r) for r in self._rows if r.get("status") == "pausing"]

    def update_status(self, job_id, status, error=None):
        self.status_updates.append((job_id, status.value, error))
        self._apply(job_id, status.value, error)

    def update_status_if(self, job_id, expected, status, error=None):
        row = next((r for r in self._rows if r["job_id"] == job_id), None)
        if row is None or row.get("status") != expected.value:
            return False
        self.update_status(job_id, status, error=error)
        return True

    def _apply(self, job_id, status, error):
        for row in self._rows:
            if row["job_id"] == job_id:
                row["status"] = status
                row["error"] = error


class LoopNebius:
    def __init__(self, busy=False, adopt="inst-0", recover_error=None):
        self.busy = busy
        self._adopt = adopt
        self.recover_error = recover_error
        self.recovered = []

    def has_busy_instance(self):
        return self.busy

    async def adopt_paused_instance(self, model_name, gpu_config):
        return self._adopt

    async def recover_stopped_instance(self, instance_name):
        if self.recover_error:
            raise self.recover_error
        self.recovered.append(instance_name)


def paused_row():
    return {
        "job_id": "p1", "model_name": "m", "server_url": "nebius-b200",
        "preempt_attempts": 1, "error": "VM preempted", "status": "paused",
        "command": json.dumps(["bash", "-c", "resume-cmd"]),
    }


def run_recovery_loop(monkeypatch, nebius, store, passes=1, active=None):
    from coding_agent_bench import api

    queue = []
    monkeypatch.setattr(api, "_nebius", nebius)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_shutting_down", False)
    monkeypatch.setattr(api, "_active_job", active)
    monkeypatch.setattr(api, "_job_queue", queue)
    patch_loop_passes(monkeypatch, passes)
    with pytest.raises(StopLoop):
        asyncio.run(api._resume_paused_jobs_loop())
    return queue


def test_recovery_loop_flips_paused_job_after_stabilizing(monkeypatch):

    nebius = LoopNebius()
    store = LoopStore([paused_row()])
    queue = run_recovery_loop(monkeypatch, nebius, store)

    assert nebius.recovered == ["inst-0"]
    assert store.status_updates
    job_id, status, error = store.status_updates[0]
    assert (job_id, status) == ("p1", "queued")
    assert "resuming" in error
    # DB flip alone is not dispatch: the worker drains _job_queue only
    assert len(queue) == 1
    assert queue[0].job_id == "p1"
    assert queue[0].command == ["bash", "-c", "resume-cmd"]


def test_recovery_loop_stays_paused_when_nebius_unavailable(monkeypatch):

    store = LoopStore([paused_row()])
    queue = run_recovery_loop(monkeypatch, LoopNebius(recover_error=RuntimeError("capacity")), store)

    assert store.status_updates == []
    assert queue == []


def test_recovery_loop_defers_to_running_jobs(monkeypatch):

    nebius = LoopNebius(busy=True)
    store = LoopStore([paused_row()])
    queue = run_recovery_loop(monkeypatch, nebius, store)

    assert store.status_updates == []
    assert nebius.recovered == []
    assert queue == []


def test_recovery_loop_requeues_when_instance_is_gone(monkeypatch):

    nebius = LoopNebius(adopt=None)
    store = LoopStore([paused_row()])
    queue = run_recovery_loop(monkeypatch, nebius, store)

    assert nebius.recovered == []  # full re-provisioning deferred to the worker
    assert store.status_updates and store.status_updates[0][1] == "queued"
    assert len(queue) == 1 and queue[0].job_id == "p1"


def test_recovery_loop_requeues_row_without_nebius_url(monkeypatch):
    store = LoopStore([{**paused_row(), "server_url": "http://model.example:8000"}])
    queue = run_recovery_loop(monkeypatch, LoopNebius(), store)

    assert store.status_updates and store.status_updates[0][1] == "queued"
    assert len(queue) == 1 and queue[0].job_id == "p1"


def test_recovery_loop_skips_while_queue_busy(monkeypatch):

    calls = {"listed": 0}

    class BusyQueueStore(LoopStore):
        def list_paused(self):
            calls["listed"] += 1
            return super().list_paused()

    queue = run_recovery_loop(
        monkeypatch, LoopNebius(), BusyQueueStore([paused_row()]),
        passes=2, active=("running-job", None),
    )

    assert calls["listed"] == 0
    assert queue == []


def test_recovery_loop_does_not_resurrect_cancelled_jobs(monkeypatch):
    # Recovery can run for minutes; a DELETE that lands mid-recovery wins.
    class CancelledMidRecovery(LoopStore):
        def update_status_if(self, job_id, expected, status, error=None):
            return False  # row is cancelled by the time recovery finishes

    nebius = LoopNebius()
    queue = run_recovery_loop(monkeypatch, nebius, CancelledMidRecovery([paused_row()]))

    assert nebius.recovered == ["inst-0"]  # recovery itself happened
    assert queue == []                     # but dispatch is refused


# ---------------------------------------------------------------------------
# Instance stabilization
# ---------------------------------------------------------------------------


class StabilizerManager:
    def __init__(self, start_results, states):
        self.start_results = start_results
        self.states = states
        self.start_calls = 0
        self.get_calls = 0

    async def start_instance(self, _name):
        result = self.start_results[min(self.start_calls, len(self.start_results) - 1)]
        self.start_calls += 1
        if isinstance(result, Exception):
            raise result
        return result

    async def get_instance(self, _name):
        state = self.states[min(self.get_calls, len(self.states) - 1)]
        self.get_calls += 1
        if isinstance(state, Exception):
            raise state
        return {"status": {"state": state}}


def make_orchestrator(manager):
    from coding_agent_bench import api

    return api.NebiusOrchestrator(
        manager=manager, subnet_id="s", instance_name_prefix="p", idle_timeout=999
    )


def test_stabilization_applies_even_when_start_was_not_issued(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "PREEMPT_STABLE_SECONDS", 0)
    manager = StabilizerManager(start_results=[False], states=["RUNNING"])
    monkeypatch.setattr(api, "_nebius", None)  # keep module globals untouched otherwise

    asyncio.run(make_orchestrator(manager).recover_stopped_instance("i"))

    # An already-RUNNING (or waited-out STARTING) VM has proven nothing
    # about surviving preemption; only the stabilization window proves it.
    assert manager.get_calls == 1


def test_stabilization_returns_after_window_without_repreemption(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "PREEMPT_STABLE_SECONDS", 0)
    manager = StabilizerManager(start_results=[True], states=["RUNNING"])

    asyncio.run(make_orchestrator(manager).recover_stopped_instance("i"))

    assert manager.get_calls == 1


def test_stabilization_gives_up_after_restart_attempts(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "PREEMPT_RESTART_ATTEMPTS", 1)
    manager = StabilizerManager(start_results=[True], states=["STOPPED"])

    with pytest.raises(RuntimeError):
        asyncio.run(make_orchestrator(manager).recover_stopped_instance("i"))

    assert manager.start_calls == 1
    assert manager.get_calls == 1


def test_stabilization_survives_transient_state_check_errors(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "PREEMPT_STABLE_SECONDS", 0)
    manager = StabilizerManager(start_results=[True], states=[RuntimeError("api blip"), "RUNNING"])

    asyncio.run(make_orchestrator(manager).recover_stopped_instance("i"))

    assert manager.get_calls == 2


def test_stabilization_bounds_persistent_state_check_errors(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "PREEMPT_STABLE_SECONDS", 30)
    monkeypatch.setattr(api, "PREEMPT_STABILIZE_ERROR_SECONDS", 20)
    manager = StabilizerManager(
        start_results=[True],
        states=[RuntimeError("api unavailable")],
    )

    with pytest.raises(RuntimeError, match="state checks failed"):
        asyncio.run(make_orchestrator(manager).recover_stopped_instance("i"))

    assert manager.get_calls == 3


def test_stabilization_fails_fast_when_instance_disappears(monkeypatch):
    from coding_agent_bench import api

    patch_sleep(monkeypatch)
    monkeypatch.setattr(api, "PREEMPT_STABLE_SECONDS", 30)
    manager = StabilizerManager(
        start_results=[True],
        states=[ValueError("RpcError: NotFound")],
    )

    with pytest.raises(RuntimeError, match="disappeared"):
        asyncio.run(make_orchestrator(manager).recover_stopped_instance("i"))

    assert manager.get_calls == 1


# ---------------------------------------------------------------------------
# Paused-job VM adoption (real orchestrator logic)
# ---------------------------------------------------------------------------


def test_adopt_refuses_unrecoverable_leftover_vms():
    for state in ("DELETED", "ERROR", "CRASHED"):
        orch = make_orchestrator(StabilizerManager(start_results=[], states=[state]))
        assert asyncio.run(orch.adopt_paused_instance("m", "b200")) is None, state
        assert orch.get_instance_states() == []


def test_adopt_returns_none_when_instance_is_gone():
    manager = StabilizerManager(start_results=[], states=[ValueError("RpcError: NotFound")])
    orch = make_orchestrator(manager)

    assert asyncio.run(orch.adopt_paused_instance("m", "b200")) is None
    assert orch.get_instance_states() == []


def test_adopt_tracks_restartable_vm():
    orch = make_orchestrator(StabilizerManager(start_results=[], states=["STOPPED"]))

    assert asyncio.run(orch.adopt_paused_instance("m", "b200")) == "p-0"
    assert [s.instance_name for s in orch.get_instance_states()] == ["p-0"]


def test_adopt_untracks_tracked_instance_that_became_a_leftover():
    manager = StabilizerManager(start_results=[], states=["STOPPED", "DELETED"])
    orch = make_orchestrator(manager)

    assert asyncio.run(orch.adopt_paused_instance("m", "b200")) == "p-0"
    assert asyncio.run(orch.adopt_paused_instance("m", "b200")) is None
    assert orch.get_instance_states() == []


def test_adopt_reraises_during_api_outage():
    manager = StabilizerManager(start_results=[], states=[RuntimeError("connection refused")])
    orch = make_orchestrator(manager)

    with pytest.raises(RuntimeError):
        asyncio.run(orch.adopt_paused_instance("m", "b200"))


def test_restore_jobs_keeps_vm_for_paused_nebius_job(monkeypatch):
    from coding_agent_bench import api

    class Event:
        def __init__(self):
            self.set_calls = 0

        def clear(self):
            pass

        def set(self):
            self.set_calls += 1

    class Store:
        def list_recoverable(self):
            return []

        def list_paused(self):
            return [{
                "job_id": "p1",
                "server_url": "nebius-b200",
                "model_name": "m",
                "command": json.dumps(["bash", "-c", "resume"]),
            }]

    queue = []
    event = Event()
    monkeypatch.setattr(api, "job_store", Store())
    monkeypatch.setattr(api, "_job_queue", queue)
    monkeypatch.setattr(api, "_job_event", event)

    assert asyncio.run(api._restore_jobs()) is True
    assert queue == []
    assert event.set_calls == 0


# ---------------------------------------------------------------------------
# Endpoints and store semantics
# ---------------------------------------------------------------------------


def test_delete_paused_job_cancels_it(monkeypatch):
    from coding_agent_bench import api

    store = FlowStore({"job_id": "p1", "status": "paused", "preempt_attempts": 1, "error": "x"})
    monkeypatch.setattr(api, "job_store", store)

    result = asyncio.run(api.delete_job("p1"))

    assert result["message"] == "Job cancelled"
    assert store.row["status"] == "cancelled"


def test_delete_paused_race_cannot_clobber_running(monkeypatch):
    from coding_agent_bench import api

    class RacyStore(FlowStore):
        def __init__(self, row):
            super().__init__(row)
            self.reads = 0

        def get(self, job_id):
            row = super().get(job_id)
            self.reads += 1
            if self.reads == 1:
                row["status"] = "paused"  # stale read; the resume loop won
            return row

    store = RacyStore({"job_id": "p1", "status": "running", "preempt_attempts": 1})

    class FakeTask:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    task = FakeTask()
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_active_job", ("p1", task))

    result = asyncio.run(api.delete_job("p1"))

    assert result["message"] == "Job cancelling"
    assert store.row["status"] == "cancelling"  # not an unconditional cancelled
    assert task.cancelled


def test_delete_pausing_job_is_rejected(monkeypatch):
    from fastapi import HTTPException

    from coding_agent_bench import api

    store = FlowStore({"job_id": "p1", "status": "pausing", "preempt_attempts": 1, "error": "x"})
    monkeypatch.setattr(api, "job_store", store)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.delete_job("p1"))

    assert exc.value.status_code == 400


def test_manual_resume_accepts_cancelled_jobs(monkeypatch):
    from coding_agent_bench import api

    store = FlowStore({
        "job_id": "c1", "job_name": "foo", "agent": "a", "dataset": "d",
        "model_name": "m", "server_url": "http://model.example:8000",
        "status": "cancelled", "preempt_attempts": 3, "error": "exhausted",
    })
    inserted = []
    store.insert = lambda *args, **kwargs: inserted.append(args)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_job_queue", [])

    result = asyncio.run(api.resume_job("c1", api.ResumeJobRequest()))

    assert result["job_name"] == "foo--resume"
    assert inserted and inserted[0][1] == "foo--resume"
    queued_command = api._job_queue[0].command
    assert "harbor jobs resume" in queued_command[2]


def test_job_store_pause_commit_state_machine(tmp_path):
    from pathlib import Path

    from coding_agent_bench import api

    store = api.JobStore(Path(tmp_path) / "jobs.db")
    store.insert("j1", "job-a", "a", "d", "m", "nebius-b200", ["harbor", "run"])
    assert store.get("j1")["preempt_attempts"] == 0

    # pause_commit only accepts rows still in pausing
    assert store.pause_commit("j1", ["bash", "-c", "x"], 1, "err") is False

    store.update_status("j1", api.JobStatus.PAUSING)
    assert store.pause_commit("j1", ["bash", "-c", "x"], 1, "unconfirmed") is False
    assert store.mark_pause_checkpointed("j1") is True
    assert store.pause_commit("j1", ["bash", "-c", "resume-cmd"], 1, "parked") is True
    row = store.get("j1")
    assert row["status"] == "paused"
    assert row["preempt_attempts"] == 1
    assert row["command"] == '["bash", "-c", "resume-cmd"]'
    assert [r["job_id"] for r in store.list_paused()] == ["j1"]
    assert store.pause_commit("j1", ["bash", "-c", "y"], 2, "again") is False

    store.update_status("j1", api.JobStatus.PAUSING)
    assert "j1" in [r["job_id"] for r in store.list_recoverable()]


def test_signal_job_pod_honors_extended_wait(monkeypatch):

    patch_sleep(monkeypatch)
    oj = OpenshiftJob("job-x")
    calls = {"selector": 0, "phase": 0}

    async def fake_oc(command, check=True, timeout_sec=None, stdin_data=None):
        if any("selector=job-name" in arg for arg in command):
            calls["selector"] += 1
            return "pod-1", ""
        if command and command[0] == "exec":
            return "", ""
        calls["phase"] += 1
        return "Running", ""

    monkeypatch.setattr(oj, "_run_oc_command", fake_oc)

    result = asyncio.run(oj._signal_job_pod(wait_seconds=6))

    assert calls["phase"] == 3  # 6s / 2s per poll instead of the legacy 30 polls
    assert result is False  # budget expired with the pod still running


def test_signal_job_pod_returns_true_on_early_exit(monkeypatch):
    patch_sleep(monkeypatch)
    oj = OpenshiftJob("job-x")
    phases = iter(["Running", "Succeeded"])

    async def fake_oc(command, check=True, timeout_sec=None, stdin_data=None):
        if any("selector=job-name" in arg for arg in command):
            return "pod-1", ""
        if command and command[0] == "exec":
            return "", ""
        return next(phases), ""

    monkeypatch.setattr(oj, "_run_oc_command", fake_oc)

    assert asyncio.run(oj._signal_job_pod(wait_seconds=600)) is True
