from pathlib import Path
from typing import Annotated, Optional

import typer

from coding_agent_bench.runner import Runner, SupportedAgent
from coding_agent_bench.utils import cmd_to_string

app = typer.Typer()


@app.command()
def run(
    agent: Annotated[
        str, typer.Option(help=f"Agent to use. Must be one of: {[e.value for e in SupportedAgent]}")
    ],
    dataset: Annotated[str, typer.Option(help="Dataset name or path")],
    model_name: Annotated[str, typer.Option(help="Model name")],
    server_url: Annotated[str, typer.Option(help="Model server URL")],
    environment: Annotated[str, typer.Option(help="Environment: docker or openshift")] = "docker",
    jobs_dir: Annotated[Path, typer.Option(help="Directory for job output")] = Path(
        "./jobs"
    ),
    job_name: Annotated[str, typer.Option(help="Name of the job")] = None,
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
    dry_run: Annotated[
        bool, typer.Option(help="Dry run mode, does not execute the job")
    ] = False,
):
    runner = Runner(jobs_dir=jobs_dir, job_name=job_name, dry_run=dry_run)
    cmd, job_dir = runner.run(
        agent=agent,
        dataset=dataset,
        model_name=model_name,
        server_url=server_url,
        environment=environment,
        dataset_pattern=dataset_pattern,
        n_concurrent=n_concurrent,
        n_tasks=n_tasks,
        model_max_len=model_max_len,
    )
    if dry_run:
        typer.echo(f"Job command:\n{cmd_to_string(cmd)}\n")
    typer.echo(f"Job output dir: {job_dir}")


if __name__ == "__main__":
    app()
