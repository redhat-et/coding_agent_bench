# Harbor Validated Commands

## Prerequisites:

- Install [Harbor](https://www.harborframework.com/docs/getting-started)
- [Set up a vLLM server](#deploy-models-with-vllm), or other Anthropic- and OpenAI-compatible server
- Set your benchmark in your environment from among the options in [Harbor Hub](https://hub.harborframework.com/), e.g.:

    ```bash
    export BENCHMARK='swe-bench/swe-bench-verified'
    ```

- If you need to filter tasks in your benchmark by name, add the `-i` flag with your glob pattern to your `harbor run` command, e.g. `-i "*ansible*"`

## Directory:

| Harness     | Model Server | Example                        | Status    |
| ----------- | ------------ | ------------------------------ | --------- |
| Claude Code | vLLM         | [Link](#claude-code-vllm)      | Validated |
| Codex       | vLLM         | [Link](#codex-vllm)            | Testing   |
| OpenClaw    | vLLM         | [Link](#openclaw-vllm)         | Validated |
| OpenCode    | vLLM         | [Link](#opencode-vllm)         | Validated |
| OpenHands   | vLLM         | [Link](#openhands-vllm)        | Validated |
| Pi          | vLLM         | [Link](#pi-vllm)               | Validated |
| Qwen Code   | vLLM         | [Link](#qwen-code-vllm)        | Validated |
| Claude Code | Anthropic    | [Link](#claude-code-anthropic) | Validated |
| Claude Code | VertexAI     | [Link](#claude-code-vertexai)  | Validated |
| Codex       | OpenAI       | [Link](#codex-openai)          | Validated |

> [!note]
> To use with a locally hosted model (e.g. llama.cpp) use a vLLM example and set `SERVER_URL=http://host.docker.internal:<server-port>`

## Claude Code vLLM

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

## Codex vLLM

Set the following variables in your environ:

```bash
export SERVER_URL=
export MODEL_NAME=
```

Use the utility script to create the `config.toml` file:

```bash
uv run scripts/codex_config_toml.py $MODEL_NAME $SERVER_URL
```

Then run:

```bash
harbor run --agent codex -d $BENCHMARK \
    -m vllm/$MODEL_NAME \
    --ae CODEX_HOME=/root/.codex/ \
    --mounts-json '[ { "type": "bind", "source":"/path/to/coding-agent-bench/config.toml", "target": "/root/.codex/config.toml" } ]'
```

## OpenClaw vLLM

Set the following variables in your environ:

```sh
export MODEL_NAME=
export SERVER_URL=
export OPENAI_BASE_URL=$SERVER_URL/v1
export OPENAI_API_KEY='NONE'
```

Then run:

```sh
harbor run --agent openclaw -p $DATASET_DIR/swe-bench-verified \
    -m openai/$MODEL_NAME \
    --agent-kwarg thinking=off \
    --n-concurrent 8
```

## OpenCode vLLM

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

## OpenHands vLLM

Set the following variables in your environ:

```bash
export MODEL_NAME=
export SERVER_URL=
export LLM_API_KEY="NONE"
```

Then run:

```bash
harbor run -d $BENCHMARK \
  -a openhands-sdk \
  -m hosted_vllm/$MODEL_NAME \
  --ae HOSTED_VLLM_API_BASE=$SERVER_URL/v1
```

## Pi vLLM

Set the following variables in your environ:

```bash
export MODEL_NAME=
```

Create a `models.json` file with your vLLM server information:

```bash
export PI_MODELS_JSON='{ "providers": { "vllm": { "baseUrl": "<server-url>", "api": "openai-completions", "apiKey": "NONE", "models": [{ "id": "gemma4-26b", "name": "<model-name>", "contextWindow": 262000 }] } } }'
echo $PI_MODELS_JSON > models.json
```

Then run:

```bash
harbor run --agent pi -d $BENCHMARK \
    -m vllm/$MODEL_NAME \
    --ae PI_OFFLINE=1 \
    --ae PI_CODING_AGENT_DIR=/root/.pi/agent \
    --mounts-json '[ { "type": "bind", "source":"/path/to/models.json", "target": "/root/.pi/agent/models.json" } ]'
```

## Qwen Code vLLM

Set the following variables in your environ:

```bash
export MODEL_NAME=
export SERVER_URL=
export OPENAI_BASE_URL=$SERVER_URL/v1
export OPENAI_API_KEY='NONE'
```

Then run:

```bash
harbor run --agent qwen-coder -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m $MODEL_NAME
```

## Claude Code Anthropic

Copy `.env.example` to `.env` and set the following variables:

```
ANTHROPIC_API_KEY=
```

Then run:

```bash
set -a
source .env

harbor run --agent claude-code -d $BENCHMARK \
    -m claude-opus-4-8
```

## Claude Code VertexAI

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
    --mounts-json '[ { "type": "bind", "source":"~/.config/gcloud/application_default_credentials.json", "target": "/app/.config/gcloud/application_default_credentials.json" } ]'
```

## Codex OpenAI

Copy `.env.example` to `.env` and set the following variables:

```
OPENAI_API_KEY=
```

Then run:

```bash
set -a
source .env

harbor run --agent codex -d $BENCHMARK \
    -m gpt-5.5
```

## WIP

### Run with Gemini and Gemini CLI

```bash
export GOOGLE_CLOUD_PROJECT="<your-project>"

harbor run --agent gemini-cli -d $BENCHMARK \
    -m $MODEL_NAME
```

### Run with vLLM and Gemini CLI

```bash
harbor run --agent gemini-cli -d $BENCHMARK \
    --ae GOOGLE_GEMINI_BASE_URL=$SERVER_URL \
    --ae GEMINI_MODEL=$MODEL_NAME \
    -m $MODEL_NAME
```
