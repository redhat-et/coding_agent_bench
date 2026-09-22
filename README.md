# Coding Agent Bench

Reproducible benchmarks for coding agents and models using Harbor

[![Documentation](https://img.shields.io/badge/Documentation-1f6feb)](https://redhat-et.github.io/coding_agent_bench/)
[![Version](https://img.shields.io/github/v/tag/redhat-et/coding_agent_bench?label=version)](https://github.com/redhat-et/coding_agent_bench/tags)

## Features

- Complete instructions for running popular benchmarks with open models
- CLI utility to simplify benchmark runs against self-hosted models
- Deployable queue service for scheduling benchmark runs in OpenShift 
- Leaderboards for popular benchmarks with instructions for reproducing results
- Full manifests for deploying open models on OpenShift with vLLM

## Leaderboards

<h3>✨ <a href="https://huggingface.co/spaces/taagarwa/coding-agent-leaderboard">Check out our Coding Agent Leaderboard on HuggingFace</a> ✨</h3>

### SWE-Bench Verified (pass@1, N=500)

| Model                          | Harness     | Score                                                            | Cost            |
| ------------------------------ | ----------- | ---------------------------------------------------------------- | --------------- |
| Opus 4.8                       | Claude Code | [86.8%](./benchmarks/SWE_Bench_Opus_4.8_Claude_Code.md)          | $395            |
| Opus 4.8                       | OpenCode    | [83.4%](./benchmarks/SWE_Bench_Opus_4.8_OpenCode.md)             | $320            |
| GPT 5.5                        | Codex       | [79.8%](./benchmarks/SWE_Bench_GPT_5.5_Codex.md)                 | $443            |
| Sonnet 4.6                     | Claude Code | [79.6%](https://www.anthropic.com/news/claude-sonnet-4-6)        | N/A             |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Pi          | [65.0%](./benchmarks/SWE_Bench_Qwen3.6_35b_NVFP4_Pi.md)          | $51<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Qwen Code   | [63.8%](./benchmarks/SWE_Bench_Qwen3.6_35b_NVFP4_Qwen_Code.md)   | $37<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Claude Code | [63.2%](./benchmarks/SWE_Bench_Qwen3.6_35b_NVFP4_Claude_Code.md) | $48<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | OpenClaw    | [58.8%](./benchmarks/SWE_Bench_Qwen3.6_35b_NVFP4_OpenClaw.md)    | $33<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | OpenCode    | [54.8%](./benchmarks/SWE_Bench_Qwen3.6_35b_NVFP4_OpenCode.md)    | $67<sup>†</sup> |


### SWE-Bench Pro - Ansible Tasks (pass@1, N=96)

| Model                          | Harness     | Score                                                                        | Cost            |
| ------------------------------ | ----------- | ---------------------------------------------------------------------------- | --------------- |
| Opus 4.8                       | OpenCode    | [78.1%](./benchmarks/SWE_Bench_Pro_Ansible_Opus_4.8_OpenCode.md)             | $151            |
| Opus 4.8                       | Claude Code | [69.8%](./benchmarks/SWE_Bench_Pro_Ansible_Opus_4.8_Claude_Code.md)          | $186            |
| GPT 5.5                        | Codex       | [60.4%](./benchmarks/SWE_Bench_Pro_Ansible_GPT_5.5_Codex.md)                 | $188            |
| GPT 5.5                        | OpenCode    | [57.3%](./benchmarks/SWE_Bench_Pro_Ansible_GPT_5.5_OpenCode.md)              | $111            |
| Opus 4.6                       | Claude Code | [51.0%](./benchmarks/SWE_Bench_Pro_Ansible_Opus_4.6_Claude_Code.md)          | $172            |
| Sonnet 4.6                     | Claude Code | [50.0%](./benchmarks/SWE_Bench_Pro_Ansible_Sonnet_4.6_Claude_Code.md)        | $184            |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Pi          | [47.9%](./benchmarks/SWE_Bench_Pro_Ansible_Qwen3.6_35b_NVFP4_Pi.md)          | $13<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Claude Code | [45.6%](./benchmarks/SWE_Bench_Pro_Ansible_Qwen3.6_35b_NVFP4_Claude_Code.md) | $10<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Qwen Code   | [43.8%](./benchmarks/SWE_Bench_Pro_Ansible_Qwen3.6_35b_NVFP4_Qwen_Code.md)   | $9<sup>†</sup>  |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | OpenClaw    | [40.6%](./benchmarks/SWE_Bench_Pro_Ansible_Qwen3.6_35b_NVFP4_OpenClaw.md)    | $9<sup>†</sup>  |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | OpenCode    | [37.5%](./benchmarks/SWE_Bench_Pro_Ansible_Qwen3.6_35b_NVFP4_OpenCode.md)    | $11<sup>†</sup> |


### Terminal Bench 2.0 (pass@1, N=87)

| Model                          | Harness  | Score                                                              | Cost            |
| ------------------------------ | -------- | ------------------------------------------------------------------ | --------------- |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | Pi       | [36.0%](./benchmarks/Terminal_Bench_Qwen3.6_35b_NVFP4_Pi.md)       | $11<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | OpenCode | [30.3%](./benchmarks/Terminal_Bench_Qwen3.6_35b_NVFP4_OpenCode.md) | $11<sup>†</sup> |
| RedHatAI/Qwen3.6-35B-A3B-NVFP4 | OpenClaw | [20.2%](./benchmarks/Terminal_Bench_Qwen3.6_35b_NVFP4_OpenClaw.md) | $10<sup>†</sup> |



More coming soon...

<sup>†</sup> - Cost estimates for OSS models are calculated by ($4 per A100 GPU hour × agent benchmark duration).

## Developers

### Bumping the Project Version

Version bumping is managed with `bump-my-version`.

First, create a new release branch for your version (e.g. v1.2.3)

```sh
git checkout -b release/v1.2.3
```

Bump the major/minor/patch version with

```sh
bump-my-version bump <major/minor/patch>
```

Then push the changes to the remote repository

```sh
git push origin release/v1.2.3
git push origin v1.2.3
```

Once merged, the CI will automatically build a new image tagged for the version and push it to GHCR.

### Deploying Changes

Three things need to happen before changes can be seen in the job queue service or other deployed resources:

1. The changes need to be merged into the main branch
2. The main branch needs to be [version bumped](#bumping-the-project-version), a PR created and merged, and an image for the new version successfully built
3. The job queue service and other resources need to be manually redeployed
