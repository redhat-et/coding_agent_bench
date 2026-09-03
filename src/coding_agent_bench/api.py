from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
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
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.nebius_utils import NebiusInstanceManager, RESOURCE_CONFIG_REGISTRY
from coding_agent_bench.models import ModelConfig, MODEL_REGISTRY
from coding_agent_bench.providers import is_openrouter, resolve_provider, OPENROUTER_UNSUPPORTED_AGENTS
from coding_agent_bench.agents import AGENT_REGISTRY
from coding_agent_bench.ui import build_submit_form_html
from coding_agent_bench import VERSION

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
    if server_url.startswith(NEBIUS_PREFIX):
        return server_url[len(NEBIUS_PREFIX):]
    return None


db_path = Path(os.environ.get("JOB_STORE_PATH", "jobs.db"))

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILING = "failing"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


NEBIUS_IDLE_TIMEOUT = int(os.environ.get("NEBIUS_IDLE_TIMEOUT_SECONDS", "600"))
CLEANUP_MAX_ATTEMPTS = int(os.environ.get("CLEANUP_MAX_ATTEMPTS", "120"))
CLEANUP_RETRY_INTERVAL_SECONDS = float(os.environ.get("CLEANUP_RETRY_INTERVAL_SECONDS", "5"))


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
        if instance_name not in self._instances:
            logger.warning(f"mark_job_started: instance {instance_name} already evicted")
            return
        self._instances[instance_name].job_running = True

    async def mark_job_completed(self, instance_name: str):
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
    n_concurrent: int = Field(1, description="Number of concurrent tasks")
    n_tasks: Optional[int] = Field(None, description="Total number of tasks to run")
    model_max_len: Optional[int] = Field(None, description="Maximum model context length in tokens")
    before_script: Optional[str] = Field(None, description="Script to run before harbor job execution")
    agent_version: Optional[str] = Field(None, description="Pin agent to a specific version (overrides default)")
    max_retries: Optional[int] = Field(None, description="Max retry attempts per task (default: 1)")
    retry_include: Optional[list[str]] = Field(None, description="Error types to retry (default: AgentTimeoutError, NonZeroAgentExitCodeError, ApiRateLimitError, ApiUsageLimitError)")


