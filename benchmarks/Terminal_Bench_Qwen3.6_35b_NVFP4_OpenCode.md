# Terminal Bench Qwen3.6-35B-A3B-NVFP4 OpenCode

## Benchmark

**Dataset:** [harborframework/terminal-bench-2.0](https://huggingface.co/datasets/harborframework/terminal-bench-2.0) (89 tasks)  
**Model:** [RedHatAI/Qwen3.6-35B-A3B-NVFP4](https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4)  
**Harness:** OpenCode  
**Environment:** Docker  
**Job Name:** 2026-06-08__09-33-24  

## Results

**Score:** 30.3%  
**Errors (Initial Run):** 16     
**Total Time:** 01h 48m 20s  
**Agent Time:** 01h 26m 03s  
**Estimated Cost:** $11.47 ($4 / GPU / hr * 2 GPU * 01h 26m 03s)  

## vLLM Server Config

**Manifest:** [Qwen3.6_35b_NVFP4.yml](../deploy/Qwen3.6_35b_NVFP4.yml)  
**Hardware:** 2x A100 40GB  
**Model Max Len:** 262,144  
**Max Concurrency:** 9.2x  
**Generation Config (Defaults):**
- **Temperature:** 1.0
- **Top p:** 0.95
- **Top k:** 20

## Harbor Config

**Command:**

```bash
export DATASET='terminal-bench/terminal-bench-2'
export MODEL_NAME='qwen3.6-35b'

export OPENCODE_CONFIG='{"$schema":"https://opencode.ai/config.json","model":"vllm/qwen3.6-35b","provider":{"vllm":{"npm":"@ai-sdk/openai-compatible","name":"vLLM","options":{"baseURL":"<server-url>"},"models":{"qwen3.6-35b":{"name":"qwen3.6-35b","limit":{"context":196500,"output":65500}}}}}}'

harbor run --agent opencode -d $DATASET \
    -m vllm/$MODEL_NAME \
    --ae "OPENCODE_CONFIG_CONTENT=$OPENCODE_CONFIG" \
    --n-concurrent 9

# Rerun failed jobs once to eliminate transient errors
harbor jobs resume -p jobs/<job-id> -f AgentTimeoutError -f NonZeroAgentExitCodeError
```

```sh
oc login
oc project harbor

export BENCHMARK='terminal-bench/terminal-bench-2'
export DATASET_DIR='datasets'
export MODEL_NAME='qwen3.6-35b'
export SERVER_URL='http://qwen36-35b-qwen36-35b.apps.ocp-beta-test.nerc.mghpcc.org'

# Run Tau3 bench with OpenCode
coding-agent-bench --agent opencode \
    --dataset $BENCHMARK \
    --model-name $MODEL_NAME \
    --server-url $SERVER_URL \
    --environment openshift --remote \
    --n-tasks 1
```

**`config.json`:**

```json
{
    "job_name": "2026-06-08__09-33-24",
    "jobs_dir": "jobs",
    "n_attempts": 1,
    "timeout_multiplier": 1.0,
    "agent_timeout_multiplier": null,
    "verifier_timeout_multiplier": null,
    "agent_setup_timeout_multiplier": null,
    "environment_build_timeout_multiplier": null,
    "debug": false,
    "n_concurrent_trials": 9,
    "quiet": false,
    "retry": {
        "max_retries": 0,
        "include_exceptions": null,
        "exclude_exceptions": [
            "VerifierTimeoutError",
            "AgentTimeoutError",
            "VerifierOutputParseError",
            "RewardFileEmptyError",
            "RewardFileNotFoundError"
        ],
        "wait_multiplier": 1.0,
        "min_wait_sec": 1.0,
        "max_wait_sec": 60.0
    },
    "environment": {
        "type": "docker",
        "import_path": null,
        "force_build": false,
        "delete": true,
        "cpu_enforcement_policy": "auto",
        "memory_enforcement_policy": "auto",
        "override_cpus": null,
        "override_memory_mb": null,
        "override_storage_mb": null,
        "override_gpus": null,
        "override_tpu": null,
        "mounts": null,
        "extra_docker_compose": [],
        "env": {},
        "kwargs": {},
        "extra_allowed_hosts": []
    },
    "verifier": {
        "override_timeout_sec": null,
        "max_timeout_sec": null,
        "env": {},
        "disable": false
    },
    "metrics": [],
    "agents": [
        {
            "name": "opencode",
            "import_path": null,
            "model_name": "vllm/qwen3.6-35b",
            "skills": [],
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "extra_allowed_hosts": [],
            "kwargs": {},
            "env": {
                "OPENCODE_CONFIG_CONTENT": "{\"$schema\":\"https://opencode.ai/config.json\",\"model\":\"vllm/qwen3.6-35b\",\"provider\":{\"vllm\":{\"npm\":\"@ai-sdk/openai-compatible\",\"name\":\"vLLM\",\"options\":{\"baseURL\":\"<server-url>\"},\"models\":{\"qwen3.6-35b\":{\"name\":\"qwen3.6-35b\",\"limit\":{\"context\":196500,\"output\":65500}}}}}}"
            },
            "mcp_servers": []
        }
    ],
    "datasets": [
        {
            "path": null,
            "name": "terminal-bench/terminal-bench-2",
            "version": null,
            "ref": "sha256:c6fc2e2382c1dbae99b2d5ecd2f4f4a60c3c01e0d84642d69b4afd92e99d078b",
            "registry_url": null,
            "registry_path": null,
            "overwrite": false,
            "download_dir": null,
            "task_names": null,
            "exclude_task_names": null,
            "n_tasks": null
        }
    ],
    "tasks": [],
    "artifacts": [],
    "extra_instruction_paths": [],
    "plugins": []
}
```

**`result.json`**

```json
{
    "id": "f317177f-88c7-4e0f-9fe5-4d4fcd0e44b5",
    "started_at": "2026-06-08T09:33:27.505804",
    "updated_at": "2026-06-08T14:05:00.264727",
    "finished_at": "2026-06-08T14:05:00.264727",
    "n_total_trials": 89,
    "stats": {
        "n_completed_trials": 89,
        "n_errored_trials": 5,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "opencode__qwen3.6-35b__terminal-bench/terminal-bench-2": {
                "n_trials": 89,
                "n_errors": 5,
                "metrics": [
                    {
                        "mean": 0.30337078651685395
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "regex-log__z5FAtr2",
                            "pypi-server__tCQjgu5",
                            "build-cython-ext__pApcSUq",
                            "multi-source-data-merger__ouQghTF",
                            "hf-model-inference__xEuRiQQ",
                            "fix-git__kDTFo8f",
                            "build-pov-ray__5eDMaaf",
                            "fix-code-vulnerability__LboURZ8",
                            "portfolio-optimization__N86AVkw",
                            "constraints-scheduling__CrzCDwU",
                            "crack-7z-hash__ffEboqv",
                            "openssl-selfsigned-cert__umqvo7r",
                            "modernize-scientific-stack__VW6uYra",
                            "pytorch-model-recovery__HBY7J6D",
                            "extract-elf__h9BAsw2",
                            "vulnerable-secret__FiSugPh",
                            "sparql-university__DH4A3zn",
                            "merge-diff-arc-agi-task__DCn2CFs",
                            "cobol-modernization__3xgBYPr",
                            "financial-document-processor__DDw8XX2",
                            "git-leak-recovery__B5iR8LP",
                            "count-dataset-tokens__izwQWro",
                            "distribution-search__AmCdk3W",
                            "nginx-request-logging__9CccK8v",
                            "custom-memory-heap-crash__SZTDeoD",
                            "kv-store-grpc__SPYtAaU",
                            "mcmc-sampling-stan__d7tqMyT"
                        ],
                        "0.0": [
                            "query-optimize__pHSMnyi",
                            "build-pmars__KqMQvrJ",
                            "sqlite-with-gcov__epuPr7S",
                            "fix-ocaml-gc__kSpCzaT",
                            "mailman__Fonya9f",
                            "torch-pipeline-parallelism__8H97z4T",
                            "circuit-fibsqrt__hEPDLzR",
                            "rstan-to-pystan__VfwYmes",
                            "torch-tensor-parallelism__QxdhcEX",
                            "large-scale-text-editing__REpm5Hk",
                            "bn-fit-modify__sNz3nC3",
                            "overfull-hbox__tZhY7YK",
                            "git-multibranch__n4zpfZC",
                            "code-from-image__8thPsNY",
                            "mteb-retrieve__3cfSjaz",
                            "cancel-async-tasks__WWbpEpw",
                            "regex-chess__5PvHxni",
                            "mteb-leaderboard__eyGHbzF",
                            "write-compressor__5oTMzGr",
                            "prove-plus-comm__FDgHT6u",
                            "chess-best-move__V57e9hJ",
                            "protein-assembly__Zn2e6nh",
                            "winning-avg-corewars__ehg5JQT",
                            "log-summary-date-ranges__f2W2SU6",
                            "path-tracing__SzV2EG2",
                            "train-fasttext__beFCR8B",
                            "qemu-startup__DwVQz7p",
                            "pytorch-model-cli__gjNXszV",
                            "polyglot-c-py__iYf2ews",
                            "break-filter-js-from-html__SiRNhg5",
                            "sanitize-git-repo__F4tU7bC",
                            "path-tracing-reverse__6WPyZeo",
                            "sam-cell-seg__XpYj8F2",
                            "feal-differential-cryptanalysis__RN3UDVu",
                            "gcode-to-text__xVx8NLT",
                            "llm-inference-batching-scheduler__QKBhFCB",
                            "polyglot-rust-c__5LLMY9W",
                            "db-wal-recovery__uY3jevM",
                            "adaptive-rejection-sampler__qQ3dEqj",
                            "configure-git-webserver__drC8xgq",
                            "video-processing__83rny7N",
                            "schemelike-metacircular-eval__hRg8sQx",
                            "feal-linear-cryptanalysis__mJLA3P9",
                            "gpt2-codegolf__wn3dNHS",
                            "dna-assembly__WBfK63u",
                            "qemu-alpine-ssh__PoG6WJc",
                            "largest-eigenval__vpt42Ls",
                            "model-extraction-relu-logits__27Cuwwt",
                            "make-mips-interpreter__zBWZQ9F",
                            "reshard-c4-data__Wcaq3rn",
                            "headless-terminal__mcTHcmy",
                            "dna-insert__fNF9uwe",
                            "filter-js-from-html__PNy5gdU",
                            "compile-compcert__N6H6sge",
                            "caffe-cifar-10__DjKPgKt",
                            "install-windows-3-11__JNFAtSP",
                            "extract-moves-from-video__4kEJka8",
                            "tune-mjcf__gr89Nye",
                            "raman-fitting__8XjmkhS",
                            "password-recovery__bvtKoAY",
                            "sqlite-db-truncate__yGavubi",
                            "make-doom-for-mips__zSVb3ep"
                        ]
                    }
                },
                "exception_stats": {
                    "NonZeroAgentExitCodeError": [
                        "compile-compcert__N6H6sge"
                    ],
                    "AgentTimeoutError": [
                        "caffe-cifar-10__DjKPgKt",
                        "install-windows-3-11__JNFAtSP",
                        "extract-moves-from-video__4kEJka8",
                        "tune-mjcf__gr89Nye"
                    ]
                }
            }
        },
        "n_input_tokens": 47607780,
        "n_cache_tokens": 0,
        "n_output_tokens": 1657188,
        "cost_usd": null
    }
}
```