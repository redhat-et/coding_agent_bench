from coding_agent_bench.models.base import ModelConfig

class Qwen_Qwen3_8_27B(ModelConfig):
    
    name = "Qwen/Qwen3.8-27B"
    model_max_len = 262144
    args = [
        "--model", "Qwen/Qwen3.8-27B" ,
        "--max-model-len", "262144" ,
        "--kv-cache-dtype", "fp8" ,
        "--enable-auto-tool-choice",
        "--tool-call-parser", "qwen3_coder" ,
        "--reasoning-parser", "qwen3" ,
        "--mm-encoder-tp-mode", "data",
    ]

class RedHatAI_gemma_4_31B_it_FP8_block(ModelConfig):
    
    name = "RedHatAI/gemma-4-31B-it-FP8-block"
    model_max_len = 262144
    args = [
        "--model", "RedHatAI/gemma-4-31B-it-FP8-block",
        "--dtype", "auto",
        "--max-model-len", "262144",
        "--trust-remote-code",
        "--kv-cache-dtype", "fp8",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "gemma4",
        "--tool-call-parser", "gemma4",
        "--default-chat-template-kwargs", '{"enable_thinking": true}',
    ]
    
class RedHatAI_gpt_oss_120b(ModelConfig):
    
    name = "RedHatAI/gpt-oss-120b"
    model_max_len = 131072
    args = [
        "--model", "RedHatAI/gpt-oss-120b",
        "--dtype", "auto",
        "--max-model-len", "131072",
        "--kv-cache-dtype", "fp8",
        "--enable-auto-tool-choice",
        "--tool-call-parser", "openai",
    ]
   
class RedHatAI_Mistral_Small_4_119B_2603_NVFP4(ModelConfig):
    
    name = "RedHatAI/Mistral-Small-4-119B-2603-NVFP4"
    model_max_len = 131072
    args = [
        "--model", "RedHatAI/Mistral-Small-4-119B-2603-NVFP4",
        "--dtype", "auto",
        "--max-model-len", "131072",
        "--trust-remote-code",
        "--kv-cache-dtype", "auto",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "mistral",
        "--tool-call-parser", "mistral",
        "--default-chat-template-kwargs", '{"reasoning_effort": "high"}',
        "--limit-mm-per-prompt", '{"image": 0}',
    ]
    
class RedHatAI_NVIDIA_Nemotron_3_Super_120B_A12B_NVFP4(ModelConfig):
    
    name = "RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4"
    model_max_len = 262144
    args = [
        "--model", "RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4",
        "--dtype", "auto",
        "--max-model-len", "262144",
        "--kv-cache-dtype", "fp8",
        "--gpu-memory-utilization", "0.9",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "nemotron_v3",
        "--tool-call-parser", "qwen3_coder",
    ]

class RedHatAI_Qwen3_6_27B_FP8(ModelConfig):

    name = "RedHatAI/Qwen3.6-27B-FP8"
    model_max_len = 131072
    args = [
        "--model", "RedHatAI/Qwen3.6-27B-FP8",
        "--dtype", "auto",
        "--max-model-len", "131072",
        "--trust-remote-code",
        "--kv-cache-dtype", "fp8",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "qwen3",
        "--tool-call-parser", "qwen3_coder",
        "--default-chat-template-kwargs", '{"enable_thinking": true}',
    ]


class RedHatAI_GLM_5_2_FP8(ModelConfig):
    # Verified: 8x H200 141GB, concurrency 2.23x at 262K context
    # Note: cannot fit 1M context on 8x H200 (needs 52.68 GiB KV, only 23.78 GiB available)

    name = "RedHatAI/GLM-5.2-FP8"
    model_max_len = 262144
    args = [
        "--model", "RedHatAI/GLM-5.2-FP8",
        "--dtype", "auto",
        "--max-model-len", "262144",
        "--trust-remote-code",
        "--kv-cache-dtype", "fp8",
        "--enable-expert-parallel",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "glm45",
        "--tool-call-parser", "glm47",
    ]


class RedHatAI_DeepSeek_V4_Flash(ModelConfig):
    # Verified: 8x H200 141GB, concurrency 9.91x at 1M context
    # Note: --moe-backend deep_gemm_mega_moe is B200-only (SM100)

    name = "RedHatAI/DeepSeek-V4-Flash"
    image = "vllm/vllm-openai:v0.27.1"
    model_max_len = 1048576
    args = [
        "--model", "RedHatAI/DeepSeek-V4-Flash",
        "--dtype", "auto",
        "--trust-remote-code",
        "--kv-cache-dtype", "fp8",
        "--block-size", "256",
        "--enable-expert-parallel",
        "--enable-auto-tool-choice",
        "--tokenizer-mode", "deepseek_v4",
        "--tool-call-parser", "deepseek_v4",
        "--reasoning-parser", "deepseek_v4",
    ]


class RedHatAI_DeepSeek_V4_Flash_NVFP4_FP8(ModelConfig):
    # Verified: 8x H200 141GB, concurrency 9.81x at 1M context
    # Note: Marlin FP4 fallback on H200 (no native SM100 FP4), similar concurrency to base

    name = "RedHatAI/DeepSeek-V4-Flash-NVFP4-FP8"
    image = "vllm/vllm-openai:v0.27.1"
    model_max_len = 1048576
    args = [
        "--model", "RedHatAI/DeepSeek-V4-Flash-NVFP4-FP8",
        "--dtype", "auto",
        "--trust-remote-code",
        "--kv-cache-dtype", "fp8",
        "--block-size", "256",
        "--enable-expert-parallel",
        "--enable-auto-tool-choice",
        "--tokenizer-mode", "deepseek_v4",
        "--tool-call-parser", "deepseek_v4",
        "--reasoning-parser", "deepseek_v4",
    ]


class RedHatAI_Inkling_Small(ModelConfig):
    # Verified: 8x H200 141GB, BF16, concurrency 13.22x at 1M context

    name = "RedHatAI/Inkling-Small"
    image = "vllm/vllm-openai:v0.27.1"
    model_max_len = 1048576
    args = [
        "--model", "RedHatAI/Inkling-Small",
        "--dtype", "auto",
        "--trust-remote-code",
        "--kv-cache-dtype", "fp8",
        "--enable-auto-tool-choice",
        "--tool-call-parser", "inkling",
        "--reasoning-parser", "inkling",
    ]


class RedHatAI_Laguna_S_2_1(ModelConfig):
    # Verified: 8x H200 141GB, BF16, max-model-len 1048576, concurrency 30.61x

    name = "RedHatAI/Laguna-S-2.1"
    model_max_len = 1048576
    args = [
        "--model", "RedHatAI/Laguna-S-2.1",
        "--dtype", "auto",
        "--trust-remote-code",
        "--kv-cache-dtype", "fp8",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "poolside_v1",
        "--tool-call-parser", "poolside_v1",
        "--default-chat-template-kwargs", '{"enable_thinking": true}',
    ]

class poolside_Laguna_S_2_1_NVFP4(ModelConfig):
    # Verified: 1x B200 183GB, NVFP4, max-model-len 1048576, concurrency 2.33x

    name = "poolside/Laguna-S-2.1-NVFP4"
    model_max_len = 1048576
    args = [
        "--model", "poolside/Laguna-S-2.1-NVFP4",
        "--dtype", "auto",
        "--trust-remote-code",
        "--kv-cache-dtype", "fp8",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "poolside_v1",
        "--tool-call-parser", "poolside_v1",
        "--default-chat-template-kwargs", '{"enable_thinking": true}',
    ]


