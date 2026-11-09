from coding_agent_bench.agents.configs import CodexAgentConfig
from coding_agent_bench.helpers.codex import codex_create_toml


def test_codex_toml_default_no_key(tmp_path):
    out = tmp_path / "config.toml"
    codex_create_toml("my-model", "http://vllm:8000", out)
    content = out.read_text()
    assert 'wire_api = "responses"' in content
    assert "requires_openai_auth = false" in content
    assert "env_key" not in content
    assert 'base_url = "http://vllm:8000/v1"' in content


def test_codex_toml_openrouter(tmp_path):
    out = tmp_path / "config.toml"
    codex_create_toml(
        "openai/gpt-4o", "https://openrouter.ai/api/v1", out, requires_auth=True
    )
    content = out.read_text()
    assert 'wire_api = "responses"' in content
    assert "requires_openai_auth = true" in content
    # Only the env var NAME is written; codex resolves the value at runtime.
    assert 'env_key = "CAB_MODEL_API_KEY"' in content
    assert 'base_url = "https://openrouter.ai/api/v1"' in content


def test_codex_agent_openrouter(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = CodexAgentConfig().configure(
        model_name="openai/gpt-4o", server_url="https://openrouter.ai/api", api_key="sk-or-test"
    )
    assert result.agent_env["CAB_MODEL_API_KEY"] == "sk-or-test"
    content = (tmp_path / "config.toml").read_text()
    assert 'wire_api = "responses"' in content


def test_codex_agent_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = CodexAgentConfig().configure(
        model_name="my-model", server_url="http://vllm:8000"
    )
    assert "OPENROUTER_API_KEY" not in result.agent_env
    content = (tmp_path / "config.toml").read_text()
    assert 'wire_api = "responses"' in content
