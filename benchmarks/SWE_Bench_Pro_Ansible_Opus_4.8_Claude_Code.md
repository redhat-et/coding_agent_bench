# SWE-Bench Pro Ansible Opus 4.8 Claude Code

## Benchmark

**Dataset:** [swe-bench-pro--ansible](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) (96 tasks, ansible only) 
**Model:** [Claude Opus 4.8](https://www.anthropic.com/news/claude-opus-4-8)    
**Harness:** Claude Code  
**Environment:** Docker  
**Job Name:** 2026-06-15__14-05-08  

## Results

**Score:** 69.8%  
**Errors (Initial Run):** 1   
**Total Time:** 00h 40m 39s  
**Agent Time:** 00h 34m 06s  
**Estimated Cost:** $185.66  

## Harbor Config

**Command:**

```bash
set -a
source .env

export BENCHMARK='scale-ai/swe-bench-pro'
export DATASET_PATTERN='*ansible*'

harbor run --agent claude-code -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m claude-opus-4-8 \
    --n-concurrent 16

# Rerun once to eliminate transient errors
harbor jobs resume -p jobs/<job-id> -f NonZeroAgentExitCodeError
```

**`config.json`:**

```json
{
    "job_name": "2026-06-15__14-05-08",
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
            "VerifierOutputParseError",
            "RewardFileEmptyError",
            "VerifierTimeoutError",
            "AgentTimeoutError"
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
            "model_name": "claude-opus-4-8",
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

`result.json`

```json
{
    "id": "1a6522b1-0c1f-4766-a6ef-3737270494a8",
    "started_at": "2026-06-15T14:05:10.822884",
    "updated_at": "2026-06-15T15:14:36.454216",
    "finished_at": "2026-06-15T15:14:36.454216",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "claude-code__claude-opus-4-8__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 0,
                "metrics": [
                    {
                        "mean": 0.6979166666666666
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "instance_ansible__ansible-a20a52__W8Y6uQX",
                            "instance_ansible__ansible-bec27f__WarSQnk",
                            "instance_ansible__ansible-0fd887__cBAo8Xf",
                            "instance_ansible__ansible-de01db__9b4iPp3",
                            "instance_ansible__ansible-d58e69__HDufpXo",
                            "instance_ansible__ansible-1ee70f__Cw7mJxB",
                            "instance_ansible__ansible-a02e22__ibrSH93",
                            "instance_ansible__ansible-a7d2a4__2LCDhgR",
                            "instance_ansible__ansible-e9e600__uerzQ5Y",
                            "instance_ansible__ansible-b2a289__kCJgTVd",
                            "instance_ansible__ansible-5e88cd__2chfA9K",
                            "instance_ansible__ansible-ea04e0__xKjnmNo",
                            "instance_ansible__ansible-6cc974__egPFYtx",
                            "instance_ansible__ansible-5d253a__3yuoDXw",
                            "instance_ansible__ansible-ed6581__5jgYQjA",
                            "instance_ansible__ansible-e0c91a__yczPYnh",
                            "instance_ansible__ansible-deb54e__hxBwyqA",
                            "instance_ansible__ansible-189fcb__mqXdwoE",
                            "instance_ansible__ansible-3db08a__UjAgEpR",
                            "instance_ansible__ansible-1b7026__ku2vp8X",
                            "instance_ansible__ansible-34db57__e2629HU",
                            "instance_ansible__ansible-415e08__U6vN4uh",
                            "instance_ansible__ansible-395e5e__BCwGhLH",
                            "instance_ansible__ansible-29aea9__mMpRfFh",
                            "instance_ansible__ansible-be2c37__kEpbH2Z",
                            "instance_ansible__ansible-cd473d__zsXSVyM",
                            "instance_ansible__ansible-185d41__cFH6oyk",
                            "instance_ansible__ansible-c616e5__YwSpn7e",
                            "instance_ansible__ansible-489156__AZAouGx",
                            "instance_ansible__ansible-83909b__Z93cpqD",
                            "instance_ansible__ansible-a6e671__yVY7QmX",
                            "instance_ansible__ansible-d30fc6__5XUmHX2",
                            "instance_ansible__ansible-7e1a34__cPEHRbU",
                            "instance_ansible__ansible-f8ef34__pP5DEd7",
                            "instance_ansible__ansible-f327e6__BfFZcnX",
                            "instance_ansible__ansible-622a49__GtFz5WM",
                            "instance_ansible__ansible-502270__pNe5VVu",
                            "instance_ansible__ansible-984216__Aigret9",
                            "instance_ansible__ansible-f86c58__agcuUQ8",
                            "instance_ansible__ansible-d62496__a5VAtqr",
                            "instance_ansible__ansible-fb144c__cDxrvdZ",
                            "instance_ansible__ansible-d6d225__XJEcL3o",
                            "instance_ansible__ansible-776587__HMmhARy",
                            "instance_ansible__ansible-106909__URkANzz",
                            "instance_ansible__ansible-379058__3vfMq2X",
                            "instance_ansible__ansible-b8025a__HnTRhAB",
                            "instance_ansible__ansible-e22e10__weUXHTJ",
                            "instance_ansible__ansible-0ea40e__tLZKAgx",
                            "instance_ansible__ansible-d9f186__PvYWh48",
                            "instance_ansible__ansible-709484__73kVxHM",
                            "instance_ansible__ansible-935528__8fKhRME",
                            "instance_ansible__ansible-5e3696__BS2qpNS",
                            "instance_ansible__ansible-526052__7N8yGcB",
                            "instance_ansible__ansible-811093__DPduGGZ",
                            "instance_ansible__ansible-3b823d__pKHMdfQ",
                            "instance_ansible__ansible-cb94c0__ENrs4vk",
                            "instance_ansible__ansible-5c225d__MXDpZv3",
                            "instance_ansible__ansible-42355d__USXwauy",
                            "instance_ansible__ansible-a26c32__CH6hDqj",
                            "instance_ansible__ansible-1a4644__tnbPPxL",
                            "instance_ansible__ansible-9a21e2__ecKfPWM",
                            "instance_ansible__ansible-12734f__hju89Yt",
                            "instance_ansible__ansible-942424__yhZaDF7",
                            "instance_ansible__ansible-1c06c4__Cgckj65",
                            "instance_ansible__ansible-9142be__KKQaMFZ",
                            "instance_ansible__ansible-748f53__X2u5eC2",
                            "instance_ansible__ansible-b6290e__QRRXh3d"
                        ],
                        "0.0": [
                            "instance_ansible__ansible-39bd8b__jy6vcAD",
                            "instance_ansible__ansible-164881__PqkXvvd",
                            "instance_ansible__ansible-ecea15__UoL2s8t",
                            "instance_ansible__ansible-be59ca__AgXLT5f",
                            "instance_ansible__ansible-e40889__7jffDeE",
                            "instance_ansible__ansible-bf98f0__UnSTLg4",
                            "instance_ansible__ansible-d33bed__bFs4YHa",
                            "instance_ansible__ansible-8127ab__QWuPpCw",
                            "instance_ansible__ansible-3889dd__iFUUduX",
                            "instance_ansible__ansible-949c50__xLwukCD",
                            "instance_ansible__ansible-eea46a__uetV8u3",
                            "instance_ansible__ansible-a1569e__bUktTfK",
                            "instance_ansible__ansible-9759e0__oxE4H5z",
                            "instance_ansible__ansible-4c5ce5__webywTa",
                            "instance_ansible__ansible-d2f809__zQASker",
                            "instance_ansible__ansible-c1f2df__YFktVwz",
                            "instance_ansible__ansible-b5e029__UAwh33G",
                            "instance_ansible__ansible-e64c6c__bsjc5FL",
                            "instance_ansible__ansible-de5858__s4ChzYe",
                            "instance_ansible__ansible-f02a62__CvCVKdU",
                            "instance_ansible__ansible-1bd7dc__vwCZRCn",
                            "instance_ansible__ansible-83fb24__J77kuJx",
                            "instance_ansible__ansible-5f4e33__FYrA9za",
                            "instance_ansible__ansible-40ade1__HkBiBPW",
                            "instance_ansible__ansible-b748ed__qsixJ9d",
                            "instance_ansible__ansible-cd9c4e__W2HhfKM",
                            "instance_ansible__ansible-564009__W97DrtS",
                            "instance_ansible__ansible-11c177__wiYBxrp",
                            "instance_ansible__ansible-d72025__cJqavTt"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 192346997,
        "n_cache_tokens": 186506482,
        "n_output_tokens": 2179945,
        "cost_usd": 185.66155285
    }
}
```
