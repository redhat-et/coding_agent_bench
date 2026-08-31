from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ModelProvider(str, Enum):
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai-compatible"


@dataclass
class AgentConfigResult:
    """Agent-specific overrides returned by AgentConfig.configure()."""

    model: str
    agent_env: dict[str, str] | None = None
    mounts: list[dict[str, Any]] | None = None
    required_host_env: tuple[str, ...] = ()


class AgentConfig(ABC):
    """Base class for agent configurations. Subclass this to add a new agent."""

    name: str
    version: str | None = None
    supported_model_providers = frozenset(ModelProvider)

    def _configure_openai_compatible(self, **kwargs) -> AgentConfigResult:
        raise NotImplementedError(
            f"{self.name} does not support OpenAI-compatible endpoints"
        )

    def _configure_openai(self, **kwargs) -> AgentConfigResult:
        raise NotImplementedError(f"{self.name} does not support OpenAI")

    def configure(
        self, model_provider: ModelProvider, **kwargs
    ) -> AgentConfigResult:
        """Return agent-specific model, env vars, and mounts. Receives all build() kwargs."""
        if model_provider not in self.supported_model_providers:
            raise ValueError(f"{self.name} does not support {model_provider.value}")
        if model_provider == ModelProvider.OPENAI:
            return self._configure_openai(**kwargs)
        return self._configure_openai_compatible(**kwargs)
