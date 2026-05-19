# Coding Agent Bench

Reproducible benchmarks for coding agents and models using Harbor

## Leaderboards

### ✨ [Check out our Coding Agent Leaderboard on HuggingFace](https://huggingface.co/spaces/taagarwa/coding-agent-leaderboard) ✨

### SWE-Bench Verified (pass@1, N=500)

| Model                          | Harness     | Score                                                            | Cost            |
| ------------------------------ | ----------- | ---------------------------------------------------------------- | --------------- |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Pi          | [65.0%](./benchmarks/SWE_Bench_Qwen3.6_35b_NVFP4_Pi.md)          | $51<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Claude Code | [63.2%](./benchmarks/SWE_Bench_Qwen3.6_35b_NVFP4_Claude_Code.md) | $48<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | OpenCode    | [54.8%](./benchmarks/SWE_Bench_Qwen3.6_35b_NVFP4_OpenCode.md)    | $67<sup>†</sup> |


### SWE-Bench Pro - Ansible Tasks (pass@1, N=96)

| Model                          | Harness     | Score                                                                        | Cost            |
| ------------------------------ | ----------- | ---------------------------------------------------------------------------- | --------------- |
| Sonnet 4.6                     | Claude Code | [50.0%](./benchmarks/SWE_Bench_Pro_Ansible_Sonnet_4.6_Claude_Code.md)        | $184            |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Pi          | [47.9%](./benchmarks/SWE_Bench_Pro_Ansible_Qwen3.6_35b_NVFP4_Pi.md)          | $13<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Claude Code | [45.6%](./benchmarks/SWE_Bench_Pro_Ansible_Qwen3.6_35b_NVFP4_Claude_Code.md) | $10<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | OpenCode    | [37.5%](./benchmarks/SWE_Bench_Pro_Ansible_Qwen3.6_35b_NVFP4_OpenCode.md)    | $11<sup>†</sup> |

More coming soon...

<sup>†</sup> - Cost estimates for OSS models are calculated by ($4 per A100 GPU hour × agent benchmark duration).

## Prerequisites

