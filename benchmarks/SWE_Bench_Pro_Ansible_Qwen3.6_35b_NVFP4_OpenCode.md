# SWE-Bench Pro Ansible Qwen3.6-35B-A3B-NVFP4 OpenCode

## Benchmark

**Dataset:** [swe-bench-pro--ansible](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) (96 tasks, ansible only)
**Model:** [RedHatAI/Qwen3.6-35B-A3B-NVFP4](https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4)  
**Harness:** OpenCode  
**Environment:** Docker  
**Job Name:** 2026-05-13__14-06-00  

## Results

**Score:** 37.5%  
**Errors (Initial Run):** 20   
**Total Time:** 1 hr 46 min  
**Agent Time:** 1 hr 32 min    
**Estimated Cost:** $12.11 ($4 / GPU / hr * 2 GPU * 1 hr 32 min)   

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

export OPENCODE_CONFIG='{"$schema":"https://opencode.ai/config.json","model":"vllm/qwen3.6-35b","provider":{"vllm":{"npm":"@ai-sdk/openai-compatible","name":"vLLM","options":{"baseURL":"<server-url>"},"models":{"qwen3.6-35b":{"name":"qwen3.6-35b","limit":{"context":196500,"output":65500}}}}}}'

# Run SWE-Bench with OpenCode
harbor run --agent opencode -d $BENCHMARK \
    -i $DATASET_PATTERN \
    -m vllm/$MODEL_NAME \
    --ae "OPENCODE_CONFIG_CONTENT=$OPENCODE_CONFIG" \
    --agent-timeout-multiplier 0.5 \
    --n-concurrent 9

