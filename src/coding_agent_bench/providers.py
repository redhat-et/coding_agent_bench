from urllib.parse import urlparse


OPENROUTER_SENTINEL = "openrouter"
# Base URL without the /v1 suffix. Agents append /v1 as needed (openclaw,
# opencode, pi, codex); claude-code uses the base as-is for ANTHROPIC_BASE_URL.
OPENROUTER_BASE_URL = "https://openrouter.ai/api"
MODEL_API_KEY_ENV = "CAB_MODEL_API_KEY"
BEARER_AUTH_HEADER = "Authorization"
ANTHROPIC_AUTH_HEADER = "x-api-key"

# Agents (SupportedAgent.value strings) that cannot use OpenRouter. This is
# only a fast, request-time 400 for create_job's lightweight openrouter
# validation branch; the authoritative guard lives in the agent's own
# configure() (see OracleAgentConfig), which still raises ValueError at
# build/run time regardless of this constant.
OPENROUTER_UNSUPPORTED_AGENTS = frozenset({"oracle"})


def is_openrouter(server_url: str) -> bool:
    """Return True if server_url is the OpenRouter sentinel."""
    return server_url == OPENROUTER_SENTINEL


def is_openai(server_url: str) -> bool:
    """Return True for the official OpenAI API endpoint."""
    parsed = urlparse(server_url)
    return parsed.scheme in {"http", "https"} and parsed.hostname == "api.openai.com"


def resolve_provider(
    server_url: str, api_key: str | None = None
) -> tuple[str, str | None, str]:
    """Resolve server_url to (base_url, api_key, auth_header).

    For the "openrouter" sentinel, return the OpenRouter base URL and the
    explicitly supplied key with bearer authentication. For other endpoints,
    return the URL and supplied key with Anthropic API-key authentication.
    Keys are request-scoped and must never come from provider-specific process
    environment variables.
    """
    if is_openrouter(server_url):
        if not api_key:
            raise ValueError(
                f"server_url '{OPENROUTER_SENTINEL}' requires a model API key"
            )
        return OPENROUTER_BASE_URL, api_key, BEARER_AUTH_HEADER
    return server_url, api_key, ANTHROPIC_AUTH_HEADER
