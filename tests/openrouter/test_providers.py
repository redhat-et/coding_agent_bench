import pytest

from coding_agent_bench.providers import (
    OPENROUTER_BASE_URL,
    is_openai,
    is_openrouter,
    resolve_provider,
)


def test_is_openrouter_true():
    assert is_openrouter("openrouter") is True


def test_is_openrouter_false():
    assert is_openrouter("https://vllm.example.com") is False


def test_is_openai():
    assert is_openai("https://api.openai.com/v1") is True
    assert is_openai("https://api.openai.com/") is True
    assert is_openai("https://proxy.example.com/v1") is False


def test_openrouter_base_url_excludes_v1():
    # Agents append /v1 as needed; claude-code uses the base without it.
    assert OPENROUTER_BASE_URL == "https://openrouter.ai/api"
    assert not OPENROUTER_BASE_URL.endswith("/v1")


def test_resolve_openrouter_returns_url_and_key():
    base_url, api_key = resolve_provider("openrouter", "sk-or-test")
    assert base_url == OPENROUTER_BASE_URL
    assert api_key == "sk-or-test"


def test_resolve_openrouter_missing_key_raises():
    with pytest.raises(ValueError, match="model API key"):
        resolve_provider("openrouter")


def test_resolve_non_openrouter_passthrough(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    base_url, api_key = resolve_provider("https://vllm.example.com")
    assert base_url == "https://vllm.example.com"
    assert api_key is None
