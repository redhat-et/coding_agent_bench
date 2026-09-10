import json

import pytest

from coding_agent_bench.agents.configs import (
    ClaudeCodeAgentConfig,
    OpenClawAgentConfig,
    OpenCodeAgentConfig,
    OracleAgentConfig,
    PiAgentConfig,
)


def test_openclaw_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    result = OpenClawAgentConfig().configure(
        model_name="openai/gpt-4o", server_url="openrouter"
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
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    PiAgentConfig().configure(model_name="openai/gpt-4o", server_url="openrouter")
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


def test_opencode_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    result = OpenCodeAgentConfig().configure(
        model_name="openai/gpt-4o", server_url="openrouter"
    )
    cfg = json.loads(result.agent_env["OPENCODE_CONFIG_CONTENT"])
    provider = cfg["provider"]["vllm"]
    assert provider["options"]["baseURL"] == "https://openrouter.ai/api/v1"
    assert provider["options"]["apiKey"] == "sk-or-test"
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


def test_oracle_rejects_openrouter():
    with pytest.raises(ValueError, match="OpenRouter"):
        OracleAgentConfig().configure(model_name="m", server_url="openrouter")


def test_claude_code_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    result = ClaudeCodeAgentConfig().configure(
        model_name="anthropic/claude-opus-5", server_url="openrouter"
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


def test_claude_code_qwen38_uses_xhigh_effort(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = ClaudeCodeAgentConfig().configure(
        model_name="Qwen/Qwen3.8-27B", server_url="http://vllm:8000"
    )
    assert result.agent_kwargs == {"reasoning_effort": "xhigh"}
