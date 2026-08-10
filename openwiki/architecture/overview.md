---
type: architecture
title: Architecture Overview
description: High-level system architecture of coding-agent-bench — the CLI tool, FastAPI queue service, Harbor integration, OpenShift orchestration, Nebius cloud integration, and vLLM deployment pipeline.
tags: [architecture, overview]
---

# Architecture Overview

Coding Agent Bench is a multi-component system for benchmarking AI coding agents. It consists of four major subsystems:

## System Components

```mermaid
graph TB
    subgraph CLI
        A[coding-agent-bench run] --> B[HarborCommandBuilder]
        A --> C[generate-manifest]
        A --> D[deploy]
        A --> E[OpenshiftJob]
    end
    
    subgraph Queue Service
        F[FastAPI API] --> G[SQLite JobStore]
        F --> H[async Worker]
        H --> I[OpenshiftJob]
        H --> J[NebiusOrchestrator]
    end
    
    subgraph Harbor
        B --> K[harbor run]
        K --> L[Agent Configs]
        K --> M[Environment Adapters]
    end
    
    subgraph OpenShift
        E --> O[Pod Spec]
        I --> P[K8s Job]
        P --> Q[Task Pod]
    end
    
    subgraph Cloud
        J --> R[Nebius Instance Manager]
        R --> S[GPU VMs]
    end
    
    subgraph vLLM
        C --> T[Model Metadata]
        T --> U[VRAM Estimation]
        U --> V[GPU Pool Selection]
        V --> W[OpenShift YAML]
        D --> X[oc apply]
        X --> Y[vLLM Deployment]
    end
    
    L --> Z[Agent Configurations]
    Z --> AA[Claude Code]
    Z --> AB[Codex]
    Z --> AC[OpenClaw]
    Z --> AD[OpenCode]
    Z --> AE[Pi]
    Z --> AF[OpenHands]
```

## Data Flow

### CLI Benchmark Run

```mermaid
sequenceDiagram
    participant User
    participant CLI as coding-agent-bench
    participant Builder as HarborCommandBuilder
    participant Agent as AgentConfig
    participant Harbor as harbor run
    participant Env as Environment
    
    User->>CLI: run --agent claude-code --dataset swe-bench-verified
    CLI->>Builder: build(agent, dataset, model_name, server_url)
    Builder->>Agent: get_agent_config("claude-code")
    Agent-->>Builder: AgentConfigResult(env_vars, mounts)
    Builder-->>CLI: harbor run --agent claude-code ...
    CLI->>Harbor: subprocess.Popen(harbor_command)
    Harbor->>Env: OpenshiftEnvironment.start()
    Env->>Env: oc new-build + start-build
    Env->>Env: apply pod spec
    Harbor->>Env: exec task commands
    Env-->>Harbor: ExecResult
    Harbor-->>CLI: Job complete
    CLI-->>User: Job output dir
```

### Queue Service Job

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Store as SQLite JobStore
    participant Worker as async worker
    participant Job as OpenshiftJob
    participant Nebius as NebiusOrchestrator
    participant K8s as OpenShift API
    
    Client->>API: POST /jobs
    API->>API: validate request
    API->>Store: insert job
    Store-->>API: job_id
    API-->>Client: {job_id, command}
    
    loop Worker loop
        Worker->>Store: get(queued jobs)
        alt nebius server_url
            Worker->>Nebius: acquire_instance(model_name)
            Nebius->>Nebius: create/start instance
            Nebius->>Nebius: start_model()
            Nebius-->>Worker: (instance_name, server_url)
        end
        Worker->>Job: apply pod spec
        Job->>K8s: oc apply -f
        K8s-->>Job: pod ready
        Job->>K8s: poll pod phase
        alt Succeeded
            K8s-->>Job: Succeeded
            Job->>Store: update_status(COMPLETED)
        else Failed
            K8s-->>Job: Failed
            Job->>Store: update_status(FAILED)
        end
        alt nebius
            Worker->>Nebius: mark_job_completed()
        end
    end
```

## Key Design Decisions

1. **Harbor as orchestrator**: The project delegates task execution to [Harbor](https://github.com/redhat-et/harbor), a benchmarking framework. This library focuses on agent configuration, job orchestration, and deployment tooling.

2. **Pluggable agent configs**: Each coding agent (Claude Code, Codex, OpenClaw, etc.) has its own `AgentConfig` subclass that produces agent-specific environment variables, model names, and volume mounts.

3. **Environment adapters**: Harbor's `BaseEnvironment` is extended for OpenShift (`OpenshiftEnvironment`) and Podman (`PodmanEnvironment`), allowing Harbor to run tasks in different container runtimes.

4. **Manifest automation**: The `manifest.py` module fetches HuggingFace model metadata, estimates VRAM requirements, selects GPU pools, and generates complete OpenShift YAML manifests — no manual configuration needed.

5. **Queue service**: A FastAPI application with SQLite persistence provides a REST API for queuing benchmark jobs, with an async worker that manages OpenShift Job lifecycle and optional Nebius GPU provisioning.

## Evidence

- Source: `src/coding_agent_bench/`, `Containerfile`, `deploy/`
- Orchestration: [Harbor framework](https://github.com/redhat-et/harbor)
- Deployment: OpenShift with vLLM
