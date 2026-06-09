from pathlib import Path
import signal
import subprocess
import sys
from typing import Annotated, Optional

import typer

from coding_agent_bench.builder import HarborCommandBuilder, SupportedAgent
from coding_agent_bench.job import OpenshiftJob
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


if __name__ == "__main__":
    app()
