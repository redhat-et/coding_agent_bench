from pathlib import Path
import json
import argparse
import shlex
from pydantic import BaseModel, computed_field

from coding_agent_bench.leaderboard_results import atomic_json, build_leaderboard_result, trial_times
from coding_agent_bench.models import MODEL_REGISTRY

DEFAULT_GPU_COST_USD_PER_HOUR = 4
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_TEMPLATE_PATH = PROJECT_ROOT / "scripts" / "templates" / "report_template.md"
REPORT_OUTPUT_DIR = PROJECT_ROOT / "benchmarks"


class Metrics(BaseModel):
    n_tasks: int
    n_errors: int | float
    score: float
    n_input_tokens: int | None
    n_cache_tokens: int | None
    n_output_tokens: int | None
    n_total_tokens: int | None
    agent_time_seconds: int | None
    total_time_seconds: int | None
    cost_usd: float | None
    wall_total_time_seconds: int | None = None
    wall_agent_time_seconds: int | None = None
    @computed_field
    def mean_input_tokens_per_task(self) -> int | None:
        return self.n_input_tokens // self.n_tasks if self.n_input_tokens is not None and self.n_tasks else None

    @computed_field
    def mean_cache_tokens_per_task(self) -> int | None:
        return self.n_cache_tokens // self.n_tasks if self.n_cache_tokens is not None and self.n_tasks else None

    @computed_field
    def mean_output_tokens_per_task(self) -> int | None:
        return self.n_output_tokens // self.n_tasks if self.n_output_tokens is not None and self.n_tasks else None

    @computed_field
    def mean_tokens_per_task(self) -> int | None:
        return self.n_total_tokens // self.n_tasks if self.n_total_tokens is not None and self.n_tasks else None

    @computed_field
    def mean_cost_usd_per_task(self) -> float | None:
        if self.cost_usd is None or not self.n_tasks:
            return None
        return round(self.cost_usd / self.n_tasks, 2)

    @computed_field
    def mean_total_time_seconds_per_task(self) -> int | None:
        return self.total_time_seconds // self.n_tasks if self.total_time_seconds is not None and self.n_tasks else None

    @computed_field
    def mean_agent_time_seconds_per_task(self) -> int | None:
        return self.agent_time_seconds // self.n_tasks if self.agent_time_seconds is not None and self.n_tasks else None

    @computed_field
    def cache_hit_rate(self) -> float | None:
        if self.n_cache_tokens is None or self.n_input_tokens in (None, 0):
            return None
        return self.n_cache_tokens / self.n_input_tokens


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "job_dirs", type=Path, nargs="+",
        help="One or more Harbor job dirs; multiple runs are averaged",
    )
    parser.add_argument("--num-gpus", type=int, default=None)
    def _positive_float(value):
        f = float(value)
        import math
        if f < 0 or not math.isfinite(f):  # reject negative, NaN, and inf
            raise argparse.ArgumentTypeError(f"must be a non-negative number, got {value}")
        return f
    parser.add_argument("--gpu-cost-per-hour", type=_positive_float, default=DEFAULT_GPU_COST_USD_PER_HOUR,
                        help=f"Cost per GPU per hour in USD (default: ${DEFAULT_GPU_COST_USD_PER_HOUR})")
    parser.add_argument("--report", action="store_true", help="Write the Markdown benchmark report")
    parser.add_argument(
        "--leaderboard-metadata",
        type=Path,
        help="JSON containing per-job leaderboard metadata (benchmark/model/harness details)",
    )
    parser.add_argument(
        "--leaderboard-output",
        type=Path,
        help="Write a leaderboard result JSON accepted by coding-agent-leaderboard",
    )
    args = parser.parse_args()
    if args.num_gpus is not None and args.num_gpus <= 0:
        parser.error("--num-gpus must be positive")
    if args.leaderboard_metadata and not args.leaderboard_output:
        parser.error("--leaderboard-metadata requires --leaderboard-output")
    if args.leaderboard_output and len(args.job_dirs) != 1:
        parser.error("Leaderboard candidate export accepts exactly one Harbor job directory")
    return args


def _sum_optional(values: list[int | None]) -> int | None:
    """Do not present partial token accounting as a complete total."""
    return sum(values) if values and all(v is not None for v in values) else None


def _trial_results(job_dir: Path) -> list[dict]:
    """Read only trial-level results, excluding nested task artifacts."""
    return [json.loads(p.read_text()) for p in sorted(job_dir.glob("*/result.json"))]


