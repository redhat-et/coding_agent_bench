# ITBench-AA Claude Sonnet 5.5 Claude Code

## Benchmark

**Run Date:** 2026-10-23T09:48:38.051434Z  
**Dataset:** [datasets/itbench-aa](https://hub.harborframework.com/datasets/datasets/itbench-aa/latest) (40 tasks)  
**Model:** claude-sonnet-5-5  
**Harness:** claude-code  
**Environment:** openshift  
**Job Name:** it_bench_aa/claude_sonnet_5_5_os_high  

## Results

**Score:** 45.0% (16 Full Reward / 4 Partial Reward / 20 Zero Reward / 0 Errors)   
**Error Rate:** 0.0% ()  
**Total Time:** 00h 25m 57s  
**Agent Time:** 00h 11m 06s (00h 01m 06s avg per task)  
**Estimated Cost:** $8.41  ($0.21 avg per task)  
**Input Tokens:** 17946155 (448653 avg per task)  
**Output Tokens:** 246809 (6170 avg per task)  
**Cache Hit Rate:** 90.4%

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

# Run the benchmark (Claude Sonnet 5.5 via a hosted Anthropic-compatible gateway)
export GATEWAY_KEY='<api-key>'
export GATEWAY_URL='<gateway-host>'

uv run harbor run --agent claude-code \
    --model claude-sonnet-5-5 \
    -p datasets/itbench-aa \
    --n-concurrent 4 \
    --env openshift \
    --ek namespace=sre-leaderboard-test \
    --ek nft_redir_init=True \
    --agent-timeout-multiplier 3 \
    --ae 'ANTHROPIC_BASE_URL=${GATEWAY_URL}' \
    --ae 'ANTHROPIC_API_KEY=${GATEWAY_KEY}' \
    --ae CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1 \
    --ak 'reasoning_effort=high' \
    --allow-agent-host $GATEWAY_URL \
    --allow-agent-host downloads.claude.ai \
    --max-retries 1 \
    --retry-include UnknownApiError \
    --retry-include AgentTimeoutError \
    --retry-include NonZeroAgentExitCodeError \
    --retry-include ApiRateLimitError \
    --retry-include ApiUsageLimitError \
    --job-name it_bench_aa/claude_sonnet_5_5_os_high \
    --debug
```

**`config.json`:**

```json
{
    "job_name": "it_bench_aa/claude_sonnet_5_5_os_high",
    "agent_timeout_multiplier": 3.0,
    "debug": true,
    "retry": {
        "max_retries": 1,
        "include_exceptions": [
            "ApiRateLimitError",
            "AgentTimeoutError",
            "UnknownApiError",
            "ApiUsageLimitError",
            "NonZeroAgentExitCodeError"
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
            "model_name": "claude-sonnet-5-5",
            "extra_allowed_hosts": [
                "api.enmaas.devshift.net",
                "downloads.claude.ai"
            ],
            "kwargs": {
                "reasoning_effort": "high"
            },
            "env": {
                "ANTHROPIC_BASE_URL": "${ENMAAS_API_ORIGIN}",
                "ANTHROPIC_API_KEY": "${ENMAAS_KEY}",
                "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1"
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
    "id": "27ea6bb6-30cf-497c-b6cb-2123cfa8aad8",
    "started_at": "2026-10-23T10:48:11.852770",
    "updated_at": "2026-10-23T11:15:45.663440",
    "finished_at": "2026-10-23T11:15:45.663440",
    "n_total_trials": 40,
    "stats": {
        "n_completed_trials": 40,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "claude-code__claude-sonnet-5-5__itbench-aa": {
                "n_trials": 40,
                "n_errors": 0,
                "metrics": [
                    {
                        "answer_format_valid": 1.0,
                        "answer_recovered_from_transcript": 0.0,
                        "entity_count_expected": 1.0,
                        "kind_match": 0.35,
                        "name_match": 0.8,
                        "namespace_applicable": 0.975,
                        "namespace_match": 0.5,
                        "reasoning_present": 0.975,
                        "reward": 0.45,
                        "submitted_entity_count": 1.175,
                        "turn_count": 22.775
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.5": [
                            "scenario-1__TpgjgJQ",
                            "scenario-33__RbDxBfJ",
                            "scenario-4__h3XeYAx",
                            "scenario-83__vueEK2M"
                        ],
                        "0.0": [
                            "scenario-102__sGSyRUJ",
                            "scenario-11__sRodve7",
                            "scenario-14__zVUgWb2",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-19__qcnJ4iK",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-34__9MvDinW",
                            "scenario-37__sTLyKPf",
                            "scenario-5__nmf2ej9",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-9__RpQu9yM"
                        ],
                        "1.0": [
                            "scenario-105__grzJGMF",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-35__yPfsk5p",
                            "scenario-38__bBKZZCG",
                            "scenario-40__y2Tvhut",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-81__DCJBSEF",
                            "scenario-91__LkeaJb4"
                        ]
                    },
                    "answer_format_valid": {
                        "1.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-102__sGSyRUJ",
                            "scenario-105__grzJGMF",
                            "scenario-11__sRodve7",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-14__zVUgWb2",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-19__qcnJ4iK",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-33__RbDxBfJ",
                            "scenario-34__9MvDinW",
                            "scenario-35__yPfsk5p",
                            "scenario-37__sTLyKPf",
                            "scenario-38__bBKZZCG",
                            "scenario-4__h3XeYAx",
                            "scenario-40__y2Tvhut",
                            "scenario-5__nmf2ej9",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-81__DCJBSEF",
                            "scenario-83__vueEK2M",
                            "scenario-9__RpQu9yM",
                            "scenario-91__LkeaJb4"
                        ]
                    },
                    "answer_recovered_from_transcript": {
                        "0.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-102__sGSyRUJ",
                            "scenario-105__grzJGMF",
                            "scenario-11__sRodve7",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-14__zVUgWb2",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-19__qcnJ4iK",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-33__RbDxBfJ",
                            "scenario-34__9MvDinW",
                            "scenario-35__yPfsk5p",
                            "scenario-37__sTLyKPf",
                            "scenario-38__bBKZZCG",
                            "scenario-4__h3XeYAx",
                            "scenario-40__y2Tvhut",
                            "scenario-5__nmf2ej9",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-81__DCJBSEF",
                            "scenario-83__vueEK2M",
                            "scenario-9__RpQu9yM",
                            "scenario-91__LkeaJb4"
                        ]
                    },
                    "name_match": {
                        "1.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-105__grzJGMF",
                            "scenario-11__sRodve7",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-14__zVUgWb2",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-31__mnbT25M",
                            "scenario-33__RbDxBfJ",
                            "scenario-34__9MvDinW",
                            "scenario-35__yPfsk5p",
                            "scenario-38__bBKZZCG",
                            "scenario-4__h3XeYAx",
                            "scenario-40__y2Tvhut",
                            "scenario-5__nmf2ej9",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-81__DCJBSEF",
                            "scenario-83__vueEK2M",
                            "scenario-9__RpQu9yM",
                            "scenario-91__LkeaJb4"
                        ],
                        "0.0": [
                            "scenario-102__sGSyRUJ",
                            "scenario-19__qcnJ4iK",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-37__sTLyKPf"
                        ]
                    },
                    "kind_match": {
                        "0.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-102__sGSyRUJ",
                            "scenario-11__sRodve7",
                            "scenario-14__zVUgWb2",
                            "scenario-17__pwnRjR4",
                            "scenario-19__qcnJ4iK",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-33__RbDxBfJ",
                            "scenario-34__9MvDinW",
                            "scenario-35__yPfsk5p",
                            "scenario-37__sTLyKPf",
                            "scenario-40__y2Tvhut",
                            "scenario-5__nmf2ej9",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-81__DCJBSEF",
                            "scenario-83__vueEK2M",
                            "scenario-9__RpQu9yM",
                            "scenario-91__LkeaJb4"
                        ],
                        "1.0": [
                            "scenario-105__grzJGMF",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-18__A6jvPKp",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-38__bBKZZCG",
                            "scenario-4__h3XeYAx",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd"
                        ]
                    },
                    "namespace_match": {
                        "1.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-105__grzJGMF",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-33__RbDxBfJ",
                            "scenario-35__yPfsk5p",
                            "scenario-38__bBKZZCG",
                            "scenario-4__h3XeYAx",
                            "scenario-40__y2Tvhut",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-81__DCJBSEF",
                            "scenario-83__vueEK2M",
                            "scenario-91__LkeaJb4"
                        ],
                        "0.0": [
                            "scenario-102__sGSyRUJ",
                            "scenario-11__sRodve7",
                            "scenario-14__zVUgWb2",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-19__qcnJ4iK",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-34__9MvDinW",
                            "scenario-37__sTLyKPf",
                            "scenario-5__nmf2ej9",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-9__RpQu9yM"
                        ]
                    },
                    "namespace_applicable": {
                        "1.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-105__grzJGMF",
                            "scenario-11__sRodve7",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-14__zVUgWb2",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-19__qcnJ4iK",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-33__RbDxBfJ",
                            "scenario-34__9MvDinW",
                            "scenario-35__yPfsk5p",
                            "scenario-37__sTLyKPf",
                            "scenario-38__bBKZZCG",
                            "scenario-4__h3XeYAx",
                            "scenario-40__y2Tvhut",
                            "scenario-5__nmf2ej9",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-81__DCJBSEF",
                            "scenario-83__vueEK2M",
                            "scenario-9__RpQu9yM",
                            "scenario-91__LkeaJb4"
                        ],
                        "0.0": [
                            "scenario-102__sGSyRUJ"
                        ]
                    },
                    "reasoning_present": {
                        "1.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-102__sGSyRUJ",
                            "scenario-105__grzJGMF",
                            "scenario-11__sRodve7",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-14__zVUgWb2",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-19__qcnJ4iK",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-33__RbDxBfJ",
                            "scenario-34__9MvDinW",
                            "scenario-35__yPfsk5p",
                            "scenario-38__bBKZZCG",
                            "scenario-4__h3XeYAx",
                            "scenario-40__y2Tvhut",
                            "scenario-5__nmf2ej9",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-81__DCJBSEF",
                            "scenario-83__vueEK2M",
                            "scenario-9__RpQu9yM",
                            "scenario-91__LkeaJb4"
                        ],
                        "0.0": [
                            "scenario-37__sTLyKPf"
                        ]
                    },
                    "entity_count_expected": {
                        "1.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-102__sGSyRUJ",
                            "scenario-105__grzJGMF",
                            "scenario-11__sRodve7",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-14__zVUgWb2",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-19__qcnJ4iK",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-33__RbDxBfJ",
                            "scenario-34__9MvDinW",
                            "scenario-35__yPfsk5p",
                            "scenario-37__sTLyKPf",
                            "scenario-38__bBKZZCG",
                            "scenario-4__h3XeYAx",
                            "scenario-40__y2Tvhut",
                            "scenario-5__nmf2ej9",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-8__yFNzHiK",
                            "scenario-80__wAKX3m3",
                            "scenario-81__DCJBSEF",
                            "scenario-83__vueEK2M",
                            "scenario-9__RpQu9yM",
                            "scenario-91__LkeaJb4"
                        ]
                    },
                    "submitted_entity_count": {
                        "2.0": [
                            "scenario-1__TpgjgJQ",
                            "scenario-14__zVUgWb2",
                            "scenario-17__pwnRjR4",
                            "scenario-33__RbDxBfJ",
                            "scenario-4__h3XeYAx",
                            "scenario-8__yFNzHiK",
                            "scenario-83__vueEK2M"
                        ],
                        "1.0": [
                            "scenario-102__sGSyRUJ",
                            "scenario-105__grzJGMF",
                            "scenario-11__sRodve7",
                            "scenario-12__u7mJ9Jq",
                            "scenario-13__rSgVzhX",
                            "scenario-15__S7SZXMF",
                            "scenario-16__ti4yXHL",
                            "scenario-18__A6jvPKp",
                            "scenario-19__qcnJ4iK",
                            "scenario-2__yq4K5Sc",
                            "scenario-20__oKnooZN",
                            "scenario-21__mSiXhfn",
                            "scenario-22__uqgfBGb",
                            "scenario-23__bMeSbJV",
                            "scenario-24__WcV2pbq",
                            "scenario-25__nKLfkFq",
                            "scenario-26__J7KHEAV",
                            "scenario-27__BxcDKP9",
                            "scenario-29__sNBt48p",
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M",
                            "scenario-34__9MvDinW",
                            "scenario-35__yPfsk5p",
                            "scenario-37__sTLyKPf",
                            "scenario-38__bBKZZCG",
                            "scenario-40__y2Tvhut",
                            "scenario-5__nmf2ej9",
                            "scenario-6__F7vf3fp",
                            "scenario-7__7MPdatd",
                            "scenario-80__wAKX3m3",
                            "scenario-81__DCJBSEF",
                            "scenario-9__RpQu9yM",
                            "scenario-91__LkeaJb4"
                        ]
                    },
                    "turn_count": {
                        "36.0": [
                            "scenario-1__TpgjgJQ"
                        ],
                        "19.0": [
                            "scenario-102__sGSyRUJ",
                            "scenario-40__y2Tvhut",
                            "scenario-80__wAKX3m3"
                        ],
                        "15.0": [
                            "scenario-105__grzJGMF"
                        ],
                        "16.0": [
                            "scenario-11__sRodve7",
                            "scenario-83__vueEK2M"
                        ],
                        "29.0": [
                            "scenario-12__u7mJ9Jq"
                        ],
                        "26.0": [
                            "scenario-13__rSgVzhX",
                            "scenario-38__bBKZZCG"
                        ],
                        "20.0": [
                            "scenario-14__zVUgWb2",
                            "scenario-17__pwnRjR4",
                            "scenario-18__A6jvPKp",
                            "scenario-25__nKLfkFq",
                            "scenario-91__LkeaJb4"
                        ],
                        "30.0": [
                            "scenario-15__S7SZXMF"
                        ],
                        "21.0": [
                            "scenario-16__ti4yXHL",
                            "scenario-27__BxcDKP9",
                            "scenario-35__yPfsk5p",
                            "scenario-9__RpQu9yM"
                        ],
                        "18.0": [
                            "scenario-19__qcnJ4iK",
                            "scenario-81__DCJBSEF"
                        ],
                        "22.0": [
                            "scenario-2__yq4K5Sc",
                            "scenario-22__uqgfBGb",
                            "scenario-37__sTLyKPf"
                        ],
                        "10.0": [
                            "scenario-20__oKnooZN"
                        ],
                        "17.0": [
                            "scenario-21__mSiXhfn",
                            "scenario-33__RbDxBfJ"
                        ],
                        "11.0": [
                            "scenario-23__bMeSbJV"
                        ],
                        "14.0": [
                            "scenario-24__WcV2pbq"
                        ],
                        "34.0": [
                            "scenario-26__J7KHEAV",
                            "scenario-7__7MPdatd"
                        ],
                        "25.0": [
                            "scenario-29__sNBt48p"
                        ],
                        "23.0": [
                            "scenario-3__C9b3jcd",
                            "scenario-31__mnbT25M"
                        ],
                        "35.0": [
                            "scenario-34__9MvDinW"
                        ],
                        "37.0": [
                            "scenario-4__h3XeYAx",
                            "scenario-8__yFNzHiK"
                        ],
                        "33.0": [
                            "scenario-5__nmf2ej9"
                        ],
                        "24.0": [
                            "scenario-6__F7vf3fp"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 17946155,
        "n_cache_tokens": 16216056,
        "n_output_tokens": 246809,
        "cost_usd": 8.4144281
    }
}
```