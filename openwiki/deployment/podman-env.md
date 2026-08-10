---
type: component
title: Podman Environment
description: Harbor environment extension that runs benchmark tasks inside local Podman containers.
tags: [harbor, podman, environment, container]
resource: src/coding_agent_bench/harbor_envs/podman.py
---

# Podman Environment

The `PodmanEnvironment` class extends Harbor's `BaseEnvironment` to run benchmark tasks inside local Podman containers. It provides a lightweight alternative to `OpenshiftEnvironment` for local development and testing.

## Key Methods

### `start(force_build: bool)`

1. If `force_build=False` and `task_env_config.docker_image` is set, uses the pre-built image directly.
2. Otherwise, builds an image from the environment directory's `Dockerfile`.
3. Removes any stale container with the same name.
4. Runs the container in detached mode with CPU/memory limits and environment variables.
5. Waits for the container to reach `running` state.
6. Creates required directories (`agent_dir`, `verifier_dir`, `artifacts_dir`) inside the container.

### `stop(delete: bool)`

1. Force-removes the container.
2. If `delete=True`, also removes the built image.

### `exec(command, cwd, env, timeout_sec, user)`

Executes a command inside the running container via `podman exec`.

### `attach()`

Attaches interactively to the container with `podman exec -it <container> bash`.

## Properties

| Property | Value |
|----------|-------|
| `type()` | `"podman"` |
| `supports_gpus` | `False` |
| `can_disable_internet` | `False` |
| `is_mounted` | `False` |

## Name Sanitization

- Container names: lowercase, replace non-alphanumeric (except `._-`) with `-`, max 63 chars
- Image names: lowercase, replace non-alphanumeric (except `._-`) with `-`, prefix with `0` if starting with non-alphanumeric

## Evidence

- Source: `src/coding_agent_bench/harbor_envs/podman.py`
- Used by: `HarborCommandBuilder._build_command()` when `environment == "docker"` (maps to Podman)
