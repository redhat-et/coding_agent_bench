from coding_agent_bench.models import get_model_config


def test_qwen38_int4_model_config():
    config = get_model_config("RedHatAI/Qwen3.8-27B-INT4")

    assert config.model_max_len == 262144
    assert config.args == [
        "--model",
        "RedHatAI/Qwen3.8-27B-INT4",
        "--max-model-len",
        "262144",
        "--kv-cache-dtype",
        "fp8",
        "--enable-auto-tool-choice",
        "--tool-call-parser",
        "qwen3_coder",
        "--reasoning-parser",
        "qwen3",
        "--mm-encoder-tp-mode",
        "data",
    ]
