# SWE Bench Pro Ansible GPT 5.5 Codex

## Benchmark

**Dataset:** [scale-ai/swe-bench-pro](https://hub.harborframework.com/datasets/scale-ai/swe-bench-pro/latest) (96 tasks)  
**Model:** gpt-5.5 - high  
**Harness:** codex  
**Environment:** Docker  
**Job Name:** 2026-06-16__13-46-36  

## Results

**Score:** 60.4%    
**Errors (Initial Run):** 0  
**Total Time:** 00h 41m 06s  
**Agent Time:** 00h 34m 17s  
**Estimated Cost:** $188.34  

## Harbor Config

**Command:**

```bash
set -a
source .env

export BENCHMARK='scale-ai/swe-bench-pro'
export DATASET_PATTERN='*ansible*'

harbor run --agent codex -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m gpt-5.5 \
    --n-concurrent 16
```

**`config.json`:**

```json
{
    "job_name": "2026-06-16__13-46-36",
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
            "VerifierTimeoutError",
            "VerifierOutputParseError",
            "RewardFileEmptyError",
            "AgentTimeoutError",
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
            "name": "codex",
            "import_path": null,
            "model_name": "gpt-5.5",
            "skills": [],
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "extra_allowed_hosts": [],
            "kwargs": {},
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
    "id": "c459530c-2477-45c6-b9b8-ca401c5468e1",
    "started_at": "2026-06-16T13:46:38.736844",
    "updated_at": "2026-06-16T14:31:11.630895",
    "finished_at": "2026-06-16T14:31:11.630895",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "codex__gpt-5.5__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 0,
                "metrics": [
                    {
                        "mean": 0.6041666666666666
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "instance_ansible__ansible-d6d225__LKuZdCC",
                            "instance_ansible__ansible-29aea9__gscipnc",
                            "instance_ansible__ansible-f8ef34__GJx78XQ",
                            "instance_ansible__ansible-a7d2a4__Dt7qUM8",
                            "instance_ansible__ansible-5d253a__mR8U7tB",
                            "instance_ansible__ansible-1b7026__9gm9kfk",
                            "instance_ansible__ansible-a6e671__98oJeAq",
                            "instance_ansible__ansible-e22e10__3W8qRyj",
                            "instance_ansible__ansible-489156__nYCqyBi",
                            "instance_ansible__ansible-cb94c0__yCpZaHc",
                            "instance_ansible__ansible-379058__xsYbQRx",
                            "instance_ansible__ansible-526052__NuUKQ9h",
                            "instance_ansible__ansible-de01db__Xd7RH8S",
                            "instance_ansible__ansible-776587__2WBcj2j",
                            "instance_ansible__ansible-d9f186__Z2nBA8o",
                            "instance_ansible__ansible-a20a52__guiEJ5J",
                            "instance_ansible__ansible-deb54e__wsywaVu",
                            "instance_ansible__ansible-3b823d__ynqdaJv",
                            "instance_ansible__ansible-f327e6__UXLFbsT",
                            "instance_ansible__ansible-ed6581__qmSwv2W",
                            "instance_ansible__ansible-942424__95JSDKw",
                            "instance_ansible__ansible-622a49__9VqpHRj",
                            "instance_ansible__ansible-b8025a__oXaQ3xD",
                            "instance_ansible__ansible-185d41__VFf73nR",
                            "instance_ansible__ansible-502270__svahiRg",
                            "instance_ansible__ansible-106909__XvRmmjd",
                            "instance_ansible__ansible-d30fc6__xrfFCdk",
                            "instance_ansible__ansible-564009__j6LCWSw",
                            "instance_ansible__ansible-415e08__EGBZn3x",
                            "instance_ansible__ansible-e0c91a__cug7aw7",
                            "instance_ansible__ansible-6cc974__6sKLeyo",
                            "instance_ansible__ansible-5c225d__wwprrGj",
                            "instance_ansible__ansible-fb144c__H5fVMpJ",
                            "instance_ansible__ansible-709484__QUfUDgR",
                            "instance_ansible__ansible-0ea40e__ZpbA7G4",
                            "instance_ansible__ansible-984216__gdgrkwG",
                            "instance_ansible__ansible-164881__mCLdTba",
                            "instance_ansible__ansible-189fcb__JBJKfqJ",
                            "instance_ansible__ansible-935528__vEVQiCB",
                            "instance_ansible__ansible-b5e029__AnhZitU",
                            "instance_ansible__ansible-3db08a__xBbKybQ",
                            "instance_ansible__ansible-1ee70f__FME3QHo",
                            "instance_ansible__ansible-811093__dbZtTQP",
                            "instance_ansible__ansible-b2a289__mzAS5ZK",
                            "instance_ansible__ansible-1a4644__j8mKPSK",
                            "instance_ansible__ansible-12734f__a8kbvUP",
                            "instance_ansible__ansible-d62496__fkP7e2j",
                            "instance_ansible__ansible-395e5e__PAmwfXU",
                            "instance_ansible__ansible-5f4e33__2XWGRrD",
                            "instance_ansible__ansible-a02e22__yzFew3u",
                            "instance_ansible__ansible-be2c37__NKj4Ggy",
                            "instance_ansible__ansible-c1f2df__atwzMXG",
                            "instance_ansible__ansible-949c50__CsjtS88",
                            "instance_ansible__ansible-ea04e0__VzgJkmn",
                            "instance_ansible__ansible-748f53__vsVwBEf",
                            "instance_ansible__ansible-e9e600__uWzP3nJ",
                            "instance_ansible__ansible-8127ab__nQYSHug",
                            "instance_ansible__ansible-42355d__D5tZ3hk"
                        ],
                        "0.0": [
                            "instance_ansible__ansible-83fb24__cP4gG6j",
                            "instance_ansible__ansible-3889dd__UrErgbD",
                            "instance_ansible__ansible-4c5ce5__cyvVzwx",
                            "instance_ansible__ansible-d58e69__ff9t35N",
                            "instance_ansible__ansible-bf98f0__Wv2A7LX",
                            "instance_ansible__ansible-bec27f__jdDFv8p",
                            "instance_ansible__ansible-b748ed__XaRTRFk",
                            "instance_ansible__ansible-b6290e__wdY66jm",
                            "instance_ansible__ansible-cd473d__aTD8jd6",
                            "instance_ansible__ansible-a26c32__5HYDHPy",
                            "instance_ansible__ansible-f86c58__meE3kmP",
                            "instance_ansible__ansible-83909b__UrMNQAE",
                            "instance_ansible__ansible-9759e0__pGE7aRN",
                            "instance_ansible__ansible-de5858__Z2YH9pE",
                            "instance_ansible__ansible-5e88cd__9JmjGEG",
                            "instance_ansible__ansible-d33bed__w6n63bV",
                            "instance_ansible__ansible-c616e5__zwHucND",
                            "instance_ansible__ansible-cd9c4e__ZBynkgw",
                            "instance_ansible__ansible-7e1a34__83RskoV",
                            "instance_ansible__ansible-f02a62__yjHMrPJ",
                            "instance_ansible__ansible-e40889__uXss8QD",
                            "instance_ansible__ansible-1bd7dc__6RYkfcv",
                            "instance_ansible__ansible-d72025__NVYysvg",
                            "instance_ansible__ansible-0fd887__jJjtLXG",
                            "instance_ansible__ansible-ecea15__GwKmAJU",
                            "instance_ansible__ansible-11c177__3o8Gjua",
                            "instance_ansible__ansible-a1569e__Hez5qtu",
                            "instance_ansible__ansible-1c06c4__4DcWtRB",
                            "instance_ansible__ansible-40ade1__EUZvgVs",
                            "instance_ansible__ansible-e64c6c__qpA9UiL",
                            "instance_ansible__ansible-39bd8b__HQGu8pi",
                            "instance_ansible__ansible-d2f809__MiBCwPz",
                            "instance_ansible__ansible-be59ca__vt6HxZt",
                            "instance_ansible__ansible-eea46a__BGekKzH",
                            "instance_ansible__ansible-9a21e2__H4q7aUw",
                            "instance_ansible__ansible-9142be__rX7EZSb",
                            "instance_ansible__ansible-5e3696__yMnRCHw",
                            "instance_ansible__ansible-34db57__uzuzbEL"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 198924339,
        "n_cache_tokens": 189578624,
        "n_output_tokens": 1560836,
        "cost_usd": 188.34296700000002
    }
}
```