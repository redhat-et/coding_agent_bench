from typing import Any, Literal
from pathlib import Path
import json
from enum import Enum
import os

from coding_agent_bench.agents import get_agent_config
from coding_agent_bench.subagents import (
    SUBAGENT_POLICY_INLINE_PREFIX,
    materialize_inline_policy,
)


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
        """Initialize a builder rooted at the current process working directory."""
        self.jobs_dir = Path(os.getcwd()) / "jobs"

    def _build_command(
        self,
        agent: str,
        dataset: str,
        model: str,
        environment: Literal["docker", "openshift"],
        mounts: list[dict[str, str]] = None,
        n_concurrent: int | None = 1,
        agent_env: dict[str, Any] = None,
        agent_kwargs: dict[str, Any] = None,
        task_include_pattern: str = None,
        n_tasks: int = None,
        job_name: str = None,
        agent_version: str = None,
        max_retries: int = None,
        retry_include: list[str] = None,
        skills: list[str] = None,
        subagent_policy: str | Path | None = None,
        extra_harbor_args: list[str] = None,
        **kwargs,
    ) -> list[str]:
        """Construct the Harbor CLI arguments for a configured benchmark run."""
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
        if subagent_policy is not None:
            args += ["--extra-instruction-path", str(subagent_policy)]

        # Add model
        args += ["--model", model]

        # Add agent envvars
        if agent_env is not None:
            for key, value in agent_env.items():
                args += ["--ae", f"{key}={value}"]
        # Add agent kwargs
        if agent_kwargs is not None:
            for key, value in agent_kwargs.items():
                args += ["--ak", f"{key}={value}"]
        # Add environment
        args += ["--env", environment]
        harbor_parent = os.environ.get("HARBOR_PARENT")
        if environment == "openshift" and harbor_parent:
            args += [
                "--ek",
                f"persistent_env={json.dumps({'HARBOR_PARENT': harbor_parent})}",
            ]
        # Add mounts
        if mounts is not None:
            args += ["--mounts-json", json.dumps(mounts)]

        # Add agent skills using Harbor's repeatable native flag.
        for skill in skills or []:
            args += ["--skill", skill]

        # Add number of concurrent tasks when explicitly requested. Omitting the
        # flag lets the Harbor/queue defaults apply.
        if n_concurrent is not None:
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

        # Append arbitrary Harbor arguments after generated configuration.
        args += extra_harbor_args or []

        # Execute the job
        cmd = ["harbor", "run", "--debug", *args]
        if os.environ.get("CAB_PAUSE_REQUEST_PATH"):
            from coding_agent_bench.preemption import PAUSE_PLUGIN

            cmd += ["--plugin", PAUSE_PLUGIN]

        return cmd

    def build(
        self,
        agent: str,
        dataset: str,
        model_name: str,
        server_url: str,
        environment: Literal["docker", "openshift"],
        dataset_pattern: str = None,
        n_concurrent: int | None = 1,
        n_tasks: int = None,
        model_max_len: int | None = None,
        job_name: str = "default",
        agent_version: str = None,
        max_retries: int = None,
        retry_include: list[str] = None,
        skills: list[str] = None,
        subagents: list[str | Path] | None = None,
        subagent_policy: str | Path | None = None,
        extra_harbor_args: list[str] = None,
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
        if (subagents or subagent_policy) and agent != SupportedAgent.opencode:
            raise ValueError("Subagents are only supported with --agent opencode")
        if subagent_policy is not None and not subagents:
            raise ValueError("--subagent-policy requires at least one --subagent")
        if model_max_len is None:
            # Keep model-specific limits in the queue's ModelConfig registry rather
            # than requiring every caller to duplicate them in its request.
            from coding_agent_bench.models import MODEL_REGISTRY

            model_config = MODEL_REGISTRY.get(model_name)
            model_max_len = model_config.model_max_len if model_config else 262000

        agent_config = get_agent_config(agent)
        result = agent_config.configure(
            model_name=model_name,
            server_url=server_url,
            model_max_len=model_max_len,
            subagents=subagents,
            subagent_policy=subagent_policy,
            **kwargs,
        )

        effective_subagent_policy = (
            materialize_inline_policy(subagent_policy)
            if subagent_policy is not None
            else None
        )
        try:
            cmd = self._build_command(
                agent=agent,
                dataset=dataset,
                model=result.model,
                environment=environment,
                mounts=result.mounts,
                n_concurrent=n_concurrent,
                agent_env=result.agent_env,
                agent_kwargs=result.agent_kwargs,
                task_include_pattern=dataset_pattern,
                n_tasks=n_tasks,
                job_name=job_name,
                agent_version=agent_version,
                max_retries=max_retries,
                retry_include=retry_include,
                skills=skills,
                subagent_policy=effective_subagent_policy,
                extra_harbor_args=extra_harbor_args,
            )
        except Exception:
            if (
                subagent_policy is not None
                and str(subagent_policy).startswith(SUBAGENT_POLICY_INLINE_PREFIX)
            ):
                effective_subagent_policy.unlink(missing_ok=True)
            raise

        job_path = self.jobs_dir / job_name
        return cmd, job_path
