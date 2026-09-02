from abc import ABC
from dataclasses import dataclass
from typing import Any

from coding_agent_bench.providers import (
    ModelProvider,
    ProviderConfig,
    resolve_provider,
)


@dataclass
class AgentConfigResult:
    """Agent-specific overrides returned by AgentConfig.configure()."""

    model: str
    agent_env: dict[str, str] | None = None
    mounts: list[dict[str, Any]] | None = None


class AgentConfig(ABC):
    """Base class for agent configurations. Subclass this to add a new agent."""

    name: str
    version: str | None = None
    supported_model_providers = frozenset(ModelProvider)

    def _configure_openai_compatible(
        self, provider: ProviderConfig, **kwargs
    ) -> AgentConfigResult:
        raise NotImplementedError(
            f"{self.name} does not support OpenAI-compatible endpoints"
        )

    def _configure_openai(self, provider: ProviderConfig, **kwargs) -> AgentConfigResult:
        raise NotImplementedError(f"{self.name} does not support OpenAI")

    def _configure_openrouter(
        self, provider: ProviderConfig, **kwargs
    ) -> AgentConfigResult:
        return self._configure_openai_compatible(provider=provider, **kwargs)

    def configure(
        self,
        model_provider: ModelProvider = ModelProvider.OPENAI_COMPATIBLE,
        **kwargs,
    ) -> AgentConfigResult:
        """Return agent-specific model, env vars, and mounts. Receives all build() kwargs."""
        model_provider = ModelProvider(model_provider)
        server_url = kwargs.pop("server_url", None)
        if model_provider not in self.supported_model_providers:
            raise ValueError(
                f"{self.name} does not support {model_provider.value}"
            )
        provider = resolve_provider(server_url, model_provider)
        if provider.model_provider == ModelProvider.OPENAI:
            return self._configure_openai(provider=provider, **kwargs)
        if provider.model_provider == ModelProvider.OPENROUTER:
            return self._configure_openrouter(provider=provider, **kwargs)
        return self._configure_openai_compatible(provider=provider, **kwargs)
