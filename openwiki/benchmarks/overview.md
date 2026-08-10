---
type: overview
title: Benchmark Results
description: Benchmark result organization — per-run markdown leaderboards, job directories with scorecards, and metrics calculation scripts.
tags: [benchmarks, results, metrics, leaderboards]
---

# Benchmark Results

Benchmark results are organized in three layers: raw job directories with per-task scorecards, aggregated markdown leaderboards, and metrics calculation scripts.

## Result Layers

### 1. Raw Job Directories (`jobs/`)

Each benchmark run creates a timestamped directory under `jobs/`:

```
jobs/
├── 2026-04-29__15-15-07/     # Run timestamp
│   ├── <task_id>/            # Per-task directory
│   │   ├── config.json       # Harbor run configuration
│   │   ├── harbor.log        # Harbor execution log
│   │   └── verifier/
│   │       └── scorecard.json  # Per-task pass/fail results
│   └── ...
├── gemma4-31b-swebench-verified-claude-code/  # Named runs
└── oracle-swe-bench/
```

Each task directory contains:
- `config.json` — Full Harbor configuration for the run
- `harbor.log` — Execution log
- `verifier/scorecard.json` — Per-test pass/fail results with `functional_items` array

### 2. Markdown Leaderboards (`benchmarks/`)

Aggregated result files in `benchmarks/` format results as markdown tables:

| File | Benchmark | Agent | Model |
|------|-----------|-------|-------|
| `SWE_Bench_Opus_4.8_Claude_Code.md` | SWE-bench Verified | Claude Code | Opus 4.8 |
| `SWE_Bench_GPT_5.5_Codex.md` | SWE-bench Verified | Codex | GPT 5.5 |
| `SWE_Bench_Pro_Ansible_Opus_4.8_Claude_Code.md` | SWE-bench Pro | Claude Code | Opus 4.8 |
| `Terminal_Bench_Qwen3.6_35b_NVFP4_Pi.md` | Terminal Bench 2.0 | Pi | Qwen3.6-35B |

Each file contains:
- Summary table with pass@1 score, task count, and cost
- Per-task detailed results with pass/fail status
- Runtime and token usage statistics

### 3. Metrics Scripts (`scripts/`)

- **`calculate_metrics.py`** — Computes aggregate metrics (pass rate, token counts, cost) from job directories
- **`pass_rate.py`** — Measures pass rates with optional N-item forgiveness
- **`download_minio.py`** — Downloads results from MinIO object storage

## Metrics Model

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
    # Computed fields:
    mean_input_tokens_per_task
    mean_cache_tokens_per_task
    mean_output_tokens_per_task
    mean_tokens_per_task
    mean_cost_usd_per_task
    mean_total_time_seconds_per_task
    mean_agent_time_seconds_per_task
```

Cost calculation uses `$4 per A100 GPU hour × agent benchmark duration` for OSS models.

## Evidence

- Source: `jobs/`, `benchmarks/`, `scripts/calculate_metrics.py`, `scripts/pass_rate.py`
- Leaderboard: [HuggingFace Space](https://huggingface.co/spaces/taagarwa/coding-agent-leaderboard)
