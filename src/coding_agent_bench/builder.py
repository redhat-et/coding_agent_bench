from typing import Any, Literal
from pathlib import Path
import json
from enum import Enum
import os

from harbor.models.environment_type import EnvironmentType

from coding_agent_bench.agents import get_agent_config


class SupportedAgent(str, Enum):

    oracle = "oracle"
    claude_code = "claude-code"
    codex = "codex"
    openclaw = "openclaw"
    opencode = "opencode"
    pi = "pi"


class HarborCommandBuilder:
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
        **kwargs,
    ) -> list[str]:
        args = []

        # Add agent
        args += ["--agent", agent]

        # Pin openclaw to last known working version (2026.7.1+ requires
        # interactive onboarding that breaks headless/container runs)
        if agent == "openclaw":
            args += ["--ak", "version=2026.6.1"]

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
        if environment == "openshift" and "openshift" not in EnvironmentType:
            args += [
                "--environment-import-path",
                "coding_agent_bench.harbor_envs.openshift:OpenshiftEnvironment",
            ]
        else:
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

        # Execute the job
        cmd = ["harbor", "run", "--debug", *args]

        return cmd

    def build(
        self,
        agent: str,
        dataset: str,
        model_name: str,
        server_url: str,
        environment: Literal["docker", "openshift"],
        dataset_pattern: str = None,
        n_concurrent: int = 1,
        n_tasks: int = None,
        model_max_len: int = 262000,
        job_name: str = "default",
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
        result = agent_config.configure(
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
        )

        job_path = self.jobs_dir / job_name
        return cmd, job_path
