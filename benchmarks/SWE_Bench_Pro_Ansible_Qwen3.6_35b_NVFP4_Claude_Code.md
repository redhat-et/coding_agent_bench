# SWE-Bench Pro Ansible Qwen3.6-35B-A3B-NVFP4 Claude Code

## Benchmark

**Dataset:** [swe-bench/swe-bench-verified](https://hub.harborframework.com/datasets/swe-bench/swe-bench-verified/latest) (500 tasks)  
**Model:** [RedHatAI/Qwen3.6-35B-A3B-NVFP4](https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4)  
**Harness:** Claude Code  
**Environment:** Docker  
**Job Name:** 2026-05-12__09-28-42  

## Results

**Score:** 45.8%  
**Errors (Initial Run):** 6  
**Total Time:** 1 hr 38 min  
**Agent Run Time:** 1 hr 12 min    
**Estimated Cost:** $9.64 ($4 / GPU / hr * 2 GPU * 1 hr 12 min)   

## vLLM Server Config

**Manifest:** [Qwen3.6_35b_NVFP4.yml](../deploy/Qwen3.6_35b_NVFP4.yml)  
**Hardware:** 2x A100 40GB  
**Model Max Len:** 262,144  
**Max Concurrency:** 9.2x  
**Generation Config (Defaults):**
- **Temperature:** 1.0
- **Top p:** 0.95
- **Top k:** 20

## Harbor Config

**Command:**

```bash
export BENCHMARK='scale-ai/swe-bench-pro'
export MODEL_NAME='qwen3.6-35b'
export DATASET_PATTERN='*ansible*'
export SERVER_URL='<server-url>'

harbor run --agent claude-code -d $BENCHMARK \
    -i $DATASET_PATTERN \
    --ae ANTHROPIC_BASE_URL=$SERVER_URL \
    --ae ANTHROPIC_API_KEY='sk-no-key-required' \
    --ae ANTHROPIC_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL_NAME \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL_NAME \
    --n-concurrent 9
```

**`config.json`:**

```json

```

## `result.json`

```json

```