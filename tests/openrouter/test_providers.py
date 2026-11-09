from coding_agent_bench.providers import (
    ANTHROPIC_AUTH_HEADER,
    is_openai,
    is_openrouter,
    resolve_provider,
)


def test_is_openrouter_true():
    assert is_openrouter("https://openrouter.ai/api") is True
    assert is_openrouter("https://OPENROUTER.AI./api/v1") is True


def test_is_openrouter_false():
    assert is_openrouter("https://vllm.example.com") is False


def test_is_openai():
    assert is_openai("https://api.openai.com/v1") is True
    assert is_openai("https://api.openai.com/") is True
    assert is_openai("https://proxy.example.com/v1") is False


def test_resolve_openrouter_passthrough():
    base_url, api_key, auth_header = resolve_provider("https://openrouter.ai/api", "sk-or-test")
    assert base_url == "https://openrouter.ai/api"
    assert api_key == "sk-or-test"
    assert auth_header == ANTHROPIC_AUTH_HEADER


def test_resolve_non_openrouter_passthrough():
    base_url, api_key, auth_header = resolve_provider("https://vllm.example.com")
    assert base_url == "https://vllm.example.com"
    assert api_key is None
    assert auth_header == ANTHROPIC_AUTH_HEADER


def test_resolve_anthropic_compatible_endpoint_uses_api_key_header():
    _, _, auth_header = resolve_provider("https://anthropic.example.com", "sk-ant-test")
    assert auth_header == ANTHROPIC_AUTH_HEADER
