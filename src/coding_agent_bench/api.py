from fastapi import APIRouter, Depends, FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator
from typing import NamedTuple, Optional

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from coding_agent_bench.builder import SupportedAgent, HarborCommandBuilder
from coding_agent_bench.intake.validation import validate_server_url
from coding_agent_bench.job import OpenshiftJob, _build_logged_shell_step
from coding_agent_bench.nebius_utils import NebiusInstanceManager, RESOURCE_CONFIG_REGISTRY
from coding_agent_bench.models import ModelConfig, MODEL_REGISTRY
from coding_agent_bench.utils import validate_remote_skill_sources
from coding_agent_bench.providers import is_openrouter, resolve_provider, OPENROUTER_UNSUPPORTED_AGENTS
from coding_agent_bench.agents import AGENT_REGISTRY
from coding_agent_bench.ui import build_submit_form_html
from coding_agent_bench import VERSION
from coding_agent_bench.preemption import CANCELLED_ERROR_TYPE, PAUSE_PLUGIN
from coding_agent_bench.resume import is_resume_command, resume_options, results_job_name

import getpass
import json
import os
import shlex
import sqlite3
import uuid
import html
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

class QueuedJob(NamedTuple):
    job_id: str
    command: list[str]
    server_url: str
    model_name: str
    adopt_existing: bool = False

_job_queue: list[QueuedJob] = []
_job_event = asyncio.Event()
_active_job: tuple[str, asyncio.Task] | None = None
_shutting_down = False
_nebius: "NebiusOrchestrator | None" = None

NEBIUS_PREFIX = "nebius-"


def _parse_nebius_url(server_url: str) -> str | None:
    """Return the resource config name if server_url is a nebius placeholder, else None."""
    if server_url.lower().startswith(NEBIUS_PREFIX):
        return server_url[len(NEBIUS_PREFIX):].lower()
    return None


def _worker_server_url_errors(
    server_url: str,
    managed_endpoint: bool = False,
) -> list[str]:
    """Revalidate a model endpoint immediately before creating its worker pod.

    Intake validation protects the queue boundary, while this second check closes
    the DNS-rebinding window between approval and execution. Managed Nebius
    instances are returned as public HTTP endpoints by the provider, so their
    generated IP endpoint is checked for public reachability without applying the
    normal HTTPS-only requirement.
    """
    if not server_url or server_url.lower() == "openrouter":
        return []
    if managed_endpoint:
        parsed = urlparse(server_url)
        if parsed.hostname is None:
            return ["Managed model endpoint has no hostname"]
        return validate_server_url(server_url, require_https=False)
    return validate_server_url(server_url)


db_path = Path(os.environ.get("JOB_STORE_PATH", "jobs.db"))

class InstancePreempted(Exception):
    """Raised when the Nebius instance backing a running job is lost mid-run.

    The affected job is paused (checkpointed to MinIO) and auto-resumed once
    Nebius is reachable again; it must never surface as user cancellation.
    """


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILING = "failing"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    PAUSING = "pausing"
    PAUSED = "paused"


NEBIUS_IDLE_TIMEOUT = int(os.environ.get("NEBIUS_IDLE_TIMEOUT_SECONDS", "600"))
CLEANUP_MAX_ATTEMPTS = int(os.environ.get("CLEANUP_MAX_ATTEMPTS", "120"))
CLEANUP_RETRY_INTERVAL_SECONDS = float(os.environ.get("CLEANUP_RETRY_INTERVAL_SECONDS", "5"))
MAX_PREEMPT_RESUMES = int(os.environ.get("MAX_PREEMPT_RESUMES", "3"))
PREEMPT_STABLE_SECONDS = int(os.environ.get("PREEMPT_STABLE_SECONDS", "90"))
PREEMPT_RESTART_ATTEMPTS = int(os.environ.get("PREEMPT_RESTART_ATTEMPTS", "10"))
PREEMPT_STABILIZE_ERROR_SECONDS = int(os.environ.get("PREEMPT_STABILIZE_ERROR_SECONDS", "120"))
PAUSED_POLL_INTERVAL_SECONDS = int(os.environ.get("PAUSED_POLL_INTERVAL_SECONDS", "60"))
PAUSE_UPLOAD_TIMEOUT_SECONDS = int(os.environ.get("PAUSE_UPLOAD_TIMEOUT_SECONDS", "600"))
NEBIUS_UNREACHABLE_TRIGGER_SECONDS = int(os.environ.get("NEBIUS_UNREACHABLE_TRIGGER_SECONDS", "300"))
NEBIUS_STOPPED_TRIGGER_SECONDS = int(os.environ.get("NEBIUS_STOPPED_TRIGGER_SECONDS", "45"))
# States no start call can bring back (idle cleanup deletes preempted VMs
# after NEBIUS_IDLE_TIMEOUT_SECONDS, leaving such records behind):
NEBIUS_UNRECOVERABLE_STATES = {"DELETED", "ERROR", "CRASHED"}


def _monotonic() -> float:
    """Monotonic clock seam (patchable in tests)."""
    return asyncio.get_running_loop().time()


# Monitor iterations run every 5s; probe Nebius state every Nth iteration.
DETECT_EVERY_N_POLLS = 3


@dataclass
class NebiusInstanceState:
    instance_name: str
    gpu_config: str
    current_model: str | None = None
    provisioning_model: str | None = None  # set while a model is being started/swapped
    job_running: bool = False
    last_job_completed_at: float | None = None


