# Deployment Configs

## Validated Models

| Column | What it means |
|--------|---------------|
| **Model** | The model being served (from [Hugging Face](https://huggingface.co/RedHatAI), served via [vLLM](https://github.com/vllm-project/vllm) on OpenShift) |
| **GPU Pool** | Cluster GPU tier and hardware used (OpenShift machinepools with autoscaling, targeted via `nodeSelector` labels) |
| **Max Model Len** | Maximum context window in tokens (set via `--max-model-len` in vLLM) |
| **Max Concurrency** | How many requests the server can handle simultaneously at full context length (reported by vLLM at startup, use for `--n-tasks` in Harbor benchmark runs) |

| Model | GPU Pool | Max Model Len | Max Concurrency |
|-------|----------|---------------|-----------------|
| Qwen3.6-27B-FP8 | xlarge (4x L40S, 192GB) | 262,144 | 13.32x |

## CLI Commands

### `generate-manifest` — Generate a vLLM deployment manifest

Fetches model metadata from HuggingFace (parameter count, dtype, context length), estimates VRAM, selects the appropriate GPU pool, and outputs a complete OpenShift YAML manifest.

```bash
coding-agent-bench generate-manifest RedHatAI/Qwen3.6-27B-FP8 \
  --anyuid \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  --chat-template-kwargs '{"enable_thinking": true}' \
  --vllm-arg="--kv-cache-dtype fp8" \
  -o deploy/Qwen3.6_27b_FP8.yml
```

The tool auto-detects GPU requirements. Use `--dry-run` to see calculations without generating YAML. Use `--gpu-pool` to override the auto-selected pool, or `--gpu-pools-file` to point to a custom YAML defining available hardware. Pass `--anyuid` to include the anyuid SCC RoleBinding required by vLLM >v0.22 on OpenShift.

Any model on HuggingFace works — vLLM-specific args (reasoning parser, tool-call parser, chat template kwargs) come from the [vLLM docs](https://docs.vllm.ai/) and must be passed as flags since they aren't derivable from HuggingFace metadata.

### `deploy` — Deploy, validate, and manage a vLLM server

Combines manifest generation, `oc apply`, health check polling, and validation into one command.

```bash
# Deploy and validate (generates manifest, applies it, waits for health, runs checks)
coding-agent-bench deploy RedHatAI/Qwen3.6-27B-FP8 \
  --anyuid \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  --chat-template-kwargs '{"enable_thinking": true}' \
  --vllm-arg="--kv-cache-dtype fp8"

# Skip validation after deploy
coding-agent-bench deploy RedHatAI/Qwen3.6-27B-FP8 \
  --anyuid \
  --reasoning-parser qwen3 \
  --skip-validation

# Scale down (frees GPUs, keeps PVC with cached model weights for fast restart)
coding-agent-bench deploy RedHatAI/Qwen3.6-27B-FP8 --scale-down

# Full teardown (deletes all resources: SA, RoleBinding, PVC, Deployment, Service, Route)
coding-agent-bench deploy RedHatAI/Qwen3.6-27B-FP8 --teardown
```

**Validation checks** (ported from `scripts/manual/validate_deployment.sh`):
1. Model responding — queries `/v1/models` and verifies `max_model_len`
2. Concurrency — sends `--concurrency` (default 8) parallel requests, all must return 200
3. Tool calling — sends a tool-use request and verifies the model returns a `tool_calls` response

**Lifecycle flags:**
- `--scale-down` scales the deployment to 0 replicas. The PVC and cached weights remain, so scaling back up is faster than a fresh deploy.
- `--teardown` deletes all 6 resources created by the manifest. Use when you're done with a model entirely.
- `--health-timeout` sets how long to wait for the vLLM server to become healthy (default: 1800s / 30 min — large models on L40S can take a while due to bandwidth).

### GPU Pools

Available pools (configurable via `--gpu-pools-file`):

| Pool | GPUs | VRAM | nodeSelector |
|------|------|------|-------------|
| small | 1x L40S | 48 GB | `gpu-pool-size: small` |
| large | 4x L4 | 92 GB | `gpu-pool-size: large` |
| xlarge | 4x L40S | 192 GB | `gpu-pool-size: xlarge` |

The tool selects the smallest pool that fits the model's weight size + 15% overhead. To use custom hardware, create a YAML file:

```yaml
pools:
  a100:
    label: "gpu-pool-size=a100"
    gpus: 2
    gpu_model: A100
    vram_per_gpu: 80
```
