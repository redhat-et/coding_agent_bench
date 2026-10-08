"""Prepare restored Harbor metadata consistently before resuming a job."""

import argparse
import json
import os
from pathlib import Path
import shlex
from urllib.parse import urlsplit


def is_resume_command(command: list[str]) -> bool:
    """Recognize the queue's shell-command representation of a resume."""
    return isinstance(command, list) and len(command) == 3 and command[0] in ("sh", "bash") and command[1] == "-c"


def resume_options(command: str | list[str]) -> dict[str, list[str]]:
    """Read artifact paths and filters from legacy commands without executing them."""
    if isinstance(command, str):
        command = json.loads(command)
    if not is_resume_command(command):
        return {}
    lexer = shlex.shlex(command[2], posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    for index in range(len(tokens) - 2):
        if tokens[index:index + 3] != ["harbor", "jobs", "resume"]:
            continue
        options: dict[str, list[str]] = {"paths": [], "filters": []}
        args = iter(tokens[index + 3:])
        for token in args:
            if token and all(char in ";&|<>" for char in token):
                break
            if token in ("-p", "--job-path"):
                options["paths"].append(next(args, ""))
            elif token in ("-f", "--filter-error-type"):
                options["filters"].append(next(args, ""))
            elif token.startswith("--job-path="):
                options["paths"].append(token.split("=", 1)[1])
            elif token.startswith("--filter-error-type="):
                options["filters"].append(token.split("=", 1)[1])
        return options
    return {}


def results_job_name(row: dict) -> str:
    """Keep the artifact identity separate from display names such as --resume."""
    if row.get("results_job_name"):
        return row["results_job_name"]
    try:
        options = resume_options(row.get("command") or [])
        for path in options.get("paths", []):
            if path.startswith("/app/jobs/"):
                return path.removeprefix("/app/jobs/").rstrip("/")
    except (ValueError, TypeError, IndexError):
        pass
    # A real benchmark can itself be named foo--resume; never strip it blindly.
    return row["job_name"]


def _metadata_files(job_dir: Path) -> list[Path]:
    """Select Harbor metadata, excluding agent logs and task-generated JSON files."""
    if not (job_dir / "config.json").is_file():
        raise FileNotFoundError(f"No restored Harbor config at {job_dir / 'config.json'}")
    directories = [job_dir] + [
        path for path in job_dir.iterdir()
        if path.is_dir() and (path / "config.json").is_file()
    ]
    return [
        directory / name for directory in directories
        for name in ("config.json", "lock.json", "result.json")
        if (directory / name).is_file()
    ]


def _config_documents(document: dict):
    """Walk config/lock/result schema containers, not arbitrary artifact content."""
    yield document
    if isinstance(document.get("config"), dict):
        yield from _config_documents(document["config"])
    for field in ("trials", "trial_results"):
        for nested in document.get(field) or []:
            if isinstance(nested, dict):
                yield from _config_documents(nested)


def _write_metadata(path: Path, document: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=4))
    temporary.replace(path)


def update_parent(job_dir: Path, parent: str) -> None:
    """Update ownership in the job, saved trials, embedded configs, and locks."""
    for path in _metadata_files(job_dir):
        document = json.loads(path.read_text())
        before = json.dumps(document)
        if path.name == "config.json":
            document.setdefault("environment", {})
        for config in _config_documents(document):
            environment = config.get("environment")
            if isinstance(environment, dict):
                env = environment.setdefault("kwargs", {}).setdefault("persistent_env", {})
                env["HARBOR_PARENT"] = parent
        if json.dumps(document) != before:
            _write_metadata(path, document)


def _agents(config: dict):
    if isinstance(config.get("agent"), dict):
        yield config["agent"]
    yield from config.get("agents") or []


def _update_agent_endpoint(agent: dict, server_url: str) -> None:
    env = agent.get("env") or {}
    base = server_url.rstrip("/")
    api_base = base.removesuffix("/v1") + "/v1"
    for key in ("ANTHROPIC_BASE_URL", "OPENAI_BASE_URL", "HOSTED_VLLM_API_BASE"):
        if key in env:
            env[key] = base if key == "ANTHROPIC_BASE_URL" else api_base
    if env.get("OPENCODE_CONFIG_CONTENT"):
        opencode = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        provider = opencode.get("provider", {}).get("vllm")
        if provider is not None:
            provider.setdefault("options", {})["baseURL"] = api_base
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps(opencode)


def _restore_agent_mounts(config: dict, server_url: str) -> None:
    """Let each registered agent recreate its own external bind-mounted files."""
    from coding_agent_bench.agents import AGENT_REGISTRY

    for agent in _agents(config):
        agent_config = AGENT_REGISTRY.get(agent.get("name"))
        if agent_config is not None:
            agent_config.restore_mounts(config, server_url)


def update_endpoint(job_dir: Path, server_url: str) -> None:
    """Retarget model settings without rewriting unrelated URLs or result data."""
    parsed = urlsplit(server_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Model server URL must be an HTTP(S) URL")
    for path in _metadata_files(job_dir):
        document = json.loads(path.read_text())
        before = json.dumps(document)
        for config in _config_documents(document):
            for agent in _agents(config):
                _update_agent_endpoint(agent, server_url)
        if json.dumps(document) != before:
            _write_metadata(path, document)
    _restore_agent_mounts(json.loads((job_dir / "config.json").read_text()), server_url)


def is_job_complete(job_dir: Path) -> bool:
    """Require a finished, error-free result before discarding recovery snapshots.

    A cooperative pause also exits with status zero. Check both the current
    pod's pause request and trial counts; preemption.json can describe an older
    attempt restored from object storage and must not block a later successful resume.
    Missing or malformed metadata is not proof of completion.
    """
    from coding_agent_bench.preemption import PAUSE_REQUEST_PATH

    try:
        request = Path(os.environ.get("CAB_PAUSE_REQUEST_PATH", PAUSE_REQUEST_PATH))
        if request.exists():
            return False
        result = json.loads((job_dir / "result.json").read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(result, dict) or not result.get("finished_at"):
        return False
    total = result.get("n_total_trials")
    stats = result.get("stats")
    if type(total) is not int or total < 0 or not isinstance(stats, dict):
        return False
    expected = {
        "n_completed_trials": total,
        "n_pending_trials": 0,
        "n_running_trials": 0,
        "n_cancelled_trials": 0,
        "n_errored_trials": 0,
    }
    return all(type(stats.get(key)) is int and stats[key] == value for key, value in expected.items())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("parent", "endpoint", "complete"))
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("server_url", nargs="?")
    args = parser.parse_args()
    if args.operation == "parent":
        update_parent(args.job_dir, os.environ["HARBOR_PARENT"])
    elif args.operation == "complete":
        raise SystemExit(0 if is_job_complete(args.job_dir) else 1)
    elif args.server_url is None:
        parser.error("endpoint requires server_url")
    else:
        update_endpoint(args.job_dir, args.server_url)


if __name__ == "__main__":
    main()
