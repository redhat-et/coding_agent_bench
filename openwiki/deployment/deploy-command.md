---
type: component
title: Deploy Command
description: End-to-end vLLM deployment automation — generates manifest, applies it, waits for health, and validates the model server. Supports scale-down and teardown.
tags: [deploy, vllm, openshift, automation]
resource: src/coding_agent_bench/manifest.py
---

# Deploy Command

The `deploy` command combines manifest generation, `oc apply`, health check polling, and validation into a single operation. It is the primary way to deploy and manage vLLM model servers on OpenShift.

## Entry Point

```
src/coding_agent_bench/manifest.py:deploy()
```

CLI command: `uv run coding-agent-bench deploy <model-id> [options]`

## Lifecycle Commands

| Command | Description |
|---------|-------------|
| `deploy <model-id>` | Full deploy: generate, apply, wait, validate |
| `deploy <model-id> --scale-down` | Scale deployment to 0 replicas (preserves PVC and cached weights) |
| `deploy <model-id> --teardown` | Delete all resources (SA, RoleBinding, PVC, Deployment, Service, Route) |

## Full Deploy Flow

```mermaid
sequenceDiagram
    participant CLI
    participant deploy()
    participant _generate_manifest
    participant apply_manifest
    participant get_route_url
    participant wait_for_health
    participant get_vllm_concurrency
    participant validate_deployment

    CLI->>deploy(): model_id + options
    deploy()->>_generate_manifest(): model_id + options
    _generate_manifest()-->>deploy(): manifest_yaml
    deploy()->>apply_manifest(): manifest_yaml, namespace
    deploy()->>get_route_url(): app_name, namespace
    deploy()->>wait_for_health(): url, timeout=1800s
    alt healthy
        deploy()->>get_vllm_concurrency(): app_name, namespace
        deploy()->>validate_deployment(): url, model_name
    else timeout
        deploy()->>CLI: ValueError
    end
```

### Step 1: Generate Manifest

Calls `_generate_manifest()` with all CLI options. See [Manifest Generation](manifest-generation.md) for details.

### Step 2: Apply Manifest

```python
def apply_manifest(manifest_yaml: str, namespace: str) -> None
```

Runs `oc apply -f - -n <namespace>` with the generated YAML.

### Step 3: Get Route URL

```python
def get_route_url(app_name: str, namespace: str) -> str
```

Runs `oc get route <app_name> -o jsonpath='{.spec.host}' -n <namespace>` and returns `https://<host>`.

### Step 4: Wait for Health

```python
def wait_for_health(url: str, timeout_seconds: int = 1800, poll_interval: int = 30, initial_delay: int = 1200) -> bool
```

Polls `http://<url>/health` until:
- Returns 200 → success
- Timeout reached → failure

**Timing:**
- **Initial delay**: 1200s (20 minutes) before first health check — large models need time to download weights
- **Poll interval**: 30 seconds between checks
- **Total timeout**: 1800 seconds (30 minutes)

### Step 5: Get Concurrency

```python
def get_vllm_concurrency(app_name: str, namespace: str) -> tuple[int, float] | None
```

Extracts vLLM's reported max concurrency from pod logs:

```
Maximum concurrency for 262,144 tokens per request: 13.32x
```

Returns `(max_len, concurrency)` or `None` if not found.

### Step 6: Validate Deployment

```python
def validate_deployment(url: str, model_name: str, concurrency: int = 8) -> bool
```

Runs three validation checks:

#### Check 1: Model Responding

Queries `GET /v1/models` and verifies the model appears in the response with a `max_model_len`.

#### Check 2: Concurrency

Sends `concurrency` (default 8) parallel requests to `POST /v1/chat/completions` using a `ThreadPoolExecutor`. All must return 200.

#### Check 3: Tool Calling

Sends a tool-use request to `POST /v1/chat/completions` with:
- A `get_weather` function definition
- `tool_choice: "auto"`
- Verifies the response contains `tool_calls`

## Scale Down

```python
def scale_down(app_name: str, namespace: str) -> None
```

Runs `oc scale deployment/<app_name> --replicas=0 -n <namespace>`.

**Effect:** Frees GPUs but keeps the PVC with cached model weights. Scaling back up is faster than a fresh deploy.

## Teardown

```python
def teardown(app_name: str, namespace: str) -> None
```

Runs `oc delete route,svc,deployment,pvc,rolebinding,sa -l app=<app_name> --ignore-not-found -n <namespace>`.

**Effect:** Deletes all 6 resources created by the manifest.

## CLI Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model_id` | (required) | HuggingFace model ID |
| `--reasoning-parser` | `None` | vLLM reasoning parser |
| `--tool-call-parser` | `None` | vLLM tool-call parser |
| `--chat-template-kwargs` | `None` | JSON for `--default-chat-template-kwargs` |
| `--vllm-arg` | `[]` | Extra vLLM arg (repeatable) |
| `--gpu-pool` | `None` | Override GPU pool |
| `--gpu-pools-file` | `None` | Custom GPU pools YAML |
| `--max-model-len` | `None` | Override max model length |
| `--namespace` | `coding-agent-leaderboard` | OpenShift namespace |
| `--vllm-image` | `vllm/vllm-openai:v0.23.0` | vLLM container image |
| `--route-timeout` | `600s` | HAProxy route timeout |
| `--app-name` | `None` | Override app name |
| `--served-model-name` | `None` | Override served model name |
| `--anyuid` | `False` | Include anyuid SCC RoleBinding |
| `--before-script` | `None` | Shell command before vLLM starts |
| `--skip-validation` | `False` | Skip health check and validation |
| `--concurrency` | `8` | Number of parallel validation requests |
| `--health-timeout` | `1800` | Health check timeout in seconds |
| `--initial-delay` | `1200` | Initial delay before first health check |
| `--scale-down` | `False` | Scale deployment to 0 replicas |
| `--teardown` | `False` | Delete all resources |

## Evidence

- Source: `src/coding_agent_bench/manifest.py` (deploy, scale_down, teardown, wait_for_health, validate_deployment, get_vllm_concurrency, get_route_url, apply_manifest functions)
- CLI integration: `src/coding_agent_bench/cli.py` (generate_manifest command)
- Deploy configs: `deploy/README.md`
