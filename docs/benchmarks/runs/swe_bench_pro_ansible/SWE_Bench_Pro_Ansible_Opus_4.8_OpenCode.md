# SWE Bench Pro Ansible Opus 4.8 OpenCode

## Benchmark

**Dataset:** [scale-ai/swe-bench-pro](https://hub.harborframework.com/datasets/scale-ai/swe-bench-pro/latest) (96 tasks)  
**Model:** anthropic/claude-opus-4-8  
**Harness:** opencode  
**Environment:** docker  
**Job Name:** 2026-06-18__12-36-00  

## Results

**Score:** 78.1%  
**Errors (Initial Run):** 1  
**Total Time:** 00h 40m 59s  
**Agent Time:** 00h 31m 57s  
**Estimated Cost:** $151.41  

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
    -m anthropic/claude-opus-4-8 \
    --agent-kwarg version=1.16.2 \
    --n-concurrent 16

# Rerun to eliminate transient errors:
harbor jobs resume -p jobs/<job-id> -f AgentTimeoutError
```

**`config.json`:**

```json
{
    "job_name": "2026-06-18__12-36-00",
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
            "VerifierOutputParseError",
            "VerifierTimeoutError",
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
            "name": "opencode",
            "import_path": null,
            "model_name": "anthropic/claude-opus-4-8",
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
    "id": "41139d2c-9a30-4227-85c9-62ddccac9ab5",
    "started_at": "2026-06-18T12:36:03.205214",
    "updated_at": "2026-06-24T10:58:58.957796",
    "finished_at": "2026-06-24T10:58:58.957796",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 0,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "opencode__claude-opus-4-8__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 0,
                "metrics": [
                    {
                        "mean": 0.78125
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "instance_ansible__ansible-1b7026__EewjqTB",
                            "instance_ansible__ansible-5d253a__pEEZQ25",
                            "instance_ansible__ansible-e9e600__wLknMqi",
                            "instance_ansible__ansible-6cc974__mkud7jv",
                            "instance_ansible__ansible-8127ab__cXnenYV",
                            "instance_ansible__ansible-34db57__bVqBq7w",
                            "instance_ansible__ansible-f86c58__eLKNQsZ",
                            "instance_ansible__ansible-379058__mcm2goB",
                            "instance_ansible__ansible-ecea15__Jvqa9bq",
                            "instance_ansible__ansible-1ee70f__hA5F5Hp",
                            "instance_ansible__ansible-d62496__obFGnri",
                            "instance_ansible__ansible-12734f__UQoEfqw",
                            "instance_ansible__ansible-f8ef34__6be8nsF",
                            "instance_ansible__ansible-526052__aBZpUjh",
                            "instance_ansible__ansible-502270__EiAfz2U",
                            "instance_ansible__ansible-a6e671__DPeA4nt",
                            "instance_ansible__ansible-29aea9__aLuM6uY",
                            "instance_ansible__ansible-de01db__asEn9ck",
                            "instance_ansible__ansible-c616e5__bZcrXSF",
                            "instance_ansible__ansible-fb144c__ZBosrSg",
                            "instance_ansible__ansible-e0c91a__m9vTwKv",
                            "instance_ansible__ansible-984216__vjSTkug",
                            "instance_ansible__ansible-935528__KzMTnPX",
                            "instance_ansible__ansible-9a21e2__QbXu5XH",
                            "instance_ansible__ansible-b2a289__qGiV9wx",
                            "instance_ansible__ansible-1a4644__XuYSB7p",
                            "instance_ansible__ansible-a1569e__TANtHqC",
                            "instance_ansible__ansible-a02e22__8vHvffY",
                            "instance_ansible__ansible-942424__NEHqKFA",
                            "instance_ansible__ansible-40ade1__n6io2sn",
                            "instance_ansible__ansible-c1f2df__6pM4uy7",
                            "instance_ansible__ansible-622a49__8Vaoskx",
                            "instance_ansible__ansible-811093__dJxPsit",
                            "instance_ansible__ansible-e40889__LXc6pgr",
                            "instance_ansible__ansible-cd473d__9xzecP4",
                            "instance_ansible__ansible-189fcb__M3HHi5h",
                            "instance_ansible__ansible-d30fc6__Z3gm76R",
                            "instance_ansible__ansible-39bd8b__jC36gQc",
                            "instance_ansible__ansible-0ea40e__4c5sduQ",
                            "instance_ansible__ansible-0fd887__ZWnjWvq",
                            "instance_ansible__ansible-e22e10__sksS93V",
                            "instance_ansible__ansible-f327e6__m9Tdzr9",
                            "instance_ansible__ansible-d9f186__nuE2Qgs",
                            "instance_ansible__ansible-3db08a__YYvJRFR",
                            "instance_ansible__ansible-f02a62__TFNxmJG",
                            "instance_ansible__ansible-9142be__JpBEYnW",
                            "instance_ansible__ansible-ea04e0__sWJPGEx",
                            "instance_ansible__ansible-489156__TS9Tzto",
                            "instance_ansible__ansible-3b823d__UCXdVA3",
                            "instance_ansible__ansible-a20a52__DG6ihhg",
                            "instance_ansible__ansible-748f53__VG44M9L",
                            "instance_ansible__ansible-5e88cd__VsqhyYF",
                            "instance_ansible__ansible-cb94c0__eE2wyaE",
                            "instance_ansible__ansible-5c225d__9JTzBfe",
                            "instance_ansible__ansible-bec27f__sPz4W7W",
                            "instance_ansible__ansible-d6d225__HocRrnp",
                            "instance_ansible__ansible-a26c32__Q2ePMEQ",
                            "instance_ansible__ansible-1c06c4__x37yD4V",
                            "instance_ansible__ansible-b8025a__6uEbFaL",
                            "instance_ansible__ansible-b6290e__VUUdRmB",
                            "instance_ansible__ansible-949c50__3NdaCMF",
                            "instance_ansible__ansible-395e5e__68KMExa",
                            "instance_ansible__ansible-7e1a34__37V6QjM",
                            "instance_ansible__ansible-776587__eeJYNiE",
                            "instance_ansible__ansible-be2c37__ka4BaU7",
                            "instance_ansible__ansible-709484__FSFNqfR",
                            "instance_ansible__ansible-5e3696__S36ngXz",
                            "instance_ansible__ansible-ed6581__Fh8ff4M",
                            "instance_ansible__ansible-83909b__9XmDGSq",
                            "instance_ansible__ansible-185d41__XZkXGDe",
                            "instance_ansible__ansible-a7d2a4__dNqoUAb",
                            "instance_ansible__ansible-42355d__itUDAgr",
                            "instance_ansible__ansible-deb54e__whvtqjG",
                            "instance_ansible__ansible-415e08__ee9ZRHg",
                            "instance_ansible__ansible-d72025__BGQDQWt"
                        ],
                        "0.0": [
                            "instance_ansible__ansible-5f4e33__myMkapf",
                            "instance_ansible__ansible-83fb24__XnsUpPP",
                            "instance_ansible__ansible-cd9c4e__MkKWJGg",
                            "instance_ansible__ansible-e64c6c__HqHxBTM",
                            "instance_ansible__ansible-106909__DyCH34a",
                            "instance_ansible__ansible-d58e69__Ah453cs",
                            "instance_ansible__ansible-be59ca__evU7ccN",
                            "instance_ansible__ansible-11c177__MD6Jqnh",
                            "instance_ansible__ansible-eea46a__hBwn8nH",
                            "instance_ansible__ansible-b5e029__4xQFiE4",
                            "instance_ansible__ansible-d33bed__FKzmdx6",
                            "instance_ansible__ansible-1bd7dc__af5CWJ5",
                            "instance_ansible__ansible-bf98f0__bfEqvwG",
                            "instance_ansible__ansible-de5858__6LaatAL",
                            "instance_ansible__ansible-b748ed__9xteMcn",
                            "instance_ansible__ansible-9759e0__TgX8gVi",
                            "instance_ansible__ansible-3889dd__fwZ7Bcv",
                            "instance_ansible__ansible-4c5ce5__WHwojCd",
                            "instance_ansible__ansible-164881__ry9VYQf",
                            "instance_ansible__ansible-564009__ZtvcwVV",
                            "instance_ansible__ansible-d2f809__aMPwLzs"
                        ]
                    }
                },
                "exception_stats": {}
            }
        },
        "n_input_tokens": 187217712,
        "n_cache_tokens": 187209844,
        "n_output_tokens": 1280944,
        "cost_usd": 151.4104807499999
    }
}
```