import os
from dataclasses import dataclass
from enum import Enum


class ModelProvider(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    OPENAI_COMPATIBLE = "openai-compatible"

# Base URL without the /v1 suffix. Agents append /v1 as needed (openclaw,
# opencode, pi, codex); claude-code uses the base as-is for ANTHROPIC_BASE_URL.
OPENROUTER_BASE_URL = "https://openrouter.ai/api"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_BASE_URL = "https://api.openai.com"

@dataclass(frozen=True)
class ProviderConfig:
    model_provider: ModelProvider
    base_url: str | None
    api_key: str | None
    api_key_env: str | None


PROVIDER_SECRETS = {
    ModelProvider.OPENAI: (OPENAI_API_KEY_ENV, "openai-api-key"),
    ModelProvider.OPENROUTER: (OPENROUTER_API_KEY_ENV, "openrouter-api-key"),
}


def resolve_provider(
    server_url: str | None,
    model_provider: ModelProvider = ModelProvider.OPENAI_COMPATIBLE,
) -> ProviderConfig:
    """Resolve a model provider's endpoint and credentials.

    The OpenAI and OpenRouter services use their canonical URLs. Custom
    OpenAI-compatible providers require an explicit server URL.
    """
    model_provider = ModelProvider(model_provider)
    if model_provider == ModelProvider.OPENAI:
        if server_url:
            raise ValueError("server_url does not apply to the OpenAI provider")
        api_key = os.environ.get(OPENAI_API_KEY_ENV)
        if not api_key:
            raise ValueError(
                f"{OPENAI_API_KEY_ENV} must be set when using the OpenAI provider"
            )
        return ProviderConfig(
            model_provider=model_provider,
            base_url=OPENAI_BASE_URL,
            api_key=api_key,
            api_key_env=OPENAI_API_KEY_ENV,
        )

    if model_provider == ModelProvider.OPENROUTER:
        if server_url:
            raise ValueError("server_url does not apply to the OpenRouter provider")
        api_key = os.environ.get(OPENROUTER_API_KEY_ENV)
        if not api_key:
            raise ValueError(
                f"{OPENROUTER_API_KEY_ENV} must be set when using the OpenRouter provider"
            )
        return ProviderConfig(
            model_provider=model_provider,
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
            api_key_env=OPENROUTER_API_KEY_ENV,
        )

    if not server_url:
        raise ValueError("server_url is required for OpenAI-compatible endpoints")
    if not server_url.startswith(("http://", "https://")):
        raise ValueError(
            "server_url must be an HTTP(S) URL for OpenAI-compatible endpoints"
        )
    return ProviderConfig(
        model_provider=model_provider,
        base_url=server_url,
        api_key=None,
        api_key_env=None,
    )
