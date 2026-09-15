from abc import ABC

class ModelConfig(ABC):

    name: str
    image: str = "vllm/vllm-openai:v0.24.0"
    args: list[str]
    model_max_len: int
    hardware_extra_args: dict[str, list[str]] = {}
    default_args: list[str] =  [
        "--gpu-memory-utilization", "0.9",
        "--async-scheduling",
        "--enable-chunked-prefill",
        "--enable-prefix-caching",
    ]
