from pathlib import Path
import json
import argparse
from pydantic import BaseModel, computed_field, model_validator
from datetime import datetime
import shlex

from coding_agent_bench.models import MODEL_REGISTRY

DEFAULT_GPU_COST_USD_PER_HOUR = 4


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
    
    @model_validator(mode="after")
    def missing_cost(self):
        if self.cost_usd is None:
            self.cost_usd = 0.0

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
        return round(self.cost_usd / self.n_tasks, 2) if self.cost_usd else 0.0

    @computed_field
    def mean_total_time_seconds_per_task(self) -> int:
        return self.total_time_seconds // self.n_tasks

    @computed_field
    def mean_agent_time_seconds_per_task(self) -> int:
        return self.agent_time_seconds // self.n_tasks
    
    @computed_field
    def cache_hit_rate(self) -> int:
        return self.n_cache_tokens / self.n_input_tokens


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--num-gpus", type=int, default=None)
    def _positive_float(value):
        f = float(value)
        import math
        if f < 0 or not math.isfinite(f):  # reject negative, NaN, and inf
            raise argparse.ArgumentTypeError(f"must be a non-negative number, got {value}")
        return f
    parser.add_argument("--gpu-cost-per-hour", type=_positive_float, default=DEFAULT_GPU_COST_USD_PER_HOUR,
                        help=f"Cost per GPU per hour in USD (default: ${DEFAULT_GPU_COST_USD_PER_HOUR})")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    return args


def determine_format(job_dir: Path):
    job_result = json.loads((job_dir / "result.json").read_text())
    if "n_input_tokens" in job_result.get("stats", {}):
        return "latest"
    return "legacy"


def compute_metrics_legacy(job_dir: Path, num_gpus: int = None, gpu_cost_per_hour: float = DEFAULT_GPU_COST_USD_PER_HOUR):

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
                if r.get("agent_execution") is not None
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
    if cost is None and num_gpus is None:
        raise ValueError(
            "'--num-gpus' must be specified when 'stats.cost_usd' is missing from job results."
        )

    print(num_gpus)
    if num_gpus is not None:
        cost = round(agent_time * gpu_cost_per_hour * num_gpus / n_concurrent / 3600, 2)

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


def compute_metrics_latest(job_dir: Path, num_gpus: int = None, gpu_cost_per_hour: float = DEFAULT_GPU_COST_USD_PER_HOUR):

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
                if r.get("agent_execution") is not None
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
    if cost is None and num_gpus is None:
        raise ValueError(
            "'--num-gpus' must be specified when 'stats.cost_usd' is missing from job results."
        )

    if num_gpus is not None:
        cost = round(agent_time * gpu_cost_per_hour * num_gpus / n_concurrent / 3600, 2)

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

def format_time(seconds: int):
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}h {m:02d}m {s:02d}s"

def prettify_command(args: list[str]):
    """Prettify a shell command with line breaks for easier reading."""
    lines = []
    i = 0

    while i < len(args):
        # If it's a flag and has a value next to it, keep them together
        if args[i].startswith("-") and i + 1 < len(args) and not args[i+1].startswith("-"):
            lines.append(f"{shlex.quote(args[i])} {shlex.quote(args[i+1])}")
            i += 2
        else:
            lines.append(shlex.quote(args[i]))
            i += 1

    pretty_command = " \\\n  ".join(lines)
    return pretty_command

