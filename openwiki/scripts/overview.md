---
type: overview
title: Utility Scripts
description: Standalone scripts for benchmark result analysis, MinIO data management, and agent configuration.
tags: [scripts, utilities, metrics]
---

# Utility Scripts

Standalone Python scripts in `scripts/` for post-benchmark analysis and operational tasks.

## Script Inventory

| Script | Purpose | Key Functionality |
|--------|---------|-------------------|
| `calculate_metrics.py` | Aggregate benchmark metrics | Computes pass rate, token counts, cost from job directories |
| `pass_rate.py` | Pass rate calculation | Measures pass rate with optional N-item forgiveness |
| `download_minio.py` | MinIO data retrieval | Downloads result folders from MinIO buckets |
| `codex_config_toml.py` | Codex config generation | Generates config.toml for Codex agent |
| `patch_opencode.py` | OpenCode patching | Applies patches to OpenCode agent |
| `pull_images.py` | Image pre-pulling | Pre-pulls container images for faster benchmark runs |
| `replace_swe_bench_images.py` | Image replacement | Replaces SWE-bench base images |

## calculate_metrics.py

```python
class Metrics(BaseModel):
    n_tasks: int
    n_errors: int
    score: float
    n_input_tokens: int
    n_cache_tokens: int
    n_output_tokens: int
    n_total_tokens: int
    agent_time_seconds: int
    total_time_seconds: int
    cost_usd: float
```

Computed fields include per-task averages for tokens, cost, and time. Default GPU cost is $4/hour.

## pass_rate.py

```bash
python scripts/pass_rate.py <job_dir> [-n N]
```

Counts tasks where the number of functional item failures is ≤ N (forgiveness). Outputs pass/fail per task and aggregate percentage.

## download_minio.py

```bash
python scripts/download_minio.py \
  --endpoint https://minio.example.com \
  --bucket results \
  --access-key <key> \
  --secret-key <secret> \
  [--pattern "*"] \
  --output ./downloads
```

Downloads folders from MinIO matching a glob pattern, skipping already-downloaded ones.

## Evidence

- Source: `scripts/` directory
- Used by: Manual analysis and CI pipelines
