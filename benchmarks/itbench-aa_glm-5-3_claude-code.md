# ITBench-AA GLM-5.3 Claude Code

## Benchmark

**Run Date:** 2026-10-07T06:38:44.281811Z, 2026-10-12T19:19:39.647478Z  
**Dataset:** [datasets/itbench-aa](https://hub.harborframework.com/datasets/datasets/itbench-aa/latest) (40 tasks)  
**Model:** rits/zai-org/glm-5-3  
**Harness:** claude-code  
**Environment:** openshift  
**Job Name:** it_bench_aa/glm53_claude_os_high, it_bench_aa/glm53_claude_os_high_2  

## Results (avg of 2 runs)

**Score:** 42.7% (13.5 Full Reward / 9.5 Partial Reward / 17 Zero Reward / 0.5 Errors)   
**Error Rate:** 1.25% (1 UnknownApiErrors)  
**Total Time:** 04h 11m 22s  
**Agent Time:** 03h 44m 09s (00h 13m 33s avg per task)  
**Estimated Cost:** $41.85  ($1.05 avg per task)  
**Input Tokens:** 212728326 (5318208 avg per task)  
**Output Tokens:** 1692045 (42301 avg per task)  
**Cache Hit Rate:** 97.1%

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

# Run the benchmark (GLM 5.3 via a hosted Anthropic-compatible gateway)
# Run 1 (glm53_claude_os_high) used --n-concurrent 2 and CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000.
export GATEWAY_KEY='<api-key>'
export GATEWAY_URL='<gateway-host>'

uv run harbor run --agent claude-code \
    --model rits/zai-org/glm-5-3 \
    -p datasets/itbench-aa \
    --n-concurrent 3 \
    --env openshift \
    --ek namespace=sre-leaderboard-test \
    --ek nft_redir_init=True \
    --agent-timeout-multiplier 3 \
    --ae 'ANTHROPIC_BASE_URL=${GATEWAY_URL}' \
    --ae 'ANTHROPIC_API_KEY=${GATEWAY_KEY}' \
    --ae CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1 \
    --ae CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000 \
    --ak 'reasoning_effort=high' \
    --allow-agent-host $GATEWAY_URL \
    --allow-agent-host downloads.claude.ai \
    --max-retries 1 \
    --retry-include UnknownApiError \
    --retry-include AgentTimeoutError \
    --retry-include NonZeroAgentExitCodeError \
    --retry-include ApiRateLimitError \
    --retry-include ApiUsageLimitError \
    --job-name it_bench_aa/glm53_claude_os_high_2 \
    --debug
```

### Run 1: it_bench_aa/glm53_claude_os_high

**`config.json`:**

```json
{
    "job_name": "it_bench_aa/glm53_claude_os_high",
    "agent_timeout_multiplier": 3.0,
    "debug": true,
    "n_concurrent_trials": 2,
    "retry": {
        "max_retries": 1,
        "include_exceptions": [
            "AgentTimeoutError",
            "UnknownApiError",
            "ApiUsageLimitError",
            "NonZeroAgentExitCodeError",
            "ApiRateLimitError"
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
            "model_name": "rits/zai-org/glm-5-3",
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

### Run 2: it_bench_aa/glm53_claude_os_high_2

**`config.json`:**

```json
{
    "job_name": "it_bench_aa/glm53_claude_os_high_2",
    "agent_timeout_multiplier": 3.0,
    "debug": true,
    "n_concurrent_trials": 3,
    "retry": {
        "max_retries": 1,
        "include_exceptions": [
            "UnknownApiError",
            "ApiUsageLimitError",
            "ApiRateLimitError",
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
            "name": "claude-code",
            "model_name": "rits/zai-org/glm-5-3",
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
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000"
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

### Run 1: it_bench_aa/glm53_claude_os_high

```json
{
    "id": "1f306e25-68f7-464f-a2c3-bc4a90228330",
    "started_at": "2026-10-07T07:38:20.854362",
    "updated_at": "2026-10-07T14:53:21.153299",
    "finished_at": "2026-10-07T14:53:21.153299",
    "n_total_trials": 40,
    "stats": {
        "n_completed_trials": 40,
        "n_errored_trials": 1,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 3,
        "evals": {
            "claude-code__zai-org/glm-5-3__itbench-aa": {
                "n_trials": 40,
                "n_errors": 1,
                "metrics": [
                    {
                        "answer_format_valid": 0.975,
                        "answer_recovered_from_transcript": 0.0,
                        "entity_count_expected": 1.0,
                        "kind_match": 0.25,
                        "name_match": 0.825,
                        "namespace_applicable": 0.975,
                        "namespace_match": 0.85,
                        "reasoning_present": 0.95,
                        "reward": 0.4008333333333334,
                        "submitted_entity_count": 2.1,
                        "turn_count": 114.05
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.3333333333333333": [
                            "scenario-1__D8k5w7z",
                            "scenario-15__oddpcgb",
                            "scenario-33__WppuExt",
                            "scenario-81__ZiYDFY9"
                        ],
                        "0.0": [
                            "scenario-102__5SxANTw",
                            "scenario-11__RXrFnhn",
                            "scenario-14__5AhEeHv",
                            "scenario-17__9huW7N8",
                            "scenario-25__wwkuHfB",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-31__2QgsoVz",
                            "scenario-37__uFzqbev",
                            "scenario-4__NcfaG2L",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-8__xzBvQLo",
                            "scenario-9__z9vAG5R",
                            "scenario-12__ff8GcbD"
                        ],
                        "1.0": [
                            "scenario-105__cTGeAcY",
                            "scenario-16__KCZHn7b",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-83__QSGzFTy"
                        ],
                        "0.5": [
                            "scenario-13__QiMLmJT",
                            "scenario-40__vGytNTP",
                            "scenario-7__7BVQrC2",
                            "scenario-80__NmnoHpg"
                        ],
                        "0.25": [
                            "scenario-2__UwiC7dx",
                            "scenario-91__jLGH8Gg"
                        ],
                        "0.2": [
                            "scenario-38__cbF42Mn"
                        ]
                    },
                    "answer_format_valid": {
                        "1.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-102__5SxANTw",
                            "scenario-105__cTGeAcY",
                            "scenario-11__RXrFnhn",
                            "scenario-13__QiMLmJT",
                            "scenario-14__5AhEeHv",
                            "scenario-15__oddpcgb",
                            "scenario-16__KCZHn7b",
                            "scenario-17__9huW7N8",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-2__UwiC7dx",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-25__wwkuHfB",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-31__2QgsoVz",
                            "scenario-33__WppuExt",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-37__uFzqbev",
                            "scenario-38__cbF42Mn",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-7__7BVQrC2",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg",
                            "scenario-81__ZiYDFY9",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R",
                            "scenario-91__jLGH8Gg"
                        ],
                        "0.0": [
                            "scenario-12__ff8GcbD"
                        ]
                    },
                    "answer_recovered_from_transcript": {
                        "0.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-102__5SxANTw",
                            "scenario-105__cTGeAcY",
                            "scenario-11__RXrFnhn",
                            "scenario-13__QiMLmJT",
                            "scenario-14__5AhEeHv",
                            "scenario-15__oddpcgb",
                            "scenario-16__KCZHn7b",
                            "scenario-17__9huW7N8",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-2__UwiC7dx",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-25__wwkuHfB",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-31__2QgsoVz",
                            "scenario-33__WppuExt",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-37__uFzqbev",
                            "scenario-38__cbF42Mn",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-7__7BVQrC2",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg",
                            "scenario-81__ZiYDFY9",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R",
                            "scenario-91__jLGH8Gg",
                            "scenario-12__ff8GcbD"
                        ]
                    },
                    "name_match": {
                        "1.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-105__cTGeAcY",
                            "scenario-11__RXrFnhn",
                            "scenario-13__QiMLmJT",
                            "scenario-14__5AhEeHv",
                            "scenario-15__oddpcgb",
                            "scenario-16__KCZHn7b",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-2__UwiC7dx",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-25__wwkuHfB",
                            "scenario-29__nkv6Pci",
                            "scenario-31__2QgsoVz",
                            "scenario-33__WppuExt",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-38__cbF42Mn",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-7__7BVQrC2",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg",
                            "scenario-81__ZiYDFY9",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R",
                            "scenario-91__jLGH8Gg"
                        ],
                        "0.0": [
                            "scenario-102__5SxANTw",
                            "scenario-17__9huW7N8",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-3__VouP9JA",
                            "scenario-37__uFzqbev",
                            "scenario-12__ff8GcbD"
                        ]
                    },
                    "kind_match": {
                        "0.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-102__5SxANTw",
                            "scenario-11__RXrFnhn",
                            "scenario-14__5AhEeHv",
                            "scenario-17__9huW7N8",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-25__wwkuHfB",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-31__2QgsoVz",
                            "scenario-33__WppuExt",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-37__uFzqbev",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg",
                            "scenario-81__ZiYDFY9",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R",
                            "scenario-91__jLGH8Gg",
                            "scenario-12__ff8GcbD"
                        ],
                        "1.0": [
                            "scenario-105__cTGeAcY",
                            "scenario-13__QiMLmJT",
                            "scenario-15__oddpcgb",
                            "scenario-16__KCZHn7b",
                            "scenario-2__UwiC7dx",
                            "scenario-20__Evgb6D5",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-38__cbF42Mn",
                            "scenario-7__7BVQrC2"
                        ]
                    },
                    "namespace_match": {
                        "1.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-105__cTGeAcY",
                            "scenario-11__RXrFnhn",
                            "scenario-13__QiMLmJT",
                            "scenario-14__5AhEeHv",
                            "scenario-15__oddpcgb",
                            "scenario-16__KCZHn7b",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-2__UwiC7dx",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-25__wwkuHfB",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-31__2QgsoVz",
                            "scenario-33__WppuExt",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-38__cbF42Mn",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-7__7BVQrC2",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg",
                            "scenario-81__ZiYDFY9",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R",
                            "scenario-91__jLGH8Gg"
                        ],
                        "0.0": [
                            "scenario-102__5SxANTw",
                            "scenario-17__9huW7N8",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-37__uFzqbev",
                            "scenario-12__ff8GcbD"
                        ]
                    },
                    "namespace_applicable": {
                        "1.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-105__cTGeAcY",
                            "scenario-11__RXrFnhn",
                            "scenario-13__QiMLmJT",
                            "scenario-14__5AhEeHv",
                            "scenario-15__oddpcgb",
                            "scenario-16__KCZHn7b",
                            "scenario-17__9huW7N8",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-2__UwiC7dx",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-25__wwkuHfB",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-31__2QgsoVz",
                            "scenario-33__WppuExt",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-37__uFzqbev",
                            "scenario-38__cbF42Mn",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-7__7BVQrC2",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg",
                            "scenario-81__ZiYDFY9",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R",
                            "scenario-91__jLGH8Gg",
                            "scenario-12__ff8GcbD"
                        ],
                        "0.0": [
                            "scenario-102__5SxANTw"
                        ]
                    },
                    "reasoning_present": {
                        "1.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-102__5SxANTw",
                            "scenario-105__cTGeAcY",
                            "scenario-11__RXrFnhn",
                            "scenario-13__QiMLmJT",
                            "scenario-14__5AhEeHv",
                            "scenario-15__oddpcgb",
                            "scenario-16__KCZHn7b",
                            "scenario-17__9huW7N8",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-2__UwiC7dx",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-25__wwkuHfB",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-31__2QgsoVz",
                            "scenario-33__WppuExt",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-38__cbF42Mn",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-7__7BVQrC2",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg",
                            "scenario-81__ZiYDFY9",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R",
                            "scenario-91__jLGH8Gg"
                        ],
                        "0.0": [
                            "scenario-37__uFzqbev",
                            "scenario-12__ff8GcbD"
                        ]
                    },
                    "entity_count_expected": {
                        "1.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-102__5SxANTw",
                            "scenario-105__cTGeAcY",
                            "scenario-11__RXrFnhn",
                            "scenario-13__QiMLmJT",
                            "scenario-14__5AhEeHv",
                            "scenario-15__oddpcgb",
                            "scenario-16__KCZHn7b",
                            "scenario-17__9huW7N8",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-2__UwiC7dx",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-25__wwkuHfB",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-31__2QgsoVz",
                            "scenario-33__WppuExt",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-37__uFzqbev",
                            "scenario-38__cbF42Mn",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-7__7BVQrC2",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg",
                            "scenario-81__ZiYDFY9",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R",
                            "scenario-91__jLGH8Gg",
                            "scenario-12__ff8GcbD"
                        ]
                    },
                    "submitted_entity_count": {
                        "4.0": [
                            "scenario-1__D8k5w7z",
                            "scenario-2__UwiC7dx",
                            "scenario-91__jLGH8Gg"
                        ],
                        "1.0": [
                            "scenario-102__5SxANTw",
                            "scenario-105__cTGeAcY",
                            "scenario-16__KCZHn7b",
                            "scenario-18__8ZfMSbf",
                            "scenario-19__H2TomAF",
                            "scenario-20__Evgb6D5",
                            "scenario-21__jETFcLN",
                            "scenario-22__iUy3QmE",
                            "scenario-23__H5bKeZV",
                            "scenario-24__mN6QGZn",
                            "scenario-34__cb6KfLY",
                            "scenario-35__dwNiPHZ",
                            "scenario-83__QSGzFTy",
                            "scenario-9__z9vAG5R"
                        ],
                        "2.0": [
                            "scenario-11__RXrFnhn",
                            "scenario-13__QiMLmJT",
                            "scenario-14__5AhEeHv",
                            "scenario-25__wwkuHfB",
                            "scenario-29__nkv6Pci",
                            "scenario-3__VouP9JA",
                            "scenario-37__uFzqbev",
                            "scenario-4__NcfaG2L",
                            "scenario-40__vGytNTP",
                            "scenario-5__YKRuAY9",
                            "scenario-6__Vpxcnoy",
                            "scenario-7__7BVQrC2",
                            "scenario-8__xzBvQLo",
                            "scenario-80__NmnoHpg"
                        ],
                        "3.0": [
                            "scenario-15__oddpcgb",
                            "scenario-17__9huW7N8",
                            "scenario-26__kehq6rE",
                            "scenario-27__CNDHUB6",
                            "scenario-33__WppuExt",
                            "scenario-81__ZiYDFY9"
                        ],
                        "6.0": [
                            "scenario-31__2QgsoVz",
                            "scenario-38__cbF42Mn"
                        ],
                        "0.0": [
                            "scenario-12__ff8GcbD"
                        ]
                    },
                    "turn_count": {
                        "146.0": [
                            "scenario-1__D8k5w7z"
                        ],
                        "79.0": [
                            "scenario-102__5SxANTw",
                            "scenario-22__iUy3QmE"
                        ],
                        "76.0": [
                            "scenario-105__cTGeAcY"
                        ],
                        "152.0": [
                            "scenario-11__RXrFnhn"
                        ],
                        "139.0": [
                            "scenario-13__QiMLmJT"
                        ],
                        "99.0": [
                            "scenario-14__5AhEeHv"
                        ],
                        "141.0": [
                            "scenario-15__oddpcgb",
                            "scenario-26__kehq6rE"
                        ],
                        "55.0": [
                            "scenario-16__KCZHn7b"
                        ],
                        "104.0": [
                            "scenario-17__9huW7N8"
                        ],
                        "77.0": [
                            "scenario-18__8ZfMSbf"
                        ],
                        "108.0": [
                            "scenario-19__H2TomAF"
                        ],
                        "144.0": [
                            "scenario-2__UwiC7dx"
                        ],
                        "82.0": [
                            "scenario-20__Evgb6D5"
                        ],
                        "71.0": [
                            "scenario-21__jETFcLN"
                        ],
                        "66.0": [
                            "scenario-23__H5bKeZV"
                        ],
                        "98.0": [
                            "scenario-24__mN6QGZn",
                            "scenario-80__NmnoHpg"
                        ],
                        "124.0": [
                            "scenario-25__wwkuHfB",
                            "scenario-6__Vpxcnoy"
                        ],
                        "122.0": [
                            "scenario-27__CNDHUB6"
                        ],
                        "86.0": [
                            "scenario-29__nkv6Pci"
                        ],
                        "109.0": [
                            "scenario-3__VouP9JA",
                            "scenario-8__xzBvQLo"
                        ],
                        "194.0": [
                            "scenario-31__2QgsoVz"
                        ],
                        "69.0": [
                            "scenario-33__WppuExt"
                        ],
                        "153.0": [
                            "scenario-34__cb6KfLY"
                        ],
                        "133.0": [
                            "scenario-35__dwNiPHZ"
                        ],
                        "132.0": [
                            "scenario-37__uFzqbev"
                        ],
                        "127.0": [
                            "scenario-38__cbF42Mn"
                        ],
                        "112.0": [
                            "scenario-4__NcfaG2L"
                        ],
                        "118.0": [
                            "scenario-40__vGytNTP"
                        ],
                        "143.0": [
                            "scenario-5__YKRuAY9"
                        ],
                        "147.0": [
                            "scenario-7__7BVQrC2"
                        ],
                        "94.0": [
                            "scenario-81__ZiYDFY9"
                        ],
                        "88.0": [
                            "scenario-83__QSGzFTy"
                        ],
                        "103.0": [
                            "scenario-9__z9vAG5R"
                        ],
                        "136.0": [
                            "scenario-91__jLGH8Gg"
                        ],
                        "184.0": [
                            "scenario-12__ff8GcbD"
                        ]
                    }
                },
                "exception_stats": {
                    "UnknownApiError": [
                        "scenario-12__ff8GcbD"
                    ]
                }
            }
        },
        "n_input_tokens": 243626009,
        "n_cache_tokens": 237868544,
        "n_output_tokens": 1364774,
        "cost_usd": 45.546767
    }
}
```

### Run 2: it_bench_aa/glm53_claude_os_high_2

```json
{
    "id": "2a90b61c-e94f-4406-a6eb-287972d81c7f",
    "started_at": "2026-10-12T20:19:18.228476",
    "updated_at": "2026-10-13T00:00:42.643023",
    "finished_at": "2026-10-13T00:00:42.643023",
    "n_total_trials": 40,
    "stats": {
        "n_completed_trials": 40,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "claude-code__zai-org/glm-5-3__itbench-aa": {
                "n_trials": 40,
                "n_errors": 0,
                "metrics": [
                    {
                        "answer_format_valid": 1.0,
                        "answer_recovered_from_transcript": 0.0,
                        "entity_count_expected": 1.0,
                        "kind_match": 0.25,
                        "name_match": 0.8,
                        "namespace_applicable": 0.975,
                        "namespace_match": 0.575,
                        "reasoning_present": 1.0,
                        "reward": 0.4541666666666667,
                        "submitted_entity_count": 1.725,
                        "turn_count": 121.8
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-105__Us7gHvw",
                            "scenario-16__jnKTmbu",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-38__NgvXiN2",
                            "scenario-40__jHbAARm",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi"
                        ],
                        "0.0": [
                            "scenario-102__Rrv2Awr",
                            "scenario-11__zRreHbd",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-17__UDeZEiG",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-37__b44Lna4",
                            "scenario-4__xVVutes",
                            "scenario-5__QicdDnF",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-9__3P8EPb3"
                        ],
                        "0.5": [
                            "scenario-12__T4pCEGj",
                            "scenario-2__tgDZdEH",
                            "scenario-24__Nr4ExE2",
                            "scenario-6__nCYJUv4"
                        ],
                        "0.25": [
                            "scenario-15__AySgWCq",
                            "scenario-91__dYmTbXN"
                        ],
                        "0.3333333333333333": [
                            "scenario-33__fVbtXq5",
                            "scenario-80__ojgWLzd"
                        ]
                    },
                    "answer_format_valid": {
                        "1.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-102__Rrv2Awr",
                            "scenario-105__Us7gHvw",
                            "scenario-11__zRreHbd",
                            "scenario-12__T4pCEGj",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-15__AySgWCq",
                            "scenario-16__jnKTmbu",
                            "scenario-17__UDeZEiG",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-2__tgDZdEH",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-24__Nr4ExE2",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-33__fVbtXq5",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-37__b44Lna4",
                            "scenario-38__NgvXiN2",
                            "scenario-4__xVVutes",
                            "scenario-40__jHbAARm",
                            "scenario-5__QicdDnF",
                            "scenario-6__nCYJUv4",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-80__ojgWLzd",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-9__3P8EPb3",
                            "scenario-91__dYmTbXN"
                        ]
                    },
                    "answer_recovered_from_transcript": {
                        "0.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-102__Rrv2Awr",
                            "scenario-105__Us7gHvw",
                            "scenario-11__zRreHbd",
                            "scenario-12__T4pCEGj",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-15__AySgWCq",
                            "scenario-16__jnKTmbu",
                            "scenario-17__UDeZEiG",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-2__tgDZdEH",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-24__Nr4ExE2",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-33__fVbtXq5",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-37__b44Lna4",
                            "scenario-38__NgvXiN2",
                            "scenario-4__xVVutes",
                            "scenario-40__jHbAARm",
                            "scenario-5__QicdDnF",
                            "scenario-6__nCYJUv4",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-80__ojgWLzd",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-9__3P8EPb3",
                            "scenario-91__dYmTbXN"
                        ]
                    },
                    "name_match": {
                        "1.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-105__Us7gHvw",
                            "scenario-11__zRreHbd",
                            "scenario-12__T4pCEGj",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-15__AySgWCq",
                            "scenario-16__jnKTmbu",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-2__tgDZdEH",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-24__Nr4ExE2",
                            "scenario-31__2KJi9sv",
                            "scenario-33__fVbtXq5",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-38__NgvXiN2",
                            "scenario-4__xVVutes",
                            "scenario-40__jHbAARm",
                            "scenario-5__QicdDnF",
                            "scenario-6__nCYJUv4",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-80__ojgWLzd",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-9__3P8EPb3",
                            "scenario-91__dYmTbXN"
                        ],
                        "0.0": [
                            "scenario-102__Rrv2Awr",
                            "scenario-17__UDeZEiG",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-37__b44Lna4"
                        ]
                    },
                    "kind_match": {
                        "0.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-102__Rrv2Awr",
                            "scenario-11__zRreHbd",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-17__UDeZEiG",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-33__fVbtXq5",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-37__b44Lna4",
                            "scenario-4__xVVutes",
                            "scenario-40__jHbAARm",
                            "scenario-5__QicdDnF",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-80__ojgWLzd",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-9__3P8EPb3",
                            "scenario-91__dYmTbXN"
                        ],
                        "1.0": [
                            "scenario-105__Us7gHvw",
                            "scenario-12__T4pCEGj",
                            "scenario-15__AySgWCq",
                            "scenario-16__jnKTmbu",
                            "scenario-2__tgDZdEH",
                            "scenario-20__kAWkowZ",
                            "scenario-23__ocY6oWM",
                            "scenario-24__Nr4ExE2",
                            "scenario-38__NgvXiN2",
                            "scenario-6__nCYJUv4"
                        ]
                    },
                    "namespace_match": {
                        "1.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-105__Us7gHvw",
                            "scenario-12__T4pCEGj",
                            "scenario-15__AySgWCq",
                            "scenario-16__jnKTmbu",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-2__tgDZdEH",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-24__Nr4ExE2",
                            "scenario-33__fVbtXq5",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-38__NgvXiN2",
                            "scenario-40__jHbAARm",
                            "scenario-6__nCYJUv4",
                            "scenario-80__ojgWLzd",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-91__dYmTbXN"
                        ],
                        "0.0": [
                            "scenario-102__Rrv2Awr",
                            "scenario-11__zRreHbd",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-17__UDeZEiG",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-37__b44Lna4",
                            "scenario-4__xVVutes",
                            "scenario-5__QicdDnF",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-9__3P8EPb3"
                        ]
                    },
                    "namespace_applicable": {
                        "1.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-105__Us7gHvw",
                            "scenario-11__zRreHbd",
                            "scenario-12__T4pCEGj",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-15__AySgWCq",
                            "scenario-16__jnKTmbu",
                            "scenario-17__UDeZEiG",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-2__tgDZdEH",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-24__Nr4ExE2",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-33__fVbtXq5",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-37__b44Lna4",
                            "scenario-38__NgvXiN2",
                            "scenario-4__xVVutes",
                            "scenario-40__jHbAARm",
                            "scenario-5__QicdDnF",
                            "scenario-6__nCYJUv4",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-80__ojgWLzd",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-9__3P8EPb3",
                            "scenario-91__dYmTbXN"
                        ],
                        "0.0": [
                            "scenario-102__Rrv2Awr"
                        ]
                    },
                    "reasoning_present": {
                        "1.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-102__Rrv2Awr",
                            "scenario-105__Us7gHvw",
                            "scenario-11__zRreHbd",
                            "scenario-12__T4pCEGj",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-15__AySgWCq",
                            "scenario-16__jnKTmbu",
                            "scenario-17__UDeZEiG",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-2__tgDZdEH",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-24__Nr4ExE2",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-33__fVbtXq5",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-37__b44Lna4",
                            "scenario-38__NgvXiN2",
                            "scenario-4__xVVutes",
                            "scenario-40__jHbAARm",
                            "scenario-5__QicdDnF",
                            "scenario-6__nCYJUv4",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-80__ojgWLzd",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-9__3P8EPb3",
                            "scenario-91__dYmTbXN"
                        ]
                    },
                    "entity_count_expected": {
                        "1.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-102__Rrv2Awr",
                            "scenario-105__Us7gHvw",
                            "scenario-11__zRreHbd",
                            "scenario-12__T4pCEGj",
                            "scenario-13__r9mS7Kt",
                            "scenario-14__svycvG5",
                            "scenario-15__AySgWCq",
                            "scenario-16__jnKTmbu",
                            "scenario-17__UDeZEiG",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-2__tgDZdEH",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-24__Nr4ExE2",
                            "scenario-25__Mtf8dwt",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-29__RE3qfgo",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-33__fVbtXq5",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-37__b44Lna4",
                            "scenario-38__NgvXiN2",
                            "scenario-4__xVVutes",
                            "scenario-40__jHbAARm",
                            "scenario-5__QicdDnF",
                            "scenario-6__nCYJUv4",
                            "scenario-7__V62GmeK",
                            "scenario-8__S4Uot8k",
                            "scenario-80__ojgWLzd",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-9__3P8EPb3",
                            "scenario-91__dYmTbXN"
                        ]
                    },
                    "submitted_entity_count": {
                        "1.0": [
                            "scenario-1__DtAGNoT",
                            "scenario-102__Rrv2Awr",
                            "scenario-105__Us7gHvw",
                            "scenario-13__r9mS7Kt",
                            "scenario-16__jnKTmbu",
                            "scenario-18__NXnpgRu",
                            "scenario-19__AjzWDUZ",
                            "scenario-20__kAWkowZ",
                            "scenario-21__HakzrBU",
                            "scenario-22__QAZ58tx",
                            "scenario-23__ocY6oWM",
                            "scenario-25__Mtf8dwt",
                            "scenario-29__RE3qfgo",
                            "scenario-34__QLHNUfN",
                            "scenario-35__p2JWYut",
                            "scenario-38__NgvXiN2",
                            "scenario-40__jHbAARm",
                            "scenario-81__owWprh3",
                            "scenario-83__4rmXsXi",
                            "scenario-9__3P8EPb3"
                        ],
                        "3.0": [
                            "scenario-11__zRreHbd",
                            "scenario-33__fVbtXq5",
                            "scenario-80__ojgWLzd"
                        ],
                        "2.0": [
                            "scenario-12__T4pCEGj",
                            "scenario-14__svycvG5",
                            "scenario-17__UDeZEiG",
                            "scenario-2__tgDZdEH",
                            "scenario-24__Nr4ExE2",
                            "scenario-26__wGbG33B",
                            "scenario-27__pv3FtyK",
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv",
                            "scenario-37__b44Lna4",
                            "scenario-4__xVVutes",
                            "scenario-5__QicdDnF",
                            "scenario-6__nCYJUv4",
                            "scenario-8__S4Uot8k"
                        ],
                        "4.0": [
                            "scenario-15__AySgWCq",
                            "scenario-7__V62GmeK",
                            "scenario-91__dYmTbXN"
                        ]
                    },
                    "turn_count": {
                        "164.0": [
                            "scenario-1__DtAGNoT"
                        ],
                        "66.0": [
                            "scenario-102__Rrv2Awr"
                        ],
                        "88.0": [
                            "scenario-105__Us7gHvw"
                        ],
                        "119.0": [
                            "scenario-11__zRreHbd",
                            "scenario-7__V62GmeK"
                        ],
                        "174.0": [
                            "scenario-12__T4pCEGj"
                        ],
                        "129.0": [
                            "scenario-13__r9mS7Kt"
                        ],
                        "125.0": [
                            "scenario-14__svycvG5"
                        ],
                        "190.0": [
                            "scenario-15__AySgWCq"
                        ],
                        "72.0": [
                            "scenario-16__jnKTmbu"
                        ],
                        "150.0": [
                            "scenario-17__UDeZEiG",
                            "scenario-27__pv3FtyK"
                        ],
                        "101.0": [
                            "scenario-18__NXnpgRu"
                        ],
                        "104.0": [
                            "scenario-19__AjzWDUZ"
                        ],
                        "137.0": [
                            "scenario-2__tgDZdEH"
                        ],
                        "80.0": [
                            "scenario-20__kAWkowZ"
                        ],
                        "120.0": [
                            "scenario-21__HakzrBU"
                        ],
                        "118.0": [
                            "scenario-22__QAZ58tx"
                        ],
                        "91.0": [
                            "scenario-23__ocY6oWM"
                        ],
                        "106.0": [
                            "scenario-24__Nr4ExE2"
                        ],
                        "76.0": [
                            "scenario-25__Mtf8dwt"
                        ],
                        "135.0": [
                            "scenario-26__wGbG33B"
                        ],
                        "103.0": [
                            "scenario-29__RE3qfgo"
                        ],
                        "110.0": [
                            "scenario-3__c8gRDYp",
                            "scenario-31__2KJi9sv"
                        ],
                        "87.0": [
                            "scenario-33__fVbtXq5"
                        ],
                        "241.0": [
                            "scenario-34__QLHNUfN"
                        ],
                        "95.0": [
                            "scenario-35__p2JWYut"
                        ],
                        "92.0": [
                            "scenario-37__b44Lna4"
                        ],
                        "155.0": [
                            "scenario-38__NgvXiN2"
                        ],
                        "114.0": [
                            "scenario-4__xVVutes"
                        ],
                        "100.0": [
                            "scenario-40__jHbAARm"
                        ],
                        "121.0": [
                            "scenario-5__QicdDnF"
                        ],
                        "167.0": [
                            "scenario-6__nCYJUv4"
                        ],
                        "90.0": [
                            "scenario-8__S4Uot8k"
                        ],
                        "109.0": [
                            "scenario-80__ojgWLzd"
                        ],
                        "102.0": [
                            "scenario-81__owWprh3"
                        ],
                        "147.0": [
                            "scenario-83__4rmXsXi"
                        ],
                        "176.0": [
                            "scenario-9__3P8EPb3"
                        ],
                        "139.0": [
                            "scenario-91__dYmTbXN"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 181830643,
        "n_cache_tokens": 175328256,
        "n_output_tokens": 2019316,
        "cost_usd": 38.144207
    }
}
```