# Rerun once
harbor jobs resume -p jobs/2026-05-13__14-06-00 -f AgentTimeoutError
```

**`config.json`:**

```json
{
    "job_name": "2026-05-13__14-06-00",
    "jobs_dir": "jobs",
    "n_attempts": 1,
    "timeout_multiplier": 1.0,
    "agent_timeout_multiplier": 0.5,
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
            "VerifierTimeoutError",
            "AgentTimeoutError",
            "VerifierOutputParseError",
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
            "name": "opencode",
            "import_path": null,
            "model_name": "vllm/qwen3.6-35b",
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "kwargs": {},
            "env": {
                "OPENCODE_CONFIG_CONTENT": "{\"$schema\":\"https://opencode.ai/config.json\",\"model\":\"vllm/qwen3.6-35b\",\"provider\":{\"vllm\":{\"npm\":\"@ai-sdk/openai-compatible\",\"name\":\"vLLM\",\"options\":{\"baseURL\":\"<server-url>\"},\"models\":{\"qwen3.6-35b\":{\"name\":\"qwen3.6-35b\",\"limit\":{\"context\":196500,\"output\":65500}}}}}}"
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
{
    "id": "bbfa9d07-f599-4037-a420-0360312eb614",
    "started_at": "2026-05-13T14:06:05.496012",
    "updated_at": "2026-05-13T20:13:50.379834",
    "finished_at": "2026-05-13T20:13:50.379834",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 4,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "opencode__qwen3.6-35b__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 4,
                "metrics": [
                    {
                        "mean": 0.375
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "0.0": [
                            "instance_ansible__ansible-bf98f0__CUtSg8m",
                            "instance_ansible__ansible-622a49__XgZYQJp",
                            "instance_ansible__ansible-f02a62__ywLXpzC",
                            "instance_ansible__ansible-949c50__Cr6S4Wh",
                            "instance_ansible__ansible-b5e029__wvTqVcs",
                            "instance_ansible__ansible-d30fc6__Ux6YHnR",
                            "instance_ansible__ansible-f86c58__D7cDi7B",
                            "instance_ansible__ansible-395e5e__eA3GsPB",
                            "instance_ansible__ansible-f327e6__6PWxV9y",
                            "instance_ansible__ansible-34db57__XWAb4Cf",
                            "instance_ansible__ansible-6cc974__GHYvxGz",
                            "instance_ansible__ansible-9a21e2__7HBMjjN",
                            "instance_ansible__ansible-d62496__roh52Sq",
                            "instance_ansible__ansible-eea46a__PMFuWhZ",
                            "instance_ansible__ansible-984216__XHwpAw5",
                            "instance_ansible__ansible-3889dd__N6v6tXc",
                            "instance_ansible__ansible-8127ab__MmbzMQj",
                            "instance_ansible__ansible-d33bed__Bi6Fvjp",
                            "instance_ansible__ansible-11c177__GJKGBNK",
                            "instance_ansible__ansible-9759e0__CuYHtfy",
                            "instance_ansible__ansible-9142be__WxSUVrs",
                            "instance_ansible__ansible-bec27f__j2ZSCWL",
                            "instance_ansible__ansible-39bd8b__pc9eRXy",
                            "instance_ansible__ansible-e22e10__bYC9aSb",
                            "instance_ansible__ansible-5e88cd__9K56YPg",
                            "instance_ansible__ansible-776587__Bja4FGx",
                            "instance_ansible__ansible-811093__xBZGCGP",
                            "instance_ansible__ansible-935528__Ky2EmMf",
                            "instance_ansible__ansible-1c06c4__veQBfwt",
                            "instance_ansible__ansible-a02e22__6H8ngCd",
                            "instance_ansible__ansible-e40889__je9M9Xv",
                            "instance_ansible__ansible-d58e69__URm5irR",
                            "instance_ansible__ansible-cd9c4e__V4BcJDi",
                            "instance_ansible__ansible-a6e671__bdKQdMj",
                            "instance_ansible__ansible-deb54e__hPEJg97",
                            "instance_ansible__ansible-106909__HZfBbL6",
                            "instance_ansible__ansible-e64c6c__7EGbUEW",
                            "instance_ansible__ansible-ecea15__bC5iChH",
                            "instance_ansible__ansible-b748ed__zmttxdQ",
                            "instance_ansible__ansible-83909b__HKZEczH",
                            "instance_ansible__ansible-e9e600__UBcb9aq",
                            "instance_ansible__ansible-d2f809__pVmKT27",
                            "instance_ansible__ansible-942424__d9t84ak",
                            "instance_ansible__ansible-83fb24__6wkWAou",
                            "instance_ansible__ansible-4c5ce5__jGxXWuD",
                            "instance_ansible__ansible-1b7026__kEGRDYA",
                            "instance_ansible__ansible-b6290e__39mfKB3",
                            "instance_ansible__ansible-cd473d__vqrNvmk",
                            "instance_ansible__ansible-de5858__svJxvpm",
                            "instance_ansible__ansible-c616e5__CTMDwmW",
                            "instance_ansible__ansible-502270__DRoiCXx",
                            "instance_ansible__ansible-564009__AVETiqa",
                            "instance_ansible__ansible-7e1a34__AcZQcjU",
                            "instance_ansible__ansible-fb144c__Po7P6bY",
                            "instance_ansible__ansible-709484__KzfrYkx",
                            "instance_ansible__ansible-1bd7dc__TsWMB6f",
                            "instance_ansible__ansible-d72025__VDyYu9a",
                            "instance_ansible__ansible-c1f2df__Eh9iUGy",
                            "instance_ansible__ansible-40ade1__Fii5Tug",
                            "instance_ansible__ansible-42355d__xBS3MBK"
                        ],
                        "1.0": [
                            "instance_ansible__ansible-a26c32__66x6ejD",
                            "instance_ansible__ansible-d6d225__BbMobmL",
                            "instance_ansible__ansible-be2c37__ahpSYgZ",
                            "instance_ansible__ansible-5e3696__hG2ZhzW",
                            "instance_ansible__ansible-ea04e0__DJiL2r8",
                            "instance_ansible__ansible-5c225d__EtiKoF6",
                            "instance_ansible__ansible-be59ca__3LXvd7h",
                            "instance_ansible__ansible-164881__XHxvGDa",
                            "instance_ansible__ansible-a1569e__uQPqXRo",
                            "instance_ansible__ansible-0fd887__DqAaptw",
                            "instance_ansible__ansible-ed6581__FpPKk3M",
                            "instance_ansible__ansible-185d41__2xegr5j",
                            "instance_ansible__ansible-a20a52__mRT7ccR",
                            "instance_ansible__ansible-5d253a__SLpUNst",
                            "instance_ansible__ansible-e0c91a__q5fjSxN",
                            "instance_ansible__ansible-189fcb__cEGEPPi",
                            "instance_ansible__ansible-cb94c0__S8qsVAQ",
                            "instance_ansible__ansible-1ee70f__Uczu6gW",
                            "instance_ansible__ansible-748f53__CNLy72R",
                            "instance_ansible__ansible-526052__HQT5BRt",
                            "instance_ansible__ansible-379058__EqSK7ti",
                            "instance_ansible__ansible-5f4e33__5LWVRtx",
                            "instance_ansible__ansible-b2a289__BoYawPw",
                            "instance_ansible__ansible-d9f186__TCCz5x3",
                            "instance_ansible__ansible-415e08__axWYqpm",
                            "instance_ansible__ansible-f8ef34__j7joDPq",
                            "instance_ansible__ansible-29aea9__yxiMD4P",
                            "instance_ansible__ansible-1a4644__nsjKZ5h",
                            "instance_ansible__ansible-3b823d__xSo8L5m",
                            "instance_ansible__ansible-de01db__r8PtVtS",
                            "instance_ansible__ansible-a7d2a4__KyVSPDC",
                            "instance_ansible__ansible-b8025a__MAAuK7B",
                            "instance_ansible__ansible-0ea40e__Kf75U8F",
                            "instance_ansible__ansible-489156__5Lqb2kK",
                            "instance_ansible__ansible-3db08a__4VtexdJ",
                            "instance_ansible__ansible-12734f__NCzrbfm"
                        ]
                    }
                },
                "exception_stats": {
                    "AgentTimeoutError": [
                        "instance_ansible__ansible-b6290e__39mfKB3",
                        "instance_ansible__ansible-de5858__svJxvpm",
                        "instance_ansible__ansible-c616e5__CTMDwmW",
                        "instance_ansible__ansible-40ade1__Fii5Tug"
                    ]
                }
            }
        },
        "n_input_tokens": 207164679,
        "n_cache_tokens": 0,
        "n_output_tokens": 1598703,
        "cost_usd": null
    }
}
```