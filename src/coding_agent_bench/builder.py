from typing import Any, Literal
from pathlib import Path
import json
from enum import Enum
import os

from harbor.models.environment_type import EnvironmentType

from coding_agent_bench.agents import ModelProvider, get_agent_config


class SupportedAgent(str, Enum):

    oracle = "oracle"
    claude_code = "claude-code"
    codex = "codex"
    openclaw = "openclaw"
    opencode = "opencode"
    pi = "pi"


class HarborCommandBuilder:
    DEFAULT_MAX_RETRIES = 1
    DEFAULT_RETRY_INCLUDE = [
        "AgentTimeoutError",
        "NonZeroAgentExitCodeError",
        "ApiRateLimitError",
        "ApiUsageLimitError",
    ]

    def __init__(self):
        self.jobs_dir = Path(os.getcwd()) / "jobs"

    def _build_command(
        self,
        agent: str,
        dataset: str,
        model: str,
        environment: Literal["docker", "openshift"],
        mounts: list[dict[str, str]] = None,
        n_concurrent: int = 1,
        agent_env: dict[str, Any] = None,
        task_include_pattern: str = None,
        n_tasks: int = None,
        job_name: str = None,
        agent_version: str = None,
        max_retries: int = None,
        retry_include: list[str] = None,
        **kwargs,
    ) -> list[str]:
        args = []

        # Add agent
        args += ["--agent", agent]

        # Pin agent version: "latest" = skip pin, CLI override > class default
        if agent_version == "latest":
            version = None
        else:
            agent_config = get_agent_config(agent)
            version = agent_version or agent_config.version
        if version:
            args += ["--ak", f"version={version}"]

        # Add dataset
        if Path(dataset).exists():
            args += ["-p", dataset]
        else:
            args += ["-d", dataset]
        if task_include_pattern is not None:
            args += ["-i", task_include_pattern]

        # Add model
        args += ["--model", model]

        # Add agent envvars
        if agent_env is not None:
            for key, value in agent_env.items():
                args += ["--ae", f"{key}={value}"]

        # Add environment
        args += ["--env", environment]

        # Add mounts
        if mounts is not None:
            args += ["--mounts-json", json.dumps(mounts)]

        # Add number of concurrent tasks
        args += ["--n-concurrent", str(n_concurrent)]

        # Add total number of tasks
        if n_tasks is not None:
            args += ["--n-tasks", str(n_tasks)]

        # Add output path args
        if job_name is not None:
            args += ["--job-name", job_name]

        # Add retry configuration
        retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        includes = retry_include if retry_include is not None else self.DEFAULT_RETRY_INCLUDE
        args += ["--max-retries", str(retries)]
        for exc in includes:
            args += ["--retry-include", exc]

        # Execute the job
        cmd = ["harbor", "run", "--debug", *args]

        return cmd

    def build(
        self,
        agent: str,
        dataset: str,
        model_name: str,
        environment: Literal["docker", "openshift"],
        model_provider: ModelProvider = ModelProvider.OPENAI_COMPATIBLE,
        server_url: str | None = None,
        dataset_pattern: str = None,
        n_concurrent: int = 1,
        n_tasks: int = None,
        model_max_len: int = 262000,
        job_name: str = "default",
        agent_version: str = None,
        max_retries: int = None,
        retry_include: list[str] = None,
        **kwargs,
    ) -> tuple[list[str], Path]:
        """
        Run a harbor job.

        Returns:
            list[str]: Constructed command for the job.
            Path: Path to the job output directory.
        """
        if environment not in ["docker", "openshift"]:
            raise ValueError(f"Invalid environment: {environment}")

        agent_config = get_agent_config(agent)
        try:
            model_provider = ModelProvider(model_provider)
        except ValueError:
            supported = ", ".join(provider.value for provider in ModelProvider)
            raise ValueError(
                f"Unsupported model provider '{model_provider}'. Choose from: {supported}"
            ) from None
        if agent_config.name != "oracle":
            if model_provider == ModelProvider.OPENAI_COMPATIBLE and not server_url:
                raise ValueError(
                    "server_url is required for OpenAI-compatible endpoints"
                )
            if model_provider == ModelProvider.OPENAI and server_url:
                raise ValueError("server_url does not apply to the OpenAI provider")
            if model_provider == ModelProvider.OPENROUTER and server_url:
                raise ValueError("server_url does not apply to the OpenRouter provider")

        result = agent_config.configure(
            model_provider=model_provider,
            model_name=model_name,
            server_url=server_url,
            model_max_len=model_max_len,
            **kwargs,
        )

        cmd = self._build_command(
            agent=agent,
            dataset=dataset,
            model=result.model,
            environment=environment,
            mounts=result.mounts,
            n_concurrent=n_concurrent,
            agent_env=result.agent_env,
            task_include_pattern=dataset_pattern,
            n_tasks=n_tasks,
            job_name=job_name,
            agent_version=agent_version,
            max_retries=max_retries,
            retry_include=retry_include,
        )

        job_path = self.jobs_dir / job_name
        return cmd, job_path
