import json
import os
from pathlib import Path

from coding_agent_bench.agents.base import AgentConfig, AgentConfigResult
from coding_agent_bench.helpers.codex import codex_create_toml
from coding_agent_bench.providers import ModelProvider


class OracleAgentConfig(AgentConfig):
    """Non-LLM oracle agent. Passes the model through with no extra configuration."""

    name = "oracle"
    supported_model_providers = frozenset(
        {ModelProvider.OPENAI_COMPATIBLE, ModelProvider.OPENAI}
    )

    def configure(self, model_provider=ModelProvider.OPENAI_COMPATIBLE, **kwargs) -> AgentConfigResult:
        model_provider = ModelProvider(model_provider)
        if model_provider not in self.supported_model_providers:
            raise ValueError(f"oracle cannot use {model_provider.value}")
        return AgentConfigResult(model=kwargs["model_name"])


class ClaudeCodeAgentConfig(AgentConfig):
    """Claude Code agent. Configures Anthropic API env vars pointing at the served model."""

    name = "claude-code"
    version = "2.1.220"
    supported_model_providers = frozenset(
        {ModelProvider.OPENAI_COMPATIBLE, ModelProvider.OPENROUTER}
    )

    def _configure_openai_compatible(self, provider, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        agent_env = {
            "ANTHROPIC_BASE_URL": provider.base_url,
            "ANTHROPIC_MODEL": model_name,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model_name,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model_name,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model_name,
        }
        if provider.api_key:
            # OpenRouter's Claude Code integration expects a blank
            # ANTHROPIC_API_KEY and the key in ANTHROPIC_AUTH_TOKEN.
            agent_env["ANTHROPIC_API_KEY"] = ""
            agent_env["ANTHROPIC_AUTH_TOKEN"] = provider.api_key
        else:
            agent_env["ANTHROPIC_API_KEY"] = "sk-no-key-required"
        return AgentConfigResult(model=model_name, agent_env=agent_env)


class CodexAgentConfig(AgentConfig):
    """Codex agent. Generates a config.toml and bind-mounts it into the container."""

    name = "codex"
    version = "0.145.0"

    def _configure_openai_compatible(self, provider, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]

        outpath = Path("config.toml").absolute()
        codex_create_toml(
            model_name=model_name,
            server_url=provider.base_url,
            outpath=outpath,
            openrouter=provider.model_provider == ModelProvider.OPENROUTER,
        )
        print(f"Created config.toml at {outpath}")

        mounts = [
            {
                "type": "bind",
                "source": str(outpath),
                "target": "/root/.codex/config.toml",
            }
        ]

        agent_env = {"CODEX_HOME": "/root/.codex/"}
        if provider.api_key:
            agent_env[provider.api_key_env] = provider.api_key

        return AgentConfigResult(
            model="vllm/" + model_name,
            agent_env=agent_env,
            mounts=mounts,
        )

    def _configure_openai(self, provider, **kwargs) -> AgentConfigResult:
        # Harbor inherits OPENAI_API_KEY; agent_env would serialize it via --ae.
        return AgentConfigResult(model="openai/" + kwargs["model_name"])


class OpenClawAgentConfig(AgentConfig):
    """OpenClaw agent. Configures OpenAI-compatible API env vars."""

    name = "openclaw"
    version = "2026.6.1"

    def _configure_openai_compatible(self, provider, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        agent_env = {
            "OPENAI_BASE_URL": provider.base_url.rstrip("/").removesuffix("/v1") + "/v1",
            "OPENAI_API_KEY": provider.api_key or "sk-no-key-required",
        }
        return AgentConfigResult(model="vllm/" + model_name, agent_env=agent_env)

    def _configure_openai(self, provider, **kwargs) -> AgentConfigResult:
        # Harbor inherits OPENAI_API_KEY; agent_env would serialize it via --ae.
        return AgentConfigResult(model="openai/" + kwargs["model_name"])


class OpenCodeAgentConfig(AgentConfig):
    """OpenCode agent. Builds a JSON config with vLLM provider and context/output limits."""

    name = "opencode"
    version = "1.18.1"

    def _configure_openai_compatible(self, provider, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        model_max_len = kwargs.get("model_max_len", 262000)

        model = "vllm/" + model_name
        context_limit = int(model_max_len * 0.75)
        output_limit = int(model_max_len * 0.25)
        options = {"baseURL": provider.base_url.rstrip("/").removesuffix("/v1") + "/v1"}
        if provider.api_key:
            options["apiKey"] = provider.api_key
        opencode_config = {
            "$schema": "https://opencode.ai/config.json",
            "model": model,
            "provider": {
                "vllm": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "vLLM",
                    "options": options,
                    "models": {
                        model_name: {
                            "name": model_name,
                            "limit": {"context": context_limit, "output": output_limit},
                        }
                    },
                }
            },
        }

        agent_env = {
            "OPENCODE_CONFIG_CONTENT": json.dumps(opencode_config),
        }
        return AgentConfigResult(model=model, agent_env=agent_env)

    def _configure_openai(self, provider, **kwargs) -> AgentConfigResult:
        # Harbor inherits OPENAI_API_KEY; agent_env would serialize it via --ae.
        return AgentConfigResult(model="openai/" + kwargs["model_name"])


class OpenHandsSdkAgentConfig(AgentConfig):
    """OpenHands agent. Sets environment variables for a vLLM provider."""
    
    name = "openhands-sdk"
    supported_model_providers = frozenset({ModelProvider.OPENAI_COMPATIBLE})

    def _configure_openai_compatible(self, provider, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]

        # Set LLM API in host environment
        os.environ["LLM_API_KEY"] = "NONE"
        
        # Configure the environment
        model = "hosted_vllm/" + model_name
        api_base = provider.base_url.rstrip("/").removesuffix("/v1") + "/v1"

        agent_env = {
            "HOSTED_VLLM_API_BASE": api_base,
        }
        return AgentConfigResult(model=model, agent_env=agent_env)


class PiAgentConfig(AgentConfig):
    """Pi agent. Generates a models.json and bind-mounts it into the container."""

    name = "pi"
    version = "0.73.1"

    def _configure_openai_compatible(self, provider, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        model_max_len = kwargs.get("model_max_len", 262000)

        models_json = {
            "providers": {
                "vllm": {
                    "baseUrl": provider.base_url.rstrip("/").removesuffix("/v1") + "/v1",
                    "api": "openai-completions",
                    "apiKey": provider.api_key or "NONE",
                    "models": [
                        {
                            "id": model_name,
                            "name": model_name,
                            "contextWindow": model_max_len,
                        }
                    ],
                }
            }
        }

        tmp = Path("models.json").absolute()
        with open(tmp, "w") as f:
            json.dump(models_json, f)
        print(f"Created models.json at {tmp}")

        mounts = [
            {
                "type": "bind",
                "source": str(tmp),
                "target": "/root/.pi/agent/models.json",
            }
        ]

        agent_env = {"PI_OFFLINE": "1", "PI_CODING_AGENT_DIR": "/root/.pi/agent"}
        return AgentConfigResult(model="vllm/" + model_name, agent_env=agent_env, mounts=mounts)

    def _configure_openai(self, provider, **kwargs) -> AgentConfigResult:
        # Harbor inherits OPENAI_API_KEY; agent_env would serialize it via --ae.
        return AgentConfigResult(model="openai/" + kwargs["model_name"])
