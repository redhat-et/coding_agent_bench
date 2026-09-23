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
    """Recreate model configuration files that lived outside the uploaded job dir."""
    for agent in config.get("agents") or []:
        name = agent.get("name")
        model = agent.get("model_name", "").removeprefix("vllm/")
        for mount in config.get("environment", {}).get("mounts") or []:
            source, target = mount.get("source"), mount.get("target", "")
            if not source:
                continue
            path = Path(source)
            if name == "codex" and target == "/root/.codex/config.toml":
                from coding_agent_bench.helpers.codex import codex_create_toml

                path.parent.mkdir(parents=True, exist_ok=True)
                codex_create_toml(
                    model, server_url, path,
                    openrouter="OPENROUTER_API_KEY" in (agent.get("env") or {}),
                )
            elif name == "pi" and target == "/root/.pi/agent/models.json":
                data = json.loads(path.read_text()) if path.exists() else {
                    "providers": {"vllm": {
                        "api": "openai-completions", "apiKey": "NONE",
                        "models": [{"id": model, "name": model}],
                    }},
                }
                data["providers"]["vllm"]["baseUrl"] = server_url.rstrip("/").removesuffix("/v1") + "/v1"
                path.parent.mkdir(parents=True, exist_ok=True)
                _write_metadata(path, data)


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("parent", "endpoint"))
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("server_url", nargs="?")
    args = parser.parse_args()
    if args.operation == "parent":
        update_parent(args.job_dir, os.environ["HARBOR_PARENT"])
    elif args.server_url is None:
        parser.error("endpoint requires server_url")
    else:
        update_endpoint(args.job_dir, args.server_url)


if __name__ == "__main__":
    main()
