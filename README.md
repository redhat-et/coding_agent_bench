# Coding Agent Bench

Benchmark coding agents and models using Harbor

## Prerequisites

- Install [Harbor](https://www.harborframework.com/docs/getting-started)

## Benchmarks

Set your benchmark in your environment from among the options in [Harbor Hub](https://hub.harborframework.com/), e.g.:

```bash
export BENCHMARK='swe-bench/swe-bench-verified'
```

## Harbor Commands

| Model Server     | Claude Code                                 | OpenCode | Gemini CLI |
| ---------------- | ------------------------------------------- | -------- | ---------- |
| VertexAI Claude  | [Link](#claude-code-vertexai-claude-docker) | TBD      | N/A        |
| VertexAI Gemini  | N/A                                         | TBD      | TBD        |
| vLLM             | [Link](#claude-code-vllm-docker)            | TBD      | TBD        |
| Ollama/llama.cpp | [Link](#claude-code-ollamallamacpp-docker)  | TBD      | TBD        |


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

## WIP

### Run with Openshift

```bash
harbor run --agent claude-code -d $BENCHMARK \
    --ae ANTHROPIC_BASE_URL=$SERVER_URL \
    --ae ANTHROPIC_API_KEY='sk-no-key-required' \
    --ae ANTHROPIC_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL_NAME \
    --environment-import-path openshift:OpenshiftEnvironment
```

## Future Work

- [ ] Support running Harbor in Openshift
- [ ] Support OpenCode configurations for vLLM and VertexAI
- [ ] Support Gemini CLI configurations for vLLM and VertexAI
