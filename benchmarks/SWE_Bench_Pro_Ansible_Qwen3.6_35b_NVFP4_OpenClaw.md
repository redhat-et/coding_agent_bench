# SWE-Bench Pro Ansible Qwen3.6-35B-A3B-NVFP4 OpenClaw

## Benchmark

**Dataset:** [swe-bench-pro--ansible](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) (96 tasks, ansible only) 
**Model:** [RedHatAI/Qwen3.6-35B-A3B-NVFP4](https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4)  
**Harness:** OpenClaw  
**Environment:** Docker  
**Job Name:** 2026-06-01__10-32-15  

## Results

**Score:** 40.6%  
**Errors (Initial Run):** 23     
**Total Time:** 01h 34m 02s  
**Agent Time:** 01h 10m 31s  
**Estimated Cost:** $9.4 ($4 / GPU / hr * 2 GPU * 01h 10m 31s) 

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
export SERVER_URL='http://qwen36-35b-qwen36-35b.apps.ocp-beta-test.nerc.mghpcc.org'
export OPENAI_BASE_URL=$SERVER_URL/v1
export OPENAI_API_KEY='NONE'

harbor run --agent openclaw -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m openai/$MODEL_NAME \
    --agent-kwarg thinking=off \
    --n-concurrent 9

# Rerun twice to eliminate transient issues with LLM
harbor jobs resume -p jobs/2026-06-01__10-32-15 -f NonZeroAgentExitCodeError -f RuntimeError
harbor jobs resume -p jobs/2026-06-01__10-32-15 -f NonZeroAgentExitCodeError -f RuntimeError
``` 

**`config.json`:**

```json
{
    "job_name": "2026-06-01__10-32-15",
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
            "AgentTimeoutError",
            "VerifierOutputParseError",
            "RewardFileEmptyError",
            "RewardFileNotFoundError",
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
    "artifacts": [],
    "extra_instruction_paths": []
}
```

## `result.json`

```json
{
    "id": "8b7c2223-d7dd-40f0-a639-313349450d65",
    "started_at": "2026-06-01T10:32:18.899562",
    "updated_at": "2026-06-01T15:21:20.134125",
    "finished_at": "2026-06-01T15:21:20.134125",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 5,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "openclaw__qwen3.6-35b__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 5,
                "metrics": [
                    {
                        "mean": 0.40625
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "instance_ansible__ansible-d2f809__G4qYShN",
                            "instance_ansible__ansible-f8ef34__3qtEMb7",
                            "instance_ansible__ansible-ed6581__929Ky2r",
                            "instance_ansible__ansible-a7d2a4__b9NDtPa",
                            "instance_ansible__ansible-be59ca__NsEdc3x",
                            "instance_ansible__ansible-3b823d__kdMFegq",
                            "instance_ansible__ansible-12734f__zaLkv6t",
                            "instance_ansible__ansible-a6e671__WDPc9Cf",
                            "instance_ansible__ansible-526052__AaDtrAp",
                            "instance_ansible__ansible-5c225d__Mswtjwu",
                            "instance_ansible__ansible-cd9c4e__8AvpJ8V",
                            "instance_ansible__ansible-935528__QS9epqL",
                            "instance_ansible__ansible-3db08a__wpAT4v2",
                            "instance_ansible__ansible-8127ab__vTXHYXE",
                            "instance_ansible__ansible-a02e22__c86b8zV",
                            "instance_ansible__ansible-fb144c__vQDb7bP",
                            "instance_ansible__ansible-29aea9__wcMGrat",
                            "instance_ansible__ansible-489156__SkD3rZG",
                            "instance_ansible__ansible-d9f186__PmKWeya",
                            "instance_ansible__ansible-0ea40e__qpCVJgc",
                            "instance_ansible__ansible-189fcb__HGBtB4j",
                            "instance_ansible__ansible-415e08__Mqouv7C",
                            "instance_ansible__ansible-b8025a__tAuRGoy",
                            "instance_ansible__ansible-d6d225__D5hbFVM",
                            "instance_ansible__ansible-748f53__reMnqVw",
                            "instance_ansible__ansible-ea04e0__SWYeTyE",
                            "instance_ansible__ansible-be2c37__iq9Vzgj",
                            "instance_ansible__ansible-b2a289__fBvew5v",
                            "instance_ansible__ansible-984216__Nhu6YMP",
                            "instance_ansible__ansible-e0c91a__tqN4yis",
                            "instance_ansible__ansible-a20a52__8ccWSBa",
                            "instance_ansible__ansible-379058__M6VkPmr",
                            "instance_ansible__ansible-cb94c0__npmhAXw",
                            "instance_ansible__ansible-f327e6__VXWCvYt",
                            "instance_ansible__ansible-9142be__hNSQxcD",
                            "instance_ansible__ansible-1ee70f__92pt4AJ",
                            "instance_ansible__ansible-a26c32__AV8JGER",
                            "instance_ansible__ansible-185d41__uaQzcxC",
                            "instance_ansible__ansible-395e5e__cqKfWTb"
                        ],
                        "0.0": [
                            "instance_ansible__ansible-942424__eYpnQsP",
                            "instance_ansible__ansible-b748ed__BeVA4D7",
                            "instance_ansible__ansible-622a49__tAXjjTJ",
                            "instance_ansible__ansible-5d253a__wy3uMxz",
                            "instance_ansible__ansible-6cc974__PaXsoY6",
                            "instance_ansible__ansible-9a21e2__CWj5eFa",
                            "instance_ansible__ansible-cd473d__QanNHyj",
                            "instance_ansible__ansible-a1569e__c2L2wmn",
                            "instance_ansible__ansible-1b7026__qy5f25G",
                            "instance_ansible__ansible-709484__uELUtxe",
                            "instance_ansible__ansible-bf98f0__Ag2QcLc",
                            "instance_ansible__ansible-e40889__yEf9PDu",
                            "instance_ansible__ansible-949c50__zEXDfLm",
                            "instance_ansible__ansible-0fd887__r2uGLmZ",
                            "instance_ansible__ansible-d62496__LeCoVnY",
                            "instance_ansible__ansible-deb54e__zb55HZr",
                            "instance_ansible__ansible-d30fc6__JauvnvX",
                            "instance_ansible__ansible-1a4644__urrU7qA",
                            "instance_ansible__ansible-502270__6ZEvVbn",
                            "instance_ansible__ansible-ecea15__DXaWkps",
                            "instance_ansible__ansible-40ade1__5eErWDd",
                            "instance_ansible__ansible-e22e10__hQe8Hqy",
                            "instance_ansible__ansible-c1f2df__hT2coAc",
                            "instance_ansible__ansible-11c177__fPhZiy5",
                            "instance_ansible__ansible-9759e0__YK3t2jZ",
                            "instance_ansible__ansible-f86c58__NCrtTu4",
                            "instance_ansible__ansible-3889dd__A4H8JuT",
                            "instance_ansible__ansible-5e3696__mR73qLU",
                            "instance_ansible__ansible-eea46a__QxMbywo",
                            "instance_ansible__ansible-83fb24__D8at8j4",
                            "instance_ansible__ansible-83909b__RF2ATPR",
                            "instance_ansible__ansible-4c5ce5__Zmc9TbP",
                            "instance_ansible__ansible-de01db__WfbSy7J",
                            "instance_ansible__ansible-e64c6c__dK2wMj2",
                            "instance_ansible__ansible-de5858__aTSLTDa",
                            "instance_ansible__ansible-5e88cd__8pTJSNR",
                            "instance_ansible__ansible-d58e69__ANFKjCa",
                            "instance_ansible__ansible-bec27f__Ck8dJLC",
                            "instance_ansible__ansible-164881__JnijTps",
                            "instance_ansible__ansible-776587__A3fkLrY",
                            "instance_ansible__ansible-e9e600__zA7oaia",
                            "instance_ansible__ansible-39bd8b__2Jako4k",
                            "instance_ansible__ansible-34db57__HGYhp9G",
                            "instance_ansible__ansible-811093__bur7KJC",
                            "instance_ansible__ansible-1c06c4__LqTNW3j",
                            "instance_ansible__ansible-5f4e33__peRymQY",
                            "instance_ansible__ansible-b5e029__XXWvq7B",
                            "instance_ansible__ansible-42355d__WbwFCXD",
                            "instance_ansible__ansible-b6290e__2qoKQCK",
                            "instance_ansible__ansible-d33bed__qvoDfPJ",
                            "instance_ansible__ansible-c616e5__9m3Hff7",
                            "instance_ansible__ansible-106909__RnMqzS7",
                            "instance_ansible__ansible-564009__GLqBgaS",
                            "instance_ansible__ansible-7e1a34__FwGgYdb",
                            "instance_ansible__ansible-f02a62__pToCw65",
                            "instance_ansible__ansible-1bd7dc__krBKcvE",
                            "instance_ansible__ansible-d72025__mxPmiJz"
                        ]
                    }
                },
                "exception_stats": {
                    "NonZeroAgentExitCodeError": [
                        "instance_ansible__ansible-b6290e__2qoKQCK",
                        "instance_ansible__ansible-d33bed__qvoDfPJ",
                        "instance_ansible__ansible-7e1a34__FwGgYdb",
                        "instance_ansible__ansible-f02a62__pToCw65",
                        "instance_ansible__ansible-d72025__mxPmiJz"
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