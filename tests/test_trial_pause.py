"""Exercise cancellation and native resume against the pinned Harbor APIs."""

import asyncio
from datetime import datetime, timezone
import json

import pytest

from coding_agent_bench.preemption import CANCELLED_ERROR_TYPE, PAUSE_PLUGIN, PauseOnRequestPlugin


@pytest.fixture
def harbor_job(tmp_path, monkeypatch):
    """Resolve a real local Harbor job; only trial environment execution is fake."""
    from harbor.job import Job
    from harbor.models.job.config import JobConfig, RetryConfig
    from harbor.models.trial.config import AgentConfig, EnvironmentConfig, TaskConfig

    monkeypatch.setenv("HARBOR_TELEMETRY", "0")
    tasks = []
    for name in ("done", "running", "pending-a", "pending-b"):
        directory = tmp_path / "tasks" / name
        (directory / "environment").mkdir(parents=True)
        (directory / "tests").mkdir()
        (directory / "solution").mkdir()
        (directory / "task.toml").write_text('version = "1.0"\n')
        (directory / "instruction.md").write_text("A local test task.")
        (directory / "environment/Dockerfile").write_text("FROM busybox")
        (directory / "tests/test.sh").write_text("exit 0")
        (directory / "solution/solve.sh").write_text("exit 0")
        tasks.append(TaskConfig(path=directory))
    config = JobConfig(
        job_name="benchmark", jobs_dir=tmp_path / "jobs", tasks=tasks,
        agents=[AgentConfig(name="oracle", env={"OPENAI_BASE_URL": "http://198.51.100.10:8000/v1"})],
        environment=EnvironmentConfig(type="docker", kwargs={"persistent_env": {"HARBOR_PARENT": "old-parent"}}),
        n_concurrent_trials=1, quiet=True,
        retry=RetryConfig(max_retries=5, min_wait_sec=0.01, max_wait_sec=0.01),
    )
    return asyncio.run(Job.create(config))


@pytest.mark.parametrize("prepare_metadata", [False, True])
def test_pending_trials_cancel_without_starting_and_native_resume_selects_them(harbor_job, tmp_path, monkeypatch, prepare_metadata):
    """Pending cancellations create result files, not trial environments or pods."""
    from harbor.cli import jobs as harbor_jobs
    from harbor.environments.factory import EnvironmentFactory
    from harbor.models.trial.paths import TrialPaths
    from harbor.models.trial.result import AgentInfo, ExceptionInfo, TrialResult
    from harbor.trial.hooks import TrialEvent, TrialHookEvent
    from harbor.trial.trial import Trial

    request = tmp_path / "pause-request.json"
    monkeypatch.setenv("CAB_PAUSE_REQUEST_PATH", str(request))
    created = []
    running = asyncio.Event()
    allow_completion = False
    hooks = []

    class FakeTrial:
        def __init__(self, config):
            self.config = config
            self.paths = TrialPaths(config.trials_dir / config.trial_name)
            self.paths.mkdir()
            self.callbacks = {event: [] for event in TrialEvent}
            self.name = config.task.path.name
            lock_index = next(i for i, c in enumerate(harbor_job._trial_configs) if c.task == config.task)
            self.lock = harbor_job._job_lock.trials[lock_index].model_copy(
                update={"environment": config.environment, "agent": config.agent}
            )
            self.result = TrialResult(
                task_name=self.name, trial_name=config.trial_name,
                trial_uri=self.paths.trial_dir.resolve().as_uri(),
                task_id=config.task.get_task_id(), task_checksum=self.lock.task.digest,
                config=config, agent_info=AgentInfo(name="oracle", version="test"),
                started_at=datetime.now(timezone.utc),
            )
            self.paths.config_path.write_text(config.model_dump_json())
            (self.paths.trial_dir / "lock.json").write_text(self.lock.model_dump_json())

        def add_hook(self, event, callback):
            self.callbacks[event].append(callback)

        async def emit(self, event):
            hooks.append((self.name, event))
            payload = TrialHookEvent(event=event, task_name=self.name, config=self.config, result=self.result, lock=self.lock)
            for callback in self.callbacks[event]:
                await callback(payload)

        async def run(self):
            await self.emit(TrialEvent.START)
            try:
                if self.name != "done" and not allow_completion:
                    running.set()
                    await asyncio.Future()
            except asyncio.CancelledError as exc:
                self.result.exception_info = ExceptionInfo.from_exception(exc)
                await self.emit(TrialEvent.CANCEL)
                raise
            finally:
                self.result.finished_at = datetime.now(timezone.utc)
                self.paths.result_path.write_text(self.result.model_dump_json())
                await self.emit(TrialEvent.END)
            return self.result

    async def create_trial(config):
        created.append(config.task.path.name)
        return FakeTrial(config)

    monkeypatch.setattr(Trial, "create", create_trial)

    async def pause_scenario():
        plugin = PauseOnRequestPlugin()
        await plugin.on_job_start(harbor_job)
        task = asyncio.create_task(harbor_job.run())
        await asyncio.wait_for(running.wait(), timeout=10)
        request.write_text(json.dumps({"reason": "Nebius instance STOPPED"}))
        result = await asyncio.wait_for(task, timeout=10)
        await plugin.on_job_end(result)
        return result

    result = asyncio.run(pause_scenario())
    assert created == ["done", "running"]
    assert len(result.trial_results) == 4
    assert result.stats.n_cancelled_trials == 3
    assert sum(r.exception_info is None for r in result.trial_results) == 1
    cancelled = [r for r in result.trial_results if r.exception_info]
    assert {r.exception_info.exception_type for r in cancelled} == {CANCELLED_ERROR_TYPE}
    assert {r.task_name for r in cancelled} == {"running", "pending-a", "pending-b"}
    assert all(r.started_at is None for r in cancelled if r.task_name.startswith("pending"))
    assert not any(name.startswith("pending") and event == TrialEvent.START for name, event in hooks)
    for trial in result.trial_results:
        persisted = TrialResult.model_validate_json(
            (harbor_job.job_dir / trial.trial_name / "result.json").read_text()
        )
        assert persisted == trial
    finished = next(r for r in result.trial_results if r.task_name == "done")
    completed_bytes = (harbor_job.job_dir / finished.trial_name / "result.json").read_bytes()

    if prepare_metadata:
        from coding_agent_bench.resume import update_endpoint, update_parent

        update_parent(harbor_job.job_dir, "new-parent")
        update_endpoint(harbor_job.job_dir, "http://203.0.113.20:9000")

    allow_completion = True
    created.clear()
    monkeypatch.setattr(EnvironmentFactory, "run_preflight", lambda **_kwargs: None)
    if prepare_metadata:
        # Preempt again before the resumed trials start: the successful original
        # trial must survive another cancellation/filter/metadata-rewrite cycle.
        harbor_jobs.resume(
            harbor_job.job_dir, filter_error_types=[CANCELLED_ERROR_TYPE],
            job_plugin=[PAUSE_PLUGIN],
        )
        assert created == []
        update_parent(harbor_job.job_dir, "new-parent-2")
        update_endpoint(harbor_job.job_dir, "http://203.0.113.21:9000")
    request.unlink()
    harbor_jobs.resume(
        harbor_job.job_dir, filter_error_types=[CANCELLED_ERROR_TYPE],
        job_plugin=[PAUSE_PLUGIN],
    )
    assert set(created) == {"running", "pending-a", "pending-b"}
    after = (harbor_job.job_dir / finished.trial_name / "result.json").read_bytes()
    if prepare_metadata:
        old, new = json.loads(completed_bytes), json.loads(after)
        config = new.pop("config")
        old.pop("config")
        assert new == old  # Preserve completed results, identity, and timings.
        assert config["environment"]["kwargs"]["persistent_env"]["HARBOR_PARENT"] == "new-parent-2"
        assert config["agent"]["env"]["OPENAI_BASE_URL"] == "http://203.0.113.21:9000/v1"
    else:
        assert after == completed_bytes


