# ITBench-AA Claude Opus 5.5 Claude Code

## Benchmark

**Run Date:** 2026-10-05T09:57:20.885228Z  
**Dataset:** [datasets/itbench-aa](https://hub.harborframework.com/datasets/datasets/itbench-aa/latest) (40 tasks)  
**Model:** claude-opus-5-5  
**Harness:** claude-code  
**Environment:** openshift  
**Job Name:** it_bench_aa/claude_opus_5_5_os_high  

## Results

**Score:** 35.4% (10 Full Reward / 9 Partial Reward / 21 Zero Reward / 0 Errors)   
**Error Rate:** 0.0% ()  
**Total Time:** 00h 33m 54s  
**Agent Time:** 00h 18m 23s (00h 01m 50s avg per task)  
**Estimated Cost:** $20.52  ($0.51 avg per task)  
**Input Tokens:** 31578057 (789451 avg per task)  
**Output Tokens:** 318164 (7954 avg per task)  
**Cache Hit Rate:** 94.8%

## Harbor Config

**Command:**

```bash
# Until the openshift tweaks and the itbench-aa adapter are merged upstream
# (PR harbor-framework/harbor#3403), pin both fork packages in pyproject.toml:
#   harbor = { git = "https://github.com/redhat-et/harbor.git", branch = "feat/itbench-aa" }
#   harbor-itbench-aa-adapter = { git = "https://github.com/redhat-et/harbor.git", branch = "feat/itbench-aa", subdirectory = "adapters/itbench-aa" }
uv sync

# Download the dataset (~31 GB, public, reuses the local HF cache on re-runs)
hf download ArtificialAnalysis/ITBench-AA --repo-type dataset

# One-time conversion of scenarios into self-contained Harbor tasks
uv run itbench-aa --output-dir datasets/itbench-aa

# Login to OpenShift and select the project (tasks run as OpenShift pods)
oc login --web
oc project sre-leaderboard-test   # redundant with --ek namespace, made explicit for clarity

# Run the benchmark
export GATEWAY_KEY='<api-key>'
export GATEWAY_URL='<gateway-host>'

uv run harbor run --agent claude-code \
    --model claude-opus-5-5 \
    -p datasets/itbench-aa \
    --n-concurrent 4 \
    --env openshift \
    --ek namespace=sre-leaderboard-test \
    --ek nft_redir_init=True \
    --agent-timeout-multiplier 3 \
    --ae 'ANTHROPIC_BASE_URL=${GATEWAY_URL}' \
    --ae 'ANTHROPIC_API_KEY=${GATEWAY_KEY}' \
    --ae CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1 \
    --ae CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000 \
    --ak 'reasoning_effort=high' \
    --allow-agent-host $GATEWAY_URL \
    --allow-agent-host downloads.claude.ai \
    --max-retries 1 \
    --retry-include UnknownApiError \
    --retry-include AgentTimeoutError \
    --retry-include NonZeroAgentExitCodeError \
    --retry-include ApiRateLimitError \
    --retry-include ApiUsageLimitError \
    --job-name it_bench_aa/claude_opus_5_5_os_high \
    --debug
```

**`config.json`:**

```json
{
    "job_name": "it_bench_aa/claude_opus_5_5_os_high",
    "n_concurrent_trials": 4,
    "agent_timeout_multiplier": 3.0,
    "debug": true,
    "retry": {
        "max_retries": 1,
        "include_exceptions": [
            "AgentTimeoutError",
            "ApiRateLimitError",
            "ApiUsageLimitError",
            "NonZeroAgentExitCodeError",
            "UnknownApiError"
        ]
    },
    "environment": {
        "type": "openshift",
        "kwargs": {
            "namespace": "sre-leaderboard-test",
            "nft_redir_init": true
        }
    },
    "agents": [
        {
            "name": "claude-code",
            "model_name": "claude-opus-5-5",
            "extra_allowed_hosts": [
                "<gateway-host>",
                "downloads.claude.ai"
            ],
            "kwargs": {
                "reasoning_effort": "high"
            },
            "env": {
                "ANTHROPIC_BASE_URL": "${GATEWAY_URL}",
                "ANTHROPIC_API_KEY": "${GATEWAY_KEY}",
                "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "128000"
            }
        }
    ],
    "datasets": [
        {
            "path": "datasets/itbench-aa"
        }
    ]
}
```

## `result.json`

```json
{
    "id": "629258c5-f9d7-449c-ad61-1512dca6b762",
    "started_at": "2026-10-05T10:56:49.179510",
    "updated_at": "2026-10-05T11:32:57.263971",
    "finished_at": "2026-10-05T11:32:57.263971",
    "n_total_trials": 40,
    "stats": {
        "n_completed_trials": 40,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "claude-code__claude-opus-5-5__itbench-aa": {
                "n_trials": 40,
                "n_errors": 0,
                "metrics": [
                    {
                        "answer_format_valid": 1.0,
                        "answer_recovered_from_transcript": 0.0,
                        "entity_count_expected": 1.0,
                        "kind_match": 0.425,
                        "name_match": 0.925,
                        "namespace_applicable": 0.975,
                        "namespace_match": 0.95,
                        "reasoning_present": 0.975,
                        "reward": 0.35416666666666663,
                        "submitted_entity_count": 1.4,
                        "turn_count": 31.95
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.5": [
                            "scenario-1__VNjQDFB",
                            "scenario-33__dKWSJMD",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-81__nX2DVi5"
                        ],
                        "0.0": [
                            "scenario-102__oUPs4Sm",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-35__cCe5fgQ",
                            "scenario-37__Sayv4Di",
                            "scenario-7__YZktrBh",
                            "scenario-80__M4KBb4E",
                            "scenario-83__MdZbX8h",
                            "scenario-91__E3nmSEu"
                        ],
                        "1.0": [
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-16__Pxt2wCr",
                            "scenario-20__g5qfxi7",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-34__YRC7TUs",
                            "scenario-40__ByRszQR",
                            "scenario-8__HiVaAv3",
                            "scenario-9__q5chVbU"
                        ],
                        "0.3333333333333333": [
                            "scenario-12__8CesrQ8",
                            "scenario-15__SYmfWVK"
                        ]
                    },
                    "answer_format_valid": {
                        "1.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-102__oUPs4Sm",
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-12__8CesrQ8",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-15__SYmfWVK",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-20__g5qfxi7",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-33__dKWSJMD",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-37__Sayv4Di",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-40__ByRszQR",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-7__YZktrBh",
                            "scenario-8__HiVaAv3",
                            "scenario-80__M4KBb4E",
                            "scenario-81__nX2DVi5",
                            "scenario-83__MdZbX8h",
                            "scenario-9__q5chVbU",
                            "scenario-91__E3nmSEu"
                        ]
                    },
                    "answer_recovered_from_transcript": {
                        "0.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-102__oUPs4Sm",
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-12__8CesrQ8",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-15__SYmfWVK",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-20__g5qfxi7",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-33__dKWSJMD",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-37__Sayv4Di",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-40__ByRszQR",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-7__YZktrBh",
                            "scenario-8__HiVaAv3",
                            "scenario-80__M4KBb4E",
                            "scenario-81__nX2DVi5",
                            "scenario-83__MdZbX8h",
                            "scenario-9__q5chVbU",
                            "scenario-91__E3nmSEu"
                        ]
                    },
                    "name_match": {
                        "1.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-12__8CesrQ8",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-15__SYmfWVK",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-20__g5qfxi7",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-31__nndP5QN",
                            "scenario-33__dKWSJMD",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-40__ByRszQR",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-7__YZktrBh",
                            "scenario-8__HiVaAv3",
                            "scenario-80__M4KBb4E",
                            "scenario-81__nX2DVi5",
                            "scenario-83__MdZbX8h",
                            "scenario-9__q5chVbU",
                            "scenario-91__E3nmSEu"
                        ],
                        "0.0": [
                            "scenario-102__oUPs4Sm",
                            "scenario-3__NhdEKyf",
                            "scenario-37__Sayv4Di"
                        ]
                    },
                    "kind_match": {
                        "0.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-102__oUPs4Sm",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-33__dKWSJMD",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-37__Sayv4Di",
                            "scenario-40__ByRszQR",
                            "scenario-7__YZktrBh",
                            "scenario-80__M4KBb4E",
                            "scenario-83__MdZbX8h",
                            "scenario-91__E3nmSEu"
                        ],
                        "1.0": [
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-12__8CesrQ8",
                            "scenario-15__SYmfWVK",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-20__g5qfxi7",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-8__HiVaAv3",
                            "scenario-81__nX2DVi5",
                            "scenario-9__q5chVbU"
                        ]
                    },
                    "namespace_match": {
                        "1.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-12__8CesrQ8",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-15__SYmfWVK",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-20__g5qfxi7",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-33__dKWSJMD",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-40__ByRszQR",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-7__YZktrBh",
                            "scenario-8__HiVaAv3",
                            "scenario-80__M4KBb4E",
                            "scenario-81__nX2DVi5",
                            "scenario-83__MdZbX8h",
                            "scenario-9__q5chVbU",
                            "scenario-91__E3nmSEu"
                        ],
                        "0.0": [
                            "scenario-102__oUPs4Sm",
                            "scenario-37__Sayv4Di"
                        ]
                    },
                    "namespace_applicable": {
                        "1.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-12__8CesrQ8",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-15__SYmfWVK",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-20__g5qfxi7",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-33__dKWSJMD",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-37__Sayv4Di",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-40__ByRszQR",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-7__YZktrBh",
                            "scenario-8__HiVaAv3",
                            "scenario-80__M4KBb4E",
                            "scenario-81__nX2DVi5",
                            "scenario-83__MdZbX8h",
                            "scenario-9__q5chVbU",
                            "scenario-91__E3nmSEu"
                        ],
                        "0.0": [
                            "scenario-102__oUPs4Sm"
                        ]
                    },
                    "reasoning_present": {
                        "1.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-102__oUPs4Sm",
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-12__8CesrQ8",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-15__SYmfWVK",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-20__g5qfxi7",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-33__dKWSJMD",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-40__ByRszQR",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-7__YZktrBh",
                            "scenario-8__HiVaAv3",
                            "scenario-80__M4KBb4E",
                            "scenario-81__nX2DVi5",
                            "scenario-83__MdZbX8h",
                            "scenario-9__q5chVbU",
                            "scenario-91__E3nmSEu"
                        ],
                        "0.0": [
                            "scenario-37__Sayv4Di"
                        ]
                    },
                    "entity_count_expected": {
                        "1.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-102__oUPs4Sm",
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-12__8CesrQ8",
                            "scenario-13__Xjs2n7R",
                            "scenario-14__Pc333Ba",
                            "scenario-15__SYmfWVK",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-20__g5qfxi7",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-33__dKWSJMD",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-37__Sayv4Di",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-40__ByRszQR",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-7__YZktrBh",
                            "scenario-8__HiVaAv3",
                            "scenario-80__M4KBb4E",
                            "scenario-81__nX2DVi5",
                            "scenario-83__MdZbX8h",
                            "scenario-9__q5chVbU",
                            "scenario-91__E3nmSEu"
                        ]
                    },
                    "submitted_entity_count": {
                        "2.0": [
                            "scenario-1__VNjQDFB",
                            "scenario-14__Pc333Ba",
                            "scenario-19__mXQupqL",
                            "scenario-2__rYPGkWt",
                            "scenario-33__dKWSJMD",
                            "scenario-38__jmGC39D",
                            "scenario-4__tNhRhDB",
                            "scenario-5__cw4icjm",
                            "scenario-6__sN8ywVy",
                            "scenario-80__M4KBb4E",
                            "scenario-81__nX2DVi5",
                            "scenario-83__MdZbX8h"
                        ],
                        "1.0": [
                            "scenario-102__oUPs4Sm",
                            "scenario-105__DR5hzxP",
                            "scenario-11__GiZdywu",
                            "scenario-13__Xjs2n7R",
                            "scenario-16__Pxt2wCr",
                            "scenario-17__VvCNZ4L",
                            "scenario-18__YbLkd5k",
                            "scenario-20__g5qfxi7",
                            "scenario-21__uWsWRiZ",
                            "scenario-22__vUoG5Ft",
                            "scenario-23__C2MKxzU",
                            "scenario-24__PPkCyPK",
                            "scenario-25__Pv7axN8",
                            "scenario-26__K5KssKa",
                            "scenario-27__9bjvkLE",
                            "scenario-29__o7EwqD2",
                            "scenario-3__NhdEKyf",
                            "scenario-31__nndP5QN",
                            "scenario-34__YRC7TUs",
                            "scenario-35__cCe5fgQ",
                            "scenario-37__Sayv4Di",
                            "scenario-40__ByRszQR",
                            "scenario-7__YZktrBh",
                            "scenario-8__HiVaAv3",
                            "scenario-9__q5chVbU",
                            "scenario-91__E3nmSEu"
                        ],
                        "3.0": [
                            "scenario-12__8CesrQ8",
                            "scenario-15__SYmfWVK"
                        ]
                    },
                    "turn_count": {
                        "44.0": [
                            "scenario-1__VNjQDFB"
                        ],
                        "24.0": [
                            "scenario-102__oUPs4Sm",
                            "scenario-18__YbLkd5k",
                            "scenario-20__g5qfxi7"
                        ],
                        "22.0": [
                            "scenario-105__DR5hzxP"
                        ],
                        "28.0": [
                            "scenario-11__GiZdywu",
                            "scenario-19__mXQupqL",
                            "scenario-35__cCe5fgQ",
                            "scenario-38__jmGC39D"
                        ],
                        "45.0": [
                            "scenario-12__8CesrQ8"
                        ],
                        "34.0": [
                            "scenario-13__Xjs2n7R",
                            "scenario-21__uWsWRiZ"
                        ],
                        "35.0": [
                            "scenario-14__Pc333Ba",
                            "scenario-80__M4KBb4E"
                        ],
                        "38.0": [
                            "scenario-15__SYmfWVK",
                            "scenario-17__VvCNZ4L"
                        ],
                        "19.0": [
                            "scenario-16__Pxt2wCr",
                            "scenario-23__C2MKxzU"
                        ],
                        "42.0": [
                            "scenario-2__rYPGkWt",
                            "scenario-26__K5KssKa",
                            "scenario-37__Sayv4Di"
                        ],
                        "27.0": [
                            "scenario-22__vUoG5Ft",
                            "scenario-25__Pv7axN8"
                        ],
                        "15.0": [
                            "scenario-24__PPkCyPK"
                        ],
                        "31.0": [
                            "scenario-27__9bjvkLE",
                            "scenario-3__NhdEKyf"
                        ],
                        "23.0": [
                            "scenario-29__o7EwqD2"
                        ],
                        "50.0": [
                            "scenario-31__nndP5QN"
                        ],
                        "20.0": [
                            "scenario-33__dKWSJMD"
                        ],
                        "36.0": [
                            "scenario-34__YRC7TUs",
                            "scenario-5__cw4icjm",
                            "scenario-81__nX2DVi5"
                        ],
                        "49.0": [
                            "scenario-4__tNhRhDB"
                        ],
                        "21.0": [
                            "scenario-40__ByRszQR"
                        ],
                        "40.0": [
                            "scenario-6__sN8ywVy"
                        ],
                        "30.0": [
                            "scenario-7__YZktrBh",
                            "scenario-83__MdZbX8h"
                        ],
                        "37.0": [
                            "scenario-8__HiVaAv3"
                        ],
                        "41.0": [
                            "scenario-9__q5chVbU"
                        ],
                        "25.0": [
                            "scenario-91__E3nmSEu"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 31578057,
        "n_cache_tokens": 29944414,
        "n_output_tokens": 318164,
        "cost_usd": 20.5190378
    }
}
```
