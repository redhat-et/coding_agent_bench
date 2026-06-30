from pathlib import Path
import signal
import subprocess
import sys
from typing import Annotated, Optional

import typer

from coding_agent_bench.builder import HarborCommandBuilder, SupportedAgent
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.manifest import deploy as deploy_model
from coding_agent_bench.manifest import generate
from coding_agent_bench.utils import cmd_to_string

app = typer.Typer()


@app.command()
def run(
    agent: Annotated[
        SupportedAgent,
        typer.Option(help=f"Agent to use"),
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
    dry_run: Annotated[
        bool, typer.Option(help="Dry run mode, does not execute the job")
    ] = False,
):
    # Raise error if remote is used and environment is not openshift
    if remote and environment != "openshift":
        raise ValueError("Remote mode is only available with `--environment=openshift`")
    
    # If remote, run as a job
    if remote:
        if dry_run:
            typer.echo("Error: Cannot use `--remote` with `--dry-run`. Dry run mode is not available on remote")
        typer.echo("Running job on remote server...")
        job = OpenshiftJob(job_name=job_name)
        remote_args = [a for a in sys.argv[1:] if a not in ("--remote", "--dry-run")]
        command = ["coding-agent-bench", *remote_args]
        try:
            job.run(command)
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
        )
        typer.echo(f"Job command:\n{cmd_to_string(harbor_command)}\n")

        if dry_run:
            return

        proc = subprocess.Popen(harbor_command)
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
            raise SystemExit(130)
        typer.echo(f"Job output dir: {job_dir}")


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
):
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
    anyuid: Annotated[
        bool, typer.Option(help="Include anyuid SCC RoleBinding (required for vLLM >v0.22)")
    ] = False,
):
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
            anyuid=anyuid,
        )
    except (ValueError, subprocess.CalledProcessError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


if __name__ == "__main__":
    app()