def test_request_before_scheduling_creates_no_trials(harbor_job, tmp_path, monkeypatch):
    """A request delivered during job preparation must gate the very first trial."""
    from harbor.trial.trial import Trial

    request = tmp_path / "pause.json"
    request.write_text(json.dumps({"reason": "Nebius STOPPED"}))
    monkeypatch.setenv("CAB_PAUSE_REQUEST_PATH", str(request))

    async def unexpected_create(_config):
        raise AssertionError("A paused task must never construct an environment")

    monkeypatch.setattr(Trial, "create", unexpected_create)

    async def scenario():
        plugin = PauseOnRequestPlugin()
        await plugin.on_job_start(harbor_job)
        result = await harbor_job.run()
        await plugin.on_job_end(result)
        return result

    result = asyncio.run(scenario())
    assert len(result.trial_results) == 4
    assert all(r.exception_info.exception_type == CANCELLED_ERROR_TYPE for r in result.trial_results)
    assert all(r.started_at is None for r in result.trial_results)


def test_cancelled_filter_alias():
    from coding_agent_bench.api import ResumeJobRequest

    assert ResumeJobRequest(filter_error_types=["cancelled", "RuntimeError"]).filter_error_types == [
        CANCELLED_ERROR_TYPE, "RuntimeError",
    ]


@pytest.mark.parametrize("terminal,expected", [("Complete", True), ("Failed", False), (None, False)])
def test_cooperative_request_requires_successful_parent_completion(monkeypatch, terminal, expected):
    from coding_agent_bench.job import OpenshiftJob
    from coding_agent_bench.preemption import PAUSE_REQUEST_PATH

    calls = []

    async def oc(command, **_kwargs):
        calls.append(command)
        if command[0] == "get":
            return json.dumps({"items": [{
                "metadata": {"name": "parent"}, "status": {"phase": "Running"},
                "spec": {"containers": [{"env": [
                    {"name": "CAB_PAUSE_REQUEST_PATH", "value": PAUSE_REQUEST_PATH},
                ]}]},
            }]}), ""
        return "", ""

    async def get_job():
        return {"status": {"conditions": (
            [{"type": terminal, "status": "True"}] if terminal else []
        )}}

    job = OpenshiftJob("test")
    monkeypatch.setattr(job, "_run_oc_command", oc)
    monkeypatch.setattr(job, "_get_job", get_job)
    assert asyncio.run(job.request_pause("Nebius STOPPED", wait_seconds=0)) is expected
    assert [call[0] for call in calls] == ["get", "exec"]
    assert "kill" not in calls[1][-1]
    assert "Nebius STOPPED" in calls[1][-1]


def test_builder_enables_plugin_only_in_pause_capable_parent(monkeypatch):
    from coding_agent_bench.builder import HarborCommandBuilder

    builder = HarborCommandBuilder()
    kwargs = dict(agent="oracle", dataset="dataset", model="model", environment="openshift")
    monkeypatch.delenv("CAB_PAUSE_REQUEST_PATH", raising=False)
    assert PAUSE_PLUGIN not in builder._build_command(**kwargs)
    monkeypatch.setenv("CAB_PAUSE_REQUEST_PATH", "/tmp/pause.json")
    assert builder._build_command(**kwargs)[-2:] == ["--plugin", PAUSE_PLUGIN]
