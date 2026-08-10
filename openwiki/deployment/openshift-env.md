---
type: component
title: OpenShift Environment
description: Harbor environment extension that runs benchmark tasks inside OpenShift pods, building images via oc build and streaming logs.
tags: [harbor, openshift, environment, container]
resource: src/coding_agent_bench/harbor_envs/openshift.py
---

# OpenShift Environment

The `OpenshiftEnvironment` class extends Harbor's `BaseEnvironment` to run benchmark tasks inside OpenShift pods. It is one of two environment adapters (alongside `PodmanEnvironment`) that allow Harbor to execute tasks in different runtime contexts.

## Architecture

```mermaid
classDiagram
    BaseEnvironment <|-- OpenshiftEnvironment
    OpenshiftEnvironment : +preflight()
    OpenshiftEnvironment : +start(force_build)
    OpenshiftEnvironment : +stop(delete)
    OpenshiftEnvironment : +exec(command)
    OpenshiftEnvironment : +_build_image()
    OpenshiftEnvironment : +_pod_spec(image)
    OpenshiftEnvironment : +_wait_for_pod_ready()
    OpenshiftEnvironment : +_start_log_streaming()
```

## Key Responsibilities

### 1. Image Building

Uses OpenShift `oc new-build` / `oc start-build` to build container images from the Harbor environment directory (which contains a `Dockerfile`). Build images are cached using `asyncio.Lock` per environment name to avoid duplicate builds.

```python
# Build flow
oc new-build --binary --name=<build_name> --strategy=docker
oc start-build <build_name> --from-dir=<env_dir> --follow --wait
```

### 2. Pod Spec Generation

Each task runs in a dedicated pod with:

- **Service account**: `harbor-task` (anyuid SCC only, no API access)
- **User**: root (`runAsUser: 0`) for unrestricted task execution
- **Restart policy**: `Never` (one-shot execution)
- **Log streaming**: Continuously tails `.log` and `.txt` files in `/logs/` to container logs

### 3. Pod Lifecycle

```mermaid
sequenceDiagram
    participant H as Harbor
    participant O as OpenshiftEnvironment
    participant K as OpenShift API
    
    H->>O: start(force_build=False)
    O->>O: check image exists
    alt image not found
        O->>K: new-build
        O->>K: start-build
    end
    O->>K: apply pod spec
    O->>O: wait_for_pod_ready()
    O->>O: wait_for_container_exec_ready()
    O->>K: exec mkdir + chmod
    O->>O: start_log_streaming()
    O->>O: upload_environment_dir_after_start()
```

### 4. Environment Validation

Requires at least one of:
- A `Dockerfile` in the environment directory
- A `docker_image` specified in `task_env_config`

### 5. Properties

| Property | Value |
|----------|-------|
| `type()` | `"openshift"` |
| `supports_gpus` | `False` |
| `can_disable_internet` | `False` |
| `is_mounted` | `False` |

## Name Sanitization

Pod and build names are sanitized to K8s-compatible identifiers:
- Lowercase, replace non-alphanumeric (except `-`) with `-`
- Strip leading dashes, prefix with `hb-` if needed
- Max 58 characters

## Evidence

- Source: `src/coding_agent_bench/harbor_envs/openshift.py`
- Used by: `HarborCommandBuilder._build_command()` when `environment == "openshift"`
- Import path: `coding_agent_bench.harbor_envs.openshift:OpenshiftEnvironment`
