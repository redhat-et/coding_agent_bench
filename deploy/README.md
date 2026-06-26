# Deployment Configs

| Column | What it means |
|--------|---------------|
| **Model** | The model being served (from [Hugging Face](https://huggingface.co/RedHatAI), served via [vLLM](https://github.com/vllm-project/vllm) on OpenShift) |
| **GPU Pool** | Cluster GPU tier and hardware used (OpenShift machinepools with autoscaling, targeted via `nodeSelector` labels) |
| **Max Model Len** | Maximum context window in tokens (set via `--max-model-len` in vLLM) |
| **Max Concurrency** | How many requests the server can handle simultaneously at full context length (reported by vLLM at startup, use for `--n-tasks` in Harbor benchmark runs) |

| Model | GPU Pool | Max Model Len | Max Concurrency |
|-------|----------|---------------|-----------------|
| Qwen3.6-27B-FP8 | xlarge (4x L40S, 192GB) | 262,144 | 13.32x |