def _run_concurrency(job_dir: Path, config: dict) -> int:
    """Read current/legacy concurrency settings; a lock is optional for export."""
    value = config.get("n_concurrent_trials") or (config.get("orchestrator") or {}).get("n_concurrent_trials")
    lock_path = job_dir / "lock.json"
    if value is None and lock_path.exists():
        value = json.loads(lock_path.read_text()).get("n_concurrent_trials")
    if value is None:
        return 1
    if type(value) is not int or value <= 0:
        raise ValueError(f"{job_dir}: concurrency must be a positive integer")
    return value


def determine_format(job_dir: Path):
    job_result = json.loads((job_dir / "result.json").read_text())
    if "n_input_tokens" in job_result.get("stats", {}):
        return "latest"
    return "legacy"


def extract_score(job_result: dict, eval_name: str) -> float:
    """Score metric: 'reward' (itbench-style) or 'mean' (legacy), mirroring aggregate_runs.py."""
    metrics = job_result["stats"]["evals"][eval_name]["metrics"][0]
    for key in ("reward", "mean"):
        if key in metrics:
            return float(metrics[key])
    raise KeyError(f"No score metric found in eval '{eval_name}'; available keys: {sorted(metrics)}")


def compute_metrics_legacy(job_dir: Path, num_gpus: int = None, gpu_cost_per_hour: float = DEFAULT_GPU_COST_USD_PER_HOUR):

    job_result_path = job_dir / "result.json"
    job_result = json.loads(job_result_path.read_text())

    job_config_path = job_dir / "config.json"
    job_config = json.loads(job_config_path.read_text())

    eval_name = list(job_result["stats"]["evals"].keys())[0]
    print(eval_name)
    n_concurrent = _run_concurrency(job_dir, job_config)
    task_results = _trial_results(job_dir)
    total_time, agent_time = trial_times(task_results, job_result["stats"].get("n_completed_trials", job_result["stats"].get("n_trials", 0)))
    agent_results = [r.get("agent_result") or {} for r in task_results]
    n_input_tokens = _sum_optional([r.get("n_input_tokens") for r in agent_results])
    n_cache_tokens = _sum_optional([r.get("n_cache_tokens") for r in agent_results])
    n_output_tokens = _sum_optional([r.get("n_output_tokens") for r in agent_results])
    total_tokens = (
        n_input_tokens + n_output_tokens
        if n_input_tokens is not None and n_output_tokens is not None
        else None
    )
    score = round(extract_score(job_result, eval_name), 3)
    cost = job_result["stats"].get("cost_usd")

    print(num_gpus)
    if num_gpus is not None:
        cost = round(agent_time * gpu_cost_per_hour * num_gpus / n_concurrent / 3600, 2) if agent_time is not None else None

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
    n_concurrent = _run_concurrency(job_dir, job_config)
    task_results = _trial_results(job_dir)
    total_time, agent_time = trial_times(task_results, job_result["stats"].get("n_completed_trials", job_result["stats"].get("n_trials", 0)))
    stats = job_result["stats"]
    n_input_tokens = stats.get("n_input_tokens")
    n_cache_tokens = stats.get("n_cache_tokens")
    n_output_tokens = stats.get("n_output_tokens")
    total_tokens = (
        n_input_tokens + n_output_tokens
        if n_input_tokens is not None and n_output_tokens is not None
        else None
    )
    score = round(extract_score(job_result, eval_name), 3)
    cost = job_result["stats"].get("cost_usd")

    if num_gpus is not None:
        cost = round(agent_time * gpu_cost_per_hour * num_gpus / n_concurrent / 3600, 2) if agent_time is not None else None

    metrics = Metrics(
        n_tasks=job_result["n_total_trials"],
        n_errors=stats.get("n_errored_trials", stats.get("n_errors", 0)),
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


def format_time(seconds: int | None) -> str:
    """Format seconds for the Markdown report, showing unknown time as N/A."""
    if seconds is None:
        return "N/A"
    hours, minutes = divmod(seconds, 3600)
    minutes, remainder = divmod(minutes, 60)
    return f"{hours:02d}h {minutes:02d}m {remainder:02d}s"


def average_metrics(metrics_list: list[Metrics], concurrencies: list[int] | None = None) -> Metrics:
    """Average compatible runs while keeping unknown metrics unknown."""
    if not metrics_list:
        raise ValueError("At least one run is required to average metrics")
    n_runs = len(metrics_list)
    if any(metrics.n_tasks != metrics_list[0].n_tasks for metrics in metrics_list):
        raise ValueError("Inconsistent runs: differing n_tasks, refusing to average")
    if concurrencies is not None and len(concurrencies) != n_runs:
        raise ValueError("Each run must have one concurrency value")

    def mean_optional(values, *, integer: bool = True):
        if any(value is None for value in values):
            return None
        mean = sum(values) / n_runs
        return int(round(mean)) if integer else mean

    errors_mean = mean_optional([metrics.n_errors for metrics in metrics_list], integer=False)
    if errors_mean is not None and errors_mean.is_integer():
        errors_mean = int(errors_mean)
    cost_mean = mean_optional([metrics.cost_usd for metrics in metrics_list], integer=False)
    wall_total = (
        mean_optional([metrics.total_time_seconds // concurrency
                       if metrics.total_time_seconds is not None else None
                       for metrics, concurrency in zip(metrics_list, concurrencies)])
        if concurrencies else None
    )
    wall_agent = (
        mean_optional([metrics.agent_time_seconds // concurrency
                       if metrics.agent_time_seconds is not None else None
                       for metrics, concurrency in zip(metrics_list, concurrencies)])
        if concurrencies else None
    )

    return Metrics(
        n_tasks=metrics_list[0].n_tasks,
        n_errors=errors_mean,
        score=round(sum(metrics.score for metrics in metrics_list) / n_runs, 3),
        n_input_tokens=mean_optional([metrics.n_input_tokens for metrics in metrics_list]),
        n_cache_tokens=mean_optional([metrics.n_cache_tokens for metrics in metrics_list]),
        n_output_tokens=mean_optional([metrics.n_output_tokens for metrics in metrics_list]),
        n_total_tokens=mean_optional([metrics.n_total_tokens for metrics in metrics_list]),
        agent_time_seconds=mean_optional([metrics.agent_time_seconds for metrics in metrics_list]),
        total_time_seconds=mean_optional([metrics.total_time_seconds for metrics in metrics_list]),
        cost_usd=round(cost_mean, 2) if cost_mean is not None else None,
        wall_total_time_seconds=wall_total,
        wall_agent_time_seconds=wall_agent,
    )


def prettify_command(args: list[str] | None) -> str:
    """Format Harbor's invocation as a readable shell command."""
    if not args:
        return "<TODO>"
    lines = []
    index = 0
    while index < len(args):
        if args[index].startswith("-") and index + 1 < len(args) and not args[index + 1].startswith("-"):
            lines.append(f"{shlex.quote(args[index])} {shlex.quote(args[index + 1])}")
            index += 2
        else:
            lines.append(shlex.quote(args[index]))
            index += 1
    return " \\\n  ".join(lines)


def _reward_outcome_counts(result_dict: dict) -> tuple[int, int, int] | None:
    """Return full/partial/zero reward counts when the run records them."""
    for eval_data in result_dict.get("stats", {}).get("evals", {}).values():
        reward_stats = (eval_data.get("reward_stats") or {}).get("reward")
        if not reward_stats:
            continue
        full = partial = zero = 0
        for reward_string, task_ids in reward_stats.items():
            reward = float(reward_string)
            if reward >= 1.0:
                full += len(task_ids)
            elif reward > 0.0:
                partial += len(task_ids)
            else:
                zero += len(task_ids)
        return full, partial, zero
    return None


def _format_count(value: float) -> str:
    """Format averaged counts without unnecessary decimal places."""
    return str(int(value)) if value == int(value) else f"{value:g}"


def _reward_outcome_string(result_dicts: list[dict], n_errors: int | float) -> str | None:
    """Summarize reward outcomes across runs, preserving fractional averages."""
    counts = [result for result in (_reward_outcome_counts(run) for run in result_dicts) if result is not None]
    if not counts:
        return None
    count = len(counts)
    full = sum(row[0] for row in counts) / count
    partial = sum(row[1] for row in counts) / count
    zero = sum(row[2] for row in counts) / count
    return (f"{_format_count(full)} Full Reward / {_format_count(partial)} Partial Reward / "
            f"{_format_count(zero)} Zero Reward / {_format_count(n_errors)} Errors")


def run_identity(job_dir: Path) -> tuple[str, str, str]:
    """Return dataset/model/harness identity used to validate averaged runs."""
    config = json.loads((job_dir / "config.json").read_text())
    agent = config["agents"][0]
    dataset_config = config["datasets"][0]
    dataset = dataset_config.get("name") or dataset_config.get("path")
    model = (agent.get("model_name") or (agent.get("env") or {}).get("ANTHROPIC_MODEL") or "").replace("vllm/", "")
    return dataset, model, agent["name"]


def create_job_report(
    job_dirs: list[Path], metrics: Metrics, num_gpus: int = None,
    gpu_cost_per_hour: float = DEFAULT_GPU_COST_USD_PER_HOUR,
) -> str:
    """Render and save the historical Markdown report for one or more runs."""
    n_runs = len(job_dirs)
    run_configs = [json.loads((directory / "config.json").read_text()) for directory in job_dirs]
    run_results = [json.loads((directory / "result.json").read_text()) for directory in job_dirs]
    run_locks = [json.loads((directory / "lock.json").read_text()) for directory in job_dirs]
    result_json = (job_dirs[0] / "result.json").read_text()
    config_json = (job_dirs[0] / "config.json").read_text()
    result_dict = run_results[0]
    config_dict = run_configs[0]
    lock_dict = run_locks[0]

    run_date = ", ".join(lock.get("created_at", "<TODO>") for lock in run_locks)
    dataset = config_dict["datasets"][0].get("name") or config_dict["datasets"][0].get("path") or "<TODO>"
    if dataset == "datasets/swe-bench-verified":
        dataset = "swe-bench/swe-bench-verified"
    num_tasks = result_dict.get("n_total_trials", metrics.n_tasks)
    environment = (config_dict.get("environment") or {}).get("type", "<TODO>")
    agent = config_dict["agents"][0]
    model = (agent.get("model_name") or (agent.get("env") or {}).get("ANTHROPIC_MODEL") or "<TODO>").replace("vllm/", "")
    harness = agent["name"]
    job_name = ", ".join(config.get("job_name", directory.name)
                          for config, directory in zip(run_configs, job_dirs))
    results_suffix = f" (avg of {n_runs} runs)" if n_runs > 1 else ""

    reward_string = _reward_outcome_string(run_results, metrics.n_errors)
    if reward_string is not None:
        score_string = reward_string
    else:
        n_success = round(metrics.score * metrics.n_tasks)
        n_failed = metrics.n_tasks - n_success - metrics.n_errors
        score_string = (f"{n_success} Success / {_format_count(n_failed)} Failed / "
                        f"{_format_count(metrics.n_errors)} Errors")

    eval_name = next(iter(result_dict.get("stats", {}).get("evals", {})), None)
    error_counts: dict[str, int] = {}
    for run_result in run_results:
        evals = run_result.get("stats", {}).get("evals", {})
        eval_data = evals.get(eval_name, {}) if eval_name else {}
        for error_type, instances in (eval_data.get("exception_stats") or {}).items():
            error_counts[error_type] = error_counts.get(error_type, 0) + len(instances)
    error_string = ", ".join(f"{count} {error_type}s" for error_type, count in error_counts.items())

    command = prettify_command(lock_dict.get("invocation"))
    concurrency = _run_concurrency(job_dirs[0], config_dict)
    total_time = format_time(
        metrics.wall_total_time_seconds if metrics.wall_total_time_seconds is not None
        else metrics.total_time_seconds // concurrency if metrics.total_time_seconds is not None else None
    )
    agent_time = format_time(
        metrics.wall_agent_time_seconds if metrics.wall_agent_time_seconds is not None
        else metrics.agent_time_seconds // concurrency if metrics.agent_time_seconds is not None else None
    )
    avg_agent_time = format_time(metrics.mean_agent_time_seconds_per_task)
    cache_hit_rate = round(metrics.cache_hit_rate * 100, 1) if metrics.cache_hit_rate is not None else "N/A"
    gpu_snippet = f"(${gpu_cost_per_hour} / GPU / hr * {num_gpus} GPU * {agent_time})" if num_gpus else ""

    model_config = MODEL_REGISTRY.get(model)
    vllm_image = model_config.image if model_config else "<TODO>"
    vllm_max_model_len = model_config.model_max_len if model_config else "<TODO>"
    vllm_command = "<TODO>"
    if model_config is not None:
        command_args = ["vllm", "serve", *model_config.args, *model_config.default_args]
        if num_gpus:
            command_args.extend(["--tensor-parallel-size", str(num_gpus)])
        vllm_command = prettify_command(command_args) if num_gpus else ""

    if n_runs == 1:
        config_section = f"**`config.json`:**\n\n```json\n{config_json}\n```"
        result_section = f"```json\n{result_json}\n```"
    else:
        config_section = "\n\n".join(
            f"### Run {index + 1}: {run_configs[index].get('job_name', directory.name)}\n\n"
            f"**`config.json`:**\n\n```json\n{(directory / 'config.json').read_text()}\n```"
            for index, directory in enumerate(job_dirs)
        )
        result_section = "\n\n".join(
            f"### Run {index + 1}: {run_configs[index].get('job_name', directory.name)}\n\n"
            f"```json\n{(directory / 'result.json').read_text()}\n```"
            for index, directory in enumerate(job_dirs)
        )

    report = REPORT_TEMPLATE_PATH.read_text().format(
        run_date=run_date,
        dataset=dataset,
        num_tasks=num_tasks,
        environment=environment,
        model=model,
        harness=harness,
        job_name=job_name,
        score=round(metrics.score * 100, 1),
        score_string=score_string,
        error_rate=round(metrics.n_errors / metrics.n_tasks * 100, 2) if metrics.n_tasks else "N/A",
        error_string=error_string,
        total_time=total_time,
        agent_time=agent_time,
        avg_agent_time_per_task=avg_agent_time,
        cost=round(metrics.cost_usd, 2) if metrics.cost_usd is not None else "N/A",
        gpu_snippet=gpu_snippet,
        avg_cost_per_task=(metrics.mean_cost_usd_per_task
                           if metrics.mean_cost_usd_per_task is not None else "N/A"),
        input_tokens=metrics.n_input_tokens if metrics.n_input_tokens is not None else "N/A",
        avg_input_per_task=metrics.mean_input_tokens_per_task if metrics.mean_input_tokens_per_task is not None else "N/A",
        output_tokens=metrics.n_output_tokens if metrics.n_output_tokens is not None else "N/A",
        avg_output_per_task=metrics.mean_output_tokens_per_task if metrics.mean_output_tokens_per_task is not None else "N/A",
        cache_hit_rate=cache_hit_rate,
        vllm_image=vllm_image,
        vllm_max_model_len=vllm_max_model_len,
        vllm_command=vllm_command,
        command=command,
        config_section=config_section,
        result_section=result_section,
        results_suffix=results_suffix,
    )

    REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_name = f"{str(dataset).split('/')[-1]}_{model.split('/')[-1]}_{harness}.md".replace("/", "_")
    (REPORT_OUTPUT_DIR / report_name).write_text(report)
    return report


def main():
    args = parse_args()
    num_gpus = args.num_gpus
    gpu_cost_per_hour = args.gpu_cost_per_hour
    job_dirs = args.job_dirs

    if args.leaderboard_output:
        job_dir = job_dirs[0]
        overrides = json.loads(args.leaderboard_metadata.read_text()) if args.leaderboard_metadata else None
        result = build_leaderboard_result(job_dir, overrides=overrides)
        if num_gpus is not None:
            config_path = job_dir / "config.json"
            config = json.loads(config_path.read_text()) if config_path.exists() else {}
            seconds = result["metrics"]["agent_time_seconds"]
            cost = round(seconds * gpu_cost_per_hour * num_gpus / _run_concurrency(job_dir, config) / 3600, 2) if seconds is not None else None
            result["metrics"]["cost_usd"] = cost
            count = result["metrics"]["n_tasks"]
            result["metrics"]["mean_cost_usd_per_task"] = round(cost / count, 2) if cost is not None and count else None
            result["run"]["cost_estimated"] = True
        atomic_json(args.leaderboard_output, result)
        print(f"Wrote leaderboard result to {args.leaderboard_output}")
        if not args.report:
            return

    job_dirs = sorted(
        job_dirs,
        key=lambda directory: json.loads((directory / "lock.json").read_text()).get("created_at", ""),
    )
    all_metrics = []
    for job_dir in job_dirs:
        job_format = determine_format(job_dir)
        if job_format == "legacy":
            metrics = compute_metrics_legacy(job_dir, num_gpus, gpu_cost_per_hour)
        else:
            metrics = compute_metrics_latest(job_dir, num_gpus, gpu_cost_per_hour)
        print(f"run {job_dir.name}: score={metrics.score} errors={metrics.n_errors} cost=${metrics.cost_usd}")
        all_metrics.append(metrics)

    if any(metrics.n_tasks != all_metrics[0].n_tasks for metrics in all_metrics):
        raise SystemExit("Inconsistent runs: differing n_tasks, refusing to average")
    identities = {run_identity(directory) for directory in job_dirs}
    if len(identities) > 1:
        raise SystemExit(f"Inconsistent runs: differing dataset/model/harness {identities}, refusing to average")

    concurrencies = []
    for job_dir in job_dirs:
        config_path = job_dir / "config.json"
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        concurrencies.append(_run_concurrency(job_dir, config))
    metrics = all_metrics[0] if len(all_metrics) == 1 else average_metrics(all_metrics, concurrencies)
    print(f"job {', '.join(directory.name for directory in job_dirs)}: score={metrics.score} errors={metrics.n_errors} cost=${metrics.cost_usd}")
    print(metrics.model_dump_json(indent=4))
    if args.report:
        create_job_report(job_dirs, metrics, num_gpus, gpu_cost_per_hour)

if __name__ == "__main__":
    main()
