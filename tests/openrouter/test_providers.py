import pytest

from coding_agent_bench.providers import (
    ModelProvider,
    OPENAI_BASE_URL,
    OPENROUTER_BASE_URL,
    resolve_provider,
)


def test_openrouter_base_url_excludes_v1():
    # Agents append /v1 as needed; claude-code uses the base without it.
    assert OPENROUTER_BASE_URL == "https://openrouter.ai/api"
    assert not OPENROUTER_BASE_URL.endswith("/v1")


def test_resolve_openrouter_returns_url_and_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    provider = resolve_provider(None, ModelProvider.OPENROUTER)
    assert provider.base_url == OPENROUTER_BASE_URL
    assert provider.api_key == "sk-or-test"
    assert provider.model_provider == ModelProvider.OPENROUTER


def test_resolve_openrouter_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        resolve_provider(None, ModelProvider.OPENROUTER)


def test_resolve_non_openrouter_passthrough(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = resolve_provider("https://vllm.example.com")
    assert provider.base_url == "https://vllm.example.com"
    assert provider.api_key is None


def test_compatible_provider_rejects_non_url():
    with pytest.raises(ValueError, match="HTTP"):
        resolve_provider("openrouter")


def test_resolve_openai_returns_native_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    provider = resolve_provider(None, ModelProvider.OPENAI)
    assert provider.base_url == OPENAI_BASE_URL
    assert provider.api_key == "sk-openai-test"
    assert provider.api_key_env == "OPENAI_API_KEY"


def test_resolve_openai_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        resolve_provider(None, ModelProvider.OPENAI)


def test_resolve_openai_rejects_server_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    with pytest.raises(ValueError, match="server_url does not apply"):
        resolve_provider("https://example.com", ModelProvider.OPENAI)
