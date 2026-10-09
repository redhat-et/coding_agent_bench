# ITBench-AA GLM-5.3 OpenCode

## Benchmark

**Run Date:** 2026-09-29T19:34:08.082935Z  
**Dataset:** [datasets/itbench-aa](https://hub.harborframework.com/datasets/datasets/itbench-aa/latest) (40 tasks)  
**Model:** gateway-hosted/rits/zai-org/glm-5-3  
**Harness:** opencode  
**Environment:** openshift  
**Job Name:** it_bench_aa/glm53_opencode_os  

## Results

**Score:** 37.7% (12 Full Reward / 8 Partial Reward / 20 Zero Reward / 0 Errors)   
**Error Rate:** 0.0% ()  
**Total Time:** 06h 53m 38s  
**Agent Time:** 06h 16m 59s (00h 18m 50s avg per task)  
**Estimated Cost:** $8.28  ($0.21 avg per task)  
**Input Tokens:** 377737743 (9443443 avg per task)  
**Output Tokens:** 2362160 (59054 avg per task)  
**Cache Hit Rate:** 97.8%

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

uv run harbor run --agent opencode \
    --model gateway-hosted/rits/zai-org/glm-5-3 \
    -p datasets/itbench-aa \
    --n-concurrent 2 \
    --env openshift \
    --ek namespace=sre-leaderboard-test \
    --ek nft_redir_init=True \
    --agent-timeout-multiplier 3 \
    --ae GATEWAY_KEY=$GATEWAY_KEY \
    --ae GATEWAY_URL=$GATEWAY_URL \
    --ak 'opencode_config={"provider":{"gateway-hosted":{"npm":"@ai-sdk/anthropic","name":"Gateway (hosted)","options":{"baseURL":"{env:GATEWAY_URL}/v1","apiKey":"{env:GATEWAY_KEY}"},"models":{"rits/zai-org/glm-5-3":{"name":"GLM 5.3 (hosted)","limit":{"context":262144,"output":128000},"tool_call":true,"reasoning":true}}}}}' \
    --allow-agent-host $GATEWAY_URL \
    --allow-agent-host models.dev \
    --max-retries 1 \
    --retry-include UnknownApiError \
    --retry-include AgentTimeoutError \
    --retry-include NonZeroAgentExitCodeError \
    --retry-include ApiRateLimitError \
    --retry-include ApiUsageLimitError \
    --job-name it_bench_aa/glm53_opencode_os \
    --debug
```

**`config.json`:**

```json
{
    "job_name": "it_bench_aa/glm53_opencode_os",
    "agent_timeout_multiplier": 3.0,
    "debug": true,
    "n_concurrent_trials": 2,
    "retry": {
        "max_retries": 1,
        "include_exceptions": [
            "NonZeroAgentExitCodeError",
            "ApiUsageLimitError",
            "AgentTimeoutError",
            "ApiRateLimitError",
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
            "name": "opencode",
            "model_name": "gateway-hosted/rits/zai-org/glm-5-3",
            "extra_allowed_hosts": [
                "<gateway-host>",
                "models.dev"
            ],
            "kwargs": {
                "opencode_config": {
                    "provider": {
                        "gateway-hosted": {
                            "npm": "@ai-sdk/anthropic",
                            "name": "Gateway (hosted)",
                            "options": {
                                "baseURL": "https://<gateway-host>/v1",
                                "apiKey": "{env:GATEWAY_KEY}"
                            },
                            "models": {
                                "rits/zai-org/glm-5-3": {
                                    "name": "GLM 5.3 (hosted)",
                                    "limit": {
                                        "context": 262144,
                                        "output": 128000
                                    },
                                    "tool_call": true,
                                    "reasoning": true
                                }
                            }
                        }
                    }
                }
            },
            "env": {
                "GATEWAY_KEY": "${GATEWAY_KEY}"
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
    "id": "ecf31fe3-ba1b-436f-97d2-6e46d6e8333a",
    "started_at": "2026-09-29T20:33:57.044201",
    "updated_at": "2026-09-30T13:01:46.201772",
    "finished_at": "2026-09-30T13:01:46.201772",
    "n_total_trials": 40,
    "stats": {
        "n_completed_trials": 40,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "opencode__rits/zai-org/glm-5-3__itbench-aa": {
                "n_trials": 40,
                "n_errors": 0,
                "metrics": [
                    {
                        "answer_format_valid": 0.925,
                        "answer_recovered_from_transcript": 0.0,
                        "entity_count_expected": 1.0,
                        "kind_match": 0.2,
                        "name_match": 0.775,
                        "namespace_applicable": 0.975,
                        "namespace_match": 0.5,
                        "reasoning_present": 0.925,
                        "reward": 0.3770833333333333,
                        "submitted_entity_count": 2.1,
                        "turn_count": 114.05
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-14__hk2E7kz",
                            "scenario-17__mQkNSnL",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-3__Lw6UZCE",
                            "scenario-4__UHaLaMh",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-8__9jmGugA",
                            "scenario-9__qKtepuX"
                        ],
                        "1.0": [
                            "scenario-105__jd95Uat",
                            "scenario-16__srCgNSz",
                            "scenario-18__2EnfVxe",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ"
                        ],
                        "0.5": [
                            "scenario-13__B7khqCR",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-40__Zx8yU5c"
                        ],
                        "0.25": [
                            "scenario-15__iuqPcWt"
                        ],
                        "0.3333333333333333": [
                            "scenario-33__Jn5gdp4",
                            "scenario-80__5wppWZQ"
                        ],
                        "0.16666666666666666": [
                            "scenario-91__tTonRCn"
                        ]
                    },
                    "answer_format_valid": {
                        "1.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-105__jd95Uat",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-13__B7khqCR",
                            "scenario-14__hk2E7kz",
                            "scenario-15__iuqPcWt",
                            "scenario-16__srCgNSz",
                            "scenario-17__mQkNSnL",
                            "scenario-18__2EnfVxe",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-33__Jn5gdp4",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-3__Lw6UZCE",
                            "scenario-40__Zx8yU5c",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-80__5wppWZQ",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ",
                            "scenario-8__9jmGugA",
                            "scenario-91__tTonRCn",
                            "scenario-9__qKtepuX"
                        ],
                        "0.0": [
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-4__UHaLaMh"
                        ]
                    },
                    "answer_recovered_from_transcript": {
                        "0.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-105__jd95Uat",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-13__B7khqCR",
                            "scenario-14__hk2E7kz",
                            "scenario-15__iuqPcWt",
                            "scenario-16__srCgNSz",
                            "scenario-17__mQkNSnL",
                            "scenario-18__2EnfVxe",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-33__Jn5gdp4",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-3__Lw6UZCE",
                            "scenario-40__Zx8yU5c",
                            "scenario-4__UHaLaMh",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-80__5wppWZQ",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ",
                            "scenario-8__9jmGugA",
                            "scenario-91__tTonRCn",
                            "scenario-9__qKtepuX"
                        ]
                    },
                    "name_match": {
                        "0.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-17__mQkNSnL",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-3__Lw6UZCE",
                            "scenario-4__UHaLaMh"
                        ],
                        "1.0": [
                            "scenario-105__jd95Uat",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-13__B7khqCR",
                            "scenario-14__hk2E7kz",
                            "scenario-15__iuqPcWt",
                            "scenario-16__srCgNSz",
                            "scenario-18__2EnfVxe",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-33__Jn5gdp4",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-40__Zx8yU5c",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-80__5wppWZQ",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ",
                            "scenario-8__9jmGugA",
                            "scenario-91__tTonRCn",
                            "scenario-9__qKtepuX"
                        ]
                    },
                    "kind_match": {
                        "0.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-14__hk2E7kz",
                            "scenario-17__mQkNSnL",
                            "scenario-18__2EnfVxe",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-33__Jn5gdp4",
                            "scenario-35__k65JCSY",
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-3__Lw6UZCE",
                            "scenario-40__Zx8yU5c",
                            "scenario-4__UHaLaMh",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-80__5wppWZQ",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ",
                            "scenario-8__9jmGugA",
                            "scenario-91__tTonRCn",
                            "scenario-9__qKtepuX"
                        ],
                        "1.0": [
                            "scenario-105__jd95Uat",
                            "scenario-13__B7khqCR",
                            "scenario-15__iuqPcWt",
                            "scenario-16__srCgNSz",
                            "scenario-20__VFViPfk",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-34__zWGicDj"
                        ]
                    },
                    "namespace_match": {
                        "0.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-14__hk2E7kz",
                            "scenario-17__mQkNSnL",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-3__Lw6UZCE",
                            "scenario-4__UHaLaMh",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-8__9jmGugA",
                            "scenario-9__qKtepuX"
                        ],
                        "1.0": [
                            "scenario-105__jd95Uat",
                            "scenario-13__B7khqCR",
                            "scenario-15__iuqPcWt",
                            "scenario-16__srCgNSz",
                            "scenario-18__2EnfVxe",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-33__Jn5gdp4",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-40__Zx8yU5c",
                            "scenario-80__5wppWZQ",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ",
                            "scenario-91__tTonRCn"
                        ]
                    },
                    "namespace_applicable": {
                        "0.0": [
                            "scenario-102__Y9VC56W"
                        ],
                        "1.0": [
                            "scenario-105__jd95Uat",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-13__B7khqCR",
                            "scenario-14__hk2E7kz",
                            "scenario-15__iuqPcWt",
                            "scenario-16__srCgNSz",
                            "scenario-17__mQkNSnL",
                            "scenario-18__2EnfVxe",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-33__Jn5gdp4",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-3__Lw6UZCE",
                            "scenario-40__Zx8yU5c",
                            "scenario-4__UHaLaMh",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-80__5wppWZQ",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ",
                            "scenario-8__9jmGugA",
                            "scenario-91__tTonRCn",
                            "scenario-9__qKtepuX"
                        ]
                    },
                    "reasoning_present": {
                        "1.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-105__jd95Uat",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-13__B7khqCR",
                            "scenario-14__hk2E7kz",
                            "scenario-15__iuqPcWt",
                            "scenario-16__srCgNSz",
                            "scenario-17__mQkNSnL",
                            "scenario-18__2EnfVxe",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-33__Jn5gdp4",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-3__Lw6UZCE",
                            "scenario-40__Zx8yU5c",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-80__5wppWZQ",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ",
                            "scenario-8__9jmGugA",
                            "scenario-91__tTonRCn",
                            "scenario-9__qKtepuX"
                        ],
                        "0.0": [
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-4__UHaLaMh"
                        ]
                    },
                    "entity_count_expected": {
                        "1.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-105__jd95Uat",
                            "scenario-11__pgER5HQ",
                            "scenario-12__Lbn8jB2",
                            "scenario-13__B7khqCR",
                            "scenario-14__hk2E7kz",
                            "scenario-15__iuqPcWt",
                            "scenario-16__srCgNSz",
                            "scenario-17__mQkNSnL",
                            "scenario-18__2EnfVxe",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-25__e3T4Hw2",
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-29__Qfe4aGk",
                            "scenario-2__Fhz2sf4",
                            "scenario-31__aSW4JGN",
                            "scenario-33__Jn5gdp4",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-3__Lw6UZCE",
                            "scenario-40__Zx8yU5c",
                            "scenario-4__UHaLaMh",
                            "scenario-5__vgQsfE6",
                            "scenario-6__QGvsSsy",
                            "scenario-7__7hbotUo",
                            "scenario-80__5wppWZQ",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ",
                            "scenario-8__9jmGugA",
                            "scenario-91__tTonRCn",
                            "scenario-9__qKtepuX"
                        ]
                    },
                    "submitted_entity_count": {
                        "1.0": [
                            "scenario-102__Y9VC56W",
                            "scenario-105__jd95Uat",
                            "scenario-16__srCgNSz",
                            "scenario-17__mQkNSnL",
                            "scenario-18__2EnfVxe",
                            "scenario-20__VFViPfk",
                            "scenario-21__LnjTSAc",
                            "scenario-22__Y2Q6dAE",
                            "scenario-23__TbicuFv",
                            "scenario-24__y2sxmDJ",
                            "scenario-25__e3T4Hw2",
                            "scenario-34__zWGicDj",
                            "scenario-35__k65JCSY",
                            "scenario-3__Lw6UZCE",
                            "scenario-6__QGvsSsy",
                            "scenario-81__RChFz8a",
                            "scenario-83__xkfi9KZ"
                        ],
                        "4.0": [
                            "scenario-11__pgER5HQ",
                            "scenario-15__iuqPcWt",
                            "scenario-31__aSW4JGN",
                            "scenario-8__9jmGugA",
                            "scenario-9__qKtepuX"
                        ],
                        "5.0": [
                            "scenario-12__Lbn8jB2"
                        ],
                        "2.0": [
                            "scenario-13__B7khqCR",
                            "scenario-14__hk2E7kz",
                            "scenario-19__NDgqiPg",
                            "scenario-1__TocSggH",
                            "scenario-29__Qfe4aGk",
                            "scenario-40__Zx8yU5c"
                        ],
                        "3.0": [
                            "scenario-26__C4KhddH",
                            "scenario-27__JyRYx6H",
                            "scenario-2__Fhz2sf4",
                            "scenario-33__Jn5gdp4",
                            "scenario-5__vgQsfE6",
                            "scenario-80__5wppWZQ"
                        ],
                        "0.0": [
                            "scenario-37__EXkqVUP",
                            "scenario-38__2czLsTm",
                            "scenario-4__UHaLaMh"
                        ],
                        "6.0": [
                            "scenario-7__7hbotUo",
                            "scenario-91__tTonRCn"
                        ]
                    },
                    "turn_count": {
                        "77.0": [
                            "scenario-102__Y9VC56W"
                        ],
                        "84.0": [
                            "scenario-105__jd95Uat"
                        ],
                        "176.0": [
                            "scenario-11__pgER5HQ"
                        ],
                        "125.0": [
                            "scenario-12__Lbn8jB2",
                            "scenario-9__qKtepuX"
                        ],
                        "113.0": [
                            "scenario-13__B7khqCR"
                        ],
                        "102.0": [
                            "scenario-14__hk2E7kz"
                        ],
                        "105.0": [
                            "scenario-15__iuqPcWt"
                        ],
                        "76.0": [
                            "scenario-16__srCgNSz"
                        ],
                        "129.0": [
                            "scenario-17__mQkNSnL",
                            "scenario-34__zWGicDj"
                        ],
                        "130.0": [
                            "scenario-18__2EnfVxe"
                        ],
                        "104.0": [
                            "scenario-19__NDgqiPg"
                        ],
                        "143.0": [
                            "scenario-1__TocSggH"
                        ],
                        "304.0": [
                            "scenario-20__VFViPfk"
                        ],
                        "70.0": [
                            "scenario-21__LnjTSAc"
                        ],
                        "81.0": [
                            "scenario-22__Y2Q6dAE"
                        ],
                        "69.0": [
                            "scenario-23__TbicuFv"
                        ],
                        "95.0": [
                            "scenario-24__y2sxmDJ"
                        ],
                        "67.0": [
                            "scenario-25__e3T4Hw2"
                        ],
                        "117.0": [
                            "scenario-26__C4KhddH"
                        ],
                        "96.0": [
                            "scenario-27__JyRYx6H"
                        ],
                        "112.0": [
                            "scenario-29__Qfe4aGk"
                        ],
                        "128.0": [
                            "scenario-2__Fhz2sf4"
                        ],
                        "139.0": [
                            "scenario-31__aSW4JGN"
                        ],
                        "51.0": [
                            "scenario-33__Jn5gdp4"
                        ],
                        "90.0": [
                            "scenario-35__k65JCSY"
                        ],
                        "60.0": [
                            "scenario-37__EXkqVUP"
                        ],
                        "62.0": [
                            "scenario-38__2czLsTm"
                        ],
                        "148.0": [
                            "scenario-3__Lw6UZCE"
                        ],
                        "94.0": [
                            "scenario-40__Zx8yU5c"
                        ],
                        "57.0": [
                            "scenario-4__UHaLaMh"
                        ],
                        "160.0": [
                            "scenario-5__vgQsfE6"
                        ],
                        "92.0": [
                            "scenario-6__QGvsSsy"
                        ],
                        "110.0": [
                            "scenario-7__7hbotUo"
                        ],
                        "281.0": [
                            "scenario-80__5wppWZQ"
                        ],
                        "100.0": [
                            "scenario-81__RChFz8a"
                        ],
                        "72.0": [
                            "scenario-83__xkfi9KZ"
                        ],
                        "114.0": [
                            "scenario-8__9jmGugA"
                        ],
                        "175.0": [
                            "scenario-91__tTonRCn"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 377737743,
        "n_cache_tokens": 369300480,
        "n_output_tokens": 2362160,
        "cost_usd": 8.284612999999998
    },
    "trial_results": []
}
```