class NebiusOrchestrator:
    """Async wrapper around NebiusInstanceManager that tracks instance lifecycle.

    Manages a pool of Nebius GPU instances (currently one, designed for easy
    extension to multiple). Handles instance creation, model swapping, idle
    cleanup, and exposes state for the UI without making CLI calls.
    """

    def __init__(self, manager: NebiusInstanceManager, subnet_id: str,
                 instance_name_prefix: str, idle_timeout: int):
        """Initialize the in-memory Nebius instance lifecycle tracker."""
        self._manager = manager
        self._subnet_id = subnet_id
        self._prefix = instance_name_prefix
        self._idle_timeout = idle_timeout
        self._instances: dict[str, NebiusInstanceState] = {}
        self._lock = asyncio.Lock()

    def _pick_instance_name(self) -> str:
        """Return the name for the next instance. Currently single-instance."""
        return f"{self._prefix}-0"

    async def acquire_instance(self, model_name: str, gpu_config: str) -> tuple[str, str]:
        """
        Provision an instance with the requested model and return (instance_name, server_url).

        Creates the VM if it doesn't exist, starts it if stopped, and swaps
        the model if a different one is loaded. Skips steps that are already
        satisfied to minimize latency.
        """
        async with self._lock:
            # Reuse an existing instance with matching gpu_config, or create a new one.
            # Delete idle instances with the wrong gpu_config to free the slot.
            instance_name = None
            to_delete: list[str] = []
            for name, state in self._instances.items():
                if state.job_running:
                    continue
                if state.gpu_config == gpu_config:
                    instance_name = name
                    break
                else:
                    to_delete.append(name)

            for name in to_delete:
                logger.info(f"Deleting nebius instance {name} (gpu_config mismatch, had {self._instances[name].gpu_config}, need {gpu_config})")
                await self._manager.delete_instance(name)
                del self._instances[name]

            if instance_name is None:
                instance_name = self._pick_instance_name()

            # Create the instance if we haven't tracked it yet
            if instance_name not in self._instances:
                if await self._manager.instance_exists(instance_name):
                    logger.info(f"Deleting untracked nebius instance {instance_name} before reuse")
                    await self._manager.delete_instance(instance_name)
                logger.info(f"Creating nebius instance {instance_name} with {gpu_config}")
                await self._manager.create_instance(instance_name, self._subnet_id, gpu_config)
                self._instances[instance_name] = NebiusInstanceState(instance_name=instance_name, gpu_config=gpu_config, last_job_completed_at=time.time())

            # Start the instance (noop if already running)
            logger.info(f"Ensuring nebius instance {instance_name} is running")
            try:
                await self._manager.start_instance(instance_name)
            except Exception as e:
                if "not found" in str(e).lower() or "NotFound" in str(e):
                    logger.warning(f"Instance {instance_name} no longer exists, recreating")
                    del self._instances[instance_name]
                    await self._manager.create_instance(instance_name, self._subnet_id, gpu_config)
                    self._instances[instance_name] = NebiusInstanceState(instance_name=instance_name, gpu_config=gpu_config, last_job_completed_at=time.time())
                    await self._manager.start_instance(instance_name)
                else:
                    raise

            state = self._instances[instance_name]

            # Swap model if needed
            if state.current_model != model_name:
                state.provisioning_model = model_name
                try:
                    try:
                        logger.info(f"Stopping any running model on {instance_name}")
                        await self._manager.stop_model(instance_name)
                    except Exception:
                        logger.debug(f"stop_model failed on {instance_name} (may be expected)", exc_info=True)
                    logger.info(f"Starting model {model_name} on {instance_name}")
                    await self._manager.start_model(instance_name, model_name)
                    state.current_model = model_name
                except Exception:
                    state.current_model = None
                    raise
                finally:
                    state.provisioning_model = None

            # Fetch the public IP and build the server URL
            ip = await self._manager.get_instance_ip_address(instance_name)
            if ip and "/" in ip:
                ip = ip.split("/")[0]
            if not ip:
                raise RuntimeError(f"Instance {instance_name} has no public IP address")
            server_url = f"http://{ip}:8000"
            return instance_name, server_url

    async def mark_job_started(self, instance_name: str):
        """Mark a tracked Nebius instance as busy."""
        if instance_name not in self._instances:
            logger.warning(f"mark_job_started: instance {instance_name} already evicted")
            return
        self._instances[instance_name].job_running = True

    async def mark_job_completed(self, instance_name: str):
        """Mark a tracked Nebius instance idle after a job completes."""
        state = self._instances.get(instance_name)
        if state is None:
            logger.warning(f"mark_job_completed: instance {instance_name} already evicted")
            return
        state.job_running = False
        state.last_job_completed_at = time.time()

    async def adopt_running_instance(self, model_name: str, gpu_config: str) -> str:
        """Restore tracking for the deterministic instance used by a running job."""
        async with self._lock:
            instance_name = self._pick_instance_name()
            if not await self._manager.instance_exists(instance_name):
                raise RuntimeError(f"Nebius instance {instance_name} is missing for recovered job")
            self._instances[instance_name] = NebiusInstanceState(
                instance_name=instance_name,
                gpu_config=gpu_config,
                current_model=model_name,
                job_running=True,
            )
            return instance_name

    async def delete_recovered_instance(self) -> None:
        """Delete the deterministic VM left behind by an interrupted terminal transition."""
        async with self._lock:
            instance_name = self._pick_instance_name()
            if await self._manager.instance_exists(instance_name):
                logger.info(f"Deleting recovered nebius instance {instance_name}")
                await self._manager.delete_instance(instance_name)
            self._instances.pop(instance_name, None)

    async def mark_job_paused(self, instance_name: str):
        """Release a preempted instance: it is free again and its model died with it."""
        state = self._instances.get(instance_name)
        if state is None:
            return
        state.job_running = False
        state.current_model = None
        state.provisioning_model = None
        state.last_job_completed_at = time.time()

    async def adopt_paused_instance(self, model_name: str, gpu_config: str) -> str | None:
        """Track the deterministic instance left by a paused job.

        Returns the instance name when it exists in a startable state and
        belongs to the paused job's gpu_config without another job on it.
        Returns None when the instance is gone or sits in an unrecoverable
        state (e.g. DELETED after idle cleanup deleted the preempted VM):
        the caller then re-queues and the worker's acquire path deletes and
        recreates it. Raises when the Nebius API is unreachable so the
        caller keeps the job paused and retries on a later pass.
        """
        async with self._lock:
            instance_name = self._pick_instance_name()
            state = self._instances.get(instance_name)
            if state is not None and (state.job_running or state.gpu_config != gpu_config):
                return None
            try:
                remote = await self.get_instance_state(instance_name)
            except Exception as e:
                if "NotFound" in str(e):
                    logger.info(
                        f"Paused job's instance {instance_name} no longer exists; "
                        "worker will recreate it"
                    )
                    self._instances.pop(instance_name, None)
                    return None
                raise
            if remote in NEBIUS_UNRECOVERABLE_STATES:
                logger.warning(
                    f"Not adopting {instance_name} for paused recovery: state {remote} "
                    "cannot be started; worker will delete and recreate it"
                )
                self._instances.pop(instance_name, None)
                return None
            if state is None:
                self._instances[instance_name] = NebiusInstanceState(
                    instance_name=instance_name,
                    gpu_config=gpu_config,
                    current_model=None,
                    job_running=False,
                    last_job_completed_at=time.time(),
                )
            return instance_name

    async def recover_stopped_instance(self, instance_name: str) -> None:
        """Start a preempted instance and prove it survives the stabilization window.

        Raises RuntimeError after PREEMPT_RESTART_ATTEMPTS failed restarts so
        the caller keeps the job paused and retries on a later pass.
        """
        for attempt in range(1, PREEMPT_RESTART_ATTEMPTS + 1):
            try:
                await self._manager.start_instance(instance_name)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(
                    f"Preemption recovery: start of {instance_name} attempt "
                    f"{attempt}/{PREEMPT_RESTART_ATTEMPTS} failed: {e}"
                )
                await asyncio.sleep(30)
                continue
            # start_instance just ensures RUNNING (it may have issued the
            # start, found it already RUNNING, or waited out STARTING/
            # CREATING). Which of those happened is not the point: only the
            # stabilization window proves a preemptible machine will stay up,
            # so always run it.
            stable_since: float | None = None
            error_since: float | None = None
            while True:
                await asyncio.sleep(10)
                try:
                    details = await self._manager.get_instance(instance_name)
                    state = details.get("status", {}).get("state")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception(f"Preemption recovery: state check failed for {instance_name}")
                    if "NotFound" in str(e):
                        raise RuntimeError(
                            f"Instance {instance_name} disappeared while stabilizing"
                        ) from e
                    if error_since is None:
                        error_since = _monotonic()
                    if _monotonic() - error_since >= PREEMPT_STABILIZE_ERROR_SECONDS:
                        raise RuntimeError(
                            f"Instance {instance_name} state checks failed for "
                            f"{PREEMPT_STABILIZE_ERROR_SECONDS}s while stabilizing"
                        ) from e
                    stable_since = None
                    continue
                error_since = None
                if state == "RUNNING":
                    if stable_since is None:
                        stable_since = _monotonic()
                    if _monotonic() - stable_since >= PREEMPT_STABLE_SECONDS:
                        logger.info(f"Preemption recovery: {instance_name} stable RUNNING for {PREEMPT_STABLE_SECONDS}s")
                        return
                elif state in ("STOPPED", "STOPPING"):
                    logger.warning(
                        f"Preemption recovery: {instance_name} preempted again while stabilizing "
                        f"(attempt {attempt}/{PREEMPT_RESTART_ATTEMPTS})"
                    )
                    break
                else:
                    raise RuntimeError(f"Instance {instance_name} entered {state} while stabilizing")
            await asyncio.sleep(30)
        raise RuntimeError(
            f"Instance {instance_name} was preempted {PREEMPT_RESTART_ATTEMPTS} times during recovery"
        )

    def has_busy_instance(self) -> bool:
        """True when any tracked Nebius instance currently hosts a job."""
        return any(state.job_running for state in self._instances.values())

    async def get_instance_state(self, instance_name: str) -> str | None:
        """Return the lifecycle state (RUNNING/STOPPED/...) of an instance.

        Raises when the Nebius API call fails (an outage signal); returns
        None when the payload lacks a usable state (a shape anomaly, which
        is neither evidence of preemption nor of an outage).
        """
        details = await self._manager.get_instance(instance_name)
        return details.get("status", {}).get("state")

    async def idle_cleanup_loop(self):
        """Periodically delete idle instances and evict stale entries."""
        while True:
            await asyncio.sleep(60)
            try:
                async with self._lock:
                    now = time.time()
                    to_delete = [
                        name for name, s in self._instances.items()
                        if not s.job_running
                        and s.last_job_completed_at is not None
                        and (now - s.last_job_completed_at) > self._idle_timeout
                    ]
                    for name in to_delete:
                        logger.info(f"Deleting idle nebius instance {name}")
                        await self._manager.delete_instance(name)
                        del self._instances[name]

                    to_evict = []
                    for name, s in self._instances.items():
                        if s.job_running:
                            continue
                        if not await self._manager.instance_exists(name):
                            to_evict.append(name)
                    for name in to_evict:
                        logger.warning(f"Evicting stale nebius instance {name} (no longer exists)")
                        del self._instances[name]
            except Exception:
                logger.exception("Nebius idle cleanup failed")

    def get_instance_states(self) -> list[NebiusInstanceState]:
        """Return current state of all managed instances (in-memory, no CLI calls)."""
        return list(self._instances.values())


class CreateJobRequest(BaseModel):
    job_name: str = Field(..., description="Name to give the job")
    agent: SupportedAgent = Field(..., description="Agent to use")
    dataset: str = Field(..., description="Dataset name or path")
    model_name: str = Field(..., description="Model name")
    server_url: str = Field(..., description="Model server URL; 'nebius-<resource>' (e.g. nebius-h200) for managed Nebius instances; or 'openrouter' to use OpenRouter (requires OPENROUTER_API_KEY on the server)")
    dataset_pattern: Optional[str] = Field(None, description="Pattern to filter dataset tasks")
    n_concurrent: int | None = Field(None, description="Number of concurrent tasks")
    n_tasks: Optional[int] = Field(None, description="Total number of tasks to run")
    model_max_len: int | None = Field(None, description="Maximum model context length in tokens")
    before_script: Optional[str] = Field(None, description="Script to run before harbor job execution")
    agent_version: Optional[str] = Field(None, description="Pin agent to a specific version (overrides default)")
    max_retries: Optional[int] = Field(None, description="Max retry attempts per task (default: 1)")
    retry_include: Optional[list[str]] = Field(None, description="Error types to retry (default: AgentTimeoutError, NonZeroAgentExitCodeError, ApiRateLimitError, ApiUsageLimitError)")
    skills: list[str] = Field(
        default_factory=list,
        description="Public Git skill sources in org/name[@ref] or HTTP(S) URL form",
    )
    idempotency_key: Optional[str] = Field(
        None,
        max_length=256,
        description="Stable key used to safely retry creation of the same job",
    )


class ResumeJobRequest(BaseModel):
    filter_error_types: list[str] = Field(
        default_factory=list,
        description="Error types to retry. 'cancelled' maps to CancelledError; empty uses Harbor's cancellation default.",
    )
    server_url: Optional[str] = Field(None, description="New model server URL (replaces old URL across all job files)")

    @field_validator("filter_error_types")
    @classmethod
    def normalize_cancelled_filter(cls, values: list[str]) -> list[str]:
        """Map the human-facing cancellation filter to Harbor's exception name."""
        return [
            CANCELLED_ERROR_TYPE if value.strip().lower() in {"cancelled", "canceled", "cancellederror"}
            else value for value in values
        ]


class CreateJobResponse(BaseModel):
    message: str
    job_id: str
    job_name: str
    command: list[str]


class JobResponse(BaseModel):
    job_id: str
    job_name: str
    agent: str
    dataset: str
    model_name: str
    server_url: str
    command: str
    status: JobStatus
    error: str | None = None
    idempotency_key: str | None = None
    results_job_name: str | None = None


