# SWE Bench Pro Ansible GPT 5.5 OpenCode

## Benchmark

**Dataset:** [scale-ai/swe-bench-pro](https://hub.harborframework.com/datasets/scale-ai/swe-bench-pro/latest) (96 tasks)  
**Model:** openai/gpt-5.5  
**Harness:** opencode  
**Environment:** docker  
**Job Name:** 2026-06-30__10-09-20  

## Results

**Score:** 57.3%    
**Errors (Initial Run):** 3  
**Total Time:** 00h 40m 03s  
**Agent Time:** 00h 29m 42s  
**Estimated Cost:** $111.64 

## Harbor Config

**Command:**

Note: `opencode>1.17.0` introduced an issue with `--json` mode causing it to never exit after conversation stop is reached. So we use `1.16.2` instead.

Related issue: [https://github.com/anomalyco/opencode/issues/32506](https://github.com/anomalyco/opencode/issues/32506)

```bash
set -a
source .env

export BENCHMARK='scale-ai/swe-bench-pro'
export DATASET_PATTERN='*ansible*'

harbor run --agent opencode -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m openai/gpt-5.5 \
    --agent-kwarg version=1.16.2 \
    --n-concurrent 16

# Rerun to eliminate transient errors
harbor jobs resume -p jobs/2026-06-30__10-09-20 -f AgentTimeoutError
```

**`config.json`:**

```json
{
    "job_name": "2026-06-30__10-09-20",
    "jobs_dir": "jobs",
    "n_attempts": 1,
    "timeout_multiplier": 1.0,
    "agent_timeout_multiplier": null,
    "verifier_timeout_multiplier": null,
    "agent_setup_timeout_multiplier": null,
    "environment_build_timeout_multiplier": null,
    "debug": false,
    "n_concurrent_trials": 16,
    "quiet": false,
    "retry": {
        "max_retries": 0,
        "include_exceptions": null,
        "exclude_exceptions": [
            "RewardFileEmptyError",
            "AgentTimeoutError",
            "VerifierOutputParseError",
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
            "name": "opencode",
            "import_path": null,
            "model_name": "openai/gpt-5.5",
            "skills": [],
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "extra_allowed_hosts": [],
            "kwargs": {
                "version": "1.16.2"
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
    "extra_instruction_paths": [],
    "plugins": []
}
```

## `result.json`

```json
{
    "id": "9e590f34-3b1d-42e4-99cc-0ebf915c8bfc",
    "started_at": "2026-06-30T10:09:22.248359",
    "updated_at": "2026-06-30T11:59:03.500788",
    "finished_at": "2026-06-30T11:59:03.500788",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "opencode__gpt-5.5__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 0,
                "metrics": [
                    {
                        "mean": 0.5729166666666666
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.0": [
                            "instance_ansible__ansible-d58e69__dFNa9V3",
                            "instance_ansible__ansible-1c06c4__jbeoziJ",
                            "instance_ansible__ansible-811093__vkhmu9b",
                            "instance_ansible__ansible-c616e5__3MoRzPr",
                            "instance_ansible__ansible-d33bed__bA6cnmh",
                            "instance_ansible__ansible-34db57__myocgim",
                            "instance_ansible__ansible-bf98f0__2oJqbyk",
                            "instance_ansible__ansible-39bd8b__xFRtbwa",
                            "instance_ansible__ansible-be59ca__VwVSr2k",
                            "instance_ansible__ansible-b748ed__4k3NbgC",
                            "instance_ansible__ansible-ecea15__wJ6pBb9",
                            "instance_ansible__ansible-564009__LygV5ap",
                            "instance_ansible__ansible-1bd7dc__diWU9cf",
                            "instance_ansible__ansible-e40889__zZUrzs5",
                            "instance_ansible__ansible-3889dd__FRyz6vf",
                            "instance_ansible__ansible-f02a62__Ce8VWQR",
                            "instance_ansible__ansible-0fd887__bCLJx66",
                            "instance_ansible__ansible-eea46a__a39amWe",
                            "instance_ansible__ansible-9142be__Tsv5WKC",
                            "instance_ansible__ansible-5e3696__YENeUuY",
                            "instance_ansible__ansible-d2f809__SVfXCTn",
                            "instance_ansible__ansible-cd9c4e__B6sQ7hX",
                            "instance_ansible__ansible-bec27f__sqV9Jor",
                            "instance_ansible__ansible-cd473d__NSqifLa",
                            "instance_ansible__ansible-de5858__FsPmbE3",
                            "instance_ansible__ansible-e64c6c__6pGXrCM",
                            "instance_ansible__ansible-9759e0__raSKWs2",
                            "instance_ansible__ansible-83fb24__5aoJxHe",
                            "instance_ansible__ansible-b6290e__qPqHf4C",
                            "instance_ansible__ansible-4c5ce5__nUCKvqs",
                            "instance_ansible__ansible-83909b__6aJSbVZ",
                            "instance_ansible__ansible-5e88cd__ZqL7rin",
                            "instance_ansible__ansible-c1f2df__f9kgFac",
                            "instance_ansible__ansible-7e1a34__HfHJuA5",
                            "instance_ansible__ansible-f86c58__MCSvJCV",
                            "instance_ansible__ansible-a26c32__vKn5L7z",
                            "instance_ansible__ansible-526052__hHXMTKu",
                            "instance_ansible__ansible-a1569e__DykUTcc",
                            "instance_ansible__ansible-d72025__faVVbxk",
                            "instance_ansible__ansible-11c177__NveT76S",
                            "instance_ansible__ansible-9a21e2__sqvLjKt"
                        ],
                        "1.0": [
                            "instance_ansible__ansible-709484__QZm6gog",
                            "instance_ansible__ansible-d6d225__EAzgacE",
                            "instance_ansible__ansible-de01db__x3dF7G2",
                            "instance_ansible__ansible-12734f__8m3gAbr",
                            "instance_ansible__ansible-776587__gQ3WMtG",
                            "instance_ansible__ansible-622a49__Y4UTWRP",
                            "instance_ansible__ansible-29aea9__HvjKhi5",
                            "instance_ansible__ansible-8127ab__ihtcU3e",
                            "instance_ansible__ansible-935528__A7M3CUY",
                            "instance_ansible__ansible-3b823d__MJWxvp7",
                            "instance_ansible__ansible-d30fc6__aMrTKTc",
                            "instance_ansible__ansible-164881__kaoek76",
                            "instance_ansible__ansible-489156__rvRVGiZ",
                            "instance_ansible__ansible-deb54e__cM2unsf",
                            "instance_ansible__ansible-a6e671__yj2mjnn",
                            "instance_ansible__ansible-1ee70f__KKPpQn3",
                            "instance_ansible__ansible-f8ef34__2QSy2wP",
                            "instance_ansible__ansible-6cc974__sErB6zW",
                            "instance_ansible__ansible-415e08__NVQANRM",
                            "instance_ansible__ansible-a7d2a4__LAcV3Ub",
                            "instance_ansible__ansible-502270__zY3dimm",
                            "instance_ansible__ansible-1b7026__xbCSfYs",
                            "instance_ansible__ansible-cb94c0__c2FWrZv",
                            "instance_ansible__ansible-a20a52__kWMRyhC",
                            "instance_ansible__ansible-5c225d__wHgjNhh",
                            "instance_ansible__ansible-3db08a__o3GnySb",
                            "instance_ansible__ansible-189fcb__mGjLcSE",
                            "instance_ansible__ansible-106909__UcKJeMV",
                            "instance_ansible__ansible-42355d__uVBn5Zh",
                            "instance_ansible__ansible-fb144c__42CNZBA",
                            "instance_ansible__ansible-e0c91a__HBKvohz",
                            "instance_ansible__ansible-984216__aJVzYxu",
                            "instance_ansible__ansible-b5e029__eC7ntHD",
                            "instance_ansible__ansible-ed6581__iGd3nLt",
                            "instance_ansible__ansible-b2a289__GKA62Tx",
                            "instance_ansible__ansible-f327e6__bTTUJBQ",
                            "instance_ansible__ansible-395e5e__ZKg4Lsg",
                            "instance_ansible__ansible-5f4e33__B7afiCi",
                            "instance_ansible__ansible-185d41__tJU5CKf",
                            "instance_ansible__ansible-be2c37__f34S9WV",
                            "instance_ansible__ansible-a02e22__6kButFg",
                            "instance_ansible__ansible-379058__w9JfCL2",
                            "instance_ansible__ansible-949c50__cwQCnzB",
                            "instance_ansible__ansible-1a4644__43GLsT9",
                            "instance_ansible__ansible-40ade1__J3LptWQ",
                            "instance_ansible__ansible-0ea40e__W3khtMW",
                            "instance_ansible__ansible-e22e10__V9FscHn",
                            "instance_ansible__ansible-748f53__to7nxNz",
                            "instance_ansible__ansible-e9e600__cGsR9Uj",
                            "instance_ansible__ansible-5d253a__g8GLQxE",
                            "instance_ansible__ansible-ea04e0__Zpmvtj5",
                            "instance_ansible__ansible-d9f186__xnm4czk",
                            "instance_ansible__ansible-b8025a__ko7Y5gh",
                            "instance_ansible__ansible-d62496__3ERYiyj",
                            "instance_ansible__ansible-942424__3goRari"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 99858264,
        "n_cache_tokens": 92975104,
        "n_output_tokens": 613598,
        "cost_usd": 111.636312
    }
}
```