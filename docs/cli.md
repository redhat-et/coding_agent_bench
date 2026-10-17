# CLI

## Prerequisites

- Install dependencies with uv
    
    ```bash
    uv sync
    ```

- Set up a vLLM server or other Anthropic- and OpenAI-compatible server
- Select a benchmark from among the options in [Harbor Hub](https://hub.harborframework.com/)
- Copy `.env.example` to `.env` and fill in the API keys for any providers you intend to use:
    ```
    ANTHROPIC_API_KEY=
    OPENAI_API_KEY=
    OPENROUTER_API_KEY=
    ```

## `run` - Run a Benchmark

The `run` command handles all the abstraction for running a benchmark with Harbor against a self-hosted model.
It simplifies the Harbor command into four primary components: the agent, the benchmark, the model name, and the server URL.

The following is the minimal configuration needed to run a job with the CLI:

```sh
uv run coding-agent-bench run \
    --agent <agent> \
    --dataset <benchmark-name> \
    --model-name <model-name> \
    --server-url <server-url>
```

For example, to run `swe-bench/swe-bench-verified` in Claude Code against a self-hosted model:

```sh
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset scale-ai/swe-bench-pro \
    --model-name my-model \
    --server-url http://my.server.url
```

If you want to see a preview of Harbor command that would be run for a given set of arguments without actually running the job, add the `--dry-run` flag.

> [!note]
> Additional configuration options are available, use `uv run coding-agent-bench run --help` to see them.

### Use Agent Skills

Pass one or more skill directories or Git sources with the repeatable `--skill`
option (`--skills` is an alias). Harbor installs the resolved skills into the
agent used by the benchmark.

To test a skill from your local filesystem:

```sh
uv run coding-agent-bench run \
    --agent opencode \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://my.server.url \
    --skill ./my-skills
```

Git sources make skills easy to share and reproduce. Repeat the option to test
multiple skill collections, for example Superpowers together with Caveman:

```sh
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://my.server.url \
    --skill obra/superpowers \
    --skill juliusbrussee/caveman
```

Harbor accepts `org/name` and `org/name@ref` shorthand and HTTP(S) Git URLs.
Repository shorthand loads skills from the repository's `skills/` directory.
Use a full URL such as
`https://github.com/org/repo/tree/<ref>/<subdir>` to select another directory.
Pin a tag or named branch with `@ref` (or in the full URL) when comparing
benchmark runs. Harbor resolves the reference to a commit and records that
commit in the job lock file for reproducibility.

### Run with Openshift

#### Prerequisites

1. Log into your OpenShift cluster and project, or create a new project:

    ```sh
    oc login --server=<server> --token=<token>
    oc project <project>
    ```

2. Copy the storage secret template locally:

    ```sh
    cp deploy/storage/base/secret.example.yaml deploy/storage/base/secret.yaml
    ```

    Fill in the values, then apply the secret:

    ```sh
    oc apply -f deploy/storage/base/secret.yaml
    ```

3. Create the RustFS service for artifact storage:

    ```sh
    oc apply -k deploy/storage/overlays/prod
    ```

4. Apply the service accounts for the orchestrator and task pods:

    ```sh
    oc kustomize deploy/job-queue | yq '. | select(.metadata.name == "harbor-orchestrator*")' | oc apply -f -
    oc kustomize deploy/job-queue | yq '. | select(.metadata.name == "harbor-task*")' | oc apply -f -
    ```

#### Run Tasks in Openshift (Orchestrate Locally)

Using the CLI, start a job and set `--environment openshift`, e.g.:

```bash
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset scale-ai/swe-bench-pro \
    --model-name my-model \
    --server-url http://my.server.url \
    --environment openshift
```

Skills used by a remote OpenShift Job must be public Git sources. Local paths
are rejected because they are not available inside the orchestrator pod. The
pod also needs outbound network access to the Git host.

```bash
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://my.server.url \
    --skill obra/superpowers@<ref> \
    --environment openshift
```


#### Run Tasks and Orchestrate in Openshift

Using the CLI, start a job with the `--remote` flag enabled and set `--environment openshift`, e.g.:

```bash
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset scale-ai/swe-bench-pro \
    --model-name my-model \
    --server-url http://my.server.url \
    --remote \
    --environment openshift
```

Skills used by a remote OpenShift Job must be public Git sources. Local paths
are rejected because they are not available inside the orchestrator pod. The
pod also needs outbound network access to the Git host.

```bash
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://my.server.url \
    --skill obra/superpowers@<ref> \
    --remote \
    --environment openshift
```

## Model Validation Utilities (Deprecated)

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

