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
