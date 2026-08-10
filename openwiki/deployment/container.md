---
type: component
title: Container Definition
description: Docker container image for coding-agent-bench — Python 3.12 with uv, OpenShift CLI, MinIO client, and Nebius CLI.
tags: [container, docker, deployment]
resource: Containerfile
---

# Container Definition

The container image (`Containerfile`) packages all runtime dependencies for running benchmarks and managing the queue service on OpenShift.

## Base Image

```dockerfile
FROM python:3.12-slim
```

## Installed Tools

The container installs three external CLI tools:

| Tool | Purpose | Source |
|------|---------|--------|
| `oc` | OpenShift CLI | mirror.openshift.com |
| `mc` | MinIO client | dl.min.io |
| `nebius` | Nebius cloud CLI | storage.eu-north1.nebius.cloud |

Additional packages: `curl`, `git` (removed curl after installation).

## Python Environment

```dockerfile
RUN pip install --upgrade pip uv
COPY --chown=1001:1001 . .
RUN uv sync --no-cache
```

Uses `uv` for fast, reproducible dependency installation from `pyproject.toml` and `uv.lock`.

## User Configuration

- Runs as non-root user `1001`
- Home directory: `/home/harbor`
- Working directory: `/app`
- `HOME` env var set to `/home/harbor`

## Image Usage

Pushed to `ghcr.io/redhat-et/coding_agent_bench` via GitHub Actions and used as the container image for:

- **Queue service deployment** (`deploy/job-queue-service.yml`)
- **OpenshiftJob pods** (`job.py:_job_spec()`)

## Evidence

- Source: `Containerfile`
- CI: `.github/workflows/build-push.yml`
