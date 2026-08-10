---
type: overview
title: Datasets
description: Benchmark dataset organization — SWE-bench Verified, SWE-bench Pro, Tau3-bench, and other task directories used by Harbor for coding agent benchmarking.
tags: [datasets, benchmarks, swe-bench]
---

# Datasets

Benchmark datasets are stored as directories of task instances under `datasets/`. Each dataset contains subdirectories named after individual tasks, following Harbor's dataset conventions.

## Dataset Organization

```
datasets/
├── swe-bench-verified/        # 502 task directories (SWE-bench Verified)
├── swe-bench-verified-optimized/  # Optimized variant
├── swe-bench-pro/             # 98 task directories (SWE-bench Pro - Ansible)
├── tau3-bench/                # 377 task directories (Tau3 benchmarks)
├── deep-swe/                  # 115 task directories
├── o11y-bench/                # 65 task directories (observability)
├── rh-swe-bench/              # 8 task directories (Red Hat SWE bench)
└── multi-swe-bench/           # Multi-task benchmark
```

## Task Directory Structure

Each task directory (e.g., `swe-bench-verified/astropy__astropy-12907/`) contains:

- `problem_statement.md` — The bug/issue description
- `test_patch.patch` — Test changes to apply
- `instance_id` — Unique task identifier
- `base_commit` — Git commit to start from
- `hints_text` — Human hints for solving the issue
- `environment_setup_commands` — Commands to set up the task environment
- `pass_to_pass` / `fail_to_pass` — Test identifiers for pass/fail cases
- `version` — Dataset version

## Supported Benchmarks

### SWE-bench Verified (N=500)
The primary benchmark suite. Each task represents a real GitHub issue with a codebase, a test patch, and a solution patch. The agent must fix the issue without seeing the solution.

### SWE-bench Pro - Ansible Tasks (N=96)
A subset focused on Ansible-related tasks, with more complex multi-file changes.

### Tau3-bench (N=377)
Observability-focused benchmark tasks covering airline, infrastructure, and other domains.

### Deep-SWE (N=115)
Deeper, more complex SWE-bench tasks requiring multi-step reasoning.

### O11y-bench (N=65)
Observability-specific tasks for monitoring, logging, and debugging systems.

## Evidence

- Source: `datasets/` directory
- Referenced by: `HarborCommandBuilder._build_command()` via `-d <dataset>` or `-p <path>` flags
