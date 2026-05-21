from pathlib import Path
import json
import argparse
from pydantic import BaseModel, computed_field
from datetime import datetime

GPU_COST_USD_PER_SECOND = 4 / 3600


class Metrics(BaseModel):
    n_tasks: int
    n_errors: int
    score: float
    n_input_tokens: int
    n_cache_tokens: int
    n_output_tokens: int
    n_total_tokens: int
    agent_time_seconds: int
    total_time_seconds: int
    cost_usd: float

    @computed_field
    def mean_input_tokens_per_task(self) -> int:
        return self.n_input_tokens // self.n_tasks

    @computed_field
    def mean_cache_tokens_per_task(self) -> int:
        return self.n_cache_tokens // self.n_tasks

    @computed_field
    def mean_output_tokens_per_task(self) -> int:
        return self.n_output_tokens // self.n_tasks

    @computed_field
    def mean_tokens_per_task(self) -> int:
        return self.n_total_tokens // self.n_tasks

    @computed_field
    def mean_cost_usd_per_task(self) -> float:
        return round(self.cost_usd / self.n_tasks, 2)

    @computed_field
    def mean_total_time_seconds_per_task(self) -> int:
        return self.total_time_seconds // self.n_tasks

    @computed_field
    def mean_agent_time_seconds_per_task(self) -> int:
        return self.agent_time_seconds // self.n_tasks


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--num-gpus", type=int, default=None)
    args = parser.parse_args()
    return args


def determine_format(job_dir: Path):
    job_result = json.loads((job_dir / "result.json").read_text())
    if "n_input_tokens" in job_result.get("stats", {}):
        return "latest"
    return "legacy"


def compute_metrics_legacy(job_dir: Path, num_gpus: int = None):

    job_result_path = job_dir / "result.json"
    job_result = json.loads(job_result_path.read_text())

    job_config_path = job_dir / "config.json"
    job_config = json.loads(job_config_path.read_text())

    eval_name = list(job_result["stats"]["evals"].keys())[0]
    print(eval_name)
    n_concurrent = job_config["n_concurrent_trials"]
    task_results = [
        json.loads(p.read_text())
        for p in job_dir.rglob("result.json")
        if p != job_result_path
    ]

    total_time = int(
        sum(
            [
                (
                    datetime.fromisoformat(r["finished_at"])
                    - datetime.fromisoformat(r["started_at"])
                ).total_seconds()
                for r in task_results
            ]
        )
    )
    agent_time = int(
        sum(
            [
                (
                    datetime.fromisoformat(r["agent_execution"]["finished_at"])
                    - datetime.fromisoformat(r["agent_execution"]["started_at"])
                ).total_seconds()
                for r in task_results
            ]
        )
    )
    n_input_tokens = int(
        sum(
            [
                r["agent_result"]["n_input_tokens"]
                for r in task_results
                if r["agent_result"]["n_input_tokens"] is not None
            ]
        )
    )
    n_cache_tokens = int(
        sum(
            [
                r["agent_result"]["n_cache_tokens"]
                for r in task_results
                if r["agent_result"]["n_cache_tokens"] is not None
            ]
        )
    )
    n_output_tokens = int(
        sum(
            [
                r["agent_result"]["n_output_tokens"]
                for r in task_results
                if r["agent_result"]["n_output_tokens"] is not None
            ]
        )
    )
    total_tokens = n_input_tokens + n_cache_tokens + n_output_tokens
    score = round(job_result["stats"]["evals"][eval_name]["metrics"][0]["mean"], 3)
    cost = job_result["stats"]["cost_usd"]
    if cost is None or cost == 0:
        if num_gpus is None:
            raise ValueError(
                "'--num-gpus' must be specified when 'stats.cost_usd' is missing from job results."
            )
        cost = round(agent_time * GPU_COST_USD_PER_SECOND * num_gpus / n_concurrent, 2)

    metrics = Metrics(
        n_tasks=job_result["n_total_trials"],
        n_errors=job_result["stats"]["n_errors"],
        score=score,
        n_input_tokens=n_input_tokens,
        n_cache_tokens=n_cache_tokens,
        n_output_tokens=n_output_tokens,
        n_total_tokens=total_tokens,
        agent_time_seconds=agent_time,
        total_time_seconds=total_time,
        cost_usd=cost,
    )
    return metrics


def compute_metrics_latest(job_dir: Path, num_gpus: int = None):

    job_result_path = job_dir / "result.json"
    job_result = json.loads(job_result_path.read_text())

    job_config_path = job_dir / "config.json"
    job_config = json.loads(job_config_path.read_text())

    eval_name = list(job_result["stats"]["evals"].keys())[0]
    print(eval_name)
    n_concurrent = job_config["n_concurrent_trials"]
    task_results = [
        json.loads(p.read_text())
        for p in job_dir.rglob("result.json")
        if p != job_result_path
    ]

    total_time = int(
        sum(
            [
                (
                    datetime.fromisoformat(r["finished_at"])
                    - datetime.fromisoformat(r["started_at"])
                ).total_seconds()
                for r in task_results
            ]
        )
    )
    agent_time = int(
        sum(
            [
                (
                    datetime.fromisoformat(r["agent_execution"]["finished_at"])
                    - datetime.fromisoformat(r["agent_execution"]["started_at"])
                ).total_seconds()
                for r in task_results
            ]
        )
    )
    total_tokens = (
        job_result["stats"]["n_input_tokens"]
        + job_result["stats"]["n_cache_tokens"]
        + job_result["stats"]["n_output_tokens"]
    )
    score = round(job_result["stats"]["evals"][eval_name]["metrics"][0]["mean"], 3)
    cost = job_result["stats"]["cost_usd"]
    if cost is None or cost == 0:
        if num_gpus is None:
            raise ValueError(
                "'--num-gpus' must be specified when 'stats.cost_usd' is missing from job results."
            )
        cost = round(agent_time * GPU_COST_USD_PER_SECOND * num_gpus / n_concurrent, 2)

    metrics = Metrics(
        n_tasks=job_result["n_total_trials"],
        n_errors=job_result["stats"]["n_errored_trials"],
        score=score,
        n_input_tokens=job_result["stats"]["n_input_tokens"],
        n_cache_tokens=job_result["stats"]["n_cache_tokens"],
        n_output_tokens=job_result["stats"]["n_output_tokens"],
        n_total_tokens=total_tokens,
        agent_time_seconds=agent_time,
        total_time_seconds=total_time,
        cost_usd=cost,
    )

    return metrics


def main():
    args = parse_args()
    job_dir = args.job_dir
    num_gpus = args.num_gpus

    # Determine job format
    job_format = determine_format(job_dir)

    # Compute metrics
    if job_format == "legacy":
        metrics = compute_metrics_legacy(job_dir, num_gpus)
    elif job_format == "latest":
        metrics = compute_metrics_latest(job_dir, num_gpus)

    print(metrics.model_dump_json(indent=4))


if __name__ == "__main__":
    main()
