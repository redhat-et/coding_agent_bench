# Validated Models

Models are validated on Nebius with the following settings

gpu-b200-sxm:
- 1x B200 (180 GB vRAM)  
- 20 vCPU  
- 224 GB RAM  
- Preemptive  
- ME-west1

| Model                                                                                                | Hardware     | KV Cache | Max Concurrency |
| ---------------------------------------------------------------------------------------------------- | ------------ | -------- | --------------- |
| [Qwen/Qwen3.8-27B](#qwenqwen38-27b)                                                                  | gpu-b200-sxm | FP8      | 12x             |
| [Qwen/Qwen3.8-27B-FP8](#qwenqwen38-27b-fp8)                                                          | gpu-b200-sxm | FP8      | 15x             |
| [RedHatAI/Qwen3.6-27B-FP8](#redhataiqwen36-27b-fp8)                                                  | gpu-b200-sxm | FP8      | 29x             |
| [RedHatAI/gemma-4-31B-it-FP8-block](#redhataigemma-4-31b-it-fp8-block)                               | gpu-b200-sxm | FP8      |                 |
| [RedHatAI/Mistral-Small-4-119B-2603-NVFP4](#redhataimistral-small-4-119b-2603-nvfp4)                 | gpu-b200-sxm | auto     |                 |
| [RedHatAI/gpt-oss-120b](#redhataigpt-oss-120b)                                                       | gpu-b200-sxm | FP8      | 40x             |
| [RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4](#redhatainvidia-nemotron-3-super-120b-a12b-nvfp4) | gpu-b200-sxm | FP8      | 14x             |


## Validated vLLM Commands

### Qwen/Qwen3.8-27B

```shell
sudo docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model Qwen/Qwen3.8-27B \
    --max-model-len 262144 \
    --tensor-parallel-size 1 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --kv-cache-dtype fp8 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --reasoning-parser qwen3 \
    --mm-encoder-tp-mode data
```

### Qwen/Qwen3.8-27B-FP8

```shell
sudo docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model Qwen/Qwen3.8-27B-FP8 \
    --max-model-len 262144 \
    --tensor-parallel-size 1 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --kv-cache-dtype fp8 \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --reasoning-parser qwen3 \
    --mm-encoder-tp-mode data
```

### RedHatAI/Qwen3.6-27B-FP8

```shell
sudo docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/Qwen3.6-27B-FP8 \
    --dtype auto \
    --max-model-len 131072 \
    --trust-remote-code \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --kv-cache-dtype fp8 \
    --enable-auto-tool-choice \
    --reasoning-parser qwen3 \
    --tool-call-parser qwen3_coder \
    --default-chat-template-kwargs '{"enable_thinking": true}'
```

### RedHatAI/gemma-4-31B-it-FP8-block

```shell
sudo docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/gemma-4-31B-it-FP8-block \
    --dtype auto \
    --max-model-len 262144 \
    --trust-remote-code \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --kv-cache-dtype fp8 \
    --enable-auto-tool-choice \
    --reasoning-parser gemma4 \
    --tool-call-parser gemma4 \
    --default-chat-template-kwargs '{"enable_thinking": true}'

```

### RedHatAI/Mistral-Small-4-119B-2603-NVFP4

```shell
sudo docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/Mistral-Small-4-119B-2603-NVFP4 \
    --dtype auto \
    --max-model-len 131072 \
    --trust-remote-code \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --kv-cache-dtype auto \
    --enable-auto-tool-choice \
    --reasoning-parser mistral \
    --tool-call-parser mistral \
    --default-chat-template-kwargs '{"reasoning_effort": "high"}' \
    --limit-mm-per-prompt '{"image": 0}'
```

### RedHatAI/gpt-oss-120b

```shell
sudo docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/gpt-oss-120b \
    --dtype auto \
    --kv-cache-dtype fp8 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --enable-auto-tool-choice \
    --tool-call-parser openai
```

### RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4

```shell
sudo docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 \
    --dtype auto \
    --kv-cache-dtype fp8 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --enable-auto-tool-choice \
    --reasoning-parser nemotron_v3 \
    --tool-call-parser qwen3_coder
```
