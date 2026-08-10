---
type: overview
title: Coding Agent Bench — Quickstart
description: Entry point to the coding-agent-bench wiki — a system for running reproducible coding agent benchmarks against self-hosted vLLM models on Docker or OpenShift, with a deployable queue service and pre-built leaderboards.
tags: [overview, quickstart]
---

# Coding Agent Bench — Quickstart

Reproducible benchmarks for coding agents and models using [Harbor](https://www.harborframework.com/).

## What This Repository Does

1. **Run benchmarks** — Execute coding agent evaluations (SWE-bench, SWE-bench Pro, Terminal Bench) against self-hosted vLLM models using the CLI or a queue service
2. **Deploy models** — Generate and apply OpenShift deployment manifests for vLLM model servers with automatic VRAM estimation and GPU pool selection
3. **Queue jobs** — Run a FastAPI queue service on OpenShift to orchestrate benchmark runs asynchronously with Nebius cloud GPU auto-provisioning
4. **Track results** — Collect per-task scorecards, compute metrics, and produce markdown leaderboards

## High-Level Architecture

```mermaid
flowchart TD
    subgraph "CLI"
        A["uv run coding-agent-bench run"] --> B[HarborCommandBuilder]
        B --> C["harbor run --agent ... --model ..."]
        A --> D["generate-manifest"]
        D --> E[manifest.py]
        E --> F["OpenShift YAML"]
        A --> G["deploy"]
        G --> E
    end

    subgraph "Queue Service"
        H["POST /jobs"] --> I[JobStore (SQLite)]
        I --> J[_worker()]
        J --> K{nebius?}
        K -->|yes| L[NebiusOrchestrator]
        L --> M[acquire_instance]
        M --> N["start vLLM on GPU"]
        K -->|no| O["use server_url directly"]
        J --> O
        N --> P[OpenshiftJob]
        O --> P
        P --> Q["oc apply Job spec"]
        Q --> R["Wait for pod"]
        R --> S["Upload to MinIO"]
    end

    subgraph "Environments"
        C --> T[Docker]
        C --> U[OpenShift]
        P --> U
    end
```

## Key Concepts

| Concept | Description | Wiki Page |
|---------|-------------|-----------|
| **Harbor Command Builder** | Constructs `harbor run` commands for 6 supported agents with per-agent env vars, mounts, and model prefixes | [Command Builder](core/command-builder.md) |
| **Agent Configs** | Per-agent configuration classes (Claude Code, Codex, OpenClaw, OpenCode, Pi, OpenHands) with registry | [Agent Configs](core/agent-configs.md) |
| **Job Orchestration** | `OpenshiftJob` class manages Kubernetes Job lifecycle (create, wait, signal, cleanup) | [Job Orchestration](core/job-orchestration.md) |
| **Model Configs** | Predefined vLLM configurations for 5 RedHatAI models with reasoning/tool-call parsers | [Model Configs](core/model-configs.md) |
| **Manifest Generation** | Fetches HuggingFace metadata, estimates VRAM, selects GPU pool, generates OpenShift YAML | [Manifest Generation](deployment/manifest-generation.md) |
| **Deploy Command** | End-to-end deploy: generate → apply → wait for health → validate (3 checks) | [Deploy Command](deployment/deploy-command.md) |
| **Queue Service** | FastAPI API with SQLite persistence, async worker, Nebius GPU provisioning | [Queue Service API](queue-service/api.md) |
| **Nebius Integration** | Cloud GPU instance management — create, start, stop, model swap, idle cleanup | [Nebius Integration](core/nebius-integration.md) |
| **Environments** | Harbor `BaseEnvironment` extensions for OpenShift (pod-based) and Podman (container-based) | [OpenShift Env](deployment/openshift-env.md) · [Podman Env](deployment/podman-env.md) |
| **Datasets** | Benchmark task directories — SWE-bench Verified, SWE-bench Pro, Tau3-bench, etc. | [Datasets](datasets/overview.md) |
| **Benchmark Results** | Scorecards, leaderboards, metrics calculation, MinIO result storage | [Benchmark Results](benchmarks/overview.md) |
| **Container** | Python 3.12-slim image with uv, oc CLI, MinIO client, Nebius CLI | [Containerfile](deployment/container.md) |
| **CI/CD** | GitHub Actions — build and push to GHCR on push to main | [CI/CD](operations/ci-cd.md) |
| **Deployment Configs** | OpenShift manifests for queue service, MinIO, service accounts, model servers | [Deployment Configs](operations/deployment-configs.md) |

## Task Routing

| Your Goal | Start Here | Key Source Files |
|-----------|-----------|-----------------|
| Run a benchmark locally | [CLI Tool](cli/tool.md) → [Command Builder](core/command-builder.md) | `src/coding_agent_bench/cli.py`, `src/coding_agent_bench/builder.py` |
| Add a new coding agent | [Agent Configs](core/agent-configs.md) | `src/coding_agent_bench/agents/configs.py` |
| Deploy a vLLM model server | [Deploy Command](deployment/deploy-command.md) → [Manifest Generation](deployment/manifest-generation.md) | `src/coding_agent_bench/manifest.py` |
| Run benchmarks on OpenShift | [Job Orchestration](core/job-orchestration.md) → [OpenShift Env](deployment/openshift-env.md) | `src/coding_agent_bench/job.py`, `src/coding_agent_bench/harbor_envs/openshift.py` |
| Queue and orchestrate jobs | [Queue Service API](queue-service/api.md) | `src/coding_agent_bench/api.py` |
| Auto-provision GPU instances | [Nebius Integration](core/nebius-integration.md) | `src/coding_agent_bench/nebius_utils.py` |
| Build the container image | [Containerfile](deployment/container.md) | `Containerfile` |
| Analyze benchmark results | [Benchmark Results](benchmarks/overview.md) → [Scripts](scripts/overview.md) | `scripts/calculate_metrics.py`, `scripts/pass_rate.py` |
| Set up the queue service | [Deployment Configs](operations/deployment-configs.md) | `deploy/job-queue-service.yml` |

## Quick Commands

```bash
# Install dependencies
uv sync

# Run a benchmark locally (Docker)
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://localhost:8000

# Run on OpenShift (remote)
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://localhost:8000 \
    --environment openshift \
    --remote

# Generate and deploy a vLLM model server
uv run coding-agent-bench deploy \
    RedHatAI/Qwen3.6-27B-FP8 \
    --anyuid \
    --reasoning-parser qwen3 \
    --tool-call-parser qwen3_coder

# Generate manifest only (dry run)
uv run coding-agent-bench generate-manifest \
    RedHatAI/Qwen3.6-27B-FP8 \
    --dry-run

# Queue a benchmark run via API
curl -X POST $JOB_QUEUE_URL/jobs \
    -d '{"job_name": "test", "agent": "pi", "dataset": "swe-bench/swe-bench-verified",
         "model_name": "qwen3.6-27b", "server_url": "http://my-server:8000", "n_tasks": 1}' \
    -H "Content-Type: application/json" \
    -H "X-API-Key: my-key"
```

## Evidence

- Source: `src/coding_agent_bench/`
- CLI entry: `src/coding_agent_bench/cli.py:app`
- Queue entry: `src/coding_agent_bench/api.py:app`
- Container: `Containerfile`
- CI/CD: `.github/workflows/build-push.yml`
