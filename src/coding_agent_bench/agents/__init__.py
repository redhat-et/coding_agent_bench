from coding_agent_bench.agents.base import AgentConfig
from coding_agent_bench.agents.configs import (
    ClaudeCodeAgentConfig,
    CodexAgentConfig,
    OpenClawAgentConfig,
    OpenCodeAgentConfig,
    OracleAgentConfig,
    PiAgentConfig,
)

AGENT_CONFIGS: list[type[AgentConfig]] = [
    OracleAgentConfig,
    ClaudeCodeAgentConfig,
    CodexAgentConfig,
    OpenClawAgentConfig,
    OpenCodeAgentConfig,
    PiAgentConfig,
]

AGENT_REGISTRY: dict[str, AgentConfig] = {cls.name: cls() for cls in AGENT_CONFIGS}


def get_agent_config(name: str) -> AgentConfig:
    """Look up an agent config by name. Raises ValueError if not found."""
    config = AGENT_REGISTRY.get(name)
    if config is None:
        raise ValueError(
            f"Unsupported agent type '{name}'. Choose from: {list(AGENT_REGISTRY.keys())}"
        )
    return config