def create_job_report(job_dir: Path, metrics: Metrics, num_gpus: int = None, gpu_cost_per_hour: float = DEFAULT_GPU_COST_USD_PER_HOUR):
    report_template_path = Path(__file__).parent / "templates" / "report_template.md"
    report_template = report_template_path.read_text()
    
    job_result_path = job_dir / "result.json"
    result_json = job_result_path.read_text()
    result_dict = json.loads(result_json)

    job_config_path = job_dir / "config.json"
    config_json = job_config_path.read_text()
    config_dict = json.loads(config_json)
    
    lock_file_path = job_dir / "lock.json"
    lock_json = lock_file_path.read_text()
    lock_dict = json.loads(lock_json)
    
    # Parse job metadata
    run_date = lock_dict["created_at"]
    dataset = config_dict["datasets"][0]["name"] if config_dict["datasets"][0]["name"] is not None else config_dict["datasets"][0]["path"]
    dataset = "swe-bench/swe-bench-verified" if dataset == "datasets/swe-bench-verified" else dataset
    num_tasks = result_dict["n_total_trials"]
    environment = config_dict["environment"]["type"]
    model = config_dict["agents"][0]["model_name"].replace("vllm/", "")
    harness = config_dict["agents"][0]["name"]
    job_name = config_dict["job_name"]

    # Create score string
    score_string = f"{int(metrics.score * metrics.n_tasks)} Success / {int((1-metrics.score) * metrics.n_tasks) - metrics.n_errors} Failed / {metrics.n_errors} Errors"
    
    # Create errors string
    eval_name = list(result_dict["stats"]["evals"].keys())[0]
    error_dict = {k: len(v) for k, v in result_dict["stats"]["evals"][eval_name]["exception_stats"].items()}
    error_string = ", ".join([f"{v} {k}s" for k, v in error_dict.items()])

    # Create command string
    invocation_command = lock_dict.get("invocation")
    command = prettify_command(invocation_command) if invocation_command else "<TODO>"

    # Calculate time spent
    n_concurrent = config_dict["n_concurrent_trials"]
    total_time = format_time(metrics.total_time_seconds // n_concurrent)
    agent_time = format_time(metrics.agent_time_seconds // n_concurrent)
    avg_agent_time_per_task = format_time(metrics.mean_agent_time_seconds_per_task)

    # Calculate Token Usage
    input_tokens = metrics.n_input_tokens
    avg_input_per_task = metrics.mean_input_tokens_per_task
    output_tokens = metrics.n_output_tokens
    avg_output_per_task = metrics.mean_output_tokens_per_task
    cache_hit_rate = round(metrics.cache_hit_rate * 100, 1)
    avg_cost_per_task = metrics.mean_cost_usd_per_task
    
    # Show GPU calculation
    gpu_snippet = f"(${gpu_cost_per_hour} / GPU / hr * {num_gpus} GPU * {agent_time})" if num_gpus else ""
    
    # Get vLLM Info
    model_config = MODEL_REGISTRY.get(model)
    vllm_image = "<TODO>"
    vllm_max_model_len = "<TODO>"
    vllm_command = "<TODO>"
    if model_config is not None:
        vllm_image = model_config.image
        vllm_max_model_len = model_config.model_max_len
        vllm_command = ["vllm", "serve"] + model_config.args + model_config.default_args + ["--tensor-parallel-size", str(num_gpus)] if num_gpus else []
        vllm_command = prettify_command(vllm_command)
    
    # Create report
    report = report_template.format(
        run_date=run_date,
        dataset=dataset,
        num_tasks=num_tasks,
        environment=environment,
        model=model,
        harness=harness,
        job_name=job_name,
        score=round(metrics.score*100, 1),
        score_string=score_string,
        error_rate=round(metrics.n_errors / metrics.n_tasks * 100, 1),
        error_string=error_string,
        total_time=total_time,
        agent_time=agent_time,
        avg_agent_time_per_task=avg_agent_time_per_task,
        cost=round(metrics.cost_usd, 2),
        gpu_snippet=gpu_snippet,
        avg_cost_per_task=avg_cost_per_task,
        input_tokens=input_tokens,
        avg_input_per_task=avg_input_per_task,
        output_tokens=output_tokens,
        avg_output_per_task=avg_output_per_task,
        cache_hit_rate=cache_hit_rate,
        vllm_image=vllm_image,
        vllm_max_model_len=vllm_max_model_len,
        vllm_command=vllm_command,
        command=command,
        config_json=config_json,
        result_json=result_json,
    )
    
    # Save report
    benchmark_dir = Path(__file__).parent.parent / "benchmarks"
    report_name = f"{dataset.split("/")[-1]}_{model.split("/")[-1]}_{harness}.md".replace("/", "_")
    with open(benchmark_dir / report_name, "w") as f:
        f.write(report)
    
    return report


def main():
    args = parse_args()
    job_dir = args.job_dir
    num_gpus = args.num_gpus
    gpu_cost_per_hour = args.gpu_cost_per_hour

    # Determine job format
    job_format = determine_format(job_dir)

    # Compute metrics
    if job_format == "legacy":
        metrics = compute_metrics_legacy(job_dir, num_gpus, gpu_cost_per_hour)
    elif job_format == "latest":
        metrics = compute_metrics_latest(job_dir, num_gpus, gpu_cost_per_hour)

    print(metrics.model_dump_json(indent=4))
    
    # Create the job report
    if args.report:
        create_job_report(job_dir, metrics, num_gpus, gpu_cost_per_hour)

if __name__ == "__main__":
    main()
