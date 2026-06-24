from typing import Any, Literal
from pathlib import Path
import json
from enum import Enum
import os

from harbor.models.environment_type import EnvironmentType

from coding_agent_bench.helpers.codex import codex_create_toml


class SupportedAgent(str, Enum):
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

    def _build_claude_code_cmd(
        self,
        model_name: str,
        server_url: str,
        **kwargs,
    ) -> list[str]:

        # Build envvars for claude code
        agent_env = {
            "ANTHROPIC_BASE_URL": server_url,
            "ANTHROPIC_API_KEY": "sk-no-key-required",
            "ANTHROPIC_MODEL": model_name,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model_name,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model_name,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model_name,
        }

        return self._build_command(
            model=model_name,
            agent_env=agent_env,
            **kwargs,
        )

    def _build_codex_cmd(
        self,
        model_name: str,
        server_url: str,
        **kwargs,
    ) -> list[str]:

        # Create file for config.toml
        outpath = Path("config.toml").absolute()
        codex_create_toml(model_name=model_name, server_url=server_url, outpath=outpath)
        print(f"Created config.toml at {outpath}")

        # Create mounts
        mounts = [
            {
                "type": "bind",
                "source": str(outpath),
                "target": "/root/.codex/config.toml",
            }
        ]

        # Create agent env and model
        model = "vllm/" + model_name
        agent_env = {"CODEX_HOME": "/root/.codex/"}

        return self._build_command(
            model=model,
            mounts=mounts,
            agent_env=agent_env,
            **kwargs,
        )

    def _build_openclaw_cmd(
        self,
        model_name: str,
        server_url: str,
        **kwargs
    ):
        # Create agent env and model
        model = "vllm/" + model_name
        agent_env = {
            "OPENAI_BASE_URL": server_url.rstrip("/") + "/v1",
            "OPENAI_API_KEY": "sk-no-key-required",
        }
        
        return self._build_command(
            model=model,
            agent_env=agent_env,
            **kwargs,
        )

    def _build_opencode_cmd(
        self,
        model_name: str,
        server_url: str,
        model_max_len: int = 262000,
        **kwargs,
    ) -> list[str]:

        # Create OpenCode config
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

        # Create agent env
        agent_env = {
            "OPENCODE_CONFIG_CONTENT": json.dumps(opencode_config),
        }

        return self._build_command(
            model=model,
            agent_env=agent_env,
            **kwargs,
        )

    def _build_pi_cmd(
        self,
        model_name: str,
        server_url: str,
        model_max_len: int = 262000,
        **kwargs,
    ) -> list[str]:

        # Create Pi models.json
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

        # Create file for models.json
        tmp = Path("models.json").absolute()
        with open(tmp, "w") as f:
            json.dump(models_json, f)
        print(f"Created models.json at {tmp}")

        # Create mounts
        mounts = [
            {
                "type": "bind",
                "source": str(tmp),
                "target": "/root/.pi/agent/models.json",
            }
        ]

        # Create agent env and model
        agent_env = {"PI_OFFLINE": "1", "PI_CODING_AGENT_DIR": "/root/.pi/agent"}
        model = "vllm/" + model_name

        return self._build_command(
            model=model,
            mounts=mounts,
            agent_env=agent_env,
            **kwargs,
        )

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

        if agent == SupportedAgent.claude_code.value:
            cmd = self._build_claude_code_cmd(
                agent=agent,
                dataset=dataset,
                environment=environment,
                model_name=model_name,
                server_url=server_url,
                model_max_len=model_max_len,
                dataset_pattern=dataset_pattern,
                n_concurrent=n_concurrent,
                n_tasks=n_tasks,
                job_name=job_name,
                **kwargs,
            )
        elif agent == SupportedAgent.codex.value:
            cmd = self._build_codex_cmd(
                agent=agent,
                dataset=dataset,
                environment=environment,
                model_name=model_name,
                server_url=server_url,
                model_max_len=model_max_len,
                dataset_pattern=dataset_pattern,
                n_concurrent=n_concurrent,
                n_tasks=n_tasks,
                job_name=job_name,
                **kwargs,
            )
        elif agent == SupportedAgent.openclaw.value:
            cmd = self._build_openclaw_cmd(
                agent=agent,
                dataset=dataset,
                environment=environment,
                model_name=model_name,
                server_url=server_url,
                model_max_len=model_max_len,
                dataset_pattern=dataset_pattern,
                n_concurrent=n_concurrent,
                n_tasks=n_tasks,
                job_name=job_name,
                **kwargs,
            )
        elif agent == SupportedAgent.opencode.value:
            cmd = self._build_opencode_cmd(
                agent=agent,
                dataset=dataset,
                environment=environment,
                model_name=model_name,
                server_url=server_url,
                model_max_len=model_max_len,
                dataset_pattern=dataset_pattern,
                n_concurrent=n_concurrent,
                n_tasks=n_tasks,
                job_name=job_name,
                **kwargs,
            )
        elif agent == SupportedAgent.pi.value:
            cmd = self._build_pi_cmd(
                agent=agent,
                dataset=dataset,
                environment=environment,
                model_name=model_name,
                server_url=server_url,
                model_max_len=model_max_len,
                dataset_pattern=dataset_pattern,
                n_concurrent=n_concurrent,
                n_tasks=n_tasks,
                job_name=job_name,
                **kwargs,
            )
        else:
            raise ValueError(
                f"Unsupported agent type. Please choose from: {[e.value for e in SupportedAgent]}."
            )

        # Find job path
        job_path = self.jobs_dir / job_name

        # If dry_run, return the command and job path
        return cmd, job_path
