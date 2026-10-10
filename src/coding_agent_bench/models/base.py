from abc import ABC

class ModelConfig(ABC):

    name: str
    """Model name for lookup and pickers."""
    image: str = "vllm/vllm-openai:v0.24.0"
    """vLLM container image."""
    args: list[str]
    """Model-specific arguments for the vLLM server engine."""
    model_max_len: int
    """Maximum context length supported by the model."""
    default_args: list[str] =  [
        "--gpu-memory-utilization", "0.9",
        "--async-scheduling",
        "--enable-chunked-prefill",
        "--enable-prefix-caching",
        "--enable-prompt-tokens-details",
    ]
    """Default arguments for vLLM server engine for all models."""
