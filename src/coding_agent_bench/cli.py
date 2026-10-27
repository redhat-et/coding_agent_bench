from pathlib import Path
import os
import signal
import subprocess
import sys
from typing import Annotated, Optional
import shlex

import click
import typer
from typer.core import TyperCommand

from coding_agent_bench.builder import HarborCommandBuilder, SupportedAgent
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.providers import is_openrouter
from coding_agent_bench.manifest import deploy as deploy_model
from coding_agent_bench.manifest import generate
from coding_agent_bench.utils import (
    cmd_to_string,
    envs_to_export_lines,
    parse_envs,
    validate_extra_harbor_flags,
    validate_remote_skill_sources,
)

def _duplicate_option(args: list[str], parameters) -> str | None:
    """Find the first repeated non-repeatable option in raw arguments."""
    option_params = {
        option: parameter
        for parameter in parameters
        for option in (
            list(getattr(parameter, "opts", []))
            + list(getattr(parameter, "secondary_opts", []))
        )
    }
    seen: set[str] = set()
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--":
            break
        option = token.split("=", 1)[0] if token.startswith("-") else None
        parameter = option_params.get(option)
        if parameter is not None:
            canonical = parameter.name
            if not getattr(parameter, "multiple", False):
                if canonical in seen:
                    return option
                seen.add(canonical)
            if (
                not getattr(parameter, "is_flag", False)
                and "=" not in token
                and index + 1 < len(args)
            ):
                index += 1
        index += 1
    return None


