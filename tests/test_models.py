from coding_agent_bench.models import get_model_config


def test_glm_5_2_fp8_model_config() -> None:
    config = get_model_config("zai-org/GLM-5.2-FP8")

    assert config.name == "zai-org/GLM-5.2-FP8"
    assert config.model_max_len == 131072
    assert config.image == "vllm/vllm-openai:v0.24.0"
    assert config.args == [
        "--model", "zai-org/GLM-5.2-FP8",
        "--max-model-len", "131072",
        "--kv-cache-dtype", "fp8",
        "--enable-auto-tool-choice",
        "--tool-call-parser", "glm47",
        "--reasoning-parser", "glm45",
    ]
