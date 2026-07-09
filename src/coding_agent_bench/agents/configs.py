import json
import os
from pathlib import Path

from coding_agent_bench.agents.base import AgentConfig, AgentConfigResult
from coding_agent_bench.helpers.codex import codex_create_toml


class OracleAgentConfig(AgentConfig):
    """Non-LLM oracle agent. Passes the model through with no extra configuration."""

    name = "oracle"

    def configure(self, **kwargs) -> AgentConfigResult:
        return AgentConfigResult(model=kwargs["model_name"])


class ClaudeCodeAgentConfig(AgentConfig):
    """Claude Code agent. Configures Anthropic API env vars pointing at the served model."""

    name = "claude-code"

    def configure(self, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        server_url = kwargs["server_url"]
        agent_env = {
            "ANTHROPIC_BASE_URL": server_url,
            "ANTHROPIC_API_KEY": "sk-no-key-required",
            "ANTHROPIC_MODEL": model_name,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model_name,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model_name,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model_name,
        }
        return AgentConfigResult(model=model_name, agent_env=agent_env)


class CodexAgentConfig(AgentConfig):
    """Codex agent. Generates a config.toml and bind-mounts it into the container."""

    name = "codex"

    def configure(self, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        server_url = kwargs["server_url"]

        outpath = Path("config.toml").absolute()
        codex_create_toml(model_name=model_name, server_url=server_url, outpath=outpath)
        print(f"Created config.toml at {outpath}")

        mounts = [
            {
                "type": "bind",
                "source": str(outpath),
                "target": "/root/.codex/config.toml",
            }
        ]

        return AgentConfigResult(
            model="vllm/" + model_name,
            agent_env={"CODEX_HOME": "/root/.codex/"},
            mounts=mounts,
        )


class OpenClawAgentConfig(AgentConfig):
    """OpenClaw agent. Configures OpenAI-compatible API env vars."""

    name = "openclaw"

    def configure(self, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        server_url = kwargs["server_url"]
        agent_env = {
            "OPENAI_BASE_URL": server_url.rstrip("/") + "/v1",
            "OPENAI_API_KEY": "sk-no-key-required",
        }
        return AgentConfigResult(model="vllm/" + model_name, agent_env=agent_env)


class OpenCodeAgentConfig(AgentConfig):
    """OpenCode agent. Builds a JSON config with vLLM provider and context/output limits."""

    name = "opencode"

    def configure(self, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        server_url = kwargs["server_url"]
        model_max_len = kwargs.get("model_max_len", 262000)

        model = "vllm/" + model_name
        context_limit = int(model_max_len * 0.75)
        output_limit = int(model_max_len * 0.25)
        opencode_config = {
            "$schema": "https://opencode.ai/config.json",
            "model": model,
            "provider": {
                "vllm": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "vLLM",
                    "options": {"baseURL": server_url.rstrip("/") + "/v1"},
                    "models": {
                        "qwen3.6-35b": {
                            "name": "qwen3.6-35b",
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


class OpenHandsSdkAgentConfig(AgentConfig):
    """OpenHands agent. Sets environment variables for a vLLM provider."""
    
    name = "openhands-sdk"

    def configure(self, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        server_url = kwargs["server_url"]

        # Set LLM API in host environment
        os.environ["LLM_API_KEY"] = "NONE"
        
        # Configure the environment
        model = "hosted_vllm/" + model_name
        api_base = server_url.rstrip("/") + "/v1"

        agent_env = {
            "HOSTED_VLLM_API_BASE": api_base,
        }
        return AgentConfigResult(model=model, agent_env=agent_env)


class PiAgentConfig(AgentConfig):
    """Pi agent. Generates a models.json and bind-mounts it into the container."""

    name = "pi"

    def configure(self, **kwargs) -> AgentConfigResult:
        model_name = kwargs["model_name"]
        server_url = kwargs["server_url"]
        model_max_len = kwargs.get("model_max_len", 262000)

        models_json = {
            "providers": {
                "vllm": {
                    "baseUrl": server_url.rstrip("/") + "/v1",
                    "api": "openai-completions",
                    "apiKey": "NONE",
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
