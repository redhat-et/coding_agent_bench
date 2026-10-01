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
    # Optional concurrency-normalized wall-clock estimates, set when averaging
    # runs that used different n_concurrent_trials settings. The base time
    # fields stay on the summed-duration basis so per-task averages remain
    # independent of concurrency.
    wall_total_time_seconds: int | None = None
    wall_agent_time_seconds: int | None = None
    
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
    parser.add_argument("job_dirs", type=Path, nargs="+",
                        help="One or more Harbor job dirs; multiple runs are averaged")
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
    n_concurrent = job_config.get("n_concurrent_trials", 1)
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
    score = round(extract_score(job_result, eval_name), 3)
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
    n_concurrent = job_config.get("n_concurrent_trials", 1)
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
    score = round(extract_score(job_result, eval_name), 3)
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

def average_metrics(metrics_list: list[Metrics], concurrencies: list[int] | None = None) -> Metrics:
    """Average metrics across multiple runs of the same benchmark/model/harness.

    agent_time_seconds/total_time_seconds are averaged as recorded (summed
    durations), keeping per-task averages concurrency-independent. When
    concurrencies is given, wall_total_time_seconds/wall_agent_time_seconds
    additionally carry the mean of per-run wall-clock estimates (each run's
    sum divided by its own concurrency), correct even when runs used
    different concurrency settings.
    """
    n_runs = len(metrics_list)

    def mean_int(values: list[int]) -> int:
        return int(round(sum(values) / n_runs))

    wall_total = (
        mean_int([m.total_time_seconds // c for m, c in zip(metrics_list, concurrencies)])
        if concurrencies else None
    )
    wall_agent = (
        mean_int([m.agent_time_seconds // c for m, c in zip(metrics_list, concurrencies)])
        if concurrencies else None
    )

    return Metrics(
        n_tasks=metrics_list[0].n_tasks,
        n_errors=mean_int([m.n_errors for m in metrics_list]),
        score=round(sum(m.score for m in metrics_list) / n_runs, 3),
        n_input_tokens=mean_int([m.n_input_tokens for m in metrics_list]),
        n_cache_tokens=mean_int([m.n_cache_tokens for m in metrics_list]),
        n_output_tokens=mean_int([m.n_output_tokens for m in metrics_list]),
        n_total_tokens=mean_int([m.n_total_tokens for m in metrics_list]),
        agent_time_seconds=mean_int([m.agent_time_seconds for m in metrics_list]),
        total_time_seconds=mean_int([m.total_time_seconds for m in metrics_list]),
        cost_usd=round(sum(m.cost_usd for m in metrics_list) / n_runs, 2),
        wall_total_time_seconds=wall_total,
        wall_agent_time_seconds=wall_agent,
    )

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

def _reward_outcome_counts(result_dict: dict) -> tuple[int, int, int] | None:
    """(full, partial, zero) reward counts from a run's reward distribution.

    Returns None when no reward distribution exists (legacy pass/fail
    benchmarks keep the Success/Failed wording).
    """
    evals = result_dict.get("stats", {}).get("evals", {})
    for eval_data in evals.values():
        reward_stats = eval_data.get("reward_stats", {}).get("reward")
        if not reward_stats:
            continue
        n_full = n_partial = n_zero = 0
        for reward_str, task_ids in reward_stats.items():
            reward = float(reward_str)
            n = len(task_ids)
            if reward >= 1.0:
                n_full += n
            elif reward > 0.0:
                n_partial += n
            else:
                n_zero += n
        return (n_full, n_partial, n_zero)
    return None

def _reward_outcome_string(result_dicts: list[dict], n_errors: int) -> str | None:
    """Outcome counts across runs, averaged for multi-run reports.

    Returns e.g. "18 Full Reward / 3 Partial Reward / 19 Zero Reward / 0 Errors"
    (mean counts across runs, rounded), or None when no run has a reward
    distribution.
    """
    all_counts = [_reward_outcome_counts(r) for r in result_dicts]
    all_counts = [c for c in all_counts if c is not None]
    if not all_counts:
        return None
    n_runs = len(all_counts)
    n_full = round(sum(c[0] for c in all_counts) / n_runs)
    n_partial = round(sum(c[1] for c in all_counts) / n_runs)
    n_zero = round(sum(c[2] for c in all_counts) / n_runs)
    return f"{n_full} Full Reward / {n_partial} Partial Reward / {n_zero} Zero Reward / {n_errors} Errors"

def create_job_report(job_dirs: list[Path], metrics: Metrics, num_gpus: int = None, gpu_cost_per_hour: float = DEFAULT_GPU_COST_USD_PER_HOUR):
    n_runs = len(job_dirs)
    job_dir = job_dirs[0]
    report_template_path = Path(__file__).parent / "templates" / "report_template.md"
    report_template = report_template_path.read_text()
    
    # Per-run configs, results, and lock files (job_dirs are ordered by start time)
    run_configs = [json.loads((d / "config.json").read_text()) for d in job_dirs]
    run_results = [json.loads((d / "result.json").read_text()) for d in job_dirs]
    run_locks = [json.loads((d / "lock.json").read_text()) for d in job_dirs]

    result_json = (job_dir / "result.json").read_text()
    result_dict = run_results[0]

    config_json = (job_dir / "config.json").read_text()
    config_dict = run_configs[0]
    
    lock_dict = run_locks[0]
    
    # Parse job metadata
    run_date = ", ".join(lock["created_at"] for lock in run_locks)
    dataset = config_dict["datasets"][0].get("name") or config_dict["datasets"][0].get("path")
    dataset = "swe-bench/swe-bench-verified" if dataset == "datasets/swe-bench-verified" else dataset
    num_tasks = result_dict["n_total_trials"]
    environment = config_dict["environment"]["type"]
    agent_config = config_dict["agents"][0]
    model = (agent_config.get("model_name") or (agent_config.get("env") or {}).get("ANTHROPIC_MODEL") or "<TODO>").replace("vllm/", "")
    harness = agent_config["name"]
    job_name = ", ".join(c["job_name"] for c in run_configs)

    # Results heading (marked as averaged when multiple runs)
    results_suffix = f" (avg of {n_runs} runs)" if n_runs > 1 else ""

    # Create score string. For reward-based benchmarks a task can score
    # partial credit, so derive full/partial/zero-reward counts from the
    # reward distribution when available instead of rounding score*n_tasks
    # (which conflates partial credit with successes).
    reward_string = _reward_outcome_string(run_results, metrics.n_errors)
    if reward_string is not None:
        score_string = reward_string
    else:
        n_success = round(metrics.score * metrics.n_tasks)
        score_string = f"{n_success} Success / {metrics.n_tasks - n_success - metrics.n_errors} Failed / {metrics.n_errors} Errors"
    
    # Create errors string
    eval_name = list(result_dict["stats"]["evals"].keys())[0]
    error_dict = {k: len(v) for k, v in result_dict["stats"]["evals"][eval_name]["exception_stats"].items()}
    error_string = ", ".join([f"{v} {k}s" for k, v in error_dict.items()])

    # Create command string
    invocation_command = lock_dict.get("invocation")
    command = prettify_command(invocation_command) if invocation_command else "<TODO>"

    # Calculate time spent. For a single run, the summed durations are divided
    # by that run's concurrency. For averaged multi-run reports, prefer the
    # per-run-normalized wall-clock estimates (each run divided by its own
    # concurrency before averaging) when present.
    n_concurrent = config_dict.get("n_concurrent_trials", 1)
    total_time = format_time(
        metrics.wall_total_time_seconds
        if metrics.wall_total_time_seconds is not None
        else metrics.total_time_seconds // n_concurrent
    )
    agent_time = format_time(
        metrics.wall_agent_time_seconds
        if metrics.wall_agent_time_seconds is not None
        else metrics.agent_time_seconds // n_concurrent
    )
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
    
    # Build config/result sections: identical to the old single-run layout for 1 run,
    # labeled "Run N" subsections (ordered by start time) for multiple runs
    if n_runs == 1:
        config_section = f"**`config.json`:**\n\n```json\n{config_json}\n```"
        result_section = f"```json\n{result_json}\n```"
    else:
        config_section = "\n\n".join(
            f"### Run {i + 1}: {run_configs[i]['job_name']}\n\n**`config.json`:**\n\n```json\n{(d / 'config.json').read_text()}\n```"
            for i, d in enumerate(job_dirs)
        )
        result_section = "\n\n".join(
            f"### Run {i + 1}: {run_configs[i]['job_name']}\n\n```json\n{(d / 'result.json').read_text()}\n```"
            for i, d in enumerate(job_dirs)
        )
    
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
        config_section=config_section,
        result_section=result_section,
        results_suffix=results_suffix,
    )
    
    # Save report
    benchmark_dir = Path(__file__).parent.parent / "benchmarks"
    report_name = f"{dataset.split("/")[-1]}_{model.split("/")[-1]}_{harness}.md".replace("/", "_")
    with open(benchmark_dir / report_name, "w") as f:
        f.write(report)
    
    return report


def run_identity(job_dir: Path) -> tuple:
    """Identity of a run for averaging compatibility: dataset, model, harness."""
    config = json.loads((job_dir / "config.json").read_text())
    agent_config = config["agents"][0]
    dataset = config["datasets"][0].get("name") or config["datasets"][0].get("path")
    model = (agent_config.get("model_name") or (agent_config.get("env") or {}).get("ANTHROPIC_MODEL") or "").replace("vllm/", "")
    harness = agent_config["name"]
    return (dataset, model, harness)

def main():
    args = parse_args()
    num_gpus = args.num_gpus
    gpu_cost_per_hour = args.gpu_cost_per_hour

    # Order runs by start time (Run 1 = earliest)
    job_dirs = sorted(
        args.job_dirs,
        key=lambda d: json.loads((d / "lock.json").read_text())["created_at"],
    )

    # Compute metrics for each run
    all_metrics = []
    for job_dir in job_dirs:
        job_format = determine_format(job_dir)
        if job_format == "legacy":
            m = compute_metrics_legacy(job_dir, num_gpus, gpu_cost_per_hour)
        elif job_format == "latest":
            m = compute_metrics_latest(job_dir, num_gpus, gpu_cost_per_hour)
        print(f"run {job_dir.name}: score={m.score} errors={m.n_errors} cost=${m.cost_usd}")
        all_metrics.append(m)

    if any(m.n_tasks != all_metrics[0].n_tasks for m in all_metrics):
        raise SystemExit("Inconsistent runs: differing n_tasks, refusing to average")

    # Refuse to average runs of different benchmarks/models/harnesses
    identities = {run_identity(d) for d in job_dirs}
    if len(identities) > 1:
        raise SystemExit(f"Inconsistent runs: differing dataset/model/harness {identities}, refusing to average")

    # Per-run concurrency (config n_concurrent_trials, falling back to the lock file)
    concurrencies = [
        json.loads((d / "config.json").read_text()).get("n_concurrent_trials")
        or json.loads((d / "lock.json").read_text()).get("n_concurrent_trials", 1)
        for d in job_dirs
    ]

    # Average across runs when more than one is given. Concurrency per run is
    # passed so wall-clock estimates normalize each run by its own setting.
    if len(all_metrics) == 1:
        metrics = all_metrics[0]
    else:
        metrics = average_metrics(all_metrics, concurrencies)

    print(metrics.model_dump_json(indent=4))
    
    # Create the job report
    if args.report:
        create_job_report(job_dirs, metrics, num_gpus, gpu_cost_per_hour)

if __name__ == "__main__":
    main()
