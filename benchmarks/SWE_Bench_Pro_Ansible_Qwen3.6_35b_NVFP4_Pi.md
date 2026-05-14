# SWE-Bench Pro Ansible Qwen3.6-35B-A3B-NVFP4 Pi

## Benchmark

**Dataset:** [swe-bench-pro--ansible](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) (96 tasks, ansible only)  
**Model:** [RedHatAI/Qwen3.6-35B-A3B-NVFP4](https://huggingface.co/RedHatAI/Qwen3.6-35B-A3B-NVFP4)  
**Harness:** Pi  
**Environment:** Docker  
**Job Name:** 2026-05-11__19-41-51   
## Results

**Score:** 47.9%  
**Errors (Initial Run):** 6   
**Total Time:** 3 hr 51 min  
**Agent Run Time:** 1 hr 41 min
**Estimated Cost:** $13.47 ($4 / GPU / hr * 2 GPU * 1 hr 41 min)  

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
export MODEL_NAME='qwen3.6-35b'
export DATASET_PATTERN='*ansible*'

export PI_MODELS_JSON='{ "providers": { "vllm": { "baseUrl": "<server-url>", "api": "openai-completions", "apiKey": "NONE", "models": [{ "id": "qwen3.6-35b", "name": "qwen3.6-35b", "contextWindow": 262000 }] } } }'

echo $PI_MODELS_JSON > models.json

harbor run --agent pi -d $BENCHMARK \
    -m vllm/$MODEL_NAME \
    -i $DATASET_PATTERN \
    --ae PI_OFFLINE=1 \
    --ae PI_CODING_AGENT_DIR=/root/.pi/agent \
    --mounts-json '[ { "type": "bind", "source":"/path/to/models.json", "target": "/root/.pi/agent/models.json" } ]' \
    --n-concurrent 9
```

**`config.json`:**

```json
{
    "job_name": "2026-05-11__19-41-51",
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
            "VerifierTimeoutError",
            "VerifierOutputParseError",
            "RewardFileNotFoundError",
            "AgentTimeoutError",
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
                "source": "/path/to/models.json",
                "target": "/root/.pi/agent/models.json"
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
            "name": "pi",
            "import_path": null,
            "model_name": "vllm/qwen3.6-35b",
            "override_timeout_sec": null,
            "override_setup_timeout_sec": null,
            "max_timeout_sec": null,
            "kwargs": {},
            "env": {
                "PI_OFFLINE": "1",
                "PI_CODING_AGENT_DIR": "/root/.pi/agent"
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
    "id": "165ca111-40d4-4dd3-9696-0c1321d66dbd",
    "started_at": "2026-05-11T19:41:56.413526",
    "updated_at": "2026-05-12T09:04:00.855357",
    "finished_at": "2026-05-12T09:04:00.855357",
    "n_total_trials": 96,
    "stats": {
        "n_completed_trials": 96,
        "n_errored_trials": 1,
        "n_running_trials": 0,
        "n_pending_trials": 0,
        "n_cancelled_trials": 0,
        "n_retries": 0,
        "evals": {
            "pi__qwen3.6-35b__scale-ai/swe-bench-pro": {
                "n_trials": 96,
                "n_errors": 1,
                "metrics": [
                    {
                        "mean": 0.4791666666666667
                    }
                ],
                "pass_at_k": {},
                "reward_stats": {
                    "reward": {
                        "1.0": [
                            "instance_ansible__ansible-185d41__ttmJncU",
                            "instance_ansible__ansible-cd9c4e__5mp5HXK",
                            "instance_ansible__ansible-5c225d__qqSxRsH",
                            "instance_ansible__ansible-be2c37__oF4wmgE",
                            "instance_ansible__ansible-e0c91a__Bnhrs8p",
                            "instance_ansible__ansible-b8025a__YUExf7T",
                            "instance_ansible__ansible-b2a289__SVLaK4v",
                            "instance_ansible__ansible-d62496__gJXGF4K",
                            "instance_ansible__ansible-164881__mP9mBZh",
                            "instance_ansible__ansible-e9e600__UczZK9z",
                            "instance_ansible__ansible-9142be__A37K52D",
                            "instance_ansible__ansible-5d253a__4bZerHs",
                            "instance_ansible__ansible-0ea40e__AGMSJuR",
                            "instance_ansible__ansible-d9f186__btJCigF",
                            "instance_ansible__ansible-a02e22__q2Dqv5f",
                            "instance_ansible__ansible-1ee70f__DehuPta",
                            "instance_ansible__ansible-3b823d__jGAMb3H",
                            "instance_ansible__ansible-ed6581__spEvGN5",
                            "instance_ansible__ansible-622a49__nhj3pky",
                            "instance_ansible__ansible-12734f__hsc2Qod",
                            "instance_ansible__ansible-489156__dxVHhHj",
                            "instance_ansible__ansible-0fd887__ggig6Gs",
                            "instance_ansible__ansible-1a4644__3CGzKEh",
                            "instance_ansible__ansible-415e08__F7austx",
                            "instance_ansible__ansible-d2f809__erEXeGw",
                            "instance_ansible__ansible-a20a52__DWyoqiY",
                            "instance_ansible__ansible-748f53__XYrGpRR",
                            "instance_ansible__ansible-526052__xAFNn7p",
                            "instance_ansible__ansible-e22e10__wJLimhC",
                            "instance_ansible__ansible-29aea9__fq7quUz",
                            "instance_ansible__ansible-cb94c0__uHtjtEt",
                            "instance_ansible__ansible-5f4e33__6XK84xK",
                            "instance_ansible__ansible-deb54e__dbeRY2m",
                            "instance_ansible__ansible-ea04e0__aM3hqFn",
                            "instance_ansible__ansible-f8ef34__94kobRb",
                            "instance_ansible__ansible-984216__SPXhcFj",
                            "instance_ansible__ansible-a26c32__n7daXXF",
                            "instance_ansible__ansible-3db08a__sw9LwRR",
                            "instance_ansible__ansible-379058__DRXoLpK",
                            "instance_ansible__ansible-de01db__jHBvETF",
                            "instance_ansible__ansible-fb144c__9Ppr8in",
                            "instance_ansible__ansible-5e3696__6ZJ7AXi",
                            "instance_ansible__ansible-bf98f0__SeoTJqu",
                            "instance_ansible__ansible-1b7026__TTscmPz",
                            "instance_ansible__ansible-f327e6__BmGLiAu",
                            "instance_ansible__ansible-d30fc6__6hKSrsy"
                        ],
                        "0.0": [
                            "instance_ansible__ansible-8127ab__osuvfZA",
                            "instance_ansible__ansible-395e5e__CEhCDgj",
                            "instance_ansible__ansible-f02a62__RavrVwe",
                            "instance_ansible__ansible-83fb24__QpzVMMo",
                            "instance_ansible__ansible-a1569e__hY7XJDo",
                            "instance_ansible__ansible-bec27f__zaBPrbn",
                            "instance_ansible__ansible-d33bed__32xbtuN",
                            "instance_ansible__ansible-d72025__aUnh3Kg",
                            "instance_ansible__ansible-935528__s6cYKRZ",
                            "instance_ansible__ansible-9a21e2__zQBozD5",
                            "instance_ansible__ansible-189fcb__pyhJQqS",
                            "instance_ansible__ansible-5e88cd__NgfQ9AF",
                            "instance_ansible__ansible-c1f2df__2HMkt83",
                            "instance_ansible__ansible-9759e0__gbrGyXG",
                            "instance_ansible__ansible-e64c6c__oPuvv2S",
                            "instance_ansible__ansible-7e1a34__sjvfX3s",
                            "instance_ansible__ansible-106909__DsZUnmn",
                            "instance_ansible__ansible-949c50__LgjhLNq",
                            "instance_ansible__ansible-42355d__YADudwp",
                            "instance_ansible__ansible-e40889__DSYFLkt",
                            "instance_ansible__ansible-b748ed__te8WbRy",
                            "instance_ansible__ansible-eea46a__v5VUAnu",
                            "instance_ansible__ansible-cd473d__UNPNUco",
                            "instance_ansible__ansible-f86c58__2JC4jUk",
                            "instance_ansible__ansible-6cc974__DYtTgYw",
                            "instance_ansible__ansible-776587__vF8kzWw",
                            "instance_ansible__ansible-1bd7dc__Xuz57oA",
                            "instance_ansible__ansible-40ade1__ev7siUa",
                            "instance_ansible__ansible-4c5ce5__ZzHhkK7",
                            "instance_ansible__ansible-83909b__ByJkuSy",
                            "instance_ansible__ansible-502270__fxByWgp",
                            "instance_ansible__ansible-b5e029__WaiTD8j",
                            "instance_ansible__ansible-564009__ZRY5fAP",
                            "instance_ansible__ansible-811093__TWXQzXd",
                            "instance_ansible__ansible-1c06c4__aEYAVV2",
                            "instance_ansible__ansible-c616e5__Xk9voGK",
                            "instance_ansible__ansible-11c177__7Fj3DmP",
                            "instance_ansible__ansible-709484__9waMvhH",
                            "instance_ansible__ansible-a7d2a4__v3NEyDx",
                            "instance_ansible__ansible-34db57__86KamM8",
                            "instance_ansible__ansible-3889dd__sLg2faB",
                            "instance_ansible__ansible-ecea15__DU7EM76",
                            "instance_ansible__ansible-be59ca__EgBYHBF",
                            "instance_ansible__ansible-b6290e__zxrtzQn",
                            "instance_ansible__ansible-39bd8b__e4ytaK3",
                            "instance_ansible__ansible-a6e671__oA6bvmS",
                            "instance_ansible__ansible-d58e69__yLxGBGn",
                            "instance_ansible__ansible-d6d225__iC9Uemy",
                            "instance_ansible__ansible-de5858__aNiz4Pe",
                            "instance_ansible__ansible-942424__GVw7gxd"
                        ]
                    }
                },
                "exception_stats": {
                    "AgentTimeoutError": [
                        "instance_ansible__ansible-de5858__aNiz4Pe"
                    ]
                }
            }
        },
        "n_input_tokens": 742491363,
        "n_cache_tokens": 0,
        "n_output_tokens": 2387609,
        "cost_usd": null
    }
}
```