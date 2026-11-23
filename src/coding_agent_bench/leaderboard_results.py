"""Save job-specific metadata and refresh leaderboard snapshots from Harbor."""

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile

from coding_agent_bench.preemption import PAUSE_REQUEST_PATH

METADATA_FILE = "leaderboard-metadata.json"
RESULT_FILE = "leaderboard-result.json"
GITHUB_DATASET_SOURCE = Path("/tmp/cab-github-dataset/source")
GITHUB_DATASET_PROVENANCE = Path("/tmp/cab-github-dataset/provenance.json")
logger = logging.getLogger(__name__)


def atomic_json(path: Path, document: dict) -> None:
    """Replace a complete document so resumes never expose a partial file."""
    content = json.dumps(document, indent=4, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_metadata(job_dir: Path, metadata: dict) -> None:
    atomic_json(job_dir / METADATA_FILE, metadata)


def job_metadata(dataset: str, model: str, agent: str, *, version=None,
                 skills=None, overrides=None, github_source=None) -> dict:
    """Capture identities from job inputs; stable catalog facts stay in the loader."""
    repo, _, ref = dataset.partition("@")
    benchmark = {"name": repo, "repo": repo, "source": "harbor"}
    if ref:
        benchmark["version"] = ref
    if Path(repo).is_absolute() or repo.startswith("."):
        benchmark = {"name": Path(repo).name, "repo": repo, "source": "local"}
    if github_source:
        repo = github_source["repository_url"].removeprefix("https://github.com/")
        directory = github_source.get("subdirectory", "")
        name = repo + (f"/{directory}" if directory else "")
        benchmark = {
            "name": name,
            "repo": repo,
            "url": github_source["repository_url"],
            "source": "github",
            "dataset_source": github_source,
        }
    harness = {"name": agent}
    if version and version not in ("unknown", "latest"):
        harness["version"] = version
    result = {
        "benchmark": benchmark,
        "model": {"name": model.removeprefix("vllm/")},
        "harness": harness,
        "configuration": {"skills": skills or []},
    }
    for section, values in (overrides or {}).items():
        if not isinstance(values, dict):
            raise ValueError(f"Metadata section {section} must be an object")
        if section == "benchmark":
            values = {key: value for key, value in values.items() if key != "dataset_source"}
        result.setdefault(section, {}).update(deepcopy(values))
    # Older saved metadata put model-serving GPU allocation under environment.
    # Move the pair when refreshing those candidates, preserving model overrides.
    environment = result.get("environment", {})
    legacy_gpu = {key: environment.pop(key) for key in ("gpu_type", "gpu_count") if key in environment}
    if not any(result["model"].get(key) is not None for key in ("gpu_type", "gpu_count")):
        result["model"].update(legacy_gpu)
    return result


def runtime_github_source(dataset: str) -> dict | None:
    path = Path(dataset)
    if path != GITHUB_DATASET_SOURCE and GITHUB_DATASET_SOURCE not in path.parents:
        return None
    return json.loads(GITHUB_DATASET_PROVENANCE.read_text())


def resolved_task_names(job_dir: Path) -> list[str]:
    """Read the canonical task set Harbor resolved before starting trials.

    Harbor's job lock contains stable task names, unlike trial names which can
    include per-run suffixes. Without a valid lock, a trustworthy task-set
    identity cannot be produced.
    """
    lock_path = job_dir / "lock.json"
    if not lock_path.is_file():
        raise ValueError(f"Harbor task lock is required for leaderboard identity: {lock_path}")
    try:
        lock = json.loads(lock_path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not read Harbor task lock {lock_path}: {error}") from error

    trials = lock.get("trials") if isinstance(lock, dict) else None
    if not isinstance(trials, list):
        raise ValueError(f"Harbor task lock {lock_path} has no trials list")

    names = []
    for trial in trials:
        task = trial.get("task") if isinstance(trial, dict) else None
        name = task.get("name") if isinstance(task, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Harbor task lock {lock_path} has a trial without a task name")
        names.append(name)
    if not names:
        raise ValueError(f"Harbor task lock {lock_path} has no task names")
    return sorted(set(names))


def dataset_identity(
    dataset: dict,
    github_source: dict | None = None,
    *,
    selected_task_names: list[str],
) -> str:
    """Identify a pinned dataset source and its resolved task set."""
    source = {key: dataset[key] for key in (
        "name", "repo", "ref", "version", "path", "registry", "registry_url", "registry_path",
    ) if dataset.get(key) is not None}
    if github_source:
        source = {key: github_source.get(key) for key in ("repository_url", "commit", "subdirectory")}
    elif source.get("ref"):
        source.pop("version", None)  # Requested aliases don't change the resolved revision.
    if not source:
        raise ValueError("Resolved dataset source is required for leaderboard identity")
    selection = {"tasks": sorted(set(selected_task_names))}
    encoded = json.dumps({"source": source, "selection": selection}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def phase_duration(timing: dict | None, *, present: bool = True) -> float | None:
    """Harbor null phases never started; absent/incomplete/invalid timings are unknown."""
    if not present:
        return None
    if timing is None:
        return 0
    if "started_at" not in timing or "finished_at" not in timing:
        return None
    start, end = timing["started_at"], timing["finished_at"]
    if start is None and end is None:
        return 0
    if start is None or end is None:
        return None
    try:
        seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    except (ValueError, TypeError):
        return None
    return seconds if seconds >= 0 else None


def result_metrics(harbor: dict, trials: list[dict]) -> dict:
    """Use recorded aggregates; unknown scores, tokens, and timings stay null."""
    stats = harbor.get("stats") or {}
    completed = stats.get("n_completed_trials", stats.get("n_trials", 0))
    result = {
        "n_tasks": completed,
        "n_errors": stats.get("n_errored_trials", stats.get("n_errors", 0)),
        "score": None,
        "cost_usd": stats.get("cost_usd"),
    }
    groups = list((stats.get("evals") or {}).values())
    if len(groups) == 1:
        for metric in groups[0].get("metrics") or []:
            for key in ("reward", "mean"):
                if metric.get(key) is not None:
                    result["score"] = metric[key]
                    break
            if result["score"] is not None:
                break
    for key in ("n_input_tokens", "n_cache_tokens", "n_output_tokens"):
        values = [(trial.get("agent_result") or {}).get(key) for trial in trials]
        result[key] = stats.get(key)
        if key not in stats and len(values) == completed and values and all(value is not None for value in values):
            result[key] = sum(values)
    result["n_total_tokens"] = (
        result["n_input_tokens"] + result["n_output_tokens"]
        if result["n_input_tokens"] is not None and result["n_output_tokens"] is not None
        else None
    )

    total_time, agent_time = trial_times(trials, completed)
    result.update(total_time_seconds=total_time, agent_time_seconds=agent_time)
    for source, target in (
        ("n_input_tokens", "input_tokens"), ("n_cache_tokens", "cache_tokens"),
        ("n_output_tokens", "output_tokens"), ("n_total_tokens", "tokens"),
        ("cost_usd", "cost_usd"), ("total_time_seconds", "total_time_seconds"),
        ("agent_time_seconds", "agent_time_seconds"),
    ):
        value = result[source]
        result[f"mean_{target}_per_task"] = (
            round(value / completed, 2) if source == "cost_usd" else int(value / completed)
        ) if value is not None and completed else None
    return result


def trial_times(trials: list[dict], completed: int) -> tuple[int | None, int | None]:
    """Share timing accounting between leaderboard snapshots and CLI metrics."""
    total_durations = [
        0 if "started_at" in trial and trial["started_at"] is None
        and (trial.get("exception_info") or {}).get("exception_type") == "CancelledError"
        else phase_duration(trial)
        for trial in trials
    ]
    agent_durations = [
        phase_duration(step.get("agent_execution"), present="agent_execution" in step)
        for trial in trials
        for step in (trial.get("step_results") or [trial])
    ]

    def total_if_known(durations: list[float | None]) -> int | None:
        if len(trials) != completed or not durations or any(value is None for value in durations):
            return None
        return int(sum(value for value in durations if value is not None))

    return total_if_known(total_durations), total_if_known(agent_durations)


def build_leaderboard_result(job_dir: Path, returncode: int | None = None,
                             overrides: dict | None = None) -> dict:
    """Build a snapshot for both automatic and manual exports without writing files."""
    result_path = job_dir / "result.json"
    harbor = json.loads(result_path.read_text())
    config_path = job_dir / "config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    metadata_path = job_dir / METADATA_FILE
    saved_metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    metadata = deepcopy(saved_metadata)
    for section, values in (overrides or {}).items():
        if not isinstance(values, dict):
            raise ValueError(f"Metadata section {section} must be an object")
        if section == "benchmark":
            values = {key: value for key, value in values.items() if key != "dataset_source"}
        metadata.setdefault(section, {}).update(deepcopy(values))
    dataset = next(iter(config.get("datasets") or []), {})
    agent = next(iter(config.get("agents") or []), {})
    selector = dataset.get("name") or dataset.get("path") or "unknown"
    github_source = None
    dataset_path_value = dataset.get("path")
    dataset_path = Path(dataset_path_value) if dataset_path_value else None
    is_github_dataset = (
        not dataset.get("name")
        and (
            dataset_path is None
            or dataset_path == GITHUB_DATASET_SOURCE
            or GITHUB_DATASET_SOURCE in dataset_path.parents
        )
    )
    if is_github_dataset:
        github_source = (saved_metadata.get("benchmark") or {}).get("dataset_source")
        if GITHUB_DATASET_PROVENANCE.is_file():
            github_source = runtime_github_source(selector) or github_source
    metadata = job_metadata(
        selector, agent.get("model_name") or "unknown", agent.get("name") or "unknown",
        skills=agent.get("skills"), overrides=metadata, github_source=github_source,
    )
    if github_source:
        # Existing labels may be reviewer overrides; the resolved source is authoritative.
        metadata["benchmark"]["dataset_source"] = github_source
    benchmark = metadata.setdefault("benchmark", {})
    task_names = resolved_task_names(job_dir)
    benchmark["id"] = dataset_identity(
        dataset,
        github_source,
        selected_task_names=task_names,
    )
    benchmark.setdefault("num_tasks", harbor.get("n_total_trials"))
    selection = {key: dataset[key] for key in (
        "name", "repo", "ref", "version", "path", "registry", "registry_url", "registry_path",
        "task_names", "exclude_task_names", "n_tasks",
    ) if dataset.get(key) is not None}
    if github_source:
        selection.pop("path", None)
    environment = metadata.setdefault("environment", {})
    environment["config"] = {**environment.get("config", {}), **selection}
    trials = []
    for path in sorted(job_dir.glob("*/result.json")):
        try:
            trials.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            logger.warning("Skipping unreadable trial result: %s", path)
    versions = {(trial.get("agent_info") or {}).get("version") for trial in trials}
    versions -= {None, "", "unknown", "latest"}
    version = next(iter(versions)) if len(versions) == 1 else (agent.get("kwargs") or {}).get("version")
    if version and version not in ("unknown", "latest"):
        metadata.setdefault("harness", {})["version"] = version
    stats = harbor.get("stats") or {}
    total = harbor.get("n_total_trials")
    completed = stats.get("n_completed_trials", stats.get("n_trials", 0))
    paused = returncode is not None and Path(os.environ.get("CAB_PAUSE_REQUEST_PATH", PAUSE_REQUEST_PATH)).exists()
    cancelled = stats.get("n_cancelled_trials", 0) or any(
        (trial.get("exception_info") or {}).get("exception_type") == "CancelledError" for trial in trials
    )
    complete = bool(harbor.get("finished_at") and completed == total and not cancelled
                    and not stats.get("n_pending_trials") and not stats.get("n_running_trials"))
    status = ("paused" if paused else "stopped" if returncode in (-15, -2, 130, 143)
              else "failed" if returncode else "completed" if complete else "partial")
    if returncode is None and (job_dir / RESULT_FILE).is_file():
        # Downloaded artifacts retain the exit status known by the queue.
        previous = json.loads((job_dir / RESULT_FILE).read_text()).get("run") or {}
        if previous.get("finished_at") == harbor.get("finished_at") and previous.get("n_completed_trials") == completed:
            returncode = previous.get("returncode")
            status = previous.get("status", status)
    result = deepcopy(metadata)
    result["run"] = {
        "status": status, "returncode": returncode,
        "complete": status == "completed", "n_total_trials": total,
        "n_completed_trials": completed,
        "started_at": harbor.get("started_at"), "finished_at": harbor.get("finished_at"),
    }
    result["metrics"] = result_metrics(harbor, trials)
    return result


def export_on_completion(job_dir: Path, returncode: int) -> Path | None:
    """Refresh the same file after any exit when Harbor has a result.json."""
    if not (job_dir / "result.json").is_file():
        return None
    result = build_leaderboard_result(job_dir, returncode)
    save_metadata(job_dir, {key: value for key, value in result.items() if key not in ("metrics", "run")})
    output = job_dir / RESULT_FILE
    atomic_json(output, result)
    return output


def try_export_on_completion(job_dir: Path, returncode: int) -> Path | None:
    try:
        return export_on_completion(job_dir, returncode)
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.warning("Could not update leaderboard result for %s: %s", job_dir, error)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("leaderboard",))
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("returncode", type=int)
    args = parser.parse_args()
    try_export_on_completion(args.job_dir, args.returncode)


if __name__ == "__main__":
    main()