class JobStore:
    def __init__(self, db_path: Path):
        """Initialize."""
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Connect to the database."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the job tracking table."""
        conn = self._connect()
        conn.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                job_name TEXT NOT NULL,
                agent TEXT NOT NULL,
                dataset TEXT NOT NULL,
                model_name TEXT NOT NULL,
                server_url TEXT NOT NULL DEFAULT '',
                command TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                error TEXT,
                idempotency_key TEXT,
                preempt_attempts INTEGER NOT NULL DEFAULT 0,
                pause_checkpointed INTEGER NOT NULL DEFAULT 0,
                results_job_name TEXT
            )"""
        )
        # Migrate columns when upgrading from an older schema.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "server_url" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN server_url TEXT NOT NULL DEFAULT ''")
        if "idempotency_key" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN idempotency_key TEXT")
        if "preempt_attempts" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN preempt_attempts INTEGER NOT NULL DEFAULT 0")
        if "pause_checkpointed" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN pause_checkpointed INTEGER NOT NULL DEFAULT 0")
        if "results_job_name" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN results_job_name TEXT")
        # Legacy resume commands retain the real artifact path even when their
        # display names have acquired one or more --resume suffixes.
        for row in conn.execute(
            "SELECT job_id, job_name, command FROM jobs WHERE results_job_name IS NULL"
        ).fetchall():
            conn.execute(
                "UPDATE jobs SET results_job_name = ? WHERE job_id = ?",
                (results_job_name(dict(row)), row["job_id"]),
            )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency_key "
            "ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL"
        )
        conn.commit()
        conn.close()

    def insert(
        self,
        job_id: str,
        job_name: str,
        agent: str,
        dataset: str,
        model_name: str,
        server_url: str,
        command: list[str],
        idempotency_key: str | None = None,
        results_job_name: str | None = None,
    ):
        """Add a new job to the tracking table."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO jobs "
                "(job_id, job_name, agent, dataset, model_name, server_url, command, status, idempotency_key, results_job_name) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    job_name,
                    agent,
                    dataset,
                    model_name,
                    server_url,
                    json.dumps(command),
                    JobStatus.QUEUED.value,
                    idempotency_key,
                    results_job_name or job_name,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def update_status(self, job_id: str, status: JobStatus, error: str | None = None):
        """Update the status of a job."""
        conn = self._connect()
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, "
            "pause_checkpointed = CASE WHEN ? = 'running' THEN 0 ELSE pause_checkpointed END "
            "WHERE job_id = ?",
            (status.value, error, status.value, job_id),
        )
        conn.commit()
        conn.close()

    def update_status_if(
        self,
        job_id: str,
        expected: JobStatus,
        status: JobStatus,
        error: str | None = None,
    ) -> bool:
        """Update status only while the job still has the expected status.

        Guards race-prone transitions (pause, requeue) from overwriting a
        concurrent terminal write such as a user cancellation.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE jobs SET status = ?, error = ? WHERE job_id = ? AND status = ?",
                (status.value, error, job_id, expected.value),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def resume_paused(
        self, job_id: str, command: list[str], server_url: str, artifact_name: str,
    ) -> bool:
        """Claim an existing paused row atomically against automatic recovery."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE jobs SET status = ?, command = ?, server_url = ?, "
                "results_job_name = ?, error = ? WHERE job_id = ? AND status = ?",
                (
                    JobStatus.QUEUED.value, json.dumps(command), server_url,
                    artifact_name, "Manual resume requested", job_id, JobStatus.PAUSED.value,
                ),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get(self, job_id: str) -> dict | None:
        """Get a job by id."""
        conn = self._connect()
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        """Return the job previously created with an idempotency key, if any."""
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM jobs WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def list(self, status: JobStatus | None = None) -> list[dict]:
        """List all jobs."""
        conn = self._connect()
        if status:
            rows = conn.execute("SELECT * FROM jobs WHERE status = ? ORDER BY rowid", (status.value,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM jobs ORDER BY rowid").fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def list_recoverable(self) -> "list[dict]":
        """List non-terminal jobs in their original enqueue order."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status IN (?, ?, ?, ?, ?, ?) ORDER BY rowid",
            (
                JobStatus.QUEUED.value,
                JobStatus.RUNNING.value,
                JobStatus.COMPLETING.value,
                JobStatus.FAILING.value,
                JobStatus.CANCELLING.value,
                JobStatus.PAUSING.value,
            ),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def list_paused(self) -> "list[dict]":
        """List preempted jobs parked and waiting for Nebius, in enqueue order."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY rowid",
            (JobStatus.PAUSED.value,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def list_pausing(self) -> "list[dict]":
        """Return checkpoints that need another non-destructive completion attempt."""
        return self.list(JobStatus.PAUSING)

    def mark_pause_checkpointed(self, job_id: str) -> bool:
        """Persist successful upload before deleting the parent workload."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE jobs SET pause_checkpointed = 1 WHERE job_id = ? AND status = ?",
                (job_id, JobStatus.PAUSING.value),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def pause_commit(
        self,
        job_id: str,
        command: "list[str]",
        attempts: int,
        error: str,
    ) -> bool:
        """Atomically park a job as paused with its rebuilt resume command.

        Only succeeds while the job is still in `pausing`, so a stale
        finalize can never resurrect a job that was cancelled meanwhile.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE jobs SET command = ?, status = ?, preempt_attempts = ?, error = ? "
                "WHERE job_id = ? AND status = ? AND pause_checkpointed = 1",
                (
                    json.dumps(command),
                    JobStatus.PAUSED.value,
                    attempts,
                    error,
                    job_id,
                    JobStatus.PAUSING.value,
                ),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


job_store = JobStore(db_path)

_api_key_header = APIKeyHeader(name="X-API-Key")


async def _verify_api_key(key: str = Depends(_api_key_header)) -> str:
    """Validate the API key supplied with an authenticated queue request."""
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="API_KEY not configured")
    if key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start queue workers and cleanly stop them with the FastAPI application."""
    global _shutting_down, _nebius
    _shutting_down = False

    # Initialize Nebius orchestrator if enabled
    background_tasks: list[asyncio.Task] = []
    if os.environ.get("NEBIUS_ENABLED") == "1":
        manager = NebiusInstanceManager(
            credentials_path=os.environ.get("NEBIUS_SERVICE_ACCOUNT_CREDS_PATH"),
            credentials=os.environ.get("NEBIUS_SERVICE_ACCOUNT_CREDS"),
            user=os.environ.get("NEBIUS_USER", getpass.getuser()),
            ssh_public_key_path=os.environ["NEBIUS_SSH_PUBLIC_KEY_PATH"],
            ssh_private_key_path=os.environ["NEBIUS_SSH_PRIVATE_KEY_PATH"],
            parent_id=os.environ["NEBIUS_PARENT_ID"],
            tenant_id=os.environ["NEBIUS_TENANT_ID"],
            service_account_id=os.environ["NEBIUS_SERVICE_ACCOUNT_ID"],
        )
        await manager.init()
        _nebius = NebiusOrchestrator(
            manager=manager,
            subnet_id=os.environ["NEBIUS_SUBNET_ID"],
            instance_name_prefix=os.environ.get("NEBIUS_INSTANCE_NAME_PREFIX", "cab-worker"),
            idle_timeout=NEBIUS_IDLE_TIMEOUT,
        )
        background_tasks.append(asyncio.create_task(_nebius.idle_cleanup_loop()))
        logger.info("Nebius orchestrator initialized")

    has_recoverable_nebius = await _restore_jobs()
    if _nebius is not None and not has_recoverable_nebius:
        background_tasks.append(asyncio.create_task(_delete_recovered_nebius("startup")))
    if _nebius is not None:
        background_tasks.append(asyncio.create_task(_resume_paused_jobs_loop()))
    worker_task = asyncio.create_task(_worker())
    cleanup_task = asyncio.create_task(_build_pod_cleanup_loop())
    yield
    _shutting_down = True
    worker_task.cancel()
    cleanup_task.cancel()
    for t in background_tasks:
        t.cancel()
    for task in (worker_task, cleanup_task, *background_tasks):
        try:
            await task
        except asyncio.CancelledError:
            pass
    # Do not delete Nebius instances here: OpenShift jobs survive queue restarts
    # and the next queue process must be able to adopt their deterministic VM.
    # Permanent decommissioning therefore requires external instance cleanup.


app = FastAPI(lifespan=lifespan)
router = APIRouter(dependencies=[Depends(_verify_api_key)])

# Public UI router (no API key required)
ui_router = APIRouter()


async def _run_oc(command: list[str], timeout_sec: int = 30) -> str:
    """Run an oc command with timeout and process-kill handling."""
    process = await asyncio.create_subprocess_exec(
        "oc", *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, _ = await asyncio.wait_for(
            process.communicate(), timeout=timeout_sec
        )
    except (asyncio.TimeoutError, asyncio.CancelledError):
        process.terminate()
        try:
            await asyncio.wait_for(process.communicate(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
        raise
    return stdout_bytes.decode() if stdout_bytes else ""


async def _build_pod_cleanup_loop():
    """Periodically delete completed/failed build pods from the namespace."""
    while True:
        await asyncio.sleep(300)
        try:
            for phase in ("Succeeded", "Failed"):
                stdout = await _run_oc([
                    "get", "pods",
                    "-l", "openshift.io/build.name",
                    f"--field-selector=status.phase=={phase}",
                    "-o", "jsonpath={.items[*].metadata.name}",
                ])
                pods = stdout.split() if stdout.strip() else []
                if pods:
                    await _run_oc(["delete", "pods", *pods, "--ignore-not-found"])
        except Exception:
            logger.exception("Build pod cleanup failed")


async def _resume_paused_jobs_loop():
    """Park-and-wait engine for preempted jobs: restart the VM, then re-queue.

    Waits for Nebius to be reachable again indefinitely; the resume budget
    only counts actual mid-run preemptions. Flipping a row to queued defers
    full re-provisioning (recreate if needed, vLLM start, new-IP rewrite) to
    the worker's normal acquire path.
    """
    while True:
        await asyncio.sleep(PAUSED_POLL_INTERVAL_SECONDS)
        if _nebius is None or _shutting_down:
            continue
        if _active_job is not None:
            continue  # never fight the serial queue for the shared instance
        try:
            # A slow/failed upload must not be turned into a resumable checkpoint.
            # Revisit retained parents after the worker's bounded wait expires.
            for pending in job_store.list_pausing():
                await _pause_commit(
                    pending["job_id"], OpenshiftJob(pending["job_id"])
                )
            rows = job_store.list_paused()
        except Exception:
            logger.exception("Paused job scan failed")
            continue
        for row in rows:
            gpu = _parse_nebius_url(row["server_url"])
            if gpu is None:
                logger.warning(
                    f"Paused job {row['job_id']} has no Nebius server URL; re-queuing for normal handling"
                )
                if job_store.update_status_if(
                    row["job_id"], JobStatus.PAUSED, JobStatus.QUEUED, error=row["error"]
                ):
                    _job_queue.append(QueuedJob(
                        row["job_id"],
                        json.loads(row["command"]),
                        row["server_url"],
                        row["model_name"],
                    ))
                    _job_event.set()
                continue
            # Note: has_busy_instance()/recovery vs. a concurrent worker
            # acquire on the same shared instance is a benign TOCTOU: the
            # serial queue means the worst case is a redundant start call
            # (idempotent when RUNNING) or one wasted model swap.
            if _nebius.has_busy_instance():
                continue
            try:
                instance_name = await _nebius.adopt_paused_instance(row["model_name"], gpu)
                if instance_name is not None:
                    if _active_job is not None:
                        continue
                    await _nebius.recover_stopped_instance(instance_name)
                attempt_note = f" (attempt {int(row.get('preempt_attempts') or 0)}/{MAX_PREEMPT_RESUMES})" if MAX_PREEMPT_RESUMES else ""
                outcome_note = (
                    "VM recovered — resuming"
                    if instance_name is not None
                    else "instance unavailable — worker will recreate"
                )
                # Recovery may take minutes: a cancellation that landed in the
                # meantime must win, so re-enter the queue only if still paused.
                if not job_store.update_status_if(
                    row["job_id"],
                    JobStatus.PAUSED,
                    JobStatus.QUEUED,
                    error=f"{outcome_note}{attempt_note}",
                ):
                    logger.info(
                        f"Paused job {row['job_id']} left the paused state during recovery; not re-queuing"
                    )
                    break
                # Flipping the DB row is not dispatch: the original QueuedJob
                # entry was popped before the job ever ran, so the row must be
                # re-added to the in-memory queue for the worker to pick it up.
                _job_queue.append(QueuedJob(
                    row["job_id"],
                    json.loads(row["command"]),
                    row["server_url"],
                    row["model_name"],
                ))
                _job_event.set()
                logger.info(f"Re-queued paused job {row['job_id']}")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    f"Nebius still unavailable for paused job {row['job_id']}; retrying next pass"
                )
            break  # one paused job per pass: the shared VM makes serial order matter


async def _best_effort_cleanup(oj: OpenshiftJob, signal: bool = False) -> str | None:
    """Run signal/delete cleanup, returning an error string on failure or None."""
    errors: list[str] = []
    if signal:
        try:
            await oj._signal_job_pod()
        except Exception as e:
            errors.append(f"signal failed: {e}")
    try:
        await oj._delete_job()
    except Exception as e:
        errors.append(f"delete failed: {e}")
    return "; ".join(errors) if errors else None


async def _finish_cancellation(job_id: str, oj: OpenshiftJob, signal: bool) -> bool:
    """Complete cancellation, leaving it recoverable when cleanup fails."""
    cleanup_err = await _best_effort_cleanup(oj, signal=signal)
    if cleanup_err:
        job_store.update_status(job_id, JobStatus.CANCELLING, error=f"cleanup failed: {cleanup_err}")
        return False
    job_store.update_status(job_id, JobStatus.CANCELLED)
    return True


async def _retry_cancellation(job_id: str, oj: OpenshiftJob) -> None:
    """Retry cancellation cleanup without blocking the serial queue forever."""
    for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
        if job_store.get(job_id)["status"] != JobStatus.CANCELLING.value:
            return
        await asyncio.sleep(CLEANUP_RETRY_INTERVAL_SECONDS)
        try:
            existing = await oj._get_job()
            await _finish_cancellation(job_id, oj, signal=existing is not None)
        except Exception:
            logger.exception(f"Cancellation cleanup retry failed for {job_id}")
        if job_store.get(job_id)["status"] != JobStatus.CANCELLING.value:
            return
        logger.warning(
            f"Cancellation cleanup attempt {attempt}/{CLEANUP_MAX_ATTEMPTS} failed for {job_id}"
        )

    row = job_store.get(job_id)
    logger.error(f"Cancellation cleanup exhausted for {job_id}; advancing the queue")
    job_store.update_status(job_id, JobStatus.CANCELLED, error=row["error"])


def _terminal_error(error: str | None) -> str | None:
    """Remove a prior cleanup suffix before retrying terminal cleanup."""
    if not error or error.startswith("cleanup failed:"):
        return None
    return error.split("; cleanup failed:", 1)[0]


async def _finish_terminal_job(
    job_id: str,
    oj: OpenshiftJob,
    final_status: JobStatus,
    error: str | None = None,
) -> bool:
    """Delete parent and child workloads before recording a terminal status."""
    pending_status = JobStatus.COMPLETING if final_status == JobStatus.COMPLETED else JobStatus.FAILING
    base_error = _terminal_error(error)
    job_store.update_status(job_id, pending_status, error=base_error)
    cleanup_err = await _best_effort_cleanup(oj)
    if cleanup_err:
        combined_error = f"cleanup failed: {cleanup_err}"
        if base_error:
            combined_error = f"{base_error}; {combined_error}"
        job_store.update_status(job_id, pending_status, error=combined_error)
        return False
    job_store.update_status(job_id, final_status, error=base_error)
    return True


async def _retry_terminal_job(
    job_id: str,
    oj: OpenshiftJob,
    final_status: JobStatus,
    error: str | None = None,
) -> None:
    """Retry terminal cleanup without blocking the serial queue forever."""
    for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
        if await _finish_terminal_job(job_id, oj, final_status, error=error):
            return
        logger.warning(
            f"Terminal cleanup attempt {attempt}/{CLEANUP_MAX_ATTEMPTS} failed for {job_id}"
        )
        if attempt < CLEANUP_MAX_ATTEMPTS:
            await asyncio.sleep(CLEANUP_RETRY_INTERVAL_SECONDS)

    row = job_store.get(job_id)
    logger.error(f"Terminal cleanup exhausted for {job_id}; advancing the queue")
    job_store.update_status(job_id, final_status, error=row["error"])


async def _delete_recovered_nebius(job_id: str) -> None:
    """Retry deletion without blocking recovery forever."""
    assert _nebius is not None
    for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
        try:
            await _nebius.delete_recovered_instance()
            return
        except Exception:
            logger.exception(
                f"Unable to delete recovered Nebius instance for {job_id} "
                f"(attempt {attempt}/{CLEANUP_MAX_ATTEMPTS})"
            )
            if attempt < CLEANUP_MAX_ATTEMPTS:
                await asyncio.sleep(CLEANUP_RETRY_INTERVAL_SECONDS)

    logger.error(f"Nebius cleanup exhausted for {job_id}; advancing recovery")


def _build_pause_resume_command(row: dict) -> list[str]:
    """Build the in-row resume command that re-runs a preempted job from MinIO.

    An explicit nebius placeholder as server_url makes the worker re-provision
    the instance and inject the URL rewrite for the new IP at run time.
    """
    attempts = int(row.get("preempt_attempts") or 0)
    original_name = results_job_name(row)
    server_url = row.get("server_url") or ""
    staging_id = f"{row['job_id']}-p{attempts}"
    shell_command = _build_resume_shell_command(
        original_name,
        staging_id,
        [CANCELLED_ERROR_TYPE],
        server_url if _parse_nebius_url(server_url) is None else None,
    )
    return ["bash", "-c", shell_command]


async def _pause_commit(job_id: str, oj: OpenshiftJob) -> bool:
    """Park only after cooperative cancellation and a confirmed checkpoint.

    A timeout, failed upload, or missing parent leaves the row pausing and
    retains local artifacts. The successful-upload bit survives a queue crash
    between deleting the parent and committing the paused row.
    """
    row = job_store.get(job_id)
    if not row or row["status"] != JobStatus.PAUSING.value:
        return True

    existing = None
    for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
        try:
            existing = await oj._get_job()
            break
        except Exception:
            logger.exception(
                f"Unable to inspect OpenShift Job for paused job {job_id} "
                f"(attempt {attempt}/{CLEANUP_MAX_ATTEMPTS})"
            )
            if attempt == CLEANUP_MAX_ATTEMPTS:
                return False
            await asyncio.sleep(CLEANUP_RETRY_INTERVAL_SECONDS)

    if not row.get("pause_checkpointed"):
        conditions = {
            condition.get("type")
            for condition in (existing or {}).get("status", {}).get("conditions", [])
            if condition.get("status") == "True"
        }
        checkpointed = "Complete" in conditions
        if existing is not None and not conditions.intersection({"Complete", "Failed"}):
            try:
                checkpointed = await oj.request_pause(
                    row.get("error") or "Nebius model server was preempted",
                    wait_seconds=PAUSE_UPLOAD_TIMEOUT_SECONDS,
                )
            except Exception:
                logger.exception("Cooperative pause request failed for %s", job_id)
        if not checkpointed:
            job_store.update_status_if(
                job_id, JobStatus.PAUSING, JobStatus.PAUSING,
                error="VM preempted; checkpoint not confirmed; parent Job retained for recovery",
            )
            return False
        if not job_store.mark_pause_checkpointed(job_id):
            return True  # A concurrent status transition won.

    try:
        await oj._delete_job()
    except Exception as e:
        job_store.update_status_if(
            job_id,
            JobStatus.PAUSING,
            JobStatus.PAUSING,
            error=f"pause cleanup failed: {e}",
        )
        return False

    attempts = int(row.get("preempt_attempts") or 0) + 1
    attempt_note = f" (attempt {attempts}/{MAX_PREEMPT_RESUMES})" if MAX_PREEMPT_RESUMES else ""
    parked = job_store.pause_commit(
        job_id,
        _build_pause_resume_command(row),
        attempts,
        f"VM preempted — awaiting Nebius recovery{attempt_note}",
    )
    if not parked:
        logger.info(f"Job {job_id} left the pausing state during finalize; skipping park")
    elif MAX_PREEMPT_RESUMES > 0 and attempts > MAX_PREEMPT_RESUMES:
        # Exhausting automatic retries must not skip cancellation/checkpointing.
        job_store.update_status_if(
            job_id, JobStatus.PAUSED, JobStatus.FAILED,
            error=f"VM preempted repeatedly; exhausted {MAX_PREEMPT_RESUMES} auto-resume attempts; checkpoint saved for manual resume",
        )
    return parked


async def _retry_pause_finalize(job_id: str, oj: OpenshiftJob) -> None:
    """Retry pause checkpointing without blocking the serial queue forever."""
    for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
        if await _pause_commit(job_id, oj):
            return
        row = job_store.get(job_id)
        if row and not row.get("pause_checkpointed"):
            return  # Let the background loop revisit the retained parent later.
        logger.warning(
            f"Pause finalize attempt {attempt}/{CLEANUP_MAX_ATTEMPTS} failed for {job_id}"
        )
        if attempt < CLEANUP_MAX_ATTEMPTS:
            await asyncio.sleep(CLEANUP_RETRY_INTERVAL_SECONDS)

    row = job_store.get(job_id)
    logger.error(f"Pause finalize exhausted for {job_id}; retaining parent and pausing state")
    if row and row["status"] == JobStatus.PAUSING.value:
        job_store.update_status_if(
            job_id, JobStatus.PAUSING, JobStatus.PAUSING,
            error="VM preempted; cleanup failure; parent retained and automatic resume deferred",
        )


async def _handle_pause(job_id: str, oj: OpenshiftJob, nebius_instance_name: str | None) -> None:
    """Pause a running job whose Nebius VM was lost, resuming it automatically later."""
    row = job_store.get(job_id)
    if not row:
        return
    attempts = int(row.get("preempt_attempts") or 0)
    if not job_store.update_status_if(
        job_id,
        JobStatus.RUNNING,
        JobStatus.PAUSING,
        error=f"VM preempted — checkpointing results to MinIO (attempt {attempts + 1}/{MAX_PREEMPT_RESUMES})",
    ):
        logger.info(f"Job {job_id} left running before pause could start; skipping pause")
        return
    if nebius_instance_name and _nebius:
        await _nebius.mark_job_paused(nebius_instance_name)
    await _retry_pause_finalize(job_id, oj)


async def _restore_jobs() -> bool:
    """Rebuild the dispatcher without making startup depend on OpenShift."""
    _job_event.clear()
    _job_queue.clear()
    has_recoverable_nebius = False
    for row in job_store.list_recoverable():
        has_recoverable_nebius |= _parse_nebius_url(row["server_url"]) is not None
        _job_queue.append(QueuedJob(
            row["job_id"],
            json.loads(row["command"]),
            row["server_url"],
            row["model_name"],
            adopt_existing=True,
        ))
    if _job_queue:
        logger.info(f"Recovered {len(_job_queue)} non-terminal jobs")
        _job_event.set()
    if not has_recoverable_nebius:
        # A paused job intentionally owns the stopped VM until recovery. Do
        # not let startup cleanup delete that VM and its warm model cache.
        has_recoverable_nebius = any(
            _parse_nebius_url(row["server_url"]) is not None
            for row in job_store.list_paused()
        )
    return has_recoverable_nebius

async def _run_job(
    job_id: str,
    command: list[str],
    server_url: str | None = None,
    managed_endpoint: bool = False,
    openrouter: bool = False,
    adopt_existing: bool = False,
    nebius_instance_name: str | None = None,
):
    """Validate, run, and monitor an OpenShift Job."""
    if server_url:
        server_url_errors = _worker_server_url_errors(
            server_url,
            managed_endpoint=managed_endpoint,
        )
        if server_url_errors:
            job_store.update_status(
                job_id,
                JobStatus.FAILED,
                error="Server URL validation failed: " + "; ".join(server_url_errors),
            )
            return

    oj = OpenshiftJob(job_name=job_id, clean_legacy_pods=adopt_existing)

    try:
        if not adopt_existing:
            is_resume = is_resume_command(command)
            if is_resume:
                job_spec = oj._resume_job_spec(command[2])
            else:
                job_spec = oj._job_spec(command, openrouter=openrouter)
            await oj._run_oc_command(
                ["apply", "-f", "-"],
                stdin_data=json.dumps(job_spec).encode(),
            )
            job_store.update_status(job_id, JobStatus.RUNNING)
            await oj._wait_for_job_pod_ready()
        else:
            if job_store.get(job_id)["status"] == JobStatus.QUEUED.value:
                job_store.update_status(job_id, JobStatus.RUNNING)
            for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
                try:
                    existing = await oj._get_job()
                    break
                except Exception:
                    logger.exception(
                        f"Unable to inspect recovered OpenShift Job {job_id} "
                        f"(attempt {attempt}/{CLEANUP_MAX_ATTEMPTS})"
                    )
                    if attempt == CLEANUP_MAX_ATTEMPTS:
                        raise
                    await asyncio.sleep(CLEANUP_RETRY_INTERVAL_SECONDS)
            conditions = {
                condition.get("type")
                for condition in (existing or {}).get("status", {}).get("conditions", [])
                if condition.get("status") == "True"
            }
            if not conditions.intersection({"Complete", "Failed"}):
                await oj._wait_for_job_pod_ready()

        consecutive_missing = 0
        max_missing = 6  # 6 polls × 5s = 30s before declaring pod gone
        poll_count = 0
        first_stopped_at: float | None = None
        first_unreachable_at: float | None = None
        last_error_note: str | None = None
        stopped_threshold = (
            float(NEBIUS_STOPPED_TRIGGER_SECONDS)
            if nebius_instance_name and not _shutting_down
            else float("inf")
        )
        error_threshold = (
            float(NEBIUS_UNREACHABLE_TRIGGER_SECONDS)
            if nebius_instance_name and not _shutting_down
            else float("inf")
        )

        while True:
            try:
                job = await oj._get_job()
            except Exception:
                logger.exception(f"Unable to query OpenShift Job for {job_id}; monitoring will retry")
                await asyncio.sleep(5)
                continue
            if job is None:
                consecutive_missing += 1
                if consecutive_missing >= max_missing:
                    await _retry_terminal_job(
                        job_id,
                        oj,
                        JobStatus.FAILED,
                        error="OpenShift Job vanished (likely deleted externally)",
                    )
                    return
                await asyncio.sleep(5)
                continue

            consecutive_missing = 0
            conditions = {
                condition.get("type"): condition
                for condition in job.get("status", {}).get("conditions", [])
                if condition.get("status") == "True"
            }
            if "Complete" in conditions:
                await _retry_terminal_job(job_id, oj, JobStatus.COMPLETED)
                return
            if "Failed" in conditions:
                reason = conditions["Failed"].get("reason", "")
                message = conditions["Failed"].get("message", "")
                error = f"Failed: reason={reason}, message={message}"
                await _retry_terminal_job(job_id, oj, JobStatus.FAILED, error=error)
                return

            # Nebius preemption detection: the queue's only view of the model
            # endpoint's health. Harbor's own connection errors are invisible
            # here, and an on-preemption-stopped instance keeps answering
            # get-by-name with state STOPPED — no error fires. Sampled every
            # DETECT_EVERY_N_POLLS monitor iterations; trigger thresholds are
            # measured on the monotonic clock, not by counting samples.
            poll_count += 1
            if (
                nebius_instance_name
                and _nebius is not None
                and not _shutting_down
                and poll_count % DETECT_EVERY_N_POLLS == 0
            ):
                now = _monotonic()
                try:
                    state = await _nebius.get_instance_state(nebius_instance_name)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    last_error_note = str(e).splitlines()[0][:200] if str(e) else e.__class__.__name__
                    first_stopped_at = None
                    if first_unreachable_at is None:
                        first_unreachable_at = now
                    if now - first_unreachable_at >= error_threshold:
                        raise InstancePreempted(
                            f"Nebius API unreachable for {nebius_instance_name} "
                            f"(last error: {last_error_note})"
                        ) from e
                else:
                    if state in ("STOPPED", "STOPPING", "DELETED", "ERROR", "CRASHED"):
                        first_unreachable_at = None
                        last_error_note = None
                        if first_stopped_at is None:
                            first_stopped_at = now
                        if now - first_stopped_at >= stopped_threshold:
                            raise InstancePreempted(
                                f"Nebius instance {nebius_instance_name} is {state}"
                            )
                    elif state is None:
                        # A response without a usable state is an observation
                        # failure, not evidence the VM stopped: the longer
                        # unavailability threshold keeps a CLI/API payload
                        # regression from mass-pausing healthy runs in 45s.
                        first_stopped_at = None
                        if first_unreachable_at is None:
                            first_unreachable_at = now
                        if now - first_unreachable_at >= error_threshold:
                            raise InstancePreempted(
                                f"Nebius instance {nebius_instance_name} reports no usable state"
                            )
                    else:
                        last_error_note = None
                        first_stopped_at = None
                        first_unreachable_at = None

            await asyncio.sleep(5)

    except asyncio.CancelledError:
        if _shutting_down:
            raise
        await _finish_cancellation(job_id, oj, signal=True)
        raise

    except InstancePreempted:
        raise

    except Exception as e:
        error = str(e)
        await _retry_terminal_job(job_id, oj, JobStatus.FAILED, error=error)


def _reorder_queue_for_nebius():
    """Stable-sort the queue so nebius jobs that can reuse the current instance
    come first. Priority: same gpu+model (free) > same gpu (model swap) >
    different gpu (instance recreate). Non-nebius jobs keep their position."""
    if not _nebius:
        return
    states = _nebius.get_instance_states()
    if not states:
        return
    current_gpu = states[0].gpu_config
    current_model = states[0].current_model

    def _sort_key(item: QueuedJob):
        if item.adopt_existing:
            return -1
        gpu = _parse_nebius_url(item.server_url)
        if gpu is None:
            return 0  # non-nebius, keep in place
        if gpu == current_gpu and item.model_name == current_model:
            return 0  # free reuse
        if gpu == current_gpu:
            return 1  # model swap only
        return 2  # instance recreate

    _job_queue.sort(key=_sort_key)


async def _process_queued_job(queued: QueuedJob) -> None:
    """Provision or adopt one queued job without risking the dispatcher task."""
    job_id, command, server_url, model_name, adopt_existing = queued
    oj = OpenshiftJob(job_name=job_id, clean_legacy_pods=adopt_existing)

    model_config: ModelConfig | None = None
    nebius_instance_name: str | None = None
    try:
        nebius_gpu_config = _parse_nebius_url(server_url)
        job_server_url: str | None = server_url
        managed_endpoint = False
        row = job_store.get(job_id)
        if not row:
            return

        if row["status"] in (JobStatus.COMPLETING.value, JobStatus.FAILING.value):
            final_status = JobStatus.COMPLETED if row["status"] == JobStatus.COMPLETING.value else JobStatus.FAILED
            if nebius_gpu_config is not None and _nebius:
                await _delete_recovered_nebius(job_id)
            await _retry_terminal_job(job_id, oj, final_status, error=row["error"])
            return

        if row["status"] == JobStatus.CANCELLING.value:
            if nebius_gpu_config is not None and _nebius:
                await _delete_recovered_nebius(job_id)
            await _retry_cancellation(job_id, oj)
            return

        if row["status"] == JobStatus.PAUSING.value:
            # A pause checkpoint was interrupted by a queue-service restart.
            # Finalizing must keep the (stopped) Nebius VM — unlike the
            # cancelling branch, this job intends to come back on it.
            if nebius_gpu_config is not None and _nebius:
                # Side effect only: tracking the stopped VM keeps a later
                # acquire_instance from deleting it as untracked garbage and
                # makes the recovery loop's adoption idempotent. Best-effort:
                # adopt_paused_instance re-raises during API outages, and an
                # uncaught exception here would kill the dispatcher — the
                # recovery loop re-adopts once Nebius answers. The name is
                # irrelevant for finalizing the pause either way.
                try:
                    await _nebius.adopt_paused_instance(model_name, nebius_gpu_config)
                except Exception:
                    logger.exception(
                        f"Could not track Nebius instance while finalizing pause for {job_id}"
                    )
            await _retry_pause_finalize(job_id, oj)
            return

        if nebius_gpu_config is not None and not _nebius:
            job_store.update_status(
                job_id,
                JobStatus.FAILED,
                error="Nebius is not enabled on this server",
            )
            return

        if adopt_existing:
            for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
                try:
                    existing = await oj._get_job()
                    break
                except Exception as e:
                    logger.exception(
                        f"Unable to reconcile recovered OpenShift Job {job_id} "
                        f"(attempt {attempt}/{CLEANUP_MAX_ATTEMPTS})"
                    )
                    if attempt < CLEANUP_MAX_ATTEMPTS:
                        await asyncio.sleep(CLEANUP_RETRY_INTERVAL_SECONDS)
                        continue
                    if nebius_gpu_config is not None and _nebius:
                        await _delete_recovered_nebius(job_id)
                    await _retry_terminal_job(job_id, oj, JobStatus.FAILED, error=str(e))
                    return
            if existing is None:
                if row["status"] == JobStatus.RUNNING.value:
                    if nebius_gpu_config is not None and _nebius:
                        await _delete_recovered_nebius(job_id)
                    await _retry_terminal_job(
                        job_id,
                        oj,
                        JobStatus.FAILED,
                        error="OpenShift Job missing after server restart",
                    )
                    return
                adopt_existing = False

        if adopt_existing and nebius_gpu_config is not None and _nebius:
            try:
                nebius_instance_name = await _nebius.adopt_running_instance(model_name, nebius_gpu_config)
            except Exception as e:
                logger.exception(f"Failed to restore Nebius tracking for job {job_id}")
                await _retry_terminal_job(
                    job_id,
                    oj,
                    JobStatus.FAILED,
                    error=str(e),
                )
                return
        elif nebius_gpu_config is not None and _nebius:
            try:
                nebius_instance_name, real_url = await _nebius.acquire_instance(model_name, gpu_config=nebius_gpu_config)
                is_resume = is_resume_command(command)
                if is_resume:
                    orig_name = results_job_name(row)
                    py_job_dir = f"/app/jobs/{orig_name}"
                    step = _build_url_replace_shell_step(real_url, py_job_dir)
                    command = list(command)
                    # AWS also uses uv run: update URLs only after restoring the config.
                    parent_step = _build_parent_env_shell_step(py_job_dir)
                    if parent_step in command[2]:
                        command[2] = command[2].replace(parent_step, parent_step + step, 1)
                    else:
                        # Queued/paused commands from an older image embed the old
                        # preparation script. Rebuild them rather than silently
                        # skipping the new VM address after an upgrade.
                        options = resume_options(command)
                        if not options:
                            raise ValueError("Unrecognized saved Harbor resume command")
                        command = ["bash", "-c", _build_resume_shell_command(
                            orig_name, str(uuid.uuid4()), options["filters"], real_url,
                        )]
                else:
                    command = [real_url if arg == server_url else arg for arg in command]
                job_server_url = real_url
                managed_endpoint = True
                model_config = MODEL_REGISTRY.get(model_name)
                await _nebius.mark_job_started(nebius_instance_name)
            except Exception as e:
                logger.exception(f"Nebius provisioning failed for job {job_id}")
                job_store.update_status(job_id, JobStatus.FAILED, error=f"Nebius provisioning failed: {e}")
                return

        if not is_resume_command(command) and "--model-max-len" not in command and model_config is not None:
            command += ["--model-max-len", str(model_config.model_max_len)]

        try:
            await _run_job(
                job_id,
                command,
                server_url=None if adopt_existing else job_server_url,
                managed_endpoint=managed_endpoint,
                openrouter=is_openrouter(server_url),
                adopt_existing=adopt_existing,
                nebius_instance_name=nebius_instance_name,
            )
        except InstancePreempted as e:
            logger.error(
                f"Nebius preemption detected for job {job_id}: {e}; "
                "checkpointing results to MinIO and parking the job as paused"
            )
            await _handle_pause(job_id, oj, nebius_instance_name)
            # A cancel may have raced the pause (which then skipped): finish it.
            if job_store.get(job_id)["status"] == JobStatus.CANCELLING.value:
                await _retry_cancellation(job_id, oj)
            return

        if job_store.get(job_id)["status"] == JobStatus.CANCELLING.value:
            await _retry_cancellation(job_id, oj)

        if nebius_instance_name and _nebius:
            await _nebius.mark_job_completed(nebius_instance_name)
    except asyncio.CancelledError:
        if _shutting_down:
            raise
        if _parse_nebius_url(server_url) is not None and _nebius:
            await _delete_recovered_nebius(job_id)
        if not await _finish_cancellation(job_id, oj, signal=True):
            await _retry_cancellation(job_id, oj)


async def _worker():
    """Process jobs from the queue one at a time."""
    global _active_job

    while True:
        await _job_event.wait()
        _job_event.clear()
        while _job_queue:
            _reorder_queue_for_nebius()
            job_id, command, server_url, model_name, adopt_existing = _job_queue.pop(0)
            row = job_store.get(job_id)
            recoverable_statuses = (
                JobStatus.QUEUED.value,
                JobStatus.RUNNING.value,
                JobStatus.COMPLETING.value,
                JobStatus.FAILING.value,
                JobStatus.CANCELLING.value,
                JobStatus.PAUSING.value,
            )
            if not row or (adopt_existing and row["status"] not in recoverable_statuses):
                continue
            if not adopt_existing and row["status"] != JobStatus.QUEUED.value:
                continue
            processing_task = asyncio.create_task(_process_queued_job(QueuedJob(job_id, command, server_url, model_name, adopt_existing)))
            _active_job = (job_id, processing_task)
            try:
                await processing_task
            except asyncio.CancelledError:
                if _shutting_down:
                    raise
                oj = OpenshiftJob(job_name=job_id, clean_legacy_pods=adopt_existing)
                if not await _finish_cancellation(job_id, oj, signal=False):
                    await _retry_cancellation(job_id, oj)
            except Exception:
                # Defensive backstop: worker_task is never restarted, so no
                # per-job failure may escape and kill the dispatcher. The row
                # keeps whatever status the crash left it in (never rewritten
                # from here, to avoid clobbering a pause/cancel in flight);
                # the queue moves on to the next job.
                logger.exception(f"Queue handler crashed while processing {job_id}")
            finally:
                if _active_job and _active_job[0] == job_id:
                    _active_job = None

@router.get("/")
async def read_root():
    """Return a lightweight health response for the queue API."""
    return {"message": "API is live."}

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    """
    User interface.
    
    Intentionally left accessible to unauthenticated users as it does not expose any secret information
    or allow users to modify any job.
    """
    columns = ["job_id", "job_name", "agent", "dataset", "model_name", "server_url", "status", "error"]

    def build_table(title: str, jobs: list[dict]) -> str:
        """Render one HTML job table for the unauthenticated status page."""
        header = "".join(f"<th>{col}</th>" for col in columns)
        rows = ""
        for job in jobs:
            cells = "".join(f"<td>{html.escape(str(job.get(col, '')) or '')}</td>" for col in columns)
            rows += f"<tr>{cells}</tr>"
        if not jobs:
            rows = f'<tr><td colspan="{len(columns)}">No jobs</td></tr>'
        return f"<h2>{title}</h2><table><tr>{header}</tr>{rows}</table>"

    running = (
        job_store.list(JobStatus.RUNNING)
        + job_store.list(JobStatus.COMPLETING)
        + job_store.list(JobStatus.FAILING)
        + job_store.list(JobStatus.CANCELLING)
    )
    paused = job_store.list(JobStatus.PAUSING) + job_store.list(JobStatus.PAUSED)
    queued = job_store.list(JobStatus.QUEUED)
    completed = job_store.list(JobStatus.COMPLETED) + job_store.list(JobStatus.FAILED) + job_store.list(JobStatus.CANCELLED)
    completed.reverse()

    # Build Nebius instances section if enabled
    nebius_section = ""
    if _nebius:
        states = _nebius.get_instance_states()
        nebius_cols = ["Instance Name", "GPU Config", "Current Model", "Status", "Last Job Completed"]
        nebius_header = "".join(f"<th>{c}</th>" for c in nebius_cols)
        nebius_rows = ""
        for s in states:
            if s.provisioning_model:
                status = f"Starting model: {html.escape(s.provisioning_model)}"
            elif s.job_running:
                status = "Running job"
            else:
                status = "Idle"
            last_completed = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.last_job_completed_at))
                if s.last_job_completed_at else "—"
            )
            nebius_rows += (
                f"<tr><td>{html.escape(s.instance_name)}</td>"
                f"<td>{html.escape(s.gpu_config)}</td>"
                f"<td>{html.escape(s.current_model or '—')}</td>"
                f"<td>{status}</td>"
                f"<td>{last_completed}</td></tr>"
            )
        if not states:
            nebius_rows = f'<tr><td colspan="{len(nebius_cols)}">No instances</td></tr>'
        nebius_section = f"<h2>Nebius Instances</h2><table><tr>{nebius_header}</tr>{nebius_rows}</table>"

    # Build API key input section
    api_key_section = """
<div id="api-key-section" style="margin-bottom: 1.5rem; padding: 0.75rem; border: 1px solid #ddd; border-radius: 8px; background: #fffbe6;">
    <label for="api-key-input" style="font-weight: bold;">API Key:</label>
    <input type="password" id="api-key-input" placeholder="Enter your API key"
           style="margin-left: 0.5rem; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; width: 300px;">
    <button type="button" onclick="saveApiKey()" style="margin-left: 0.5rem; padding: 0.5rem 1rem; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer;">Save</button>
    <button type="button" onclick="clearApiKey()" style="margin-left: 0.25rem; padding: 0.5rem 1rem; background: #666; color: white; border: none; border-radius: 4px; cursor: pointer;">Clear</button>
    <span id="api-key-status" style="margin-left: 1rem;"></span>
</div>
<script>
function saveApiKey() {{
    const key = document.getElementById('api-key-input').value.trim();
    if (key) {{
        localStorage.setItem('coding_agent_bench_api_key', key);
        document.getElementById('api-key-status').textContent = 'API key saved.';
        document.getElementById('api-key-status').style.color = 'green';
    }}
}}
function clearApiKey() {{
    localStorage.removeItem('coding_agent_bench_api_key');
    document.getElementById('api-key-input').value = '';
    document.getElementById('api-key-status').textContent = 'API key cleared.';
    document.getElementById('api-key-status').style.color = '#cc6600';
}}
(function() {{
    const savedKey = localStorage.getItem('coding_agent_bench_api_key');
    if (savedKey) {{
        document.getElementById('api-key-input').value = savedKey;
    }}
}})();
</script>
"""

    # Build submit form with current data
    nebius_enabled = os.environ.get("NEBIUS_ENABLED") == "1"
    submit_form_html = build_submit_form_html(
        models=list(MODEL_REGISTRY.keys()),
        agents=list(AGENT_REGISTRY.keys()),
        nebius_configs=list(RESOURCE_CONFIG_REGISTRY.keys()) if nebius_enabled else [],
        nebius_enabled=nebius_enabled,
    )

    html_page = f"""<!DOCTYPE html>
<html>
<head>
<title>Job Queue</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
th {{ background: #f5f5f5; }}
h1 {{ display: flex; align-items: center; gap: 0.75rem; }}
h1 svg {{ flex-shrink: 0; }}
</style>
</head>
<body>
<h1>
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 145" width="32" height="32" aria-hidden="true"><style>.cls-1{{fill:#e00;}}</style><path d="M157.77,62.61a14,14,0,0,1,.31,3.42c0,14.88-18.1,17.46-30.61,17.46C78.83,83.49,42.53,53.26,42.53,44a6.43,6.43,0,0,1,.22-1.94l-3.66,9.06a18.45,18.45,0,0,0-1.51,7.33c0,18.11,41,45.48,87.74,45.48,20.69,0,36.43-7.76,36.43-21.77,0-1.08,0-1.94-1.73-10.13Z"/><path class="cls-1" d="M127.47,83.49c12.51,0,30.61-2.58,30.61-17.46a14,14,0,0,0-.31-3.42l-7.45-32.36c-1.72-7.12-3.23-10.35-15.73-16.6C124.89,8.69,103.76.5,97.51.5,91.69.5,90,8,83.06,8c-6.68,0-11.64-5.6-17.89-5.6-6,0-9.91,4.09-12.93,12.5,0,0-8.41,23.72-9.49,27.16A6.43,6.43,0,0,0,42.53,44c0,9.22,36.3,39.45,84.94,39.45M160,72.07c1.73,8.19,1.73,9.05,1.73,10.13,0,14-15.74,21.77-36.43,21.77C78.54,104,37.58,76.6,37.58,58.49a18.45,18.45,0,0,1,1.51-7.33C22.27,52,.5,55,.5,74.22c0,31.48,74.59,70.28,133.65,70.28,45.28,0,56.7-20.48,56.7-36.65,0-12.72-11-27.16-30.83-35.78"/></svg>
  Job Queue <font size="4">v{VERSION}</font>
</h1>
{api_key_section}
{submit_form_html}
{nebius_section}
{build_table("Running", running)}
{build_table("Paused (awaiting Nebius recovery)", paused)}
{build_table("Queued", queued)}
{build_table("Completed", completed)}
</body>
</html>"""
    return html_page

def build_cli_command(req: CreateJobRequest):
    """Build the coding-agent-bench CLI command."""
    command = ["coding-agent-bench", "run"]
    
    # Add required parameters
    command += [
        "--job-name", req.job_name,
        "--agent", req.agent,
        "--dataset", req.dataset,
        "--model-name", req.model_name,
        "--server-url", req.server_url,
        "--environment", "openshift",
    ]
    
    # Add optional parameters
    if req.dataset_pattern:
        command += ["--dataset-pattern", req.dataset_pattern]
    if req.n_concurrent is not None:
        command += ["--n-concurrent", str(req.n_concurrent)]
    if req.n_tasks is not None:
        command += ["--n-tasks", str(req.n_tasks)]
    model_max_len = req.model_max_len
    if model_max_len is None:
        model_config = MODEL_REGISTRY.get(req.model_name)
        model_max_len = model_config.model_max_len if model_config else None
    if model_max_len is not None:
        command += ["--model-max-len", str(model_max_len)]
    if req.before_script:
        command += ["--before-script", req.before_script]
    if req.agent_version:
        command += ["--agent-version", req.agent_version]
    if req.max_retries is not None:
        command += ["--max-retries", str(req.max_retries)]
    if req.retry_include is not None:
        for exc in req.retry_include:
            command += ["--retry-include", exc]
    for skill in req.skills:
        command += ["--skill", skill]

    return command


def _job_create_response(row: dict, message: str) -> CreateJobResponse:
    """Reconstruct a create response from a job persisted in the queue store."""
    try:
        command = json.loads(row["command"])
    except (KeyError, TypeError, json.JSONDecodeError):
        command = []
    if not isinstance(command, list):
        command = []
    return CreateJobResponse(
        message=message,
        job_id=row["job_id"],
        job_name=row["job_name"],
        command=command,
    )


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(
    req: CreateJobRequest,
    idempotency_key_header: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Create a new benchmark job."""
    # FastAPI replaces the Header marker at request time; treating it as absent
    # also keeps direct unit calls to this coroutine straightforward.
    if not isinstance(idempotency_key_header, str):
        idempotency_key_header = None
    raw_idempotency_key = (
        idempotency_key_header
        if idempotency_key_header is not None
        else req.idempotency_key
    )
    idempotency_key = raw_idempotency_key.strip() if raw_idempotency_key else None
    if raw_idempotency_key is not None and not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key must not be blank")

    if idempotency_key:
        existing = job_store.get_by_idempotency_key(idempotency_key)
        if existing:
            return _job_create_response(existing, message="Job already exists.")

    try:
        validate_remote_skill_sources(req.skills)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Skip harbor command validation for nebius jobs (server_url is a placeholder)
    nebius_gpu_config = _parse_nebius_url(req.server_url)
    if nebius_gpu_config is not None:
        if not _nebius:
            raise HTTPException(status_code=400, detail="Nebius is not enabled on this server")
        if nebius_gpu_config not in RESOURCE_CONFIG_REGISTRY:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown resource config '{nebius_gpu_config}'. Choose from: {', '.join(RESOURCE_CONFIG_REGISTRY)}",
            )
    elif is_openrouter(req.server_url):
        # Skip HarborCommandBuilder().build() for openrouter jobs: build() runs
        # each agent's configure(), and PiAgentConfig.configure() writes the
        # real OpenRouter key to models.json on the API host's CWD as a side
        # effect. Validate cheaply instead, deferring dataset-existence checks
        # to run time (same trade-off as the nebius branch above).
        try:
            resolve_provider(req.server_url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if req.agent.value in OPENROUTER_UNSUPPORTED_AGENTS:
            raise HTTPException(status_code=400, detail=f"agent '{req.agent.value}' cannot use OpenRouter")
    else:
        if req.server_url.lower() != "openrouter":
            server_url_errors = validate_server_url(req.server_url)
            if server_url_errors:
                raise HTTPException(status_code=400, detail="; ".join(server_url_errors))
        try:
            HarborCommandBuilder().build(
                agent=req.agent,
                dataset=req.dataset,
                model_name=req.model_name,
                server_url=req.server_url,
                environment="openshift",
                dataset_pattern=req.dataset_pattern,
                n_concurrent=req.n_concurrent,
                n_tasks=req.n_tasks,
                model_max_len=req.model_max_len,
                job_name=req.job_name,
                skills=req.skills,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Build the CLI command
    command = build_cli_command(req=req)

    # Start the job
    job_id = str(uuid.uuid4())
    try:
        job_store.insert(
            job_id,
            req.job_name,
            req.agent.value,
            req.dataset,
            req.model_name,
            req.server_url,
            command,
            idempotency_key=idempotency_key,
        )
    except sqlite3.IntegrityError:
        # A concurrent retry may win the unique-key race between the lookup above
        # and the insert. Return that request's original result without enqueuing a
        # second job.
        if idempotency_key:
            existing = job_store.get_by_idempotency_key(idempotency_key)
            if existing:
                return _job_create_response(existing, message="Job already exists.")
        raise HTTPException(status_code=409, detail="Job already exists")
    _job_queue.append(QueuedJob(job_id, command, req.server_url, req.model_name))
    _job_event.set()

    # Return a success response
    return CreateJobResponse(message="Job created.", job_id=job_id, job_name=req.job_name, command=command)

@router.get("/jobs", response_model=list[JobResponse])
async def get_jobs(status: JobStatus | None = None):
    """List all jobs or filter by status."""
    return [JobResponse(**row) for row in job_store.list(status)]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get a job by ID."""
    row = job_store.get(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**row)


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Cancel a queued or running job."""
    job_row = job_store.get(job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_row["status"] == JobStatus.CANCELLING.value:
        return {"message": "Job cancelling", "job_id": job_id}

    if job_row["status"] in (
        JobStatus.COMPLETING,
        JobStatus.COMPLETED,
        JobStatus.FAILING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.PAUSING,
    ):
        raise HTTPException(status_code=400, detail=f"Job already {job_row['status']}")

    # A paused job has no live workloads; cancelling it just retires the row.
    # The shared Nebius instance must NOT be released here: it belongs to the
    # pool, and idle cleanup handles it.
    if job_row["status"] == JobStatus.PAUSED.value:
        # CAS: the resume loop may have re-queued the job since the read;
        # never clobber a live status with an unconditional write. If the
        # race was lost, fall through to the normal cancel path with a
        # refreshed row.
        if job_store.update_status_if(job_id, JobStatus.PAUSED, JobStatus.CANCELLED):
            return {"message": "Job cancelled", "job_id": job_id}
        job_row = job_store.get(job_id)
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")

    # Remove from the queue only when the persisted job has never started.
    for i, queued in enumerate(_job_queue):
        if queued.job_id == job_id:
            if (
                job_row["status"] == JobStatus.QUEUED.value
                and not queued.adopt_existing
            ):
                _job_queue.pop(i)
                job_store.update_status(job_id, JobStatus.CANCELLED)
                return {"message": "Job cancelled", "job_id": job_id}
            if job_row["status"] in (
                JobStatus.QUEUED.value,
                JobStatus.RUNNING.value,
            ):
                job_store.update_status(job_id, JobStatus.CANCELLING)
            _job_event.set()
            return {"message": "Job cancelling", "job_id": job_id}

    # Cancel the actively running job
    if _active_job and _active_job[0] == job_id:
        job_store.update_status(job_id, JobStatus.CANCELLING)
        _active_job[1].cancel()
        return {"message": "Job cancelling", "job_id": job_id}

    return {"message": "Job cancelled", "job_id": job_id}

def _build_url_replace_shell_step(server_url: str, py_job_dir: str) -> str:
    """Retarget model settings consistently, including changed IPs and schemes."""
    return " && " + shlex.join([
        "uv", "run", "--no-sync", "--no-cache", "python", "-m",
        "coding_agent_bench.resume", "endpoint", py_job_dir, server_url,
    ])


def _build_parent_env_shell_step(py_job_dir: str) -> str:
    """Update parent ownership in the root config, saved trials, and locks."""
    return " && " + shlex.join([
        "uv", "run", "--no-sync", "--no-cache", "python", "-m",
        "coding_agent_bench.resume", "parent", py_job_dir,
    ])


def _build_resume_shell_command(
    original_job_name: str,
    staging_id: str,
    filter_error_types: list[str],
    server_url: str | None,
) -> str:
    """Build the bash -c payload that restores a job from MinIO and resumes it.

    Shared by the manual resume endpoint and preemption auto-resume. The
    worker injects the Nebius URL-rewrite step at run time for placeholder
    server URLs, so this builder only embeds a rewrite for explicit URLs.
    """
    job_dir = f"/app/jobs/{shlex.quote(original_job_name)}"
    py_job_dir = f"/app/jobs/{original_job_name}"
    aws = "uv run --no-sync --no-cache aws --endpoint-url http://harbor-minio:9000"
    results_uri = shlex.quote(f"s3://results/{original_job_name}/")
    # A separate bucket keeps recovery snapshots out of results consumers' listings.
    staging_root = f"s3://results-staging/{original_job_name}/{staging_id}"
    original_uri = shlex.quote(f"{staging_root}/original/")
    updated_uri = shlex.quote(f"{staging_root}/updated/")
    resume_command = [
        "uv", "run", "--no-sync", "--no-cache", "harbor", "jobs", "resume",
        "-p", py_job_dir,
        "--plugin", PAUSE_PLUGIN,
    ]
    for error_type in filter_error_types:
        resume_command += ["-f", error_type]

    # URL replacement only applies to real, changing hostnames (e.g. a new
    # nebius instance IP). It is skipped for nebius placeholders (deferred to
    # the worker) and for the openrouter sentinel, whose URL is static and
    # already baked into the restored config.
    url_replace_step = ""
    if server_url and _parse_nebius_url(server_url) is None and not is_openrouter(server_url):
        url_replace_step = _build_url_replace_shell_step(server_url, py_job_dir)

    return (
        "export AWS_ACCESS_KEY_ID=\"$MINIO_ROOT_USER\" "
        "AWS_SECRET_ACCESS_KEY=\"$MINIO_ROOT_PASSWORD\" "
        "AWS_DEFAULT_REGION=us-east-1 AWS_EC2_METADATA_DISABLED=true"
        f" && {aws} s3 cp --recursive {results_uri} {job_dir}/"
        f"{_build_parent_env_shell_step(py_job_dir)}"
        f"{url_replace_step}"
        f" && ({aws} s3api head-bucket --bucket results-staging >/dev/null 2>&1"
        f" || {aws} s3 mb s3://results-staging"
        f" || {aws} s3api head-bucket --bucket results-staging)"
        # Preserve the original before Harbor removes/retries local trial files.
        f" && {aws} s3 cp --recursive {results_uri} {original_uri}"
        f" && printf 'complete\\n' | {aws} s3 cp - {shlex.quote(staging_root + '/original.complete')}"
        " || exit $?; "
        f"{_build_logged_shell_step(resume_command, py_job_dir)}"
        # Never touch the canonical prefix until the entire updated upload succeeds.
        f" {aws} s3 cp --recursive {job_dir}/ {updated_uri}"
        f" && printf 'complete\\n' | {aws} s3 cp - {shlex.quote(staging_root + '/updated.complete')}"
        f" && {aws} s3 sync --delete {updated_uri} {results_uri}"
        # Keep both snapshots for recovery if promotion partially fails or is interrupted.
        " || exit $?; exit \"$harbor_rc\""
    )


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str, req: ResumeJobRequest = ResumeJobRequest()):
    """Resume a finished or paused job, preserving its original artifact location."""
    job_row = job_store.get(job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_row["status"] not in (
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
        JobStatus.PAUSED.value,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Can only resume completed/failed/cancelled/paused jobs, got {job_row['status']}",
        )

    original_job_name = results_job_name(job_row)
    resume_job_id = str(uuid.uuid4())
    resume_job_name = f"{original_job_name}--resume"

    original_server_url = job_row.get("server_url", "")
    effective_server_url = req.server_url or original_server_url

    # Validate nebius URLs the same way create_job does
    nebius_gpu_config = _parse_nebius_url(effective_server_url)
    if nebius_gpu_config is not None:
        if not _nebius:
            raise HTTPException(status_code=400, detail="Nebius is not enabled on this server")
        if nebius_gpu_config not in RESOURCE_CONFIG_REGISTRY:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown resource config '{nebius_gpu_config}'. Choose from: {', '.join(RESOURCE_CONFIG_REGISTRY)}",
            )

    shell_command = _build_resume_shell_command(
        original_job_name,
        resume_job_id,
        req.filter_error_types or [CANCELLED_ERROR_TYPE],
        effective_server_url,
    )

    command = ["bash", "-c", shell_command]
    if job_row["status"] == JobStatus.PAUSED.value:
        # Reuse the row, as automatic recovery does. Creating a child and leaving
        # the original paused would allow the background loop to run both.
        if not job_store.resume_paused(job_id, command, effective_server_url, original_job_name):
            raise HTTPException(status_code=409, detail="Job left the paused state; refresh before retrying")
        _job_queue.append(QueuedJob(job_id, command, effective_server_url, job_row["model_name"]))
        _job_event.set()
        return {"message": "Paused job queued for resume", "job_id": job_id, "job_name": job_row["job_name"]}
    job_store.insert(
        resume_job_id, resume_job_name, job_row["agent"],
        job_row["dataset"], job_row["model_name"], effective_server_url, command,
        results_job_name=original_job_name,
    )
    _job_queue.append(QueuedJob(resume_job_id, command, effective_server_url, job_row["model_name"]))
    _job_event.set()

    return {
        "message": "Resume job created",
        "job_id": resume_job_id,
        "job_name": resume_job_name,
        "parent_job_id": job_id,
    }

@router.get("/models")
async def get_models():
    """List available models for managed servers."""
    models = list(MODEL_REGISTRY.keys())
    return {"models": models}

@ui_router.get("/api/models")
async def get_models_public():
    """List available models (public endpoint for UI)."""
    return {"models": list(MODEL_REGISTRY.keys())}

@ui_router.get("/api/agents")
async def get_agents():
    """List available agents (public endpoint for UI)."""
    return {"agents": list(AGENT_REGISTRY.keys())}

@ui_router.get("/api/nebius-configs")
async def get_nebius_configs():
    """List available nebius resource configs (public endpoint for UI)."""
    nebius_enabled = os.environ.get("NEBIUS_ENABLED") == "1"
    return {
        "nebius_enabled": nebius_enabled,
        "configs": list(RESOURCE_CONFIG_REGISTRY.keys()),
    }

app.include_router(router)
app.include_router(ui_router)