class ResumeJobRequest(BaseModel):
    filter_error_types: list[str] = Field(
        default_factory=list,
        description="Error types to retry (e.g. RuntimeError). Empty = retry all errors",
    )
    server_url: Optional[str] = Field(None, description="New model server URL (replaces old URL across all job files)")


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
                error TEXT
            )"""
        )
        # Migrate: add server_url if upgrading from an older schema
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "server_url" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN server_url TEXT NOT NULL DEFAULT ''")
        conn.commit()
        conn.close()

    def insert(self, job_id: str, job_name: str, agent: str, dataset: str, model_name: str, server_url: str, command: list[str]):
        """Add a new job to the tracking table."""
        conn = self._connect()
        conn.execute(
            "INSERT INTO jobs (job_id, job_name, agent, dataset, model_name, server_url, command, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, job_name, agent, dataset, model_name, server_url, json.dumps(command), JobStatus.QUEUED.value),
        )
        conn.commit()
        conn.close()

    def update_status(self, job_id: str, status: JobStatus, error: str | None = None):
        """Update the status of a job."""
        conn = self._connect()
        conn.execute(
            "UPDATE jobs SET status = ?, error = ? WHERE job_id = ?",
            (status.value, error, job_id),
        )
        conn.commit()
        conn.close()

    def get(self, job_id: str) -> dict | None:
        """Get a job by id."""
        conn = self._connect()
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
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
            "SELECT * FROM jobs WHERE status IN (?, ?, ?, ?, ?) ORDER BY rowid",
            (
                JobStatus.QUEUED.value,
                JobStatus.RUNNING.value,
                JobStatus.COMPLETING.value,
                JobStatus.FAILING.value,
                JobStatus.CANCELLING.value,
            ),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]


job_store = JobStore(db_path)

_api_key_header = APIKeyHeader(name="X-API-Key")


async def _verify_api_key(key: str = Depends(_api_key_header)) -> str:
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="API_KEY not configured")
    if key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
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
    return has_recoverable_nebius


async def _run_job(job_id: str, command: list[str], adopt_existing: bool = False, openrouter: bool = False):
    """Run and monitor an Openshift Job."""
    oj = OpenshiftJob(job_name=job_id, clean_legacy_pods=adopt_existing)

    try:
        if not adopt_existing:
            is_resume = len(command) == 3 and command[0] == "sh" and command[1] == "-c"
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
            await asyncio.sleep(5)

    except asyncio.CancelledError:
        if _shutting_down:
            raise
        await _finish_cancellation(job_id, oj, signal=True)
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
                is_resume = len(command) == 3 and command[0] == "sh" and command[1] == "-c"
                if is_resume:
                    row = job_store.get(job_id)
                    job_name = row["job_name"]
                    orig_name = job_name.removesuffix("--resume")
                    py_job_dir = f"/app/jobs/{orig_name}"
                    step = _build_url_replace_shell_step(real_url, py_job_dir)
                    command = list(command)
                    command[2] = command[2].replace(" && uv run", f"{step} && uv run", 1)
                else:
                    command = [real_url if arg == server_url else arg for arg in command]
                model_config = MODEL_REGISTRY.get(model_name)
                await _nebius.mark_job_started(nebius_instance_name)
            except Exception as e:
                logger.exception(f"Nebius provisioning failed for job {job_id}")
                job_store.update_status(job_id, JobStatus.FAILED, error=f"Nebius provisioning failed: {e}")
                return

        if "--model-max-len" not in command and model_config is not None:
            command += ["--model-max-len", str(model_config.model_max_len)]

        await _run_job(job_id, command, openrouter=is_openrouter(server_url), adopt_existing=adopt_existing)

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
            finally:
                if _active_job and _active_job[0] == job_id:
                    _active_job = None

@router.get("/")
async def read_root():
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
    if req.n_concurrent:
        command += ["--n-concurrent", str(req.n_concurrent)]
    if req.n_tasks:
        command += ["--n-tasks", str(req.n_tasks)]
    if req.model_max_len:
        command += ["--model-max-len", str(req.model_max_len)]
    if req.before_script:
        command += ["--before-script", req.before_script]
    if req.agent_version:
        command += ["--agent-version", req.agent_version]
    if req.max_retries is not None:
        command += ["--max-retries", str(req.max_retries)]
    if req.retry_include is not None:
        for exc in req.retry_include:
            command += ["--retry-include", exc]

    return command

@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(req: CreateJobRequest):
    """Create a new benchmark job."""
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
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Build the CLI command
    command = build_cli_command(req=req)

    # Start the job
    job_id = str(uuid.uuid4())
    job_store.insert(job_id, req.job_name, req.agent.value, req.dataset, req.model_name, req.server_url, command)
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
    ):
        raise HTTPException(status_code=400, detail=f"Job already {job_row['status']}")

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
    """Build shell step that replaces model server URLs in downloaded job files."""
    new_host = urlparse(server_url.rstrip("/")).netloc
    new_domain = ".".join(new_host.rsplit(".", 2)[-2:])
    replace_lines = [
        "import os, json, re",
        f"job_dir = {json.dumps(py_job_dir)}",
        f"new_host = {json.dumps(new_host)}",
        f"new_domain = {json.dumps(new_domain)}",
        "config_path = os.path.join(job_dir, 'config.json')",
        "if not os.path.exists(config_path): exit(0)",
        "with open(config_path) as f: c = json.load(f)",
        "envs = c.get('agents', [{}])[0].get('env', {})",
        "hosts = set()",
        "for v in envs.values():",
        "    if not isinstance(v, str): continue",
        "    for m in re.finditer('https?://([^\"\\\\s,}/]+)', v):",
        "        hosts.add(m.group(1).split('/')[0])",
        "hosts = [h for h in hosts if h != new_host and h.endswith(new_domain)]",
        "replaced = 0",
        "if hosts:",
        "    for root, dirs, files in os.walk(job_dir):",
        "        for file in files:",
        "            if not file.endswith('.json'): continue",
        "            path = os.path.join(root, file)",
        "            with open(path, 'r') as f: content = f.read()",
        "            orig = content",
        "            for h in hosts: content = content.replace(h, new_host)",
        "            if content != orig:",
        "                with open(path, 'w') as f: f.write(content)",
        "                replaced += 1",
        "print(f'Replaced URL in {replaced} files')",
        "# Regenerate Pi/Codex mount files with new URL",
        f"server_url = {json.dumps(server_url)}",
        "agent = c.get('agents', [{}])[0]",
        "model_name = agent.get('model_name', '')",
        "mounts = c.get('environment', {}).get('mounts', [])",
        "for m in mounts:",
        "    src, tgt = m.get('source',''), m.get('target','')",
        "    if agent.get('name') == 'pi' and 'models.json' in tgt:",
        "        json.dump({'providers': {'vllm': {'baseUrl': server_url, 'api': 'openai-completions', 'apiKey': 'NONE', 'models': [{'id': model_name, 'name': model_name}]}}}, open(src, 'w'))",
        "        print('Regenerated Pi models.json')",
        "    if agent.get('name') == 'codex' and 'config.toml' in tgt:",
        "        open(src, 'w').write(f'[api]\\nbase_url = \"{server_url}\"\\napi_key = \"sk-no-key\"\\n[model]\\nmodel_id = \"{model_name}\"\\n')",
        "        print('Regenerated Codex config.toml')",
    ]
    replace_script = "\n".join(replace_lines)
    return f" && python3 -c {shlex.quote(replace_script)}"


def _build_parent_env_shell_step(py_job_dir: str) -> str:
    """Update a resumed Harbor config so new task pods retain parent ownership."""
    lines = [
        "import json, os",
        f"path = {json.dumps(f'{py_job_dir}/config.json')}",
        "with open(path) as f: config = json.load(f)",
        "kwargs = config.setdefault('environment', {}).setdefault('kwargs', {})",
        "env = kwargs.setdefault('persistent_env', {})",
        "env['HARBOR_PARENT'] = os.environ['HARBOR_PARENT']",
        "with open(path, 'w') as f: json.dump(config, f)",
    ]
    return f" && python3 -c {shlex.quote(chr(10).join(lines))}"


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str, req: ResumeJobRequest = ResumeJobRequest()):
    """Resume a completed/failed job by retrying errored tasks via harbor jobs resume."""
    job_row = job_store.get(job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_row["status"] not in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
        raise HTTPException(
            status_code=400,
            detail=f"Can only resume completed/failed jobs, got {job_row['status']}",
        )

    original_job_name = job_row["job_name"]
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

    filter_flags = "".join(f" -f {shlex.quote(t)}" for t in req.filter_error_types)
    job_dir = f"/app/jobs/{shlex.quote(original_job_name)}"
    py_job_dir = f"/app/jobs/{original_job_name}"

    # URL replacement only applies to real, changing hostnames (e.g. a new
    # nebius instance IP). It is skipped for nebius placeholders (deferred to
    # the worker) and for the openrouter sentinel, whose URL is static and
    # already baked into the restored config.
    url_replace_step = ""
    if req.server_url and nebius_gpu_config is None and not is_openrouter(req.server_url):
        url_replace_step = _build_url_replace_shell_step(req.server_url, py_job_dir)

    shell_command = (
        "mc alias set minio http://harbor-minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD"
        f" && mc cp --recursive minio/results/{shlex.quote(original_job_name)}/ {job_dir}/"
        f"{_build_parent_env_shell_step(py_job_dir)}"
        f"{url_replace_step}"
        f" && uv run --no-sync --no-cache harbor jobs resume -p {job_dir}{filter_flags}"
        f" ; mc rm --recursive --force minio/results/{shlex.quote(original_job_name)}/"
        f" && mc cp --recursive {job_dir}/ minio/results/{shlex.quote(original_job_name)}/"
    )

    command = ["sh", "-c", shell_command]
    job_store.insert(
        resume_job_id, resume_job_name, job_row["agent"],
        job_row["dataset"], job_row["model_name"], effective_server_url, command,
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
