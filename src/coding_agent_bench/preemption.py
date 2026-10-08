"""Cooperative Harbor trial cancellation for preempted model servers.

The queue service writes a request in the parent pod. This job plugin stops
Harbor's trial queue and persists CancelledError results even for trials that
never acquired a concurrency slot. No environment is constructed for them.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path

from harbor.models.trial.result import AgentInfo, ExceptionInfo, ModelInfo, TrialResult
from harbor.trial.hooks import TrialEvent, TrialHookEvent
from harbor.trial.queue import TrialQueue


PAUSE_REQUEST_PATH = "/tmp/cab-pause-request.json"
PAUSE_PLUGIN = "coding_agent_bench.preemption:PauseOnRequestPlugin"
CANCELLED_ERROR_TYPE = "CancelledError"
logger = logging.getLogger(__name__)


def _write_json(path: Path, value: dict) -> None:
    """Publish complete JSON files without exposing partially written results."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


class PausableTrialQueue(TrialQueue):
    """Gate scheduling and retries while allowing cancellation cleanup to finish.

    The adapter uses the queue and job internals of the Harbor revision pinned
    in uv.lock. Keep the integration tests when upgrading that dependency.
    """

    def __init__(self, job, request_path: Path):
        super().__init__(
            n_concurrent=job.config.n_concurrent_trials,
            retry_config=job.config.retry,
            hooks=job._trial_queue._hooks,
        )
        self.job = job
        self.request_path = request_path
        self.reason: str | None = None
        self._tasks: set[asyncio.Task] = set()
        self._locks: dict | None = None
        self._cancelled_names: set[str] = set()

    def check_pause(self) -> bool:
        """Latch a pause request and cancel existing workers exactly once."""
        if self.reason is not None:
            return True
        try:
            request = json.loads(self.request_path.read_text())
        except FileNotFoundError:
            return False
        self.reason = request["reason"]
        _write_json(self.job.job_dir / "preemption.json", {
            "state": "pausing", "reason": self.reason,
            "requested_at": request.get("requested_at"),
        })
        logger.warning("Pausing Harbor job: %s", self.reason)
        current = asyncio.current_task()
        for task in self._tasks:
            # Do not interrupt a trial's cleanup with a second cancellation.
            if task is not current and not task.done() and not task.cancelling():
                task.cancel(self.reason)
        return True

    def _should_retry_exception(self, exception_type: str) -> bool:
        if self.check_pause() or exception_type == CANCELLED_ERROR_TYPE:
            return False
        return super()._should_retry_exception(exception_type)

    async def _run_trial(self, trial_config) -> TrialResult:
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            if self.check_pause():
                return await self._cancelled_result(trial_config)
            async with self._semaphore:
                # Recheck after waiting: no new Trial/Pod may start after pause.
                if self.check_pause():
                    return await self._cancelled_result(trial_config)
                result = await self._execute_trial_with_retries(trial_config)
                if self.check_pause() and result.exception_info is not None:
                    return await self._cancelled_result(trial_config)
                return result
        except asyncio.CancelledError:
            if self.reason is None:
                raise  # Preserve normal Ctrl-C/service-cancellation semantics.
            return await self._cancelled_result(trial_config)
        finally:
            self._tasks.discard(task)

    async def _cancelled_result(self, config) -> TrialResult:
        """Save a resumable cancellation without constructing a Harbor Trial."""
        directory = config.trials_dir / config.trial_name
        result_path = directory / "result.json"
        existing = (
            TrialResult.model_validate_json(result_path.read_text())
            if result_path.exists() else None
        )
        if existing is not None and existing.finished_at is not None:
            if existing.exception_info is None:
                return existing  # A completed trial won the cancellation race.
            if existing.exception_info.exception_type == CANCELLED_ERROR_TYPE:
                self._cancelled_names.add(config.trial_name)
                return existing  # Harbor already persisted it and emitted END.

        if self._locks is None:
            self._locks = {
                trial.trial_name: lock
                for trial, lock in zip(
                    self.job._trial_configs, self.job._job_lock.trials, strict=True
                )
            }
        lock = self._locks[config.trial_name]
        now = datetime.now(timezone.utc)
        model = config.agent.model_name
        provider, _, model_name = (model or "").partition("/")
        result = existing or TrialResult(
            task_name=lock.task.name,
            trial_name=config.trial_name,
            trial_uri=directory.resolve().as_uri(),
            task_id=config.task.get_task_id(),
            source=config.task.source,
            task_checksum=lock.task.digest.removeprefix("sha256:"),
            config=config,
            agent_info=AgentInfo(
                name=config.agent.name or config.agent.import_path or "unknown",
                version=str(config.agent.kwargs.get("version", "unknown")),
                model_info=(ModelInfo(
                    name=model_name or provider,
                    provider=provider if model_name else None,
                ) if model else None),
            ),
        )
        result.exception_info = ExceptionInfo(
            exception_type=CANCELLED_ERROR_TYPE,
            exception_message=self.reason,
            exception_traceback="",
            occurred_at=now,
        )
        result.finished_at = now
        _write_json(directory / "config.json", config.model_dump(mode="json"))
        _write_json(directory / "lock.json", lock.model_dump(mode="json"))
        _write_json(result_path, result.model_dump(mode="json"))
        self._cancelled_names.add(config.trial_name)
        for event in (TrialEvent.CANCEL, TrialEvent.END):
            hook_event = TrialHookEvent(
                event=event, task_name=result.task_name, config=config,
                result=result, lock=lock,
            )
            for hook in self._hooks[event]:
                await hook(hook_event)
        return result


class PauseOnRequestPlugin:
    """Watch the parent pod's pause request through Harbor's job-plugin API."""

    async def on_job_start(self, job) -> None:
        path = Path(os.environ.get("CAB_PAUSE_REQUEST_PATH", PAUSE_REQUEST_PATH))
        self.queue = PausableTrialQueue(job, path)
        job._trial_queue = self.queue
        self.queue.check_pause()
        self._watcher = asyncio.create_task(self._watch(), name="cab-pause-watcher")

    async def _watch(self) -> None:
        while not self.queue.check_pause():
            await asyncio.sleep(0.5)

    async def on_job_end(self, job_result) -> None:
        self._watcher.cancel()
        try:
            await self._watcher
        except asyncio.CancelledError:
            pass
        if self.queue.reason is not None:
            _write_json(self.queue.job.job_dir / "preemption.json", {
                "state": "paused", "reason": self.queue.reason,
                "cancelled_error_type": CANCELLED_ERROR_TYPE,
                "cancelled_trials": sorted(self.queue._cancelled_names),
                "paused_at": datetime.now(timezone.utc).isoformat(),
            })
