from typing import Any, Literal
from dotenv import load_dotenv
import os

from kfp import dsl, compiler
from kfp.client import Client

from coding_agent_bench.runner import Runner


def get_kfp_client() -> Client:
    load_dotenv()
    kfp_host = os.getenv("KFP_HOST")
    client = Client(host=kfp_host)
    return client


@dsl.component
def run(
    agent: str,
    dataset: str,
    model_name: str,
    server_url: str,
    dataset_pattern: str = None,
    n_concurrent: int = 1,
    n_tasks: int = None,
    model_max_len: int = 262000,
) -> str:
    runner = Runner()
    job_outpath = runner.run(
        agent=agent,
        dataset=dataset,
        model_name=model_name,
        server_url=server_url,
        dataset_pattern=dataset_pattern,
        n_concurrent=n_concurrent,
        n_tasks=n_tasks,
        model_max_len=model_max_len,
    )
    return str(job_outpath)


@dsl.component
def save_artifacts(job_outpath: str):
    return "Done"


@dsl.pipeline
def pipeline(
    agent: str,
    dataset: str,
    model_name: str,
    server_url: str,
    dataset_pattern: str = None,
    n_concurrent: int = 1,
    n_tasks: int = None,
    model_max_len: int = 262000,
):
    run_task = run(
        agent=agent,
        dataset=dataset,
        model_name=model_name,
        server_url=server_url,
        n_concurrent=n_concurrent,
        dataset_pattern=dataset_pattern,
        n_tasks=n_tasks,
        model_max_len=model_max_len,
    )
    artifacts_task = save_artifacts(job_outpath=run_task.output)
    return artifacts_task.outputs