- Install [Harbor](https://www.harborframework.com/docs/getting-started)

## Benchmarks

Set your benchmark in your environment from among the options in [Harbor Hub](https://hub.harborframework.com/), e.g.:

```bash
export BENCHMARK='swe-bench/swe-bench-verified'
```

## Harbor Commands

| Model Server     | Claude Code                                 | OpenCode                      | Gemini CLI |
| ---------------- | ------------------------------------------- | ----------------------------- | ---------- |
| VertexAI Claude  | [Link](#claude-code-vertexai-claude-docker) | TBD                           | N/A        |
| VertexAI Gemini  | N/A                                         | TBD                           | TBD        |
| vLLM             | [Link](#claude-code-vllm-docker)            | [Link](#opencode-vllm-docker) | TBD        |
| Ollama/llama.cpp | [Link](#claude-code-ollamallamacpp-docker)  | TBD                           | TBD        |


> [!note]
> You can resume a stopped job with `harbor job resume -p path/to/job`

### Claude Code VertexAI Claude Docker

Set the following variables in your environ:

```bash
export CLOUD_ML_REGION=
export ANTHROPIC_VERTEX_PROJECT_ID=
export ANTHROPIC_MODEL=
```

Then run:

```bash
harbor run --agent claude-code -d $BENCHMARK \
    --ae CLAUDE_CODE_USE_VERTEX=1 \
    --ae CLOUD_ML_REGION=$CLOUD_ML_REGION \
    --ae ANTHROPIC_VERTEX_PROJECT_ID=$ANTHROPIC_VERTEX_PROJECT_ID \
    --ae ANTHROPIC_MODEL=$ANTHROPIC_MODEL \
    --ae GOOGLE_APPLICATION_CREDENTIALS='/app/.config/gcloud/application_default_credentials.json' \
    --mounts-json '["~/.config/gcloud/application_default_credentials.json:/app/.config/gcloud/application_default_credentials.json"]'
```

### Claude Code vLLM Docker

Set the following variables in your environ:

```bash
export SERVER_URL=
export MODEL_NAME=
```

Then run:

```bash
harbor run --agent claude-code -d $BENCHMARK \
    --ae ANTHROPIC_BASE_URL=$SERVER_URL \
    --ae ANTHROPIC_API_KEY='sk-no-key-required' \
    --ae ANTHROPIC_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL_NAME
```

### Claude Code Ollama/llama.cpp Docker

Set the following variables in your environ:

```bash
export SERVER_URL='http://host.docker.internal:11434'
export MODEL_NAME=
```

Then run:

```bash
harbor run --agent claude-code -d $BENCHMARK \
    --ae ANTHROPIC_BASE_URL=$SERVER_URL \
    --ae ANTHROPIC_API_KEY='sk-no-key-required' \
    --ae ANTHROPIC_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL_NAME
```

### OpenCode vLLM Docker

Set the following variables in your environ:

```bash
export MODEL_NAME=
```

Set the content of your OpenCode config in your environ. Remember to replace the `<server-url>` with your vLLM server url and the `<model-name>` with your served model name:

```bash
export OPENCODE_CONFIG_CONTENT='{"$schema":"https://opencode.ai/config.json","model":"vllm/<model-name>","provider":{"vllm":{"npm":"@ai-sdk/openai-compatible","name":"vLLM","options":{"baseURL":"<server-url>"},"models":{"<model-name>":{"name":"<model-name>","limit":{"context":196500,"output":65500}}}}}}'
```

Then run:

```sh
harbor run --agent opencode -p $DATASET_DIR/swe-bench-verified \
    -m vllm/$MODEL_NAME \
    --ae "OPENCODE_CONFIG_CONTENT=$OPENCODE_CONFIG_CONTENT"
```

## SWE-Bench Acceleration

### Use accelerated images for SWE-bench-verified

1. Download the SWE-Bench-Verified tasks

```sh
harbor download swe-bench/swe-bench-verified
```

2. Replace images with the accelerated ones from [Epoch AI](https://epoch.ai/blog/swebench-docker)

```sh
uv run scripts/replace_swe_bench_images.py <path-to-dataset>
```

### Pre-pull base images

1. Download the dataset

```sh
harbor download <dataset>
```

2. Pull all the base images

```sh
uv run scripts/pull_images.py <path-to-dataset>
```


## WIP

### Run with Podman

Requires `podman` on PATH with a running Podman machine.

```bash
harbor run --agent claude-code -d $BENCHMARK \
    --ae ANTHROPIC_BASE_URL=$SERVER_URL \
    --ae ANTHROPIC_API_KEY='sk-no-key-required' \
    --ae ANTHROPIC_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL_NAME \
    --environment-import-path coding_agent_bench.harbor_envs.podman:PodmanEnvironment
```

### Run with Openshift

Login to your cluster and select a project:

```bash
oc login --token=<token> --server=<server>
oc project <project>
```

Then run:

```bash
harbor run --agent claude-code -d $BENCHMARK \
    --ae ANTHROPIC_BASE_URL=$SERVER_URL \
    --ae ANTHROPIC_API_KEY='sk-no-key-required' \
    --ae ANTHROPIC_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL_NAME \
    --environment-import-path coding_agent_bench.harbor_envs.openshift:OpenshiftEnvironment
```

### Run with Gemini and Gemini CLI

```bash
export GOOGLE_CLOUD_PROJECT="<your-project>"

harbor run --agent gemini-cli -d $BENCHMARK \
    -m $MODEL_NAME
```

### Run with Llama.cpp and Gemini CLI

```bash
harbor run --agent gemini-cli -d $BENCHMARK \
    --ae GOOGLE_GEMINI_BASE_URL=$SERVER_URL \
    --ae GEMINI_MODEL=$MODEL_NAME \
    -m $MODEL_NAME
```

## Deploy models with vLLM

Check out [`deploy/qwen-all-in-one.yml`](./deploy/qwen-all-in-one.yml) for a sample vLLM deployment of RedHatAI/Qwen3.6-35B-A3B-NVFP4.

Apply to your cluster by running:

```sh
oc apply -f deploy/qwen-all-in-one.yml
```

## Future Work

- [ ] Support running Harbor in Openshift
- [ ] Support running Harbor with Podman
- [ ] Support OpenCode configurations for vLLM and VertexAI
- [ ] Support Gemini CLI configurations for vLLM and VertexAI
