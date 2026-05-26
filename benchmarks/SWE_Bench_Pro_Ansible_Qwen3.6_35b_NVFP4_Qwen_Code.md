# SWE-Bench Pro Ansible Qwen3.6-35B-A3B-NVFP4 Qwen Code

## Benchmark

**Dataset:** [swe-bench/swe-bench-verified](https://hub.harborframework.com/datasets/swe-bench/swe-bench-verified/latest) (500 tasks)  
**Model:** [RedHatAI/Qwen3.6-35B-A3B-NVFP4](https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4)  
**Harness:** Qwen Code  
**Environment:** Docker  
**Job Name:** 2026-05-26__09-51-40  

## Results

**Score:** 43.8%   
**Errors (Initial Run):** 29   
**Total Time:** 1h 20m  
**Agent Time:** 1h 10m  
**Estimated Cost:** $9.34 ($4 / GPU / hr * 2 GPU * )   

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
export BENCHMARK='scale-ai/swe-bench-pro'
export DATASET_PATTERN='*ansible*'
export MODEL_NAME='qwen3.6-35b'
export SERVER_URL='<server-url>'
export OPENAI_BASE_URL=$SERVER_URL/v1
export OPENAI_API_KEY='NONE'

harbor run --agent qwen-coder -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m $MODEL_NAME \
    --n-concurrent 8

# Rerun twice to reduce transient errors
harbor jobs resume -p jobs/<job-id> -f NonZeroAgentExitCodeError
harbor jobs resume -p jobs/<job-id> -f NonZeroAgentExitCodeError
```

**`config.json`:**

```json
{
    "job_name": "2026-05-26__09-51-40",
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
            "RewardFileNotFoundError",
            "VerifierOutputParseError",
            "RewardFileEmptyError",
            "AgentTimeoutError",
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
        "override_cpus": null,
        "override_memory_mb": null,
        "override_storage_mb": null,
        "override_gpus": null,
        "suppress_override_warnings": false,
        "mounts_json": null,
        "env": {},
        "kwargs": {}
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
            "name": "qwen-coder",
            "import_path": null,
            "model_name": "qwen3.6-35b",
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "kwargs": {},
            "env": {}
        }
    ],
    "datasets": [
        {
            "path": null,
            "name": "scale-ai/swe-bench-pro",
            "version": null,
            "ref": "sha256:88411d32ff27e53a4c1a7e29f0c2aeba180c8e5d60f221cab5ed56325f33549d",
            "registry_url": null,
            "registry_path": null,
            "overwrite": false,
            "download_dir": null,
            "task_names": [
                "*ansible*"
            ],
            "exclude_task_names": null,
            "n_tasks": null
        }
    ],
    "tasks": [],
    "artifacts": []
}
```

## `result.json`

```json
{
    "id": "e80ee6a4-0429-4845-a5c7-0e62a5eb4a78",
    "started_at": "2026-05-26T09:51:48.721557",
    "updated_at": "2026-05-26T12:21:34.037963",
    "finished_at": "2026-05-26T12:21:34.037963",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 9,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "qwen-coder__qwen3.6-35b__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 9,
                "metrics": [
                    {
                        "mean": 0.4375
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.0": [
                            "instance_ansible__ansible-be59ca__EnLMRAk",
                            "instance_ansible__ansible-eea46a__gx6xW8b",
                            "instance_ansible__ansible-d33bed__sHEqRv7",
                            "instance_ansible__ansible-cd473d__gKyM7iP",
                            "instance_ansible__ansible-deb54e__vXKJUf2",
                            "instance_ansible__ansible-949c50__A44GMpr",
                            "instance_ansible__ansible-9a21e2__R6VdLNb",
                            "instance_ansible__ansible-709484__4zXY8TW",
                            "instance_ansible__ansible-811093__LGuCPSK",
                            "instance_ansible__ansible-d2f809__PTKCDoq",
                            "instance_ansible__ansible-5e3696__tenEU7V",
                            "instance_ansible__ansible-42355d__7p9Nvrr",
                            "instance_ansible__ansible-d30fc6__dxfSrP4",
                            "instance_ansible__ansible-1bd7dc__vWsV39W",
                            "instance_ansible__ansible-39bd8b__YKu9aBK",
                            "instance_ansible__ansible-ecea15__mikCRzb",
                            "instance_ansible__ansible-34db57__JotH5Sp",
                            "instance_ansible__ansible-1c06c4__2jzM3hA",
                            "instance_ansible__ansible-bec27f__UA2WN5e",
                            "instance_ansible__ansible-6cc974__AuPQaGF",
                            "instance_ansible__ansible-502270__7ztoFek",
                            "instance_ansible__ansible-5e88cd__eR8BR8x",
                            "instance_ansible__ansible-4c5ce5__e6UVCkC",
                            "instance_ansible__ansible-bf98f0__9aCGy7a",
                            "instance_ansible__ansible-9142be__6pQoKbh",
                            "instance_ansible__ansible-564009__LPzP8SK",
                            "instance_ansible__ansible-83fb24__eKS6Afa",
                            "instance_ansible__ansible-d58e69__FKNHa58",
                            "instance_ansible__ansible-11c177__QoceCN4",
                            "instance_ansible__ansible-984216__TfGFPcq",
                            "instance_ansible__ansible-83909b__Hjiczvc",
                            "instance_ansible__ansible-106909__sJdVmYw",
                            "instance_ansible__ansible-9759e0__eJhpw2w",
                            "instance_ansible__ansible-a1569e__oB6mz4Q",
                            "instance_ansible__ansible-e64c6c__nMaRAQw",
                            "instance_ansible__ansible-8127ab__pxGuLqb",
                            "instance_ansible__ansible-b748ed__Hkk8gDu",
                            "instance_ansible__ansible-f86c58__SGobggt",
                            "instance_ansible__ansible-942424__bNnqY7t",
                            "instance_ansible__ansible-e40889__hvLzzjF",
                            "instance_ansible__ansible-de5858__6zWfwBb",
                            "instance_ansible__ansible-b8025a__JdtXyaV",
                            "instance_ansible__ansible-3889dd__dFdVKU9",
                            "instance_ansible__ansible-5d253a__9cFh6yv",
                            "instance_ansible__ansible-1b7026__pNbQzyf",
                            "instance_ansible__ansible-b6290e__VX3dmja",
                            "instance_ansible__ansible-776587__GB3tpdg",
                            "instance_ansible__ansible-c616e5__vViWRDk",
                            "instance_ansible__ansible-622a49__d9N6pUh",
                            "instance_ansible__ansible-7e1a34__WZuBV9t",
                            "instance_ansible__ansible-f02a62__xmAxMr8",
                            "instance_ansible__ansible-d72025__u8nqavE",
                            "instance_ansible__ansible-c1f2df__G2E2f4p",
                            "instance_ansible__ansible-40ade1__GdjxCzV"
                        ],
                        "1.0": [
                            "instance_ansible__ansible-d6d225__wAemXBw",
                            "instance_ansible__ansible-748f53__ncSysdt",
                            "instance_ansible__ansible-e9e600__NoMvKKQ",
                            "instance_ansible__ansible-a02e22__pa4ZHfb",
                            "instance_ansible__ansible-415e08__TEHyA9n",
                            "instance_ansible__ansible-ea04e0__nHdn5zJ",
                            "instance_ansible__ansible-5c225d__mABvEWs",
                            "instance_ansible__ansible-1ee70f__hsf2GhD",
                            "instance_ansible__ansible-d62496__FHFL9GJ",
                            "instance_ansible__ansible-f8ef34__Pq6avrC",
                            "instance_ansible__ansible-a6e671__iStafsz",
                            "instance_ansible__ansible-935528__xwS4AVd",
                            "instance_ansible__ansible-395e5e__Cz2PfmL",
                            "instance_ansible__ansible-f327e6__ZQiyJfW",
                            "instance_ansible__ansible-e22e10__7CPPMV5",
                            "instance_ansible__ansible-379058__rB6c6Fz",
                            "instance_ansible__ansible-5f4e33__3e8NUB8",
                            "instance_ansible__ansible-1a4644__MYqsVEF",
                            "instance_ansible__ansible-0ea40e__zRrfX2s",
                            "instance_ansible__ansible-185d41__dTkkwfy",
                            "instance_ansible__ansible-fb144c__bSRAG6p",
                            "instance_ansible__ansible-a26c32__eZnZa7L",
                            "instance_ansible__ansible-a20a52__oMSRnFT",
                            "instance_ansible__ansible-de01db__cxs9mKM",
                            "instance_ansible__ansible-d9f186__VSYZvoe",
                            "instance_ansible__ansible-3db08a__qmuzVnd",
                            "instance_ansible__ansible-ed6581__CnKi4fz",
                            "instance_ansible__ansible-b5e029__5j9odjz",
                            "instance_ansible__ansible-489156__LQUwuPG",
                            "instance_ansible__ansible-12734f__FmecBu9",
                            "instance_ansible__ansible-526052__oUXtoEk",
                            "instance_ansible__ansible-a7d2a4__fBEai7w",
                            "instance_ansible__ansible-b2a289__7X96hSX",
                            "instance_ansible__ansible-164881__nTesX5T",
                            "instance_ansible__ansible-be2c37__HrgvRCg",
                            "instance_ansible__ansible-0fd887__qa54Rxe",
                            "instance_ansible__ansible-e0c91a__S3Db6s8",
                            "instance_ansible__ansible-cb94c0__LXaNbuF",
                            "instance_ansible__ansible-cd9c4e__KYr88tn",
                            "instance_ansible__ansible-189fcb__buyuTEM",
                            "instance_ansible__ansible-29aea9__SFgYUuB",
                            "instance_ansible__ansible-3b823d__76rXBpn"
                        ]
                    }
                },
                "exception_stats": {
                    "NonZeroAgentExitCodeError": [
                        "instance_ansible__ansible-5d253a__9cFh6yv",
                        "instance_ansible__ansible-b6290e__VX3dmja",
                        "instance_ansible__ansible-c616e5__vViWRDk",
                        "instance_ansible__ansible-622a49__d9N6pUh",
                        "instance_ansible__ansible-7e1a34__WZuBV9t",
                        "instance_ansible__ansible-f02a62__xmAxMr8",
                        "instance_ansible__ansible-d72025__u8nqavE",
                        "instance_ansible__ansible-c1f2df__G2E2f4p",
                        "instance_ansible__ansible-40ade1__GdjxCzV"
                    ]
                }
            }
        },
        "n_input_tokens": 159198517,
        "n_cache_tokens": 0,
        "n_output_tokens": 972133,
        "cost_usd": null
    }
}
```