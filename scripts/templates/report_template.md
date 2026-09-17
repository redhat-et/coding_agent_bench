# <TODO>

## Benchmark

**Run Date:** {run_date}  
**Dataset:** [{dataset}](https://hub.harborframework.com/datasets/{dataset}/latest) ({num_tasks} tasks)  
**Model:** {model}  
**Harness:** {harness}  
**Environment:** {environment}  
**Job Name:** {job_name}  

## Results

**Score:** {score}% ({score_string})   
**Error Rate:** {error_rate}% ({error_string})  
**Total Time:** {total_time}  
**Agent Time:** {agent_time} ({avg_agent_time_per_task} avg per task)  
**Estimated Cost:** ${cost} {gpu_snippet} (${avg_cost_per_task} avg per task)  
**Input Tokens:** {input_tokens} ({avg_input_per_task} avg per task)  
**Output Tokens:** {output_tokens} ({avg_output_per_task} avg per task)  
**Cache Hit Rate:** {cache_hit_rate}%

## vLLM Server Config
  
**Container Image:** {vllm_image}
**Hardware:** <TODO>  
**Model Max Len:** {vllm_max_model_len}  
**Max Concurrency:** <TODO>  

**Command:**

```bash
{vllm_command}
```

## Harbor Config

**Command:**

```bash
{command}
```

**`config.json`:**

```json
{config_json}
```

## `result.json`

```json
{result_json}
```