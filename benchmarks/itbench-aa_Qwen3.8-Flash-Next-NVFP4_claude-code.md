# ITBench-AA Qwen3.8-Flash-Next-NVFP4 Claude Code

## Benchmark

**Run Date:** 2026-09-30T06:06:56.855360Z  
**Dataset:** [datasets/itbench-aa](https://hub.harborframework.com/datasets/datasets/itbench-aa/latest) (40 tasks)  
**Model:** Inferact/Qwen3.8-Flash-Next-NVFP4  
**Harness:** claude-code  
**Environment:** openshift  
**Job Name:** it_bench_aa/qwen38_flash_claude_os_xhigh  

## Results

**Score:** 39.2% (14 Full Reward / 4 Partial Reward / 22 Zero Reward / 0 Errors)   
**Error Rate:** 0.0% ()  
**Total Time:** 05h 54m 28s  
**Agent Time:** 05h 35m 20s (00h 25m 09s avg per task)  
**Estimated Cost:** $11.76  ($0.29 avg per task)  
**Input Tokens:** 96024051 (2400601 avg per task)  
**Output Tokens:** 1398403 (34960 avg per task)  
**Cache Hit Rate:** 25.7%

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
    --model Inferact/Qwen3.8-Flash-Next-NVFP4 \
    -p datasets/itbench-aa \
    --n-concurrent 3 \
    --env openshift \
    --ek namespace=sre-leaderboard-test \
    --ek nft_redir_init=True \
    --agent-timeout-multiplier 3 \
    --ae 'ANTHROPIC_BASE_URL=${GATEWAY_URL}' \
    --ae 'ANTHROPIC_API_KEY=${GATEWAY_KEY}' \
    --ae CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1 \
    --ae CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000 \
    --ak reasoning_effort=xhigh \
    --allow-agent-host $GATEWAY_URL \
    --allow-agent-host downloads.claude.ai \
    --max-retries 1 \
    --retry-include UnknownApiError \
    --retry-include AgentTimeoutError \
    --retry-include NonZeroAgentExitCodeError \
    --retry-include ApiRateLimitError \
    --retry-include ApiUsageLimitError \
    --job-name it_bench_aa/qwen38_flash_claude_os_xhigh \
    --debug
```

**`config.json`:**

```json
{
    "job_name": "it_bench_aa/qwen38_flash_claude_os_xhigh",
    "agent_timeout_multiplier": 3.0,
    "debug": true,
    "n_concurrent_trials": 3,
    "retry": {
        "max_retries": 1,
        "include_exceptions": [
            "UnknownApiError",
            "NonZeroAgentExitCodeError",
            "ApiRateLimitError",
            "ApiUsageLimitError",
            "AgentTimeoutError"
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
            "model_name": "Inferact/Qwen3.8-Flash-Next-NVFP4",
            "extra_allowed_hosts": [
                "<gateway-host>",
                "downloads.claude.ai"
            ],
            "kwargs": {
                "reasoning_effort": "xhigh"
            },
            "env": {
                "ANTHROPIC_BASE_URL": "https://<gateway-host>",
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
    "id": "66fb91d5-556d-49da-92ea-560a64808d7f",
    "started_at": "2026-09-30T07:06:43.907619",
    "updated_at": "2026-09-30T14:46:02.495419",
    "finished_at": "2026-09-30T14:46:02.495419",
    "n_total_trials": 40,
    "stats": {
        "n_completed_trials": 40,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "claude-code__Qwen3.8-Flash-Next-NVFP4__itbench-aa": {
                "n_trials": 40,
                "n_errors": 0,
                "metrics": [
                    {
                        "answer_format_valid": 1.0,
                        "answer_recovered_from_transcript": 0.0,
                        "entity_count_expected": 1.0,
                        "kind_match": 0.2,
                        "name_match": 0.875,
                        "namespace_applicable": 0.975,
                        "namespace_match": 0.45,
                        "reasoning_present": 1.0,
                        "reward": 0.39166666666666666,
                        "submitted_entity_count": 1.45,
                        "turn_count": 99.275
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-17__TCVbD8g",
                            "scenario-25__vVphBz3",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-34__KoMAkeC",
                            "scenario-37__upPzhra",
                            "scenario-3__XnVmCcc",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-8__ZQoxz5h",
                            "scenario-9__GgKkJYa"
                        ],
                        "1.0": [
                            "scenario-105__gse3LGZ",
                            "scenario-16__V5JLV4C",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-35__ryznmQD",
                            "scenario-40__U25eHFM",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va"
                        ],
                        "0.5": [
                            "scenario-33__3FEPdUc",
                            "scenario-80__ieA9CQC"
                        ],
                        "0.3333333333333333": [
                            "scenario-38__ZJn7Fea",
                            "scenario-91__duNJ4FU"
                        ]
                    },
                    "answer_format_valid": {
                        "1.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-105__gse3LGZ",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-16__V5JLV4C",
                            "scenario-17__TCVbD8g",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-25__vVphBz3",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-33__3FEPdUc",
                            "scenario-34__KoMAkeC",
                            "scenario-35__ryznmQD",
                            "scenario-37__upPzhra",
                            "scenario-38__ZJn7Fea",
                            "scenario-3__XnVmCcc",
                            "scenario-40__U25eHFM",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-80__ieA9CQC",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-8__ZQoxz5h",
                            "scenario-91__duNJ4FU",
                            "scenario-9__GgKkJYa"
                        ]
                    },
                    "answer_recovered_from_transcript": {
                        "0.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-105__gse3LGZ",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-16__V5JLV4C",
                            "scenario-17__TCVbD8g",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-25__vVphBz3",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-33__3FEPdUc",
                            "scenario-34__KoMAkeC",
                            "scenario-35__ryznmQD",
                            "scenario-37__upPzhra",
                            "scenario-38__ZJn7Fea",
                            "scenario-3__XnVmCcc",
                            "scenario-40__U25eHFM",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-80__ieA9CQC",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-8__ZQoxz5h",
                            "scenario-91__duNJ4FU",
                            "scenario-9__GgKkJYa"
                        ]
                    },
                    "name_match": {
                        "0.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-25__vVphBz3",
                            "scenario-29__k2JFya2",
                            "scenario-37__upPzhra",
                            "scenario-3__XnVmCcc"
                        ],
                        "1.0": [
                            "scenario-105__gse3LGZ",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-16__V5JLV4C",
                            "scenario-17__TCVbD8g",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-33__3FEPdUc",
                            "scenario-34__KoMAkeC",
                            "scenario-35__ryznmQD",
                            "scenario-38__ZJn7Fea",
                            "scenario-40__U25eHFM",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-80__ieA9CQC",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-8__ZQoxz5h",
                            "scenario-91__duNJ4FU",
                            "scenario-9__GgKkJYa"
                        ]
                    },
                    "kind_match": {
                        "0.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-25__vVphBz3",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-33__3FEPdUc",
                            "scenario-34__KoMAkeC",
                            "scenario-35__ryznmQD",
                            "scenario-37__upPzhra",
                            "scenario-3__XnVmCcc",
                            "scenario-40__U25eHFM",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-80__ieA9CQC",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-8__ZQoxz5h",
                            "scenario-9__GgKkJYa"
                        ],
                        "1.0": [
                            "scenario-105__gse3LGZ",
                            "scenario-16__V5JLV4C",
                            "scenario-17__TCVbD8g",
                            "scenario-20__sXFTgp3",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-38__ZJn7Fea",
                            "scenario-91__duNJ4FU"
                        ]
                    },
                    "namespace_match": {
                        "0.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-17__TCVbD8g",
                            "scenario-25__vVphBz3",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-34__KoMAkeC",
                            "scenario-37__upPzhra",
                            "scenario-3__XnVmCcc",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-8__ZQoxz5h",
                            "scenario-9__GgKkJYa"
                        ],
                        "1.0": [
                            "scenario-105__gse3LGZ",
                            "scenario-16__V5JLV4C",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-33__3FEPdUc",
                            "scenario-35__ryznmQD",
                            "scenario-38__ZJn7Fea",
                            "scenario-40__U25eHFM",
                            "scenario-80__ieA9CQC",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-91__duNJ4FU"
                        ]
                    },
                    "namespace_applicable": {
                        "0.0": [
                            "scenario-102__p6ePwAP"
                        ],
                        "1.0": [
                            "scenario-105__gse3LGZ",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-16__V5JLV4C",
                            "scenario-17__TCVbD8g",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-25__vVphBz3",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-33__3FEPdUc",
                            "scenario-34__KoMAkeC",
                            "scenario-35__ryznmQD",
                            "scenario-37__upPzhra",
                            "scenario-38__ZJn7Fea",
                            "scenario-3__XnVmCcc",
                            "scenario-40__U25eHFM",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-80__ieA9CQC",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-8__ZQoxz5h",
                            "scenario-91__duNJ4FU",
                            "scenario-9__GgKkJYa"
                        ]
                    },
                    "reasoning_present": {
                        "1.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-105__gse3LGZ",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-16__V5JLV4C",
                            "scenario-17__TCVbD8g",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-25__vVphBz3",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-33__3FEPdUc",
                            "scenario-34__KoMAkeC",
                            "scenario-35__ryznmQD",
                            "scenario-37__upPzhra",
                            "scenario-38__ZJn7Fea",
                            "scenario-3__XnVmCcc",
                            "scenario-40__U25eHFM",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-80__ieA9CQC",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-8__ZQoxz5h",
                            "scenario-91__duNJ4FU",
                            "scenario-9__GgKkJYa"
                        ]
                    },
                    "entity_count_expected": {
                        "1.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-105__gse3LGZ",
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-14__4BxDzNb",
                            "scenario-15__zTgBsV4",
                            "scenario-16__V5JLV4C",
                            "scenario-17__TCVbD8g",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-25__vVphBz3",
                            "scenario-26__QLnmM2k",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-2__JKVuFpT",
                            "scenario-31__aFSavKx",
                            "scenario-33__3FEPdUc",
                            "scenario-34__KoMAkeC",
                            "scenario-35__ryznmQD",
                            "scenario-37__upPzhra",
                            "scenario-38__ZJn7Fea",
                            "scenario-3__XnVmCcc",
                            "scenario-40__U25eHFM",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-7__BUcRaUF",
                            "scenario-80__ieA9CQC",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-8__ZQoxz5h",
                            "scenario-91__duNJ4FU",
                            "scenario-9__GgKkJYa"
                        ]
                    },
                    "submitted_entity_count": {
                        "1.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-105__gse3LGZ",
                            "scenario-12__cLnDCz8",
                            "scenario-13__7fKJ7We",
                            "scenario-16__V5JLV4C",
                            "scenario-18__L7LE7GP",
                            "scenario-19__N9uScCE",
                            "scenario-1__VbuGHhC",
                            "scenario-20__sXFTgp3",
                            "scenario-21__PyRbtBH",
                            "scenario-22__JYR7Bnm",
                            "scenario-23__9P4yfHS",
                            "scenario-24__XJqRWiY",
                            "scenario-25__vVphBz3",
                            "scenario-27__DRW2dV7",
                            "scenario-29__k2JFya2",
                            "scenario-31__aFSavKx",
                            "scenario-34__KoMAkeC",
                            "scenario-35__ryznmQD",
                            "scenario-37__upPzhra",
                            "scenario-3__XnVmCcc",
                            "scenario-40__U25eHFM",
                            "scenario-4__G7WDfnd",
                            "scenario-5__C9ZWs2Q",
                            "scenario-6__UUj372m",
                            "scenario-81__VuVsQtv",
                            "scenario-83__t9VW3Va",
                            "scenario-9__GgKkJYa"
                        ],
                        "2.0": [
                            "scenario-11__uyDq2s7",
                            "scenario-14__4BxDzNb",
                            "scenario-17__TCVbD8g",
                            "scenario-33__3FEPdUc",
                            "scenario-7__BUcRaUF",
                            "scenario-80__ieA9CQC",
                            "scenario-8__ZQoxz5h"
                        ],
                        "3.0": [
                            "scenario-15__zTgBsV4",
                            "scenario-26__QLnmM2k",
                            "scenario-38__ZJn7Fea",
                            "scenario-91__duNJ4FU"
                        ],
                        "4.0": [
                            "scenario-2__JKVuFpT"
                        ]
                    },
                    "turn_count": {
                        "107.0": [
                            "scenario-102__p6ePwAP",
                            "scenario-22__JYR7Bnm",
                            "scenario-80__ieA9CQC"
                        ],
                        "86.0": [
                            "scenario-105__gse3LGZ"
                        ],
                        "105.0": [
                            "scenario-11__uyDq2s7",
                            "scenario-12__cLnDCz8"
                        ],
                        "92.0": [
                            "scenario-13__7fKJ7We"
                        ],
                        "80.0": [
                            "scenario-14__4BxDzNb"
                        ],
                        "88.0": [
                            "scenario-15__zTgBsV4"
                        ],
                        "81.0": [
                            "scenario-16__V5JLV4C",
                            "scenario-18__L7LE7GP"
                        ],
                        "95.0": [
                            "scenario-17__TCVbD8g"
                        ],
                        "85.0": [
                            "scenario-19__N9uScCE",
                            "scenario-21__PyRbtBH"
                        ],
                        "134.0": [
                            "scenario-1__VbuGHhC"
                        ],
                        "62.0": [
                            "scenario-20__sXFTgp3"
                        ],
                        "61.0": [
                            "scenario-23__9P4yfHS"
                        ],
                        "94.0": [
                            "scenario-24__XJqRWiY"
                        ],
                        "70.0": [
                            "scenario-25__vVphBz3"
                        ],
                        "135.0": [
                            "scenario-26__QLnmM2k"
                        ],
                        "99.0": [
                            "scenario-27__DRW2dV7"
                        ],
                        "73.0": [
                            "scenario-29__k2JFya2"
                        ],
                        "103.0": [
                            "scenario-2__JKVuFpT"
                        ],
                        "125.0": [
                            "scenario-31__aFSavKx"
                        ],
                        "116.0": [
                            "scenario-33__3FEPdUc"
                        ],
                        "96.0": [
                            "scenario-34__KoMAkeC",
                            "scenario-4__G7WDfnd",
                            "scenario-6__UUj372m"
                        ],
                        "127.0": [
                            "scenario-35__ryznmQD"
                        ],
                        "151.0": [
                            "scenario-37__upPzhra"
                        ],
                        "83.0": [
                            "scenario-38__ZJn7Fea",
                            "scenario-83__t9VW3Va"
                        ],
                        "89.0": [
                            "scenario-3__XnVmCcc"
                        ],
                        "51.0": [
                            "scenario-40__U25eHFM"
                        ],
                        "104.0": [
                            "scenario-5__C9ZWs2Q"
                        ],
                        "126.0": [
                            "scenario-7__BUcRaUF"
                        ],
                        "97.0": [
                            "scenario-81__VuVsQtv"
                        ],
                        "123.0": [
                            "scenario-8__ZQoxz5h"
                        ],
                        "145.0": [
                            "scenario-91__duNJ4FU"
                        ],
                        "128.0": [
                            "scenario-9__GgKkJYa"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 96024051,
        "n_cache_tokens": 24637600,
        "n_output_tokens": 1398403,
        "cost_usd": 11.759417000000001
    },
    "trial_results": []
}
```
