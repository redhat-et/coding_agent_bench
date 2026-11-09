import json

import pytest

from coding_agent_bench.agents.configs import (
    ClaudeCodeAgentConfig,
    OpenClawAgentConfig,
    OpenCodeAgentConfig,
    OracleAgentConfig,
    PiAgentConfig,
)


def test_openclaw_openrouter():
    result = OpenClawAgentConfig().configure(
        model_name="openai/gpt-4o", server_url="openrouter", api_key="sk-or-test"
    )
    assert result.agent_env["OPENAI_BASE_URL"] == "https://openrouter.ai/api/v1"
    assert result.agent_env["OPENAI_API_KEY"] == "sk-or-test"


def test_openclaw_default_placeholder(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = OpenClawAgentConfig().configure(
        model_name="m", server_url="http://vllm:8000"
    )
    assert result.agent_env["OPENAI_BASE_URL"] == "http://vllm:8000/v1"
    assert result.agent_env["OPENAI_API_KEY"] == "sk-no-key-required"


def test_pi_openrouter(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    PiAgentConfig().configure(model_name="openai/gpt-4o", server_url="openrouter", api_key="sk-or-test")
    cfg = json.loads((tmp_path / "models.json").read_text())
    provider = cfg["providers"]["vllm"]
    assert provider["baseUrl"] == "https://openrouter.ai/api/v1"
    assert provider["apiKey"] == "sk-or-test"


def test_pi_default_placeholder(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    PiAgentConfig().configure(model_name="m", server_url="http://vllm:8000")
    cfg = json.loads((tmp_path / "models.json").read_text())
    assert cfg["providers"]["vllm"]["apiKey"] == "NONE"


def test_pi_restore_missing_file_uses_model_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CAB_MODEL_API_KEY", "sk-restore-test")
    source = tmp_path / "models.json"
    config = {
        "agents": [{"name": "pi", "model_name": "m"}],
        "environment": {"mounts": [{"source": str(source), "target": "/root/.pi/agent/models.json"}]},
    }

    PiAgentConfig().restore_mounts(config, "http://vllm:8000")

    provider = json.loads(source.read_text())["providers"]["vllm"]
    assert provider["apiKey"] == "sk-restore-test"


def test_pi_openai_uses_responses_api(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = PiAgentConfig().configure(
        model_name="gpt-5.6-luna",
        server_url="https://api.openai.com/v1",
        api_key="sk-test",
    )
    cfg = json.loads((tmp_path / "models.json").read_text())
    provider = cfg["providers"]["openai"]

    assert result.model == "openai/gpt-5.6-luna"
    assert provider["api"] == "openai-responses"
    assert provider["baseUrl"] == "https://api.openai.com/v1"
    assert provider["apiKey"] == "sk-test"


def test_opencode_openrouter():
    result = OpenCodeAgentConfig().configure(
        model_name="openai/gpt-4o", server_url="openrouter", api_key="sk-or-test"
    )
    cfg = json.loads(result.agent_env["OPENCODE_CONFIG_CONTENT"])
    provider = cfg["provider"]["vllm"]
    assert provider["options"]["baseURL"] == "https://openrouter.ai/api/v1"
    assert provider["options"]["apiKey"] == "{env:CAB_MODEL_API_KEY}"
    assert result.agent_env["CAB_MODEL_API_KEY"] == "sk-or-test"
    assert json.loads(result.agent_kwargs["opencode_config"])["provider"]["vllm"]["options"] == provider["options"]
    assert "openai/gpt-4o" in provider["models"]


def test_opencode_default_no_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = OpenCodeAgentConfig().configure(
        model_name="m", server_url="http://vllm:8000"
    )
    cfg = json.loads(result.agent_env["OPENCODE_CONFIG_CONTENT"])
    provider = cfg["provider"]["vllm"]
    assert provider["options"]["baseURL"] == "http://vllm:8000/v1"
    assert "apiKey" not in provider["options"]


def test_opencode_openai_uses_native_provider_without_limits():
    result = OpenCodeAgentConfig().configure(
        model_name="gpt-5", server_url="https://api.openai.com/v1", api_key="sk-test"
    )
    cfg = json.loads(result.agent_env["OPENCODE_CONFIG_CONTENT"])
    provider = cfg["provider"]["openai"]

    assert result.model == "openai/gpt-5"
    assert provider["npm"] == "@ai-sdk/openai"
    assert provider["options"] == {
        "baseURL": "https://api.openai.com/v1",
        "apiKey": "{env:CAB_MODEL_API_KEY}",
    }
    assert provider["models"]["gpt-5"] == {"name": "gpt-5"}


def test_opencode_openai_detection_does_not_match_other_hosts():
    result = OpenCodeAgentConfig().configure(
        model_name="m", server_url="https://proxy.example.com/openai/v1"
    )
    cfg = json.loads(result.agent_env["OPENCODE_CONFIG_CONTENT"])
    provider = cfg["provider"]["vllm"]

    assert provider["npm"] == "@ai-sdk/openai-compatible"
    assert "limit" in provider["models"]["m"]


def test_oracle_rejects_openrouter():
    with pytest.raises(ValueError, match="OpenRouter"):
        OracleAgentConfig().configure(model_name="m", server_url="openrouter")


def test_claude_code_openrouter():
    result = ClaudeCodeAgentConfig().configure(
        model_name="anthropic/claude-opus-5", server_url="openrouter", api_key="sk-or-test"
    )
    # OpenRouter's Claude Code integration: base URL without /v1, blank
    # ANTHROPIC_API_KEY, key in ANTHROPIC_AUTH_TOKEN.
    assert result.agent_env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"
    assert result.agent_env["ANTHROPIC_API_KEY"] == ""
    assert result.agent_env["ANTHROPIC_AUTH_TOKEN"] == "sk-or-test"


def test_claude_code_default_vllm(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = ClaudeCodeAgentConfig().configure(
        model_name="m", server_url="http://vllm:8000"
    )
    assert result.agent_env["ANTHROPIC_BASE_URL"] == "http://vllm:8000"
    assert result.agent_env["ANTHROPIC_API_KEY"] == "sk-no-key-required"
    assert "ANTHROPIC_AUTH_TOKEN" not in result.agent_env
    assert result.agent_kwargs is None


def test_claude_code_anthropic_compatible_endpoint_uses_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = ClaudeCodeAgentConfig().configure(
        model_name="m", server_url="https://anthropic.example.com", api_key="sk-ant-test"
    )
    assert result.agent_env["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert "ANTHROPIC_AUTH_TOKEN" not in result.agent_env


def test_claude_code_qwen38_uses_xhigh_effort(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = ClaudeCodeAgentConfig().configure(
        model_name="Qwen/Qwen3.8-27B", server_url="http://vllm:8000"
    )
    assert result.agent_kwargs == {"reasoning_effort": "xhigh"}
