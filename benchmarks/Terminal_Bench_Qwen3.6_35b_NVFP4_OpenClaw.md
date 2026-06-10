# Terminal Bench Qwen3.6-35B-A3B-NVFP4 OpenClaw

## Benchmark

**Dataset:** [harborframework/terminal-bench-2.0](https://huggingface.co/datasets/harborframework/terminal-bench-2.0) (89 tasks)   
**Model:** [RedHatAI/Qwen3.6-35B-A3B-NVFP4](https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4)  
**Harness:** OpenClaw  
**Environment:** Docker  
**Job Name:** 2026-06-10__10-26-03  

## Results

**Score:** 20.2%  
**Errors (Initial Run):** 11   
**Total Time:** 01h 47m 33s  
**Agent Time:** 01h 13m 54s  
**Estimated Cost:** $9.86 ($4 / GPU / hr * 2 GPU * 01h 13m 54s)  

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
export BENCHMARK='terminal-bench/terminal-bench-2'
export MODEL_NAME='qwen3.6-35b'
export SERVER_URL='<server-url>'

export OPENAI_BASE_URL=$SERVER_URL/v1
export OPENAI_API_KEY='NONE'

harbor run --agent openclaw -d $BENCHMARK \
    -m openai/$MODEL_NAME \
    --agent-kwarg thinking=off \
    --n-concurrent 8
```

**`config.json`:**

```json
{
    "job_name": "2026-06-10__10-26-03",
    "jobs_dir": "jobs",
    "n_attempts": 1,
    "timeout_multiplier": 1.0,
    "agent_timeout_multiplier": null,
    "verifier_timeout_multiplier": null,
    "agent_setup_timeout_multiplier": null,
    "environment_build_timeout_multiplier": null,
    "debug": false,
    "n_concurrent_trials": 8,
    "quiet": false,
    "retry": {
        "max_retries": 0,
        "include_exceptions": null,
        "exclude_exceptions": [
            "AgentTimeoutError",
            "RewardFileNotFoundError",
            "RewardFileEmptyError",
            "VerifierOutputParseError",
            "VerifierTimeoutError"
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
            "name": "openclaw",
            "import_path": null,
            "model_name": "openai/qwen3.6-35b",
            "skills": [],
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "extra_allowed_hosts": [],
            "kwargs": {
                "thinking": "off"
            },
            "env": {},
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
    "id": "a14b9ae7-f0f3-41aa-a797-51c0cb401b8e",
    "started_at": "2026-06-10T10:26:06.273478",
    "updated_at": "2026-06-10T14:53:11.423927",
    "finished_at": "2026-06-10T14:53:11.423927",
    "n_total_trials": 89,
    "stats": {
        "n_completed_trials": 89,
        "n_errored_trials": 11,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "openclaw__qwen3.6-35b__terminal-bench/terminal-bench-2": {
                "n_trials": 89,
                "n_errors": 11,
                "metrics": [
                    {
                        "mean": 0.20224719101123595
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "headless-terminal__YazhfvH",
                            "prove-plus-comm__29jSp9R",
                            "nginx-request-logging__JMQUCic",
                            "log-summary-date-ranges__iBpgkT3",
                            "modernize-scientific-stack__fzcHp68",
                            "openssl-selfsigned-cert__agycTNd",
                            "extract-elf__UcZLwwn",
                            "vulnerable-secret__EUohDUS",
                            "multi-source-data-merger__8bEnFYE",
                            "portfolio-optimization__UeGTJHx",
                            "hf-model-inference__NGRJSaA",
                            "fix-code-vulnerability__4Qfhxvm",
                            "fix-git__Kzoudan",
                            "git-leak-recovery__wAoDHKy",
                            "constraints-scheduling__kztE6m4",
                            "build-cython-ext__HPWhPZ6",
                            "count-dataset-tokens__LZXFBJk",
                            "code-from-image__GJmFbqt"
                        ],
                        "0.0": [
                            "dna-assembly__oDJFK7x",
                            "torch-tensor-parallelism__tAgXPXr",
                            "tune-mjcf__WFuTEML",
                            "crack-7z-hash__o4Z2YFc",
                            "filter-js-from-html__EdG4nEG",
                            "cobol-modernization__KHqSR3s",
                            "overfull-hbox__MPkKqKB",
                            "chess-best-move__ggvBoqF",
                            "sqlite-db-truncate__DJQZ5zX",
                            "fix-ocaml-gc__yQMHcV4",
                            "sqlite-with-gcov__zBUPda6",
                            "configure-git-webserver__eNw2Cs9",
                            "winning-avg-corewars__X7Vrzcw",
                            "cancel-async-tasks__trbgsiK",
                            "reshard-c4-data__RCRXrTd",
                            "path-tracing__rBe7Uej",
                            "circuit-fibsqrt__EfPRV2G",
                            "sam-cell-seg__dNNRAiC",
                            "mcmc-sampling-stan__ngRofJK",
                            "break-filter-js-from-html__WMD3xrk",
                            "write-compressor__7vWrPyn",
                            "merge-diff-arc-agi-task__oKZFsHz",
                            "feal-differential-cryptanalysis__hJPaJEe",
                            "pytorch-model-recovery__s2PSM9W",
                            "sparql-university__trf3U2x",
                            "password-recovery__PqWofyq",
                            "make-doom-for-mips__TX7ZnrQ",
                            "build-pov-ray__bjX6VCx",
                            "mailman__dUe42At",
                            "mteb-retrieve__GvNuax7",
                            "path-tracing-reverse__SSL6aVY",
                            "schemelike-metacircular-eval__wGANK82",
                            "polyglot-c-py__7g8CGUE",
                            "extract-moves-from-video__efPTUbr",
                            "compile-compcert__peovBfK",
                            "large-scale-text-editing__eLXqorn",
                            "largest-eigenval__8yw8UQm",
                            "query-optimize__pKc78Vw",
                            "sanitize-git-repo__gxWwYEY",
                            "video-processing__6S9gBbh",
                            "mteb-leaderboard__sXhQsCZ",
                            "db-wal-recovery__iQryVPN",
                            "gcode-to-text__z46BXJb",
                            "llm-inference-batching-scheduler__ZFsb53q",
                            "build-pmars__MoDgvE6",
                            "custom-memory-heap-crash__M357xAz",
                            "protein-assembly__iMKFZge",
                            "polyglot-rust-c__jMwmW6w",
                            "git-multibranch__imJmdWi",
                            "make-mips-interpreter__W98SCGp",
                            "distribution-search__BhvqsYi",
                            "caffe-cifar-10__oTRLxYM",
                            "install-windows-3-11__xRVFSGe",
                            "feal-linear-cryptanalysis__7rWcFPy",
                            "dna-insert__Mv3gX6T",
                            "rstan-to-pystan__Bk4dEfp",
                            "regex-chess__hxSbi65",
                            "kv-store-grpc__898cPer",
                            "qemu-alpine-ssh__qSdre6A",
                            "regex-log__f3RmbqR",
                            "train-fasttext__3dLJJ6o",
                            "torch-pipeline-parallelism__EENXpsV",
                            "raman-fitting__ZYABx9V",
                            "pypi-server__c5AsoML",
                            "model-extraction-relu-logits__DzQYqkT",
                            "pytorch-model-cli__Wig8r8C",
                            "bn-fit-modify__GWxqVUL",
                            "adaptive-rejection-sampler__MSVNWpz",
                            "gpt2-codegolf__owJnyEt",
                            "financial-document-processor__d67hS8T",
                            "qemu-startup__G95ayHC"
                        ]
                    }
                },
                "exception_stats": {
                    "NonZeroAgentExitCodeError": [
                        "make-mips-interpreter__W98SCGp",
                        "distribution-search__BhvqsYi",
                        "feal-linear-cryptanalysis__7rWcFPy",
                        "dna-insert__Mv3gX6T",
                        "raman-fitting__ZYABx9V",
                        "pytorch-model-cli__Wig8r8C",
                        "adaptive-rejection-sampler__MSVNWpz"
                    ],
                    "AgentTimeoutError": [
                        "caffe-cifar-10__oTRLxYM",
                        "install-windows-3-11__xRVFSGe",
                        "kv-store-grpc__898cPer",
                        "train-fasttext__3dLJJ6o"
                    ]
                }
            }
        },
        "n_input_tokens": 0,
        "n_cache_tokens": 0,
        "n_output_tokens": 0,
        "cost_usd": null
    }
}
```