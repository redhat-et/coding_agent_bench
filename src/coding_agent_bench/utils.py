import os
import re
import shlex
from pathlib import Path

from harbor.skills import resolve_repo_source

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_STORAGE_ENDPOINT_URL = "http://harbor-storage:9000"
# Keep policy explicit and small. Harbor options are otherwise forwarded
# dynamically; add a flag name here only when CAB must prevent passthrough.
BLOCKED_HARBOR_FLAGS: frozenset[str] = frozenset(
    {
        # CAB owns these Harbor options because they determine orchestration,
        # model selection, task input, result storage, and job plugins.
        "--env",
        "-e",
        "--model",
        "-m",
        "--path",
        "-p",
        "--dataset",
        "-d",
        "--mounts-json",
        "--plugin",
        "--jobs-dir",
        "-o",
    }
)


def storage_endpoint_url() -> str:
    """Return the configured storage API endpoint, with an in-cluster default."""
    configured = os.environ.get("STORAGE_ENDPOINT_URL", "").strip().rstrip("/")
    return configured or DEFAULT_STORAGE_ENDPOINT_URL


def cmd_to_string(cmd: list[str]):
    """Format a bash command as a string."""
    cmd_string = shlex.join(cmd)
    return cmd_string


def validate_remote_skill_sources(skills: list[str] | None) -> None:
    """Require remotely executed skills to use Harbor-supported Git sources."""
    for skill in skills or []:
        try:
            if skill.startswith((".", "/", "~")) or Path(skill).exists():
                raise ValueError
            resolve_repo_source(skill)
        except ValueError as exc:
            raise ValueError(
                f"Remote skill source {skill!r} is not a Git source. "
                "Use org/name[@ref] or an HTTP(S) Git URL; local paths are "
                "only supported for locally orchestrated runs."
            ) from exc


def is_stage_environment() -> bool:
    """Return True if the application is running in stage environment."""
    environment = os.environ.get("ENVIRONMENT", "").lower()
    if environment not in {"prod", "stage"}:
        raise ValueError("ENVIRONMENT must be set to either 'prod' or 'stage'")
    return environment == "stage"


def parse_envs(envs: str | list[str] | None) -> dict[str, str]:
    """Parse repeatable `key=value` entries into a dict.

    Each entry may itself be a comma-separated `key=value,key=value` string,
    preserving the original single-flag form. Later entries override earlier
    ones on key collision.
    """
    if not envs:
        return {}
    entries = [envs] if isinstance(envs, str) else envs
    parsed = {}
    for entry in entries:
        for pair in entry.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                raise ValueError(f"Invalid --envs entry (expected key=value): {pair!r}")
            key, value = pair.split("=", 1)
            key = key.strip()
            if not _ENV_KEY_RE.match(key):
                raise ValueError(
                    f"Invalid --envs entry (variable name must match [A-Za-z_][A-Za-z0-9_]*): {pair!r}"
                )
            parsed[key] = value
    return parsed


def parse_extra_harbor_lines(lines: list[str] | None) -> list[str]:
    """Split frontend/API Harbor flag lines into command-line tokens."""
    tokens: list[str] = []
    for line in lines or []:
        try:
            tokens.extend(shlex.split(line))
        except ValueError as exc:
            raise ValueError(f"Invalid extra Harbor flags line {line!r}: {exc}") from exc
    return tokens


def harbor_flag_name(token: str) -> str | None:
    """Return an option's name, excluding an optional ``=value`` suffix."""
    if not token.startswith("-") or token == "-":
        return None
    if token.startswith("--"):
        return token.split("=", 1)[0]
    return token[:2]


def validate_extra_harbor_flags(
    tokens: list[str], cab_flags: set[str] | frozenset[str]
) -> None:
    """Reject blocked Harbor flags and duplicate CAB-owned options."""
    for token in tokens:
        flag = harbor_flag_name(token)
        if flag is None:
            continue
        if flag in BLOCKED_HARBOR_FLAGS:
            raise ValueError(f"Harbor flag {flag!r} is blocked from passthrough")
        if flag in cab_flags:
            raise ValueError(
                f"Harbor flag {flag!r} is already supported by coding-agent-bench"
            )


def envs_to_export_lines(envs: dict[str, str]) -> str:
    """Format env vars as `export KEY=VALUE` lines, for display purposes only."""
    return "\n".join(f"export {key}={shlex.quote(value)}" for key, value in envs.items())
