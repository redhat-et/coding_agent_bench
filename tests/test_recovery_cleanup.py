import asyncio


class FakeJobStore:
    def __init__(self, status, error="cleanup failed: unavailable"):
        self.row = {"status": status.value, "error": error}

    def get(self, _job_id):
        return self.row

    def update_status(self, _job_id, status, error=None):
        self.row = {"status": status.value, "error": error}


def disable_retry_delays(monkeypatch, api):
    async def no_sleep(_seconds):
        pass

    monkeypatch.setattr(api, "CLEANUP_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(api.asyncio, "sleep", no_sleep)


def test_terminal_cleanup_advances_queue_after_retry_limit(monkeypatch):
    from coding_agent_bench import api

    disable_retry_delays(monkeypatch, api)
    store = FakeJobStore(api.JobStatus.FAILING)
    monkeypatch.setattr(api, "job_store", store)

    attempts = 0

    async def fail_cleanup(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        return False

    monkeypatch.setattr(api, "_finish_terminal_job", fail_cleanup)

    asyncio.run(
        api._retry_terminal_job("job-1", object(), api.JobStatus.FAILED, error="failed")
    )

    assert attempts == 2
    assert store.row == {
        "status": api.JobStatus.FAILED.value,
        "error": "cleanup failed: unavailable",
    }


def test_cancellation_advances_queue_after_retry_limit(monkeypatch):
    from coding_agent_bench import api

    disable_retry_delays(monkeypatch, api)
    store = FakeJobStore(api.JobStatus.CANCELLING)
    monkeypatch.setattr(api, "job_store", store)

    class Job:
        async def _get_job(self):
            return {}

    async def fail_cleanup(*_args, **_kwargs):
        return False

    monkeypatch.setattr(api, "_finish_cancellation", fail_cleanup)

    asyncio.run(api._retry_cancellation("job-1", Job()))

    assert store.row == {
        "status": api.JobStatus.CANCELLED.value,
        "error": "cleanup failed: unavailable",
    }


def test_nebius_cleanup_stops_after_retry_limit(monkeypatch):
    from coding_agent_bench import api

    disable_retry_delays(monkeypatch, api)

    class Nebius:
        attempts = 0

        async def delete_recovered_instance(self):
            self.attempts += 1
            raise RuntimeError("unavailable")

    nebius = Nebius()
    monkeypatch.setattr(api, "_nebius", nebius)

    asyncio.run(api._delete_recovered_nebius("job-1"))

    assert nebius.attempts == 2


def test_run_job_stops_recovery_probe_after_retry_limit(monkeypatch):
    from coding_agent_bench import api

    disable_retry_delays(monkeypatch, api)
    store = FakeJobStore(api.JobStatus.RUNNING)
    monkeypatch.setattr(api, "job_store", store)

    class Job:
        attempts = 0

        def __init__(self, **_kwargs):
            pass

        async def _get_job(self):
            type(self).attempts += 1
            raise RuntimeError("unavailable")

    terminal_errors = []

    async def finish_terminal(_job_id, _job, _status, error=None):
        terminal_errors.append(error)

    monkeypatch.setattr(api, "OpenshiftJob", Job)
    monkeypatch.setattr(api, "_retry_terminal_job", finish_terminal)

    asyncio.run(api._run_job("job-1", [], adopt_existing=True))

    assert Job.attempts == 2
    assert terminal_errors == ["unavailable"]


def test_process_queued_job_stops_recovery_probe_after_retry_limit(monkeypatch):
    from coding_agent_bench import api

    disable_retry_delays(monkeypatch, api)
    store = FakeJobStore(api.JobStatus.RUNNING)
    monkeypatch.setattr(api, "job_store", store)

    class Job:
        attempts = 0

        def __init__(self, **_kwargs):
            pass

        async def _get_job(self):
            type(self).attempts += 1
            raise RuntimeError("unavailable")

    terminal_errors = []

    async def finish_terminal(_job_id, _job, _status, error=None):
        terminal_errors.append(error)

    monkeypatch.setattr(api, "OpenshiftJob", Job)
    monkeypatch.setattr(api, "_retry_terminal_job", finish_terminal)

    queued = api.QueuedJob("job-1", [], "https://example.com", "model", True)
    asyncio.run(api._process_queued_job(queued))

    assert Job.attempts == 2
    assert terminal_errors == ["unavailable"]


def test_cancelled_nebius_job_deletes_instance_instead_of_marking_idle(monkeypatch):
    from coding_agent_bench import api

    store = FakeJobStore(api.JobStatus.RUNNING)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_shutting_down", False)

    existing = {"status": {"conditions": []}}

    class Job:
        instances = 0

        def __init__(self, **_kwargs):
            self.instance = type(self).instances
            type(self).instances += 1
            self.calls = 0

        async def _get_job(self):
            self.calls += 1
            if self.instance == 1 and self.calls == 2:
                store.update_status("job-1", api.JobStatus.CANCELLING)
                raise asyncio.CancelledError
            return existing

        async def _wait_for_job_pod_ready(self):
            pass

        async def _signal_job_pod(self):
            pass

        async def _delete_job(self):
            pass

    class Nebius:
        deleted = 0
        completed = 0

        async def adopt_running_instance(self, _model_name, _gpu_config):
            return "instance-1"

        async def delete_recovered_instance(self):
            self.deleted += 1

        async def mark_job_completed(self, _instance_name):
            self.completed += 1

    nebius = Nebius()
    monkeypatch.setattr(api, "OpenshiftJob", Job)
    monkeypatch.setattr(api, "_nebius", nebius)

    queued = api.QueuedJob("job-1", [], "nebius-gpu", "model", True)
    asyncio.run(api._process_queued_job(queued))

    assert nebius.deleted == 1
    assert nebius.completed == 0
    assert store.row["status"] == api.JobStatus.CANCELLED.value
