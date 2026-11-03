# ITBench-AA Claude Sonnet 5.5 OpenCode

## Benchmark

**Run Date:** 2026-10-23T12:20:28.237323Z  
**Dataset:** [datasets/itbench-aa](https://hub.harborframework.com/datasets/datasets/itbench-aa/latest) (40 tasks)  
**Model:** enmaas/claude-sonnet-5-5  
**Harness:** opencode  
**Environment:** openshift  
**Job Name:** it_bench_aa/claude_sonnet_5_5_opencode_os  

## Results

**Score:** 52.1% (18 Full Reward / 6 Partial Reward / 16 Zero Reward, incl. 7 trials that raised an agent exception and were still graded)   
**Error Rate:** 17.5% (3 NetworkConnectionErrors, 1 ApiRateLimitErrors, 3 NonZeroAgentExitCodeErrors)  
**Total Time:** 00h 26m 57s  
**Agent Time:** 00h 12m 58s (00h 01m 17s avg per task)  
**Estimated Cost:** $9.91  ($0.25 avg per task)  
**Input Tokens:** 20968100 (524202 avg per task)  
**Output Tokens:** 220663 (5516 avg per task)  
**Cache Hit Rate:** 100.0%

## Harbor Config

**Command:**

```bash
# Until the itbench-aa adapter is merged upstream (PR harbor-framework/adapters#14)
# pin the fork package in pyproject.toml:
#   harbor = { git = "https://github.com/redhat-et/harbor.git" }
#   harbor-itbench-aa-adapter = { git = "https://github.com/redhat-et/harbor.git", branch = "feat/itbench-aa", subdirectory = "adapters/itbench-aa" }
# Then add "harbor-itbench-aa-adapter" to dependencies
uv sync

# Download the dataset (~31 GB, public, reuses the local HF cache on re-runs)
hf download ArtificialAnalysis/ITBench-AA --repo-type dataset

# One-time conversion of scenarios into self-contained Harbor tasks
uv run itbench-aa --output-dir datasets/itbench-aa

# Login to OpenShift and select the project (tasks run as OpenShift pods)
oc login --web
oc project sre-leaderboard-test   # redundant with --ek namespace, made explicit for clarity

# Run the benchmark (Claude Sonnet 5.5 via a hosted Anthropic-compatible gateway; OpenCode harness)
export GATEWAY_KEY='<api-key>'
export GATEWAY_URL='<gateway-host>'

uv run harbor run --agent opencode \
    --model gateway-hosted/claude-sonnet-5-5 \
    -p datasets/itbench-aa \
    --n-concurrent 4 \
    --env openshift \
    --ek namespace=sre-leaderboard-test \
    --ek nft_redir_init=True \
    --agent-timeout-multiplier 3 \
    --ae GATEWAY_KEY=$GATEWAY_KEY \
    --ae GATEWAY_URL=$GATEWAY_URL \
    --ak 'opencode_config={"provider":{"gateway-hosted":{"npm":"@ai-sdk/anthropic","name":"Gateway (hosted)","options":{"baseURL":"{env:GATEWAY_URL}/v1","apiKey":"{env:GATEWAY_KEY}"},"models":{"claude-sonnet-5-5":{"name":"Claude Sonnet 5.5 (hosted)","tool_call":true,"reasoning":true,"options":{"thinking":{"blockBinding":false}}}}}}}' \
    --allow-agent-host $GATEWAY_URL \
    --allow-agent-host models.dev \
    --max-retries 1 \
    --retry-include UnknownApiError \
    --retry-include AgentTimeoutError \
    --retry-include NonZeroAgentExitCodeError \
    --retry-include ApiRateLimitError \
    --retry-include ApiUsageLimitError \
    --job-name it_bench_aa/claude_sonnet_5_5_opencode_os \
    --debug
```

**`config.json`:**

```json
{
    "job_name": "it_bench_aa/claude_sonnet_5_5_opencode_os",
    "agent_timeout_multiplier": 3.0,
    "debug": true,
    "retry": {
        "max_retries": 1,
        "include_exceptions": [
            "ApiRateLimitError",
            "UnknownApiError",
            "ApiUsageLimitError",
            "NonZeroAgentExitCodeError",
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
            "name": "opencode",
            "model_name": "enmaas/claude-sonnet-5-5",
            "extra_allowed_hosts": [
                "api.enmaas.devshift.net",
                "models.dev"
            ],
            "kwargs": {
                "opencode_config": {
                    "provider": {
                        "enmaas": {
                            "npm": "@ai-sdk/anthropic",
                            "name": "EnMaaS",
                            "options": {
                                "baseURL": "{env:ENMAAS_BASE_URL}",
                                "apiKey": "{env:ENMAAS_KEY}"
                            },
                            "models": {
                                "claude-sonnet-5-5": {
                                    "name": "Claude Sonnet 5.5 (EnMaaS)",
                                    "tool_call": true,
                                    "reasoning": true,
                                    "options": {
                                        "thinking": {
                                            "blockBinding": false
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "env": {
                "ENMAAS_BASE_URL": "https://api.enmaas.devshift.net/v1",
                "ENMAAS_KEY": "${ENMAAS_KEY}"
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
    "id": "ebccdd68-20f7-4166-896f-cd48276ed826",
    "started_at": "2026-10-23T13:20:09.309882",
    "updated_at": "2026-10-27T10:16:13.768585",
    "finished_at": "2026-10-27T10:16:13.768585",
    "n_total_trials": 40,
    "stats": {
        "n_completed_trials": 40,
        "n_errored_trials": 7,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 32,
        "evals": {
            "opencode__claude-sonnet-5-5__itbench-aa": {
                "n_trials": 40,
                "n_errors": 7,
                "metrics": [
                    {
                        "answer_format_valid": 1.0,
                        "answer_recovered_from_transcript": 0.0,
                        "entity_count_expected": 1.0,
                        "kind_match": 0.35,
                        "name_match": 0.85,
                        "namespace_applicable": 0.975,
                        "namespace_match": 0.6,
                        "reasoning_present": 0.975,
                        "reward": 0.5208333333333333,
                        "submitted_entity_count": 1.225,
                        "turn_count": 14.625
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-38__mAMm7hE",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-9__ARRFEcv",
                            "scenario-17__NaTL2iZ",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-37__oGmefSJ"
                        ],
                        "1.0": [
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-34__FEHd5cs",
                            "scenario-7__92s3MZ7",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-40__6YWBaCf"
                        ],
                        "0.5": [
                            "scenario-21__uzRffm9",
                            "scenario-33__TmqALfi",
                            "scenario-4__Z5FPxCm",
                            "scenario-8__c2WgXEe",
                            "scenario-91__qSRq6eP"
                        ],
                        "0.3333333333333333": [
                            "scenario-19__hqE4Yur"
                        ]
                    },
                    "answer_format_valid": {
                        "1.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-21__uzRffm9",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-33__TmqALfi",
                            "scenario-34__FEHd5cs",
                            "scenario-38__mAMm7hE",
                            "scenario-4__Z5FPxCm",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-7__92s3MZ7",
                            "scenario-8__c2WgXEe",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-9__ARRFEcv",
                            "scenario-91__qSRq6eP",
                            "scenario-17__NaTL2iZ",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-19__hqE4Yur",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-37__oGmefSJ",
                            "scenario-40__6YWBaCf"
                        ]
                    },
                    "answer_recovered_from_transcript": {
                        "0.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-21__uzRffm9",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-33__TmqALfi",
                            "scenario-34__FEHd5cs",
                            "scenario-38__mAMm7hE",
                            "scenario-4__Z5FPxCm",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-7__92s3MZ7",
                            "scenario-8__c2WgXEe",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-9__ARRFEcv",
                            "scenario-91__qSRq6eP",
                            "scenario-17__NaTL2iZ",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-19__hqE4Yur",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-37__oGmefSJ",
                            "scenario-40__6YWBaCf"
                        ]
                    },
                    "name_match": {
                        "0.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-3__cWvdxEz",
                            "scenario-37__oGmefSJ"
                        ],
                        "1.0": [
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-21__uzRffm9",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-31__r9GgnVG",
                            "scenario-33__TmqALfi",
                            "scenario-34__FEHd5cs",
                            "scenario-38__mAMm7hE",
                            "scenario-4__Z5FPxCm",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-7__92s3MZ7",
                            "scenario-8__c2WgXEe",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-9__ARRFEcv",
                            "scenario-91__qSRq6eP",
                            "scenario-17__NaTL2iZ",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-19__hqE4Yur",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-35__k7eQaQC",
                            "scenario-40__6YWBaCf"
                        ]
                    },
                    "kind_match": {
                        "0.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-18__qVzPbgt",
                            "scenario-21__uzRffm9",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-33__TmqALfi",
                            "scenario-34__FEHd5cs",
                            "scenario-38__mAMm7hE",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-9__ARRFEcv",
                            "scenario-91__qSRq6eP",
                            "scenario-17__NaTL2iZ",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-37__oGmefSJ",
                            "scenario-40__6YWBaCf"
                        ],
                        "1.0": [
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-2__g6VjjJx",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-4__Z5FPxCm",
                            "scenario-7__92s3MZ7",
                            "scenario-8__c2WgXEe",
                            "scenario-20__S4KQ5sR",
                            "scenario-19__hqE4Yur"
                        ]
                    },
                    "namespace_match": {
                        "0.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-38__mAMm7hE",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-9__ARRFEcv",
                            "scenario-17__NaTL2iZ",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-37__oGmefSJ"
                        ],
                        "1.0": [
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-21__uzRffm9",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-33__TmqALfi",
                            "scenario-34__FEHd5cs",
                            "scenario-4__Z5FPxCm",
                            "scenario-7__92s3MZ7",
                            "scenario-8__c2WgXEe",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-91__qSRq6eP",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-19__hqE4Yur",
                            "scenario-40__6YWBaCf"
                        ]
                    },
                    "namespace_applicable": {
                        "1.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-21__uzRffm9",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-33__TmqALfi",
                            "scenario-34__FEHd5cs",
                            "scenario-38__mAMm7hE",
                            "scenario-4__Z5FPxCm",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-7__92s3MZ7",
                            "scenario-8__c2WgXEe",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-9__ARRFEcv",
                            "scenario-91__qSRq6eP",
                            "scenario-17__NaTL2iZ",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-19__hqE4Yur",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-37__oGmefSJ",
                            "scenario-40__6YWBaCf"
                        ],
                        "0.0": [
                            "scenario-102__AQtAyke"
                        ]
                    },
                    "reasoning_present": {
                        "1.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-21__uzRffm9",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-33__TmqALfi",
                            "scenario-34__FEHd5cs",
                            "scenario-38__mAMm7hE",
                            "scenario-4__Z5FPxCm",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-7__92s3MZ7",
                            "scenario-8__c2WgXEe",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-9__ARRFEcv",
                            "scenario-91__qSRq6eP",
                            "scenario-17__NaTL2iZ",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-19__hqE4Yur",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-40__6YWBaCf"
                        ],
                        "0.0": [
                            "scenario-37__oGmefSJ"
                        ]
                    },
                    "entity_count_expected": {
                        "1.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-21__uzRffm9",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-33__TmqALfi",
                            "scenario-34__FEHd5cs",
                            "scenario-38__mAMm7hE",
                            "scenario-4__Z5FPxCm",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-7__92s3MZ7",
                            "scenario-8__c2WgXEe",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-9__ARRFEcv",
                            "scenario-91__qSRq6eP",
                            "scenario-17__NaTL2iZ",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-19__hqE4Yur",
                            "scenario-11__W89Tdt3",
                            "scenario-26__6H3vq2w",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-37__oGmefSJ",
                            "scenario-40__6YWBaCf"
                        ]
                    },
                    "submitted_entity_count": {
                        "1.0": [
                            "scenario-1__U7QcwQa",
                            "scenario-102__AQtAyke",
                            "scenario-105__2MuRLFY",
                            "scenario-12__K3HpEq9",
                            "scenario-13__ffsgjBB",
                            "scenario-14__59UCLQD",
                            "scenario-15__6JvdKVq",
                            "scenario-16__hqtLibT",
                            "scenario-18__qVzPbgt",
                            "scenario-2__g6VjjJx",
                            "scenario-23__i9iDUyW",
                            "scenario-24__JV4uq3k",
                            "scenario-25__MBsLjwV",
                            "scenario-29__SixmmHc",
                            "scenario-31__r9GgnVG",
                            "scenario-34__FEHd5cs",
                            "scenario-38__mAMm7hE",
                            "scenario-5__VShJtBg",
                            "scenario-6__BTnZZDG",
                            "scenario-7__92s3MZ7",
                            "scenario-80__TeqxMqV",
                            "scenario-81__dsSLg76",
                            "scenario-9__ARRFEcv",
                            "scenario-20__S4KQ5sR",
                            "scenario-22__5oHQm3w",
                            "scenario-83__5o2PdqD",
                            "scenario-11__W89Tdt3",
                            "scenario-27__fcFWdrm",
                            "scenario-3__cWvdxEz",
                            "scenario-35__k7eQaQC",
                            "scenario-37__oGmefSJ",
                            "scenario-40__6YWBaCf"
                        ],
                        "2.0": [
                            "scenario-21__uzRffm9",
                            "scenario-33__TmqALfi",
                            "scenario-4__Z5FPxCm",
                            "scenario-8__c2WgXEe",
                            "scenario-91__qSRq6eP",
                            "scenario-17__NaTL2iZ",
                            "scenario-26__6H3vq2w"
                        ],
                        "3.0": [
                            "scenario-19__hqE4Yur"
                        ]
                    },
                    "turn_count": {
                        "20.0": [
                            "scenario-1__U7QcwQa"
                        ],
                        "9.0": [
                            "scenario-102__AQtAyke",
                            "scenario-24__JV4uq3k",
                            "scenario-33__TmqALfi",
                            "scenario-80__TeqxMqV"
                        ],
                        "8.0": [
                            "scenario-105__2MuRLFY",
                            "scenario-22__5oHQm3w"
                        ],
                        "21.0": [
                            "scenario-12__K3HpEq9"
                        ],
                        "12.0": [
                            "scenario-13__ffsgjBB",
                            "scenario-83__5o2PdqD",
                            "scenario-19__hqE4Yur"
                        ],
                        "13.0": [
                            "scenario-14__59UCLQD",
                            "scenario-21__uzRffm9",
                            "scenario-5__VShJtBg",
                            "scenario-17__NaTL2iZ",
                            "scenario-37__oGmefSJ",
                            "scenario-40__6YWBaCf"
                        ],
                        "15.0": [
                            "scenario-15__6JvdKVq",
                            "scenario-38__mAMm7hE",
                            "scenario-7__92s3MZ7"
                        ],
                        "11.0": [
                            "scenario-16__hqtLibT",
                            "scenario-29__SixmmHc",
                            "scenario-91__qSRq6eP",
                            "scenario-20__S4KQ5sR",
                            "scenario-35__k7eQaQC"
                        ],
                        "17.0": [
                            "scenario-18__qVzPbgt",
                            "scenario-31__r9GgnVG"
                        ],
                        "19.0": [
                            "scenario-2__g6VjjJx",
                            "scenario-6__BTnZZDG",
                            "scenario-8__c2WgXEe",
                            "scenario-27__fcFWdrm"
                        ],
                        "5.0": [
                            "scenario-23__i9iDUyW"
                        ],
                        "18.0": [
                            "scenario-25__MBsLjwV",
                            "scenario-9__ARRFEcv"
                        ],
                        "29.0": [
                            "scenario-34__FEHd5cs"
                        ],
                        "26.0": [
                            "scenario-4__Z5FPxCm"
                        ],
                        "14.0": [
                            "scenario-81__dsSLg76",
                            "scenario-11__W89Tdt3"
                        ],
                        "34.0": [
                            "scenario-26__6H3vq2w"
                        ],
                        "10.0": [
                            "scenario-3__cWvdxEz"
                        ]
                    }
                },
                "exception_stats": {
                    "NetworkConnectionError": [
                        "scenario-11__W89Tdt3",
                        "scenario-35__k7eQaQC",
                        "scenario-40__6YWBaCf"
                    ],
                    "ApiRateLimitError": [
                        "scenario-26__6H3vq2w"
                    ],
                    "NonZeroAgentExitCodeError": [
                        "scenario-27__fcFWdrm",
                        "scenario-3__cWvdxEz",
                        "scenario-37__oGmefSJ"
                    ]
                }
            }
        },
        "n_input_tokens": 20968100,
        "n_cache_tokens": 20966850,
        "n_output_tokens": 220663,
        "cost_usd": 9.911675
    }
}

```