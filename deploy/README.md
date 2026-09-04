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

Any model on HuggingFace works — vLLM-specific args (reasoning parser, tool-call parser, chat template kwargs) come from the [vLLM docs](https://docs.vllm.ai/) and must be passed as flags since they aren't derivable from HuggingFace metadata. See [Model-Specific Args](#model-specific-vllm-args) below for the flags each model needs.

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

### Model-Specific vLLM Args

Each model requires different vLLM flags for reasoning and tool calling. The `--enable-auto-tool-choice` flag is always included automatically.

**Qwen3.6-27B-FP8** ([HuggingFace](https://huggingface.co/RedHatAI/Qwen3.6-27B-FP8))

```bash
coding-agent-bench deploy RedHatAI/Qwen3.6-27B-FP8 --anyuid \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  --chat-template-kwargs '{"enable_thinking": true}'
```

**Gemma-4-31B-it-FP8-block** ([HuggingFace](https://huggingface.co/RedHatAI/gemma-4-31B-it-FP8-block))

```bash
coding-agent-bench deploy RedHatAI/gemma-4-31B-it-FP8-block --anyuid \
  --reasoning-parser gemma4 \
  --tool-call-parser gemma4 \
  --chat-template-kwargs '{"enable_thinking": true}'
```

**Mistral-Small-4-119B-2603** ([HuggingFace](https://huggingface.co/RedHatAI/Mistral-Small-4-119B-2603))

```bash
coding-agent-bench deploy RedHatAI/Mistral-Small-4-119B-2603 --anyuid \
  --reasoning-parser mistral \
  --tool-call-parser mistral \
  --chat-template-kwargs '{"reasoning_effort": "high"}'
```

**gpt-oss-120b** ([HuggingFace](https://huggingface.co/RedHatAI/gpt-oss-120b))

```bash
coding-agent-bench deploy RedHatAI/gpt-oss-120b --anyuid \
  --tool-call-parser openai
```

**NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4** ([HuggingFace](https://huggingface.co/RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4))

```bash
coding-agent-bench deploy RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 --anyuid \
  --reasoning-parser nemotron_v3 \
  --tool-call-parser qwen3_coder \
  --before-script "wget https://raw.githubusercontent.com/RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4/refs/heads/main/nemotron_nas_parser.py"
```

Nemotron requires downloading a custom parser before vLLM starts. The `--before-script` flag prepends a shell command to the container's entrypoint.

### GPU Pools

Available pools (configurable via `--gpu-pools-file`):

| Pool | GPUs | VRAM | nodeSelector |
|------|------|------|-------------|
| small | 1x L40S | 48 GB | `gpu-pool-size: small` |
| large | 4x L4 | 92 GB | `gpu-pool-size: large` |
| xlarge | 4x L40S | 192 GB | `gpu-pool-size: xlarge` |

The tool selects the smallest pool that fits the model's estimated VRAM (weights + 15% overhead + KV cache for one full-context request). KV cache estimation accounts for sliding window attention where applicable. To use custom hardware, create a YAML file:

```yaml
pools:
  a100:
    label: "gpu-pool-size=a100"
    gpus: 2
    gpu_model: A100
    vram_per_gpu: 80
```

## Intake Poller

The `intake-poller` CronJob (`deploy/intake-cronjob.yml`) reads benchmark
requests from a Google Sheet, submits approved rows to the job queue, and emails
submitters when a job is queued, completed, or failed. It runs every 6 hours.

### Google Sheet

The poller reads from a tab named `Queue` (not the raw `Form Responses 1` tab),
laid out in the exact order of `coding_agent_bench.intake.config.Column`. A
scheduled Apps Script macro (`scripts/manual/intake_queue_sync.gs`) copies new
form responses into that tab, mapping columns by header name so the form's
question order can change without breaking the poller. Install the macro via
Extensions > Apps Script and add a form-submit or time-driven trigger for
`syncFormResponsesToQueue`.

### Secrets

**`job-queue-secret`** — shared with the job-queue Deployment. Keep `API_KEY`
and queue-service or Nebius settings here. Poller-only settings belong in the
separate `intake-poller-secret` described below.

| Key | Description |
|-----|-------------|
| `API_KEY` | API key for the job-queue service |

The intake payload intentionally leaves concurrency and model context length
unset. The queue service applies its configured defaults and model-specific
`ModelConfig` values. Do not add plaintext `http://` endpoints to the
poller secret; `ALLOW_INSECURE_QUEUE_HTTP=true` is supported only for local
development.

**`intake-poller-secret`** — read only by the intake CronJob. Create it with:

| Key | Description |
|-----|-------------|
| `GOOGLE_SHEET_ID` | ID of the intake Google Sheet (the value between `/d/` and `/edit` in its URL) |
| `JOB_QUEUE_URL` | HTTPS URL for the queue API. Use the cluster's TLS/mTLS endpoint; the poller fails closed instead of using plaintext HTTP. |
| `SENDER_EMAIL` | Address notification emails are sent from. Set it to `ace-model-evals@redhat.com`. |
| `AUTO_APPROVE` | `"true"` to auto-submit rows with a blank status, otherwise `"false"` |

### Queue TLS

`deploy/job-queue-service.yml` enables OpenShift's service-serving certificate
operator with the `service.beta.openshift.io/serving-cert-secret-name`
annotation. The operator creates `job-queue-tls` with `tls.crt`, `tls.key`, and
the service CA; the queue mounts that Secret and Uvicorn serves HTTPS on port
8443. The Service exposes it as port 443 and the Route uses `reencrypt`
termination, keeping router-to-pod traffic encrypted as well. Apply the
manifest before starting the poller and wait for `job-queue-tls` to be created.

The URL check runs before a job is queued and again immediately before its
worker pod is created, covering DNS changes and private or link-local targets.
Managed Nebius endpoints are checked as public provider-generated addresses.

For managed Nebius capacity, an approver can set `SERVER_URL` to an explicit
resource token such as `nebius-h200` (or `nebius-b200x8`). The queue service
validates that token, provisions the instance, and supplies its endpoint after
approval; the requester never needs to know that endpoint.

**`intake-poller-google-sa`** — the Google service-account credential mounted
at `/etc/google/service-account.json` for Sheets access. Notification email is
sent through the internal SMTP relay, so no Gmail mailbox credential or
domain-wide delegation is required.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: intake-poller-google-sa
type: Opaque
stringData:
  service-account.json: <sa-file-content>
```

The CronJob sends notifications through `smtp.corp.redhat.com` on port 25.
Set `SMTP_HOST` and `SMTP_PORT` on the poller when a different internal relay
is required. Set `SMTP_STARTTLS=true` when that relay requires STARTTLS. The
configured `SENDER_EMAIL` must be an address permitted by the relay.

Each submitted Queue row carries a deterministic idempotency key. If the
CronJob is retried after a network timeout, the queue API returns the original
job instead of creating a duplicate.
