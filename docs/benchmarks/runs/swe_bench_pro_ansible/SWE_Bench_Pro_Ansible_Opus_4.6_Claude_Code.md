# SWE-Bench Pro Ansible Opus 4.6 Claude Code

## Benchmark

**Dataset:** [swe-bench-pro--ansible](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) (96 tasks, ansible only) 
**Model:** [Claude Sonnet 4.6](https://www.anthropic.com/news/claude-sonnet-4-6)    
**Harness:** Claude Code  
**Environment:** Docker  
**Job Name:** 2026-06-15__15-53-26  

## Results

**Score:** 51.0%  
**Errors (Initial Run):** 0   
**Total Time:** 00h 48m 57s  
**Agent Time:** 00h 43m 03s  
**Estimated Cost:** $172.05

## Harbor Config

**Command:**

```bash
set -a
source .env

export BENCHMARK='scale-ai/swe-bench-pro'
export DATASET_PATTERN='*ansible*'

harbor run --agent claude-code -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m claude-opus-4-6 \
    --n-concurrent 16
```  

**`config.json`:**

```json
{
    "job_name": "2026-06-15__15-53-26",
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
            "RewardFileNotFoundError",
            "RewardFileEmptyError",
            "AgentTimeoutError",
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
            "name": "claude-code",
            "import_path": null,
            "model_name": "claude-opus-4-6",
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

**`result.json`**

```json
{
    "id": "be5f6631-0b0d-4ad4-ba6e-e1ac31d97dcf",
    "started_at": "2026-06-15T15:53:28.846677",
    "updated_at": "2026-06-15T16:49:46.956261",
    "finished_at": "2026-06-15T16:49:46.956261",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "claude-code__claude-opus-4-6__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 0,
                "metrics": [
                    {
                        "mean": 0.5104166666666666
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.0": [
                            "instance_ansible__ansible-d6d225__Rm2fEY7",
                            "instance_ansible__ansible-83fb24__xBrmtDH",
                            "instance_ansible__ansible-3889dd__bohpKJp",
                            "instance_ansible__ansible-4c5ce5__9nJ2mXV",
                            "instance_ansible__ansible-d58e69__DG6VX9g",
                            "instance_ansible__ansible-1b7026__PNVewsn",
                            "instance_ansible__ansible-bf98f0__zhFhRkx",
                            "instance_ansible__ansible-489156__nn9vwt9",
                            "instance_ansible__ansible-bec27f__LvAeDWw",
                            "instance_ansible__ansible-b748ed__S8UNYc9",
                            "instance_ansible__ansible-b6290e__zApV2Ls",
                            "instance_ansible__ansible-cd473d__QgruuhB",
                            "instance_ansible__ansible-a26c32__TPxMxoe",
                            "instance_ansible__ansible-f86c58__dHvTZ5f",
                            "instance_ansible__ansible-83909b__a7A4dze",
                            "instance_ansible__ansible-9759e0__nnFWN5d",
                            "instance_ansible__ansible-de5858__XPAkDiS",
                            "instance_ansible__ansible-d33bed__qoDSypF",
                            "instance_ansible__ansible-c616e5__YRBWQPw",
                            "instance_ansible__ansible-942424__G9Ajr9p",
                            "instance_ansible__ansible-502270__VfRTPS8",
                            "instance_ansible__ansible-d30fc6__ZonM5HF",
                            "instance_ansible__ansible-564009__idMamFQ",
                            "instance_ansible__ansible-f02a62__o3XBzGh",
                            "instance_ansible__ansible-e40889__WNRW5KA",
                            "instance_ansible__ansible-1bd7dc__idsMcR7",
                            "instance_ansible__ansible-984216__ErLC3JY",
                            "instance_ansible__ansible-164881__xDutcAE",
                            "instance_ansible__ansible-935528__GdwT5UB",
                            "instance_ansible__ansible-b5e029__uoKFEkv",
                            "instance_ansible__ansible-ecea15__hwT8Xv6",
                            "instance_ansible__ansible-811093__VVKvBVq",
                            "instance_ansible__ansible-1a4644__aVoSZMz",
                            "instance_ansible__ansible-11c177__iXNxvdN",
                            "instance_ansible__ansible-a1569e__nDjF45L",
                            "instance_ansible__ansible-c1f2df__UK4oWy2",
                            "instance_ansible__ansible-40ade1__ZLgyqne",
                            "instance_ansible__ansible-949c50__wjbofRM",
                            "instance_ansible__ansible-e64c6c__cqiaou8",
                            "instance_ansible__ansible-ea04e0__jAAr8hT",
                            "instance_ansible__ansible-39bd8b__8B4PFD6",
                            "instance_ansible__ansible-e9e600__AsYbBtM",
                            "instance_ansible__ansible-eea46a__D2zyTxy",
                            "instance_ansible__ansible-9a21e2__A2667EP",
                            "instance_ansible__ansible-9142be__9oe3p4p",
                            "instance_ansible__ansible-5e3696__scjWCgq",
                            "instance_ansible__ansible-34db57__bt8Vt7v"
                        ],
                        "1.0": [
                            "instance_ansible__ansible-29aea9__c6qqSzS",
                            "instance_ansible__ansible-f8ef34__VHxdREH",
                            "instance_ansible__ansible-a7d2a4__yFVqkTZ",
                            "instance_ansible__ansible-5d253a__MT8bc6M",
                            "instance_ansible__ansible-a6e671__LFVeU7d",
                            "instance_ansible__ansible-e22e10__aUta5i5",
                            "instance_ansible__ansible-cb94c0__exK2ErA",
                            "instance_ansible__ansible-379058__mmerF4c",
                            "instance_ansible__ansible-526052__BEBLujd",
                            "instance_ansible__ansible-de01db__6wCmhPf",
                            "instance_ansible__ansible-776587__cjnLr2V",
                            "instance_ansible__ansible-d9f186__XUUBwyz",
                            "instance_ansible__ansible-5e88cd__YbCBMJ7",
                            "instance_ansible__ansible-a20a52__j3NoE6W",
                            "instance_ansible__ansible-deb54e__AtPgkPU",
                            "instance_ansible__ansible-3b823d__rwi4L9z",
                            "instance_ansible__ansible-f327e6__oxQB3PS",
                            "instance_ansible__ansible-ed6581__4TXtzjT",
                            "instance_ansible__ansible-622a49__NiQX4LF",
                            "instance_ansible__ansible-b8025a__bu6WfAb",
                            "instance_ansible__ansible-185d41__w2RC96P",
                            "instance_ansible__ansible-106909__bJ4fELP",
                            "instance_ansible__ansible-cd9c4e__JhbcQHu",
                            "instance_ansible__ansible-7e1a34__GbF7hDu",
                            "instance_ansible__ansible-415e08__7viQPtK",
                            "instance_ansible__ansible-e0c91a__7SPr99m",
                            "instance_ansible__ansible-6cc974__gRJSfFh",
                            "instance_ansible__ansible-5c225d__tDMHaWg",
                            "instance_ansible__ansible-fb144c__Na9UtVn",
                            "instance_ansible__ansible-709484__sfUo8iq",
                            "instance_ansible__ansible-0ea40e__4pqHF5X",
                            "instance_ansible__ansible-189fcb__95etvfr",
                            "instance_ansible__ansible-d72025__oVr2deZ",
                            "instance_ansible__ansible-0fd887__GzE6Abe",
                            "instance_ansible__ansible-3db08a__5hTaeE5",
                            "instance_ansible__ansible-1ee70f__vUERcNP",
                            "instance_ansible__ansible-b2a289__DZr755x",
                            "instance_ansible__ansible-12734f__dngJqQW",
                            "instance_ansible__ansible-d62496__waedHVd",
                            "instance_ansible__ansible-395e5e__e9pQuvF",
                            "instance_ansible__ansible-5f4e33__6oUobhg",
                            "instance_ansible__ansible-a02e22__chAQPzu",
                            "instance_ansible__ansible-be2c37__CEQunnN",
                            "instance_ansible__ansible-1c06c4__PhhGY2m",
                            "instance_ansible__ansible-748f53__AW9eERp",
                            "instance_ansible__ansible-8127ab__dNk4Kt2",
                            "instance_ansible__ansible-42355d__hLsNa4g",
                            "instance_ansible__ansible-d2f809__cex4Vuf",
                            "instance_ansible__ansible-be59ca__CqFsDpf"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 179598057,
        "n_cache_tokens": 174512868,
        "n_output_tokens": 1731490,
        "cost_usd": 172.04781100000005
    }
}
```