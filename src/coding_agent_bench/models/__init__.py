from coding_agent_bench.models.base import ModelConfig
from coding_agent_bench.models.configs import (
    Qwen_Qwen3_8_27B,
    RedHatAI_gemma_4_31B_it_FP8_block,
    RedHatAI_gpt_oss_120b,
    RedHatAI_Mistral_Small_4_119B_2603_NVFP4,
    RedHatAI_NVIDIA_Nemotron_3_Super_120B_A12B_NVFP4,
    RedHatAI_Qwen3_6_27B_FP8,
)

MODEL_CONFIGS: list[type[ModelConfig]] = [
    Qwen_Qwen3_8_27B,
    RedHatAI_gemma_4_31B_it_FP8_block,
    RedHatAI_gpt_oss_120b,
    RedHatAI_Mistral_Small_4_119B_2603_NVFP4,
    RedHatAI_NVIDIA_Nemotron_3_Super_120B_A12B_NVFP4,
    RedHatAI_Qwen3_6_27B_FP8,
]

MODEL_REGISTRY: dict[str, ModelConfig] = {cls.name: cls() for cls in MODEL_CONFIGS}


def get_model_config(name: str) -> ModelConfig:
    """Look up a model config by name. Raises ValueError if not found."""
    config = MODEL_REGISTRY.get(name)
    if config is None:
        raise ValueError(
            f"Unsupported model type '{name}'. Choose from: {list(MODEL_REGISTRY.keys())}"
        )
    return config
