import pytest

from coding_agent_bench.builder import HarborCommandBuilder
from coding_agent_bench.providers import ModelProvider


def test_builder_uses_native_openai_without_serializing_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")

    command, _ = HarborCommandBuilder().build(
        agent="codex",
        dataset="example/dataset",
        model_name="gpt-5",
        model_provider=ModelProvider.OPENAI,
        environment="docker",
    )

    model_index = command.index("--model")
    assert command[model_index + 1] == "openai/gpt-5"
    assert not any("OPENAI_API_KEY" in argument for argument in command)
    assert not any("sk-openai-test" in argument for argument in command)


def test_builder_requires_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        HarborCommandBuilder().build(
            agent="codex",
            dataset="example/dataset",
            model_name="gpt-5",
            model_provider=ModelProvider.OPENAI,
            environment="docker",
        )


def test_builder_requires_server_for_compatible_provider():
    with pytest.raises(ValueError, match="server_url is required"):
        HarborCommandBuilder().build(
            agent="codex",
            dataset="example/dataset",
            model_name="model",
            model_provider=ModelProvider.OPENAI_COMPATIBLE,
            environment="docker",
        )
