from urllib.parse import urlparse


MODEL_API_KEY_ENV = "CAB_MODEL_API_KEY"
BEARER_AUTH_HEADER = "Authorization"
ANTHROPIC_AUTH_HEADER = "x-api-key"


def is_openrouter(server_url: str) -> bool:
    """Return True when server_url uses OpenRouter's hostname."""
    parsed = urlparse(server_url)
    return parsed.hostname is not None and parsed.hostname.rstrip(".").lower() == "openrouter.ai"


def is_openai(server_url: str) -> bool:
    """Return True for the official OpenAI API endpoint."""
    parsed = urlparse(server_url)
    return parsed.scheme in {"http", "https"} and parsed.hostname == "api.openai.com"


def resolve_provider(
    server_url: str, api_key: str | None = None
) -> tuple[str, str | None, str]:
    """Return the submitted URL, key, and default Anthropic auth header."""
    return server_url, api_key, ANTHROPIC_AUTH_HEADER
