from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentConfigResult:
    """Agent-specific overrides returned by AgentConfig.configure()."""

    model: str
    agent_env: dict[str, str] | None = None
    mounts: list[dict[str, Any]] | None = None


class AgentConfig(ABC):
    """Base class for agent configurations. Subclass this to add a new agent."""

    name: str

    @abstractmethod
    def configure(self, **kwargs) -> AgentConfigResult:
        """Return agent-specific model, env vars, and mounts. Receives all build() kwargs."""
        ...
