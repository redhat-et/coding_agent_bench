# ITBench-AA Claude Haiku 4.5 Claude Code

## Benchmark

**Run Date:** 2026-10-05T11:10:26.137568Z  
**Dataset:** [datasets/itbench-aa](https://hub.harborframework.com/datasets/datasets/itbench-aa/latest) (40 tasks)  
**Model:** claude-haiku-4-5-20251001  
**Harness:** claude-code  
**Environment:** openshift  
**Job Name:** it_bench_aa/claude_haiku_4_5_os_high  

## Results

**Score:** 18.1% (6 Full Reward / 3 Partial Reward / 31 Zero Reward / 0 Errors)   
**Error Rate:** 0.0% ()  
**Total Time:** 00h 58m 23s  
**Agent Time:** 00h 42m 51s (00h 04m 17s avg per task)  
**Estimated Cost:** $18.44  ($0.46 avg per task)  
**Input Tokens:** 105433712 (2635842 avg per task)  
**Output Tokens:** 1004356 (25108 avg per task)  
**Cache Hit Rate:** 97.6%

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
    --model claude-haiku-4-5-20251001 \
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
    --job-name it_bench_aa/claude_haiku_4_5_os_high \
    --debug
```

**`config.json`:**

```json
{
    "job_name": "it_bench_aa/claude_haiku_4_5_os_high",
    "n_concurrent_trials": 4,
    "agent_timeout_multiplier": 3.0,
    "debug": true,
    "retry": {
        "max_retries": 1,
        "include_exceptions": [
            "ApiUsageLimitError",
            "ApiRateLimitError",
            "AgentTimeoutError",
            "UnknownApiError",
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
            "model_name": "claude-haiku-4-5-20251001",
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
    "id": "44ce5b09-04c3-4ffe-88a9-9568df526f0b",
    "started_at": "2026-10-05T12:10:01.004781",
    "updated_at": "2026-10-05T14:21:10.186264",
    "finished_at": "2026-10-05T14:21:10.186264",
    "n_total_trials": 40,
    "stats": {
        "n_completed_trials": 40,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 1,
        "evals": {
            "claude-code__claude-haiku-4-5-20251001__itbench-aa": {
                "n_trials": 40,
                "n_errors": 0,
                "metrics": [
                    {
                        "answer_format_valid": 1.0,
                        "answer_recovered_from_transcript": 0.0,
                        "entity_count_expected": 1.0,
                        "kind_match": 0.1,
                        "name_match": 0.475,
                        "namespace_applicable": 0.975,
                        "namespace_match": 0.425,
                        "reasoning_present": 0.625,
                        "reward": 0.18125,
                        "submitted_entity_count": 1.85,
                        "turn_count": 96.35
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-13__7ai4sTB",
                            "scenario-14__vMKJX7F",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-19__omTznHW",
                            "scenario-2__hnR8v3H",
                            "scenario-21__tkAqzpQ",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-31__LDLViYt",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-38__bzC4USR",
                            "scenario-4__KzdPmA4",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-8__dnMcm5p",
                            "scenario-80__dfPmbuz",
                            "scenario-81__zaSfMg8",
                            "scenario-9__kdcyx4g",
                            "scenario-102__mmDazwS",
                            "scenario-11__KVDjRv9"
                        ],
                        "1.0": [
                            "scenario-18__oVQYi4T",
                            "scenario-20__2p7kENu",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-40__ChuyGUt",
                            "scenario-91__NE5LYFP"
                        ],
                        "0.25": [
                            "scenario-33__aRMtpnj"
                        ],
                        "0.5": [
                            "scenario-83__eJCaqdg",
                            "scenario-1__Pre79WX"
                        ]
                    },
                    "answer_format_valid": {
                        "1.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-13__7ai4sTB",
                            "scenario-14__vMKJX7F",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-18__oVQYi4T",
                            "scenario-19__omTznHW",
                            "scenario-2__hnR8v3H",
                            "scenario-20__2p7kENu",
                            "scenario-21__tkAqzpQ",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-31__LDLViYt",
                            "scenario-33__aRMtpnj",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-38__bzC4USR",
                            "scenario-4__KzdPmA4",
                            "scenario-40__ChuyGUt",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-8__dnMcm5p",
                            "scenario-80__dfPmbuz",
                            "scenario-81__zaSfMg8",
                            "scenario-83__eJCaqdg",
                            "scenario-9__kdcyx4g",
                            "scenario-91__NE5LYFP",
                            "scenario-1__Pre79WX",
                            "scenario-102__mmDazwS",
                            "scenario-11__KVDjRv9"
                        ]
                    },
                    "answer_recovered_from_transcript": {
                        "0.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-13__7ai4sTB",
                            "scenario-14__vMKJX7F",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-18__oVQYi4T",
                            "scenario-19__omTznHW",
                            "scenario-2__hnR8v3H",
                            "scenario-20__2p7kENu",
                            "scenario-21__tkAqzpQ",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-31__LDLViYt",
                            "scenario-33__aRMtpnj",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-38__bzC4USR",
                            "scenario-4__KzdPmA4",
                            "scenario-40__ChuyGUt",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-8__dnMcm5p",
                            "scenario-80__dfPmbuz",
                            "scenario-81__zaSfMg8",
                            "scenario-83__eJCaqdg",
                            "scenario-9__kdcyx4g",
                            "scenario-91__NE5LYFP",
                            "scenario-1__Pre79WX",
                            "scenario-102__mmDazwS",
                            "scenario-11__KVDjRv9"
                        ]
                    },
                    "name_match": {
                        "0.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-13__7ai4sTB",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-19__omTznHW",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-8__dnMcm5p",
                            "scenario-81__zaSfMg8",
                            "scenario-9__kdcyx4g",
                            "scenario-102__mmDazwS"
                        ],
                        "1.0": [
                            "scenario-14__vMKJX7F",
                            "scenario-18__oVQYi4T",
                            "scenario-2__hnR8v3H",
                            "scenario-20__2p7kENu",
                            "scenario-21__tkAqzpQ",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-31__LDLViYt",
                            "scenario-33__aRMtpnj",
                            "scenario-38__bzC4USR",
                            "scenario-4__KzdPmA4",
                            "scenario-40__ChuyGUt",
                            "scenario-80__dfPmbuz",
                            "scenario-83__eJCaqdg",
                            "scenario-91__NE5LYFP",
                            "scenario-1__Pre79WX",
                            "scenario-11__KVDjRv9"
                        ]
                    },
                    "kind_match": {
                        "0.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-13__7ai4sTB",
                            "scenario-14__vMKJX7F",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-18__oVQYi4T",
                            "scenario-19__omTznHW",
                            "scenario-2__hnR8v3H",
                            "scenario-21__tkAqzpQ",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-31__LDLViYt",
                            "scenario-33__aRMtpnj",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-38__bzC4USR",
                            "scenario-4__KzdPmA4",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-8__dnMcm5p",
                            "scenario-80__dfPmbuz",
                            "scenario-81__zaSfMg8",
                            "scenario-83__eJCaqdg",
                            "scenario-9__kdcyx4g",
                            "scenario-91__NE5LYFP",
                            "scenario-1__Pre79WX",
                            "scenario-102__mmDazwS",
                            "scenario-11__KVDjRv9"
                        ],
                        "1.0": [
                            "scenario-20__2p7kENu",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-40__ChuyGUt"
                        ]
                    },
                    "namespace_match": {
                        "0.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-13__7ai4sTB",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-19__omTznHW",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-38__bzC4USR",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-8__dnMcm5p",
                            "scenario-80__dfPmbuz",
                            "scenario-81__zaSfMg8",
                            "scenario-9__kdcyx4g",
                            "scenario-102__mmDazwS"
                        ],
                        "1.0": [
                            "scenario-14__vMKJX7F",
                            "scenario-18__oVQYi4T",
                            "scenario-2__hnR8v3H",
                            "scenario-20__2p7kENu",
                            "scenario-21__tkAqzpQ",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-31__LDLViYt",
                            "scenario-33__aRMtpnj",
                            "scenario-4__KzdPmA4",
                            "scenario-40__ChuyGUt",
                            "scenario-83__eJCaqdg",
                            "scenario-91__NE5LYFP",
                            "scenario-1__Pre79WX",
                            "scenario-11__KVDjRv9"
                        ]
                    },
                    "namespace_applicable": {
                        "1.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-13__7ai4sTB",
                            "scenario-14__vMKJX7F",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-18__oVQYi4T",
                            "scenario-19__omTznHW",
                            "scenario-2__hnR8v3H",
                            "scenario-20__2p7kENu",
                            "scenario-21__tkAqzpQ",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-31__LDLViYt",
                            "scenario-33__aRMtpnj",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-38__bzC4USR",
                            "scenario-4__KzdPmA4",
                            "scenario-40__ChuyGUt",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-8__dnMcm5p",
                            "scenario-80__dfPmbuz",
                            "scenario-81__zaSfMg8",
                            "scenario-83__eJCaqdg",
                            "scenario-9__kdcyx4g",
                            "scenario-91__NE5LYFP",
                            "scenario-1__Pre79WX",
                            "scenario-11__KVDjRv9"
                        ],
                        "0.0": [
                            "scenario-102__mmDazwS"
                        ]
                    },
                    "reasoning_present": {
                        "0.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-19__omTznHW",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-81__zaSfMg8",
                            "scenario-102__mmDazwS"
                        ],
                        "1.0": [
                            "scenario-13__7ai4sTB",
                            "scenario-14__vMKJX7F",
                            "scenario-17__jhADgsU",
                            "scenario-18__oVQYi4T",
                            "scenario-2__hnR8v3H",
                            "scenario-20__2p7kENu",
                            "scenario-21__tkAqzpQ",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-31__LDLViYt",
                            "scenario-33__aRMtpnj",
                            "scenario-38__bzC4USR",
                            "scenario-4__KzdPmA4",
                            "scenario-40__ChuyGUt",
                            "scenario-8__dnMcm5p",
                            "scenario-80__dfPmbuz",
                            "scenario-83__eJCaqdg",
                            "scenario-9__kdcyx4g",
                            "scenario-91__NE5LYFP",
                            "scenario-1__Pre79WX",
                            "scenario-11__KVDjRv9"
                        ]
                    },
                    "entity_count_expected": {
                        "1.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-13__7ai4sTB",
                            "scenario-14__vMKJX7F",
                            "scenario-15__pYD7W3F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-18__oVQYi4T",
                            "scenario-19__omTznHW",
                            "scenario-2__hnR8v3H",
                            "scenario-20__2p7kENu",
                            "scenario-21__tkAqzpQ",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-26__iacAGuP",
                            "scenario-27__RvWSVz6",
                            "scenario-29__kGrEY6A",
                            "scenario-3__VRY4CSW",
                            "scenario-31__LDLViYt",
                            "scenario-33__aRMtpnj",
                            "scenario-34__yXCjPGY",
                            "scenario-35__YGUGdAQ",
                            "scenario-37__Fv4W3Ne",
                            "scenario-38__bzC4USR",
                            "scenario-4__KzdPmA4",
                            "scenario-40__ChuyGUt",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-7__vjZJbFM",
                            "scenario-8__dnMcm5p",
                            "scenario-80__dfPmbuz",
                            "scenario-81__zaSfMg8",
                            "scenario-83__eJCaqdg",
                            "scenario-9__kdcyx4g",
                            "scenario-91__NE5LYFP",
                            "scenario-1__Pre79WX",
                            "scenario-102__mmDazwS",
                            "scenario-11__KVDjRv9"
                        ]
                    },
                    "submitted_entity_count": {
                        "2.0": [
                            "scenario-105__QpNYnmD",
                            "scenario-12__wqiW6h7",
                            "scenario-15__pYD7W3F",
                            "scenario-2__hnR8v3H",
                            "scenario-24__68ngGgq",
                            "scenario-25__UFibTz8",
                            "scenario-26__iacAGuP",
                            "scenario-3__VRY4CSW",
                            "scenario-31__LDLViYt",
                            "scenario-38__bzC4USR",
                            "scenario-5__DWTxZCZ",
                            "scenario-6__ELXSPia",
                            "scenario-8__dnMcm5p",
                            "scenario-81__zaSfMg8",
                            "scenario-83__eJCaqdg",
                            "scenario-1__Pre79WX"
                        ],
                        "1.0": [
                            "scenario-13__7ai4sTB",
                            "scenario-18__oVQYi4T",
                            "scenario-19__omTznHW",
                            "scenario-20__2p7kENu",
                            "scenario-21__tkAqzpQ",
                            "scenario-22__Aq9cSrF",
                            "scenario-23__oXRqMgH",
                            "scenario-29__kGrEY6A",
                            "scenario-34__yXCjPGY",
                            "scenario-37__Fv4W3Ne",
                            "scenario-40__ChuyGUt",
                            "scenario-7__vjZJbFM",
                            "scenario-80__dfPmbuz",
                            "scenario-91__NE5LYFP",
                            "scenario-102__mmDazwS",
                            "scenario-11__KVDjRv9"
                        ],
                        "3.0": [
                            "scenario-14__vMKJX7F",
                            "scenario-16__MEu5spF",
                            "scenario-17__jhADgsU",
                            "scenario-27__RvWSVz6",
                            "scenario-35__YGUGdAQ",
                            "scenario-9__kdcyx4g"
                        ],
                        "4.0": [
                            "scenario-33__aRMtpnj",
                            "scenario-4__KzdPmA4"
                        ]
                    },
                    "turn_count": {
                        "78.0": [
                            "scenario-105__QpNYnmD"
                        ],
                        "106.0": [
                            "scenario-12__wqiW6h7"
                        ],
                        "86.0": [
                            "scenario-13__7ai4sTB",
                            "scenario-16__MEu5spF",
                            "scenario-35__YGUGdAQ"
                        ],
                        "92.0": [
                            "scenario-14__vMKJX7F",
                            "scenario-3__VRY4CSW",
                            "scenario-38__bzC4USR"
                        ],
                        "102.0": [
                            "scenario-15__pYD7W3F",
                            "scenario-25__UFibTz8",
                            "scenario-7__vjZJbFM"
                        ],
                        "79.0": [
                            "scenario-17__jhADgsU"
                        ],
                        "87.0": [
                            "scenario-18__oVQYi4T",
                            "scenario-33__aRMtpnj"
                        ],
                        "112.0": [
                            "scenario-19__omTznHW",
                            "scenario-9__kdcyx4g"
                        ],
                        "111.0": [
                            "scenario-2__hnR8v3H"
                        ],
                        "69.0": [
                            "scenario-20__2p7kENu"
                        ],
                        "113.0": [
                            "scenario-21__tkAqzpQ"
                        ],
                        "100.0": [
                            "scenario-22__Aq9cSrF",
                            "scenario-5__DWTxZCZ"
                        ],
                        "128.0": [
                            "scenario-23__oXRqMgH"
                        ],
                        "84.0": [
                            "scenario-24__68ngGgq"
                        ],
                        "161.0": [
                            "scenario-26__iacAGuP"
                        ],
                        "129.0": [
                            "scenario-27__RvWSVz6"
                        ],
                        "90.0": [
                            "scenario-29__kGrEY6A"
                        ],
                        "67.0": [
                            "scenario-31__LDLViYt"
                        ],
                        "68.0": [
                            "scenario-34__yXCjPGY",
                            "scenario-8__dnMcm5p"
                        ],
                        "149.0": [
                            "scenario-37__Fv4W3Ne"
                        ],
                        "118.0": [
                            "scenario-4__KzdPmA4"
                        ],
                        "124.0": [
                            "scenario-40__ChuyGUt"
                        ],
                        "94.0": [
                            "scenario-6__ELXSPia",
                            "scenario-102__mmDazwS"
                        ],
                        "63.0": [
                            "scenario-80__dfPmbuz"
                        ],
                        "108.0": [
                            "scenario-81__zaSfMg8"
                        ],
                        "115.0": [
                            "scenario-83__eJCaqdg"
                        ],
                        "52.0": [
                            "scenario-91__NE5LYFP"
                        ],
                        "71.0": [
                            "scenario-1__Pre79WX"
                        ],
                        "77.0": [
                            "scenario-11__KVDjRv9"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 105433712,
        "n_cache_tokens": 102933620,
        "n_output_tokens": 1004356,
        "cost_usd": 18.436671000000004
    }
}
```
