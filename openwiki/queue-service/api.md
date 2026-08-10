---
type: component
title: Queue Service API
description: FastAPI queue service for scheduling and managing benchmark jobs on OpenShift, with Nebius cloud GPU provisioning and SQLite-backed job persistence.
tags: [queue, fastapi, api, openshift, nebius]
resource: src/coding_agent_bench/api.py
---

# Queue Service API

The queue service is a FastAPI application that provides a REST API for queuing, monitoring, and managing benchmark jobs on OpenShift. It supports Nebius cloud GPU auto-provisioning for models that aren't already deployed.

## Entry Point

```
src/coding_agent_bench/api.py:app
```

Deployed via `uvicorn coding_agent_bench.api:app --host 0.0.0.0 --port 8000` inside an OpenShift container.

## Architecture

```mermaid
flowchart TD
    subgraph "FastAPI App"
        A[FastAPI lifespan] --> B[JobStore init]
        A --> C[_worker loop]
        A --> D[_build_pod_cleanup_loop]
        A --> E[NebiusOrchestrator (if enabled)]
    end
    subgraph "Job Processing"
        C --> F[_reorder_queue_for_nebius]
        F --> G{server_url == nebius?}
        G -->|yes| H[NebiusOrchestrator.acquire_instance]
        G -->|no| I[_run_job]
        H --> I
        I --> J[OpenshiftJob.run_async]
        J --> K[oc apply Job]
        K --> L[poll pod status]
        L --> M{phase?}
        M -->|Succeeded| N[COMPLETED]
        M -->|Failed| O[FAILED]
    end
    subgraph "Persistence"
        P[SQLite: jobs.db] --> Q[JobStore]
        Q --> R[insert / get / list / update_status]
    end
```

## Application Lifecycle

### Startup (`lifespan` context manager)

1. Calls `job_store.mark_orphaned()` — marks QUEUED/RUNNING/CANCELLING jobs as FAILED with error "Server restarted"
2. If `NEBIUS_ENABLED=1`:
   - Creates `NebiusInstanceManager` with credentials from environment
   - Creates `NebiusOrchestrator` with subnet, GPU config, idle timeout
   - Starts idle cleanup background task
3. Starts `_worker()` — main job processor loop
4. Starts `_build_pod_cleanup_loop()` — deletes completed/failed build pods every 5 minutes

### Shutdown

1. Sets `_shutting_down = True`
2. Cancels worker and cleanup tasks
3. Waits for graceful cancellation

## API Endpoints

All endpoints except `/` and `/ui` require API key authentication via `X-API-Key` header.

### `GET /`

Returns `{"message": "API is live."}` — health check endpoint, no auth required.

### `GET /ui`

Returns an HTML dashboard showing:
- Nebius instance states (if enabled): instance name, current model, status, last job completed
- Running jobs table
- Queued jobs table
- Completed/failed/cancelled jobs table (newest first)

Auto-refreshes every 5 seconds. No auth required (read-only, no secrets exposed).

### `POST /jobs` — Create a Job

**Request:** `CreateJobRequest`

```python
class CreateJobRequest(BaseModel):
    job_name: str
    agent: SupportedAgent
    dataset: str
    model_name: str
    server_url: str
    dataset_pattern: Optional[str] = None
    n_concurrent: int = 1
    n_tasks: Optional[int] = None
    model_max_len: int = 262000
    before_script: Optional[str] = None
    agent_version: Optional[str] = None
```

**Response:** `CreateJobResponse`

```python
class CreateJobResponse(BaseModel):
    message: str
    job_id: str
    job_name: str
    command: list[str]
```

**Flow:**
1. Validates the command (skips validation for `server_url="nebius"`)
2. If `server_url="nebius"` but Nebius is not enabled → 400 error
3. Generates a UUID `job_id`
4. Inserts job into `JobStore` with status `QUEUED`
5. Appends to `_job_queue` and signals the worker
6. Returns the job details

### `GET /jobs` — List Jobs

**Query params:** `status: JobStatus | None = None`

**Response:** `list[JobResponse]`

```python
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
```

Filters by status if provided.

### `GET /jobs/{job_id}` — Get Job

Returns a single job by ID, or 404 if not found.

### `DELETE /jobs/{job_id}` — Cancel Job

**Flow:**
1. Looks up the job
2. If already COMPLETED/FAILED/CANCELLED → 400 error
3. Removes from `_job_queue` if still waiting → sets status to CANCELLED
4. If actively running (`_active_job`), cancels the worker task → sets status to CANCELLING
5. Returns `{"message": "Job cancelled", "job_id": job_id}`

### `POST /jobs/{job_id}/resume` — Resume Failed Job

**Request:** `ResumeJobRequest`

```python
class ResumeJobRequest(BaseModel):
    filter_error_types: list[str] = []
    server_url: Optional[str] = None
```

**Response:** `{"message": "Resume job created", "job_id": str, "job_name": str, "parent_job_id": str}`

**Flow:**
1. Validates the job is COMPLETED or FAILED
2. Creates a new resume job with name `{original_name}--resume`
3. Downloads results from MinIO: `mc cp --recursive minio/results/<job-name>/ <job-dir>/`
4. If `server_url` is provided, runs a Python script to:
   - Replace old server URLs in all JSON config files (matching domain patterns)
   - Regenerate Pi `models.json` and Codex `config.toml` with new URL
