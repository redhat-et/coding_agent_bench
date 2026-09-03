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
