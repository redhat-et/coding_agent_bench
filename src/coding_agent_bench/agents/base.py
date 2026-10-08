from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentConfigResult:
    """Agent-specific overrides returned by AgentConfig.configure()."""

    model: str
    agent_env: dict[str, str] | None = None
    mounts: list[dict[str, Any]] | None = None
    agent_kwargs: dict[str, Any] | None = None


class AgentConfig(ABC):
    """Base class for agent configurations. Subclass this to add a new agent."""

    name: str
    version: str | None = None

    @abstractmethod
    def configure(self, **kwargs) -> AgentConfigResult:
        """Return agent-specific model, env vars, and mounts. Receives all build() kwargs."""
        ...

    def restore_mounts(self, config: dict[str, Any], server_url: str) -> None:
        """Regenerate external bind-mounted config files after a job is restored.

        Override this for agents whose configure() method creates mount sources
        outside the Harbor job directory. Most agents need no restoration work.
        """