class NoDuplicateOptionsCommand(TyperCommand):
    """Reject repeated non-repeatable CAB options before Click overwrites them."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        duplicate = _duplicate_option(args, self.params)
        if duplicate:
            raise click.UsageError(
                f"Option {duplicate!r} was provided more than once", ctx
            )
        return super().parse_args(ctx, args)


class DuplicateCheckingTyper(typer.Typer):
    """Print duplicate-option errors cleanly for the installed console script."""

    def __call__(self, *args, **kwargs):
        if len(sys.argv) > 1 and sys.argv[1] == "run":
            from typer.main import get_command

            command = get_command(self)
            run_command = command.commands["run"]
            duplicate = _duplicate_option(sys.argv[2:], run_command.params)
            if duplicate:
                typer.echo(
                    f"Error: option {duplicate!r} was provided more than once",
                    err=True,
                )
                raise SystemExit(2)
        return super().__call__(*args, **kwargs)


app = DuplicateCheckingTyper()


def get_cab_option_names() -> set[str]:
    """Return all option spellings registered on the CAB CLI command."""
    from typer.main import get_command

    command = get_command(app)
    command = command.commands["run"] if hasattr(command, "commands") else command
    return {
        option
        for parameter in command.params
        for option in (
            list(getattr(parameter, "opts", []))
            + list(getattr(parameter, "secondary_opts", []))
        )
    }


@app.command(
    cls=NoDuplicateOptionsCommand,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run(
    ctx: typer.Context,
    agent: Annotated[
        SupportedAgent,
        typer.Option(help="Agent to use"),
    ],
    dataset: Annotated[str, typer.Option(help="Dataset name or path")],
    model_name: Annotated[str, typer.Option(help="Model name")],
    server_url: Annotated[str, typer.Option(help="Model server URL")],
    environment: Annotated[
        str, typer.Option(help="Environment: docker or openshift")
    ] = "docker",
    job_name: Annotated[str, typer.Option(help="Name to give the job")] = "default",
    dataset_pattern: Annotated[
        Optional[str], typer.Option(help="Pattern to filter dataset tasks")
    ] = None,
    n_concurrent: Annotated[int, typer.Option(help="Number of concurrent tasks")] = 1,
    n_tasks: Annotated[
        Optional[int], typer.Option(help="Total number of tasks to run")
    ] = None,
    model_max_len: Annotated[
        int, typer.Option(help="Maximum model context length in tokens")
    ] = 262000,
    remote: Annotated[
        bool,
        typer.Option(
            help="Run in the logged in Openshift namespace. Only availble with `--environment=openshift`"
        ),
    ] = False,
    before_script: Annotated[
        Optional[str], typer.Option(help="Script to run before the job starts. Only available with `--remote`.")
    ] = None,
    agent_version: Annotated[
        Optional[str], typer.Option(help="Pin agent to a specific version (overrides agent_versions.toml)")
    ] = None,
    leaderboard_metadata: Annotated[
        Optional[Path], typer.Option(help="Optional overrides for automatically collected job metadata")
    ] = None,
    leaderboard_metadata_json: Annotated[
        Optional[str], typer.Option(help="Inline leaderboard metadata JSON (used by the queue)")
    ] = None,
    max_retries: Annotated[
        Optional[int], typer.Option(help="Max retry attempts per task (default: 1)")
    ] = None,
    retry_include: Annotated[
        Optional[list[str]], typer.Option(help="Error types to retry (repeatable)")
    ] = None,
    skills: Annotated[
        Optional[list[str]],
        typer.Option(
            "--skill",
            "--skills",
            help="Path or git source (org/name[@ref], URL) for skill directories. Can be used multiple times.",
        ),
    ] = None,
    envs: Annotated[
        Optional[list[str]],
        typer.Option(
            help="Extra environment variables for the harbor process, KEY=VALUE entries (repeatable; each entry may also contain comma-separated pairs, e.g. --envs FOO=bar --envs BAZ=qux)"
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option(help="Dry run mode, does not execute the job")
    ] = False,
):
    """Run a benchmark with full Harbor configuration support."""
    from coding_agent_bench.leaderboard_results import (
        job_metadata, runtime_github_source, save_metadata, try_export_on_completion,
    )

    if leaderboard_metadata is not None and leaderboard_metadata_json is not None:
        raise typer.BadParameter("Use only one leaderboard metadata option")
    metadata = None
    if leaderboard_metadata is not None or leaderboard_metadata_json is not None:
        import json

        try:
            metadata = json.loads(leaderboard_metadata.read_text() if leaderboard_metadata is not None else leaderboard_metadata_json)
            if not isinstance(metadata, dict):
                raise ValueError("Leaderboard metadata must be a JSON object")
        except (OSError, ValueError) as error:
            raise typer.BadParameter(str(error)) from error
    # Raise error if remote is used and environment is not openshift
    if remote and environment != "openshift":
        raise ValueError("Remote mode is only available with `--environment=openshift`")

    try:
        extra_envs = parse_envs(envs)
        extra_harbor_args = list(ctx.args)
        validate_extra_harbor_flags(extra_harbor_args, get_cab_option_names())
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e

    # If remote, run as a job
    if remote:
        try:
            validate_remote_skill_sources(skills)
        except ValueError as exc:
            raise typer.BadParameter(str(exc), param_hint="--skill") from exc
        if dry_run:
            typer.echo("Error: Cannot use `--remote` with `--dry-run`. Dry run mode is not available on remote")
        typer.echo("Running job on remote server...")
        job = OpenshiftJob(job_name=job_name)
        remote_args = [a for a in sys.argv[1:] if a not in ("--remote", "--dry-run")]
        if metadata is not None:
            # A client-side file path is not available in the remote pod.
            filtered = []
            arguments = iter(remote_args)
            for argument in arguments:
                if argument in ("--leaderboard-metadata", "--leaderboard-metadata-json"):
                    next(arguments, None)
                elif not argument.startswith(("--leaderboard-metadata=", "--leaderboard-metadata-json=")):
                    filtered.append(argument)
            remote_args = [*filtered, "--leaderboard-metadata-json", json.dumps(metadata)]
        command = ["coding-agent-bench", "run", *remote_args]
        
        # Parse before script if provided
        _before_script = None
        if before_script is not None:
            try:
                _before_script = shlex.split(before_script)
            except Exception as e:
                typer.echo(f"Error: Failed to parse before_script: {e}")
        
        # Create the job
        try:
            job.run(command, _before_script, openrouter=is_openrouter(server_url))
        except KeyboardInterrupt:
            typer.echo("\nInterrupted — cleaning up remote job...")
            job.cleanup()
            raise SystemExit(130)
        typer.echo("Job started successfully")

    else:
        builder = HarborCommandBuilder()
        harbor_command, job_dir = builder.build(
            agent=agent,
            dataset=dataset,
            model_name=model_name,
            server_url=server_url,
            environment=environment,
            dataset_pattern=dataset_pattern,
            n_concurrent=n_concurrent,
            n_tasks=n_tasks,
            model_max_len=model_max_len,
            job_name=job_name,
            agent_version=agent_version,
            max_retries=max_retries,
            retry_include=retry_include,
            skills=skills,
            extra_harbor_args=extra_harbor_args,
        )
        preview = ""
        if dry_run:
            export_lines = envs_to_export_lines(extra_envs)
            preview = f"{export_lines}\n" if export_lines else ""
        typer.echo(f"Job command:\n{preview}{cmd_to_string(harbor_command)}\n")

        if dry_run:
            return

        metadata = job_metadata(
            dataset, model_name, agent.value, version=agent_version, skills=skills,
            overrides=metadata, github_source=runtime_github_source(dataset),
        )
        save_metadata(job_dir, metadata)
        proc = subprocess.Popen(harbor_command, env={**os.environ, **extra_envs})
        try:
            proc.wait()
        except KeyboardInterrupt:
            typer.echo("\nInterrupted — waiting for harbor to shut down...")
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                typer.echo("Harbor did not exit in time, terminating...")
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            try_export_on_completion(job_dir, 130)
            raise SystemExit(130)
        typer.echo(f"Job output dir: {job_dir}")
        try_export_on_completion(job_dir, proc.returncode)
        # The pod's logging/upload wrapper must observe Harbor's failure status.
        raise typer.Exit(proc.returncode if proc.returncode >= 0 else 128 - proc.returncode)


@app.command()
def generate_manifest(
    model_id: Annotated[str, typer.Argument(help="HuggingFace model ID (e.g., RedHatAI/Qwen3.6-27B-FP8)")],
    reasoning_parser: Annotated[
        Optional[str], typer.Option(help="vLLM reasoning parser (e.g., qwen3, nemotron_v3)")
    ] = None,
    tool_call_parser: Annotated[
        Optional[str], typer.Option(help="vLLM tool-call parser (e.g., qwen3_coder, mistral)")
    ] = None,
    chat_template_kwargs: Annotated[
        Optional[str], typer.Option(help="JSON string for --default-chat-template-kwargs")
    ] = None,
    vllm_arg: Annotated[
        Optional[list[str]], typer.Option(help="Extra vLLM arg (repeatable)")
    ] = None,
    gpu_pool: Annotated[
        Optional[str], typer.Option(help="Override GPU pool (e.g., small, large, xlarge)")
    ] = None,
    gpu_pools_file: Annotated[
        Optional[Path], typer.Option(help="Path to YAML file defining available GPU pools")
    ] = None,
    max_model_len: Annotated[
        Optional[int], typer.Option(help="Override max model length")
    ] = None,
    namespace: Annotated[
        str, typer.Option(help="OpenShift namespace")
    ] = "coding-agent-leaderboard",
    vllm_image: Annotated[
        str, typer.Option(help="vLLM container image")
    ] = "vllm/vllm-openai:v0.23.0",
    route_timeout: Annotated[
        str, typer.Option(help="HAProxy route timeout")
    ] = "600s",
    app_name: Annotated[
        Optional[str], typer.Option(help="Override app/resource name")
    ] = None,
    served_model_name: Annotated[
        Optional[str], typer.Option(help="Override served model name")
    ] = None,
    output: Annotated[
        Optional[Path], typer.Option("-o", "--output", help="Output file (default: stdout)")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option(help="Show calculations only, no YAML")
    ] = False,
    anyuid: Annotated[
        bool, typer.Option(help="Include anyuid SCC RoleBinding (required for vLLM >v0.22)")
    ] = False,
    before_script: Annotated[
        Optional[str], typer.Option(help="Shell command to run before vLLM starts (e.g., download a custom parser)")
    ] = None,
):
    """Generate a vLLM OpenShift deployment manifest from a HuggingFace model ID."""
    try:
        generate(
            model_id=model_id,
            reasoning_parser=reasoning_parser,
            tool_call_parser=tool_call_parser,
            chat_template_kwargs=chat_template_kwargs,
            extra_vllm_args=vllm_arg,
            gpu_pool_override=gpu_pool,
            gpu_pools_file=gpu_pools_file,
            max_model_len_override=max_model_len,
            namespace=namespace,
            vllm_image=vllm_image,
            route_timeout=route_timeout,
            app_name_override=app_name,
            served_model_name_override=served_model_name,
            output=output,
            dry_run=dry_run,
            anyuid=anyuid,
            before_script=before_script,
        )
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@app.command()
def deploy(
    model_id: Annotated[str, typer.Argument(help="HuggingFace model ID (e.g., RedHatAI/Qwen3.6-27B-FP8)")],
    reasoning_parser: Annotated[
        Optional[str], typer.Option(help="vLLM reasoning parser (e.g., qwen3, nemotron_v3)")
    ] = None,
    tool_call_parser: Annotated[
        Optional[str], typer.Option(help="vLLM tool-call parser (e.g., qwen3_coder, mistral)")
    ] = None,
    chat_template_kwargs: Annotated[
        Optional[str], typer.Option(help="JSON string for --default-chat-template-kwargs")
    ] = None,
    vllm_arg: Annotated[
        Optional[list[str]], typer.Option(help="Extra vLLM arg (repeatable)")
    ] = None,
    gpu_pool: Annotated[
        Optional[str], typer.Option(help="Override GPU pool (e.g., small, large, xlarge)")
    ] = None,
    gpu_pools_file: Annotated[
        Optional[Path], typer.Option(help="Path to YAML file defining available GPU pools")
    ] = None,
    max_model_len: Annotated[
        Optional[int], typer.Option(help="Override max model length")
    ] = None,
    namespace: Annotated[
        str, typer.Option(help="OpenShift namespace")
    ] = "coding-agent-leaderboard",
    vllm_image: Annotated[
        str, typer.Option(help="vLLM container image")
    ] = "vllm/vllm-openai:v0.23.0",
    route_timeout: Annotated[
        str, typer.Option(help="HAProxy route timeout")
    ] = "600s",
    app_name: Annotated[
        Optional[str], typer.Option(help="Override app/resource name")
    ] = None,
    served_model_name: Annotated[
        Optional[str], typer.Option(help="Override served model name")
    ] = None,
    scale_down: Annotated[
        bool, typer.Option(help="Scale deployment to 0 (frees GPUs, keeps cached weights)")
    ] = False,
    teardown: Annotated[
        bool, typer.Option(help="Delete all resources for this model")
    ] = False,
    skip_validation: Annotated[
        bool, typer.Option(help="Skip health check and validation after deploy")
    ] = False,
    concurrency: Annotated[
        int, typer.Option(help="Number of concurrent requests for validation")
    ] = 8,
    health_timeout: Annotated[
        int, typer.Option(help="Health check timeout in seconds")
    ] = 1800,
    initial_delay: Annotated[
        int, typer.Option(help="Seconds to wait before first health check (model download time)")
    ] = 1200,
    anyuid: Annotated[
        bool, typer.Option(help="Include anyuid SCC RoleBinding (required for vLLM >v0.22)")
    ] = False,
    before_script: Annotated[
        Optional[str], typer.Option(help="Shell command to run before vLLM starts (e.g., download a custom parser)")
    ] = None,
):
    """Deploy, validate, and manage a vLLM model server on OpenShift."""
    try:
        deploy_model(
            model_id=model_id,
            reasoning_parser=reasoning_parser,
            tool_call_parser=tool_call_parser,
            chat_template_kwargs=chat_template_kwargs,
            extra_vllm_args=vllm_arg,
            gpu_pool_override=gpu_pool,
            gpu_pools_file=gpu_pools_file,
            max_model_len_override=max_model_len,
            namespace=namespace,
            vllm_image=vllm_image,
            route_timeout=route_timeout,
            app_name_override=app_name,
            served_model_name_override=served_model_name,
            do_scale_down=scale_down,
            do_teardown=teardown,
            skip_validation=skip_validation,
            concurrency=concurrency,
            health_timeout=health_timeout,
            initial_delay=initial_delay,
            anyuid=anyuid,
            before_script=before_script,
        )
    except (ValueError, subprocess.CalledProcessError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


if __name__ == "__main__":
    app()
