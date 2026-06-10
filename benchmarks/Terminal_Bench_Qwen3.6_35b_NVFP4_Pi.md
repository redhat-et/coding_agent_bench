# Terminal Bench Qwen3.6-35B-A3B-NVFP4 Pi

## Benchmark

**Dataset:** [harborframework/terminal-bench-2.0](https://huggingface.co/datasets/harborframework/terminal-bench-2.0) (89 tasks)   
**Model:** [RedHatAI/Qwen3.6-35B-A3B-NVFP4](https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4)  
**Harness:** Pi  
**Environment:** Docker  
**Job Name:** 2026-06-08__14-30-39  

## Results

**Score:** 36.0%  
**Errors (Initial Run):** 14   
**Total Time:** 01h 59m 55s  
**Agent Time:** 01h 23m 19s  
**Estimated Cost:** $11.11 ($4 / GPU / hr * 2 GPU * 01h 23m 19s)  

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

export PI_MODELS_JSON='{ "providers": { "vllm": { "baseUrl": "<server-url>", "api": "openai-completions", "apiKey": "NONE", "models": [{ "id": "qwen3.6-35b", "name": "qwen3.6-35b", "contextWindow": 262000 }] } } }'

echo $PI_MODELS_JSON > models.json

harbor run --agent pi -d $DATASET \
    -m vllm/$MODEL_NAME \
    --ae PI_OFFLINE=1 \
    --ae PI_CODING_AGENT_DIR=/root/.pi/agent \
    --mounts-json '[ { "type": "bind", "source":"/path/to/models.json", "target": "/root/.pi/agent/models.json" } ]'\
    --n-concurrent 9

# Rerun once to eliminate transient errors
harbor jobs resume -p jobs/2026-06-08__14-30-39 -f AgentTimeoutError -f NonZeroAgentExitCodeError
```

**`config.json`:**

```json
{
    "job_name": "2026-06-08__14-30-39",
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
            "RewardFileEmptyError",
            "AgentTimeoutError",
            "VerifierOutputParseError",
            "VerifierTimeoutError",
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
        "mounts": [
            {
                "type": "bind",
                "source": "/path/to/models.json",
                "target": "/root/.pi/agent/models.json"
            }
        ],
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
            "name": "pi",
            "import_path": null,
            "model_name": "vllm/qwen3.6-35b",
            "skills": [],
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "extra_allowed_hosts": [],
            "kwargs": {},
            "env": {
                "PI_OFFLINE": "1",
                "PI_CODING_AGENT_DIR": "/root/.pi/agent"
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

## `result.json`

```json
{
    "id": "afefdf57-4d0c-49ad-9c0d-88153e183627",
    "started_at": "2026-06-08T14:30:41.877237",
    "updated_at": "2026-06-08T20:21:41.464800",
    "finished_at": "2026-06-08T20:21:41.464800",
    "n_total_trials": 89,
    "stats": {
        "n_completed_trials": 89,
        "n_errored_trials": 5,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "pi__qwen3.6-35b__terminal-bench/terminal-bench-2": {
                "n_trials": 89,
                "n_errors": 5,
                "metrics": [
                    {
                        "mean": 0.3595505617977528
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "git-leak-recovery__ZC8Ruzy",
                            "fix-code-vulnerability__yFYEGTk",
                            "mcmc-sampling-stan__yHQYEkA",
                            "multi-source-data-merger__YTCLajR",
                            "code-from-image__GqVHHPg",
                            "mailman__hhbyZvx",
                            "kv-store-grpc__n2D8cxQ",
                            "bn-fit-modify__ffYgA79",
                            "pytorch-model-cli__R6cfMNG",
                            "hf-model-inference__JNgRxKy",
                            "count-dataset-tokens__HCJJikD",
                            "constraints-scheduling__Hz9g9Gv",
                            "modernize-scientific-stack__TjY5aVV",
                            "vulnerable-secret__fQyLimc",
                            "compile-compcert__3sziLwA",
                            "cobol-modernization__ueWp3a2",
                            "financial-document-processor__fuTamyi",
                            "pypi-server__qb7vhfb",
                            "distribution-search__y26PmCr",
                            "configure-git-webserver__ZxHsc8Y",
                            "overfull-hbox__wutNGYa",
                            "merge-diff-arc-agi-task__jzLCzdf",
                            "password-recovery__M3qLcKB",
                            "log-summary-date-ranges__gYAqEnq",
                            "nginx-request-logging__d7VHGN5",
                            "prove-plus-comm__gKKzMPD",
                            "model-extraction-relu-logits__Y5zqd5P",
                            "build-cython-ext__x8ZLE2P",
                            "fix-git__99BNf2Q",
                            "crack-7z-hash__akoRx8f",
                            "large-scale-text-editing__pjRywyR",
                            "portfolio-optimization__HTL2PG7"
                        ],
                        "0.0": [
                            "qemu-alpine-ssh__45eMqkM",
                            "feal-linear-cryptanalysis__Vd9hVqf",
                            "caffe-cifar-10__UUFAhSp",
                            "sparql-university__toi2LJY",
                            "sqlite-with-gcov__ca8eBhG",
                            "make-mips-interpreter__zNE5VyB",
                            "video-processing__UvGUDgE",
                            "dna-assembly__SMXJEaV",
                            "sam-cell-seg__RTrfwkR",
                            "extract-elf__JL7tkzr",
                            "path-tracing-reverse__ZTqzTnd",
                            "winning-avg-corewars__rFVTxRs",
                            "db-wal-recovery__6tXBG5y",
                            "torch-tensor-parallelism__nycw5oy",
                            "path-tracing__5UbKLQG",
                            "install-windows-3-11__DN4QeGm",
                            "protein-assembly__tYRxXmj",
                            "custom-memory-heap-crash__y2sn9AZ",
                            "sanitize-git-repo__gsTipAv",
                            "write-compressor__3vMJ3Zf",
                            "torch-pipeline-parallelism__6a6GjWm",
                            "largest-eigenval__ogKxdGZ",
                            "openssl-selfsigned-cert__EjqFUFg",
                            "sqlite-db-truncate__72HzbMH",
                            "polyglot-rust-c__xhKh5aV",
                            "mteb-retrieve__HLLttJg",
                            "fix-ocaml-gc__RYdtuoz",
                            "mteb-leaderboard__jVWNCTV",
                            "build-pmars__eK2aMQu",
                            "reshard-c4-data__K4KRq4L",
                            "feal-differential-cryptanalysis__GMs87vx",
                            "build-pov-ray__5gzUzMU",
                            "regex-chess__6qFyZJd",
                            "polyglot-c-py__DjSebTu",
                            "headless-terminal__cZsnAzw",
                            "regex-log__xbHHJFo",
                            "adaptive-rejection-sampler__N54ZRqk",
                            "cancel-async-tasks__6gGmPfP",
                            "llm-inference-batching-scheduler__mfhzR8x",
                            "query-optimize__XUUNDj5",
                            "schemelike-metacircular-eval__P4QEYkQ",
                            "rstan-to-pystan__2zWxr2W",
                            "gcode-to-text__dEQLwJs",
                            "git-multibranch__ETgMzFe",
                            "gpt2-codegolf__eFAuzN2",
                            "raman-fitting__69xTMnc",
                            "circuit-fibsqrt__P2MeLfT",
                            "filter-js-from-html__c39VKm5",
                            "dna-insert__cAMc5ZD",
                            "break-filter-js-from-html__af7xYAp",
                            "pytorch-model-recovery__3fPEehU",
                            "chess-best-move__Xe8NneC",
                            "extract-moves-from-video__S8Vb9sq",
                            "tune-mjcf__Hke5yX3",
                            "train-fasttext__e764AmM",
                            "make-doom-for-mips__UZmUuG7",
                            "qemu-startup__caXtiWj"
                        ]
                    }
                },
                "exception_stats": {
                    "NonZeroAgentExitCodeError": [
                        "pytorch-model-recovery__3fPEehU"
                    ],
                    "AgentTimeoutError": [
                        "extract-moves-from-video__S8Vb9sq",
                        "tune-mjcf__Hke5yX3",
                        "train-fasttext__e764AmM",
                        "make-doom-for-mips__UZmUuG7"
                    ]
                }
            }
        },
        "n_input_tokens": 82108716,
        "n_cache_tokens": 0,
        "n_output_tokens": 2056390,
        "cost_usd": null
    }
}
```