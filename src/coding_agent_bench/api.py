from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Optional

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path

from coding_agent_bench.builder import SupportedAgent, HarborCommandBuilder
from coding_agent_bench.job import OpenshiftJob
import json
import os
import sqlite3
import uuid
import html

_job_queue: list[tuple[str, list[str]]] = []
_job_event = asyncio.Event()
_active_job: tuple[str, asyncio.Task, OpenshiftJob] | None = None
_shutting_down = False

db_path = Path(os.environ.get("JOB_STORE_PATH", "jobs.db"))

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"

        
class CreateJobRequest(BaseModel):
    job_name: str = Field(..., description="Name to give the job")
    agent: SupportedAgent = Field(..., description="Agent to use")
    dataset: str = Field(..., description="Dataset name or path")
    model_name: str = Field(..., description="Model name")
    server_url: str = Field(..., description="Model server URL")  
    dataset_pattern: Optional[str] = Field(None, description="Pattern to filter dataset tasks")
    n_concurrent: int = Field(1, description="Number of concurrent tasks")
    n_tasks: Optional[int] = Field(None, description="Total number of tasks to run")
    model_max_len: int = Field(262000, description="Maximum model context length in tokens")
    before_script: Optional[str] = Field(None, description="Script to run before harbor job execution")


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
                command TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                error TEXT
            )"""
        )
        conn.commit()
        conn.close()

    def insert(self, job_id: str, job_name: str, agent: str, dataset: str, model_name: str, command: list[str]):
        """Add a new job to the tracking table."""
        conn = self._connect()
        conn.execute(
            "INSERT INTO jobs (job_id, job_name, agent, dataset, model_name, command, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, job_name, agent, dataset, model_name, json.dumps(command), JobStatus.QUEUED.value),
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
            rows = conn.execute("SELECT * FROM jobs WHERE status = ?", (status.value,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM jobs").fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def mark_orphaned(self):
        """Mark queued or running jobs as failed on server restart."""
        conn = self._connect()
        conn.execute(
            "UPDATE jobs SET status = ?, error = ? WHERE status IN (?, ?, ?)",
            (JobStatus.FAILED.value, "Server restarted", JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobStatus.CANCELLING.value),
        )
        conn.commit()
        conn.close()


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
    global _shutting_down
    job_store.mark_orphaned()
    worker_task = asyncio.create_task(_worker())
    cleanup_task = asyncio.create_task(_build_pod_cleanup_loop())
    yield
    _shutting_down = True
    worker_task.cancel()
    cleanup_task.cancel()
    for task in (worker_task, cleanup_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)
router = APIRouter(dependencies=[Depends(_verify_api_key)])


async def _build_pod_cleanup_loop():
    """Periodically delete completed/failed build pods from the namespace."""
    while True:
        await asyncio.sleep(300)
        try:
            for phase in ("Succeeded", "Failed"):
                process = await asyncio.create_subprocess_exec(
                    "oc", "get", "pods",
                    "-l", "openshift.io/build.name",
                    f"--field-selector=status.phase=={phase}",
                    "-o", "jsonpath={.items[*].metadata.name}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                pods = stdout.decode().split() if stdout and stdout.strip() else []
                if pods:
                    await asyncio.create_subprocess_exec(
                        "oc", "delete", "pods", *pods, "--ignore-not-found",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
        except Exception:
            pass


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


async def _run_job(job_id: str, command: list[str]):
    """Run and monitor an Openshift Job."""
    global _active_job

    oj = OpenshiftJob(job_name=job_id)
    task = asyncio.current_task()
    assert task is not None
    _active_job = (job_id, task, oj)

    try:
        job_spec = oj._job_spec(command)
        await oj._run_oc_command(
            ["apply", "-f", "-"],
            stdin_data=json.dumps(job_spec).encode(),
        )
        await oj._wait_for_job_pod_ready()
        job_store.update_status(job_id, JobStatus.RUNNING)

        while True:
            stdout, _ = await oj._run_oc_command(
                ["get", "pod", f"--selector=job-name={oj._pod_name}", "-o", "json"],
                check=False,
            )
            if stdout:
                pods = json.loads(stdout).get("items", [])
                if pods:
                    phase = pods[0].get("status", {}).get("phase", "")
                    if phase == "Succeeded":
                        cleanup_err = await _best_effort_cleanup(oj)
                        job_store.update_status(
                            job_id, JobStatus.COMPLETED,
                            error=f"cleanup failed: {cleanup_err}" if cleanup_err else None,
                        )
                        return
                    if phase in ("Failed", "Unknown", "Error"):
                        reason = pods[0].get("status", {}).get("reason", "")
                        message = pods[0].get("status", {}).get("message", "")
                        cleanup_err = await _best_effort_cleanup(oj)
                        error = f"{phase}: reason={reason}, message={message}"
                        if cleanup_err:
                            error += f"; cleanup failed: {cleanup_err}"
                        job_store.update_status(job_id, JobStatus.FAILED, error=error)
                        return
            await asyncio.sleep(5)

    except asyncio.CancelledError:
        if _shutting_down:
            cleanup_err = await _best_effort_cleanup(oj)
            error = "Server shut down"
            if cleanup_err:
                error += f"; cleanup failed: {cleanup_err}"
            job_store.update_status(job_id, JobStatus.FAILED, error=error)
            raise
        cleanup_err = await _best_effort_cleanup(oj, signal=True)
        error = f"cleanup failed: {cleanup_err}" if cleanup_err else None
        job_store.update_status(job_id, JobStatus.CANCELLED, error=error)

    except Exception as e:
        cleanup_err = await _best_effort_cleanup(oj)
        error = str(e)
        if cleanup_err:
            error += f"; cleanup failed: {cleanup_err}"
        job_store.update_status(job_id, JobStatus.FAILED, error=error)

    finally:
        _active_job = None


async def _worker():
    """Process jobs from the queue one at a time."""
    while True:
        await _job_event.wait()
        _job_event.clear()
        while _job_queue:
            job_id, command = _job_queue.pop(0)
            row = job_store.get(job_id)
            if not row or row["status"] != JobStatus.QUEUED.value:
                continue
            await _run_job(job_id, command)

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
    columns = ["job_id", "job_name", "agent", "dataset", "model_name", "status", "error"]

    def build_table(title: str, jobs: list[dict]) -> str:
        header = "".join(f"<th>{col}</th>" for col in columns)
        rows = ""
        for job in jobs:
            cells = "".join(f"<td>{html.escape(str(job.get(col, '')) or '')}</td>" for col in columns)
            rows += f"<tr>{cells}</tr>"
        if not jobs:
            rows = f'<tr><td colspan="{len(columns)}">No jobs</td></tr>'
        return f"<h2>{title}</h2><table><tr>{header}</tr>{rows}</table>"

    running = job_store.list(JobStatus.RUNNING) + job_store.list(JobStatus.CANCELLING)
    queued = job_store.list(JobStatus.QUEUED)
    completed = job_store.list(JobStatus.COMPLETED) + job_store.list(JobStatus.CANCELLED)
    completed.reverse()

    html_page = f"""<!DOCTYPE html>
<html>
<head>
<title>Job Queue</title>
<meta http-equiv="refresh" content="5">
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
th {{ background: #f5f5f5; }}
</style>
</head>
<body>
<h1>Job Queue</h1>
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

    return command

@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(req: CreateJobRequest):
    """Create a new benchmark job."""
    # Verify the harbor command
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
    
    # Build the CLI comand
    command = build_cli_command(req=req)

    # Start the job
    job_id = str(uuid.uuid4())
    job_store.insert(job_id, req.job_name, req.agent.value, req.dataset, req.model_name, command)
    _job_queue.append((job_id, command))
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

    if job_row["status"] in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Job already {job_row['status']}")

    # Remove from queue if still waiting
    for i, (qid, _) in enumerate(_job_queue):
        if qid == job_id:
            _job_queue.pop(i)
            job_store.update_status(job_id, JobStatus.CANCELLED)
            return {"message": "Job cancelled", "job_id": job_id}

    # Cancel the actively running job
    if _active_job and _active_job[0] == job_id:
        job_store.update_status(job_id, JobStatus.CANCELLING)
        _active_job[1].cancel()
        return {"message": "Job cancelling", "job_id": job_id}

    return {"message": "Job cancelled", "job_id": job_id}

app.include_router(router)
