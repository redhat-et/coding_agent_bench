# SWE-Bench Pro Ansible Qwen3.6-35B-A3B-NVFP4 Claude Code

## Benchmark

**Dataset:** [swe-bench/swe-bench-verified](https://hub.harborframework.com/datasets/swe-bench/swe-bench-verified/latest) (500 tasks)  
**Model:**   
**Harness:** Claude Code  
**Environment:** Docker  
**Job Name:** 2026-05-18__15-38-59  

## Results

**Score:** 50.0%  
**Errors (Initial Run):** 1  
**Total Time:** 52 min  
**Agent Run Time:** 42 min    
**Cost:** $184.43    

## Harbor Config

**Command:**

```bash
export BENCHMARK='scale-ai/swe-bench-pro'
export DATASET_PATTERN='*ansible*'

harbor run --agent claude-code -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m claude-sonnet-4-6@latest \
    --ae CLAUDE_CODE_USE_VERTEX=1 \
    --ae CLOUD_ML_REGION=$CLOUD_ML_REGION \
    --ae ANTHROPIC_VERTEX_PROJECT_ID=$ANTHROPIC_VERTEX_PROJECT_ID \
    --ae ANTHROPIC_MODEL=$ANTHROPIC_MODEL \
    --ae GOOGLE_APPLICATION_CREDENTIALS='/app/.config/gcloud/application_default_credentials.json' \
    --mounts-json '[ { "type": "bind", "source": "~/.config/gcloud/application_default_credentials.json", "target": "/app/.config/gcloud/application_default_credentials.json" } ]' \
    --n-concurrent 16
```

**`config.json`:**

```json
{
    "job_name": "2026-05-18__15-38-59",
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
            "AgentTimeoutError",
            "VerifierOutputParseError",
            "RewardFileNotFoundError",
            "RewardFileEmptyError"
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
        "mounts_json": [
            {
                "type": "bind",
                "source": "~/.config/gcloud/application_default_credentials.json",
                "target": "/app/.config/gcloud/application_default_credentials.json"
            }
        ],
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
            "name": "claude-code",
            "import_path": null,
            "model_name": "claude-sonnet-4-6@latest",
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "kwargs": {},
            "env": {
                "CLAUDE_CODE_USE_VERTEX": "1",
                "CLOUD_ML_REGION": "global",
                "ANTHROPIC_VERTEX_PROJECT_ID": "itpc-gcp-octo-eng-claude",
                "ANTHROPIC_MODEL": "claude-opus-4-6@default",
                "GOOGLE_APPLICATION_CREDENTIALS": "/app****son"
            }
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
{{
    "id": "cd270ff6-695d-41c3-a39f-69403ba16ddd",
    "started_at": "2026-05-18T15:39:04.428212",
    "updated_at": "2026-05-18T16:36:38.579031",
    "finished_at": "2026-05-18T16:36:38.579031",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 1,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "claude-code__claude-sonnet-4-6@latest__scale-ai/swe-bench-pro": {
                "n_trials": 95,
                "n_errors": 1,
                "metrics": [
                    {
                        "mean": 0.5
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "instance_ansible__ansible-d6d225__wtTzENp",
                            "instance_ansible__ansible-29aea9__xFCcwxw",
                            "instance_ansible__ansible-f8ef34__Z6qhmZe",
                            "instance_ansible__ansible-a7d2a4__Rm86py2",
                            "instance_ansible__ansible-1b7026__ob2xyAM",
                            "instance_ansible__ansible-a6e671__nFtTZrM",
                            "instance_ansible__ansible-e22e10__agsH36o",
                            "instance_ansible__ansible-cb94c0__bfyKg9J",
                            "instance_ansible__ansible-379058__AsMKSYi",
                            "instance_ansible__ansible-526052__ZY7gQj8",
                            "instance_ansible__ansible-de01db__jnYypxi",
                            "instance_ansible__ansible-776587__SbWrjvT",
                            "instance_ansible__ansible-9759e0__u8BSZWR",
                            "instance_ansible__ansible-a20a52__hykEU9q",
                            "instance_ansible__ansible-deb54e__g64iDJJ",
                            "instance_ansible__ansible-3b823d__6x5WRXW",
                            "instance_ansible__ansible-f327e6__un4mjPK",
                            "instance_ansible__ansible-ed6581__hXD5H4n",
                            "instance_ansible__ansible-622a49__6fbFb97",
                            "instance_ansible__ansible-185d41__EyrnVSS",
                            "instance_ansible__ansible-106909__7NgPw2f",
                            "instance_ansible__ansible-cd9c4e__GAABUZb",
                            "instance_ansible__ansible-f02a62__KoqBWX2",
                            "instance_ansible__ansible-415e08__j88EBjG",
                            "instance_ansible__ansible-e0c91a__CA87njc",
                            "instance_ansible__ansible-6cc974__5WfqjAJ",
                            "instance_ansible__ansible-5c225d__CfvyVKw",
                            "instance_ansible__ansible-fb144c__hD5kArs",
                            "instance_ansible__ansible-709484__dN8s5Fx",
                            "instance_ansible__ansible-0ea40e__EZaC8wQ",
                            "instance_ansible__ansible-189fcb__E6DbAMa",
                            "instance_ansible__ansible-d72025__HDhWNpm",
                            "instance_ansible__ansible-3db08a__ykfhEWd",
                            "instance_ansible__ansible-1ee70f__YUDS9HP",
                            "instance_ansible__ansible-b2a289__EtVGaC9",
                            "instance_ansible__ansible-1a4644__hbGK7mp",
                            "instance_ansible__ansible-12734f__2YwVgnY",
                            "instance_ansible__ansible-d62496__CDRb73L",
                            "instance_ansible__ansible-11c177__9NakPqq",
                            "instance_ansible__ansible-395e5e__F74HcZ7",
                            "instance_ansible__ansible-5f4e33__MgqSETy",
                            "instance_ansible__ansible-a02e22__MNPPvV4",
                            "instance_ansible__ansible-be2c37__jLbEUQt",
                            "instance_ansible__ansible-c1f2df__2Q6WAn6",
                            "instance_ansible__ansible-748f53__NmK7z78",
                            "instance_ansible__ansible-42355d__UsehWeB",
                            "instance_ansible__ansible-be59ca__dkbEWTD",
                            "instance_ansible__ansible-5e3696__iAnPhGp"
                        ],
                        "0.0": [
                            "instance_ansible__ansible-83fb24__WxpLvak",
                            "instance_ansible__ansible-3889dd__ajdFKXu",
                            "instance_ansible__ansible-4c5ce5__UxoDXvv",
                            "instance_ansible__ansible-d58e69__dxxbvxf",
                            "instance_ansible__ansible-bf98f0__WzPi9Sd",
                            "instance_ansible__ansible-489156__D79giVg",
                            "instance_ansible__ansible-bec27f__QD33cNj",
                            "instance_ansible__ansible-b748ed__AgKqvp6",
                            "instance_ansible__ansible-b6290e__4opgPVS",
                            "instance_ansible__ansible-cd473d__khYNysH",
                            "instance_ansible__ansible-a26c32__Xi5vWgm",
                            "instance_ansible__ansible-f86c58__mVaCQ9H",
                            "instance_ansible__ansible-83909b__nenwGZZ",
                            "instance_ansible__ansible-de5858__sEVWS7L",
                            "instance_ansible__ansible-d9f186__hNkS2rY",
                            "instance_ansible__ansible-5e88cd__fgh8zff",
                            "instance_ansible__ansible-d33bed__3JQQJBS",
                            "instance_ansible__ansible-c616e5__5USy2Ar",
                            "instance_ansible__ansible-942424__5Tb5hXh",
                            "instance_ansible__ansible-b8025a__WyU8NnT",
                            "instance_ansible__ansible-502270__srQsW86",
                            "instance_ansible__ansible-d30fc6__VtQrP5b",
                            "instance_ansible__ansible-564009__7zZ49nW",
                            "instance_ansible__ansible-7e1a34__QkDiF3u",
                            "instance_ansible__ansible-e40889__GhS8A94",
                            "instance_ansible__ansible-1bd7dc__6VzjTrC",
                            "instance_ansible__ansible-984216__La3m4bu",
                            "instance_ansible__ansible-164881__gapVQNp",
                            "instance_ansible__ansible-935528__cnTMkjY",
                            "instance_ansible__ansible-b5e029__JoN3wnb",
                            "instance_ansible__ansible-0fd887__HcgtoGi",
                            "instance_ansible__ansible-ecea15__tjJcFwE",
                            "instance_ansible__ansible-811093__j5bonG7",
                            "instance_ansible__ansible-a1569e__iodesX5",
                            "instance_ansible__ansible-1c06c4__CDVpMeB",
                            "instance_ansible__ansible-40ade1__P8vywfi",
                            "instance_ansible__ansible-949c50__5qe3JYV",
                            "instance_ansible__ansible-e64c6c__mULGf6X",
                            "instance_ansible__ansible-ea04e0__zxY7neq",
                            "instance_ansible__ansible-39bd8b__pTBUJy5",
                            "instance_ansible__ansible-e9e600__FzmhnWC",
                            "instance_ansible__ansible-8127ab__PSaxhBS",
                            "instance_ansible__ansible-d2f809__vvc8B6r",
                            "instance_ansible__ansible-eea46a__BViH7m2",
                            "instance_ansible__ansible-9a21e2__US96id7",
                            "instance_ansible__ansible-9142be__NhXQBCG",
                            "instance_ansible__ansible-34db57__4mNqT7T"
                        ]
                    }
                },
                "exception_stats": {
                    "NonZeroAgentExitCodeError": [
                        "instance_ansible__ansible-5d253a__UMxMDFT"
                    ]
                }
            }
        },
        "n_input_tokens": 190672390,
        "n_cache_tokens": 184409111,
        "n_output_tokens": 1593112,
        "cost_usd": 184.42824124999996
    }
}
```