5. Runs `harbor jobs resume -p <job-dir>` with optional `-f <error_type>` filters
6. Uploads updated results back to MinIO
7. Inserts the resume command into the job queue

## Internal Components

### `JobStore`

SQLite-backed job persistence. Single table:

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    job_name TEXT NOT NULL,
    agent TEXT NOT NULL,
    dataset TEXT NOT NULL,
    model_name TEXT NOT NULL,
    server_url TEXT NOT NULL DEFAULT '',
    command TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    error TEXT
)
```

Methods: `insert()`, `update_status()`, `get()`, `list()`, `mark_orphaned()`

### `_worker()` — Job Processor

Single-threaded loop that:
1. Waits on `_job_event` (set by `create_job`)
2. Calls `_reorder_queue_for_nebius()` to optimize for model reuse
3. Pops the next QUEUED job from `_job_queue`
4. If `server_url == "nebius"`:
   - Calls `NebiusOrchestrator.acquire_instance(model_name)`
   - Patches the command with the real server URL
   - Marks the instance as job-running
5. Calls `_run_job(job_id, command)`
6. Marks the Nebius instance as job-completed (if applicable)

### `_run_job()` — Execute a Single Job

1. Creates `OpenshiftJob(job_name=job_id)`
2. Sets `_active_job = (job_id, task, oj)`
3. Generates job spec (standard or resume)
4. Applies via `oc apply -f -`
5. Waits for pod readiness
6. Updates status to RUNNING
7. Polls pod status every 5 seconds until Succeeded/Failed
8. On completion: calls `_best_effort_cleanup()` and updates status
9. On cancellation: signals the pod, deletes the job
10. On error: deletes the job, updates status to FAILED

### `NebiusOrchestrator`

Manages a pool of Nebius GPU instances. Currently designed for single-instance but extensible.

```python
class NebiusOrchestrator:
    def __init__(self, manager, subnet_id, gpu_config, instance_name_prefix, idle_timeout)
    
    async def acquire_instance(model_name) -> (instance_name, server_url)
    async def mark_job_started(instance_name)
    async def mark_job_completed(instance_name)
    async def idle_cleanup_loop()
    def get_instance_states() -> list[NebiusInstanceState]
```

**`acquire_instance()` flow:**
1. Reuses an existing instance with the same model, or any idle instance
2. Creates a new instance if none available
3. Starts the instance if stopped
4. Swaps the model if different from `current_model`
5. Fetches the public IP and returns `http://<ip>:8000`

**Idle cleanup:** Deletes instances that have been idle longer than `NEBIUS_IDLE_TIMEOUT_SECONDS` (default: 600s).

### `NebiusInstanceState`

```python
@dataclass
class NebiusInstanceState:
    instance_name: str
    current_model: str | None = None
    provisioning_model: str | None = None
    job_running: bool = False
    last_job_completed_at: float | None = None
```

### `_reorder_queue_for_nebius()`

Stable-sorts the queue so that Nebius jobs matching the currently loaded model come first, minimizing expensive model swaps.

### `_build_pod_cleanup_loop()`

Every 5 minutes, deletes pods with `status.phase in (Succeeded, Failed)` and label `openshift.io/build.name` set.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `JOB_STORE_PATH` | `jobs.db` | SQLite database path |
| `API_KEY` | (required) | API key for authentication |
| `NEBIUS_ENABLED` | `0` | Enable Nebius auto-provisioning |
| `NEBIUS_SERVICE_ACCOUNT_CREDS_PATH` | (required if enabled) | Path to service account credentials |
| `NEBIUS_USER` | (required if enabled) | SSH user for Nebius instances |
| `NEBIUS_SSH_PUBLIC_KEY_PATH` | (required if enabled) | SSH public key path |
| `NEBIUS_SSH_PRIVATE_KEY_PATH` | (required if enabled) | SSH private key path |
| `NEBIUS_PARENT_ID` | (required if enabled) | Nebius parent ID |
| `NEBIUS_TENANT_ID` | (required if enabled) | Nebius tenant ID |
| `NEBIUS_SERVICE_ACCOUNT_ID` | (required if enabled) | Nebius service account ID |
| `NEBIUS_SUBNET_ID` | (required if enabled) | Nebius subnet ID |
| `NEBIUS_GPU_CONFIG` | `h200` | GPU preset (b200 or h200) |
| `NEBIUS_INSTANCE_NAME_PREFIX` | `cab-worker` | Instance name prefix |
| `NEBIUS_IDLE_TIMEOUT_SECONDS` | `600` | Idle timeout before instance deletion |

## Deployment

Deployed via `deploy/job-queue-service.yml`:
- PVC for persistent SQLite storage (`job-queue-pvc`)
- Deployment with `uvicorn` command
- Service (ClusterIP port 80 → 8000)
- Route (`job-queue-route`) for external access
- API key from `job-queue-secret` secret

## Evidence

- Source: `src/coding_agent_bench/api.py`
- Job orchestration: `src/coding_agent_bench/job.py`
- Nebius utilities: `src/coding_agent_bench/nebius_utils.py`
- Deployment: `deploy/job-queue-service.yml`
- Container: `Containerfile`
