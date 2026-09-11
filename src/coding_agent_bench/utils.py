import shlex
from pathlib import Path

from harbor.skills import resolve_repo_source


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


def parse_envs(envs: str | None) -> dict[str, str]:
    """Parse a comma-separated `key=value,key=value` string into a dict."""
    if not envs:
        return {}
    parsed = {}
    for pair in envs.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"Invalid --envs entry (expected key=value): {pair!r}")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --envs entry (empty key): {pair!r}")
        parsed[key] = value
    return parsed


def envs_to_export_lines(envs: dict[str, str]) -> str:
    """Format env vars as `export KEY=VALUE` lines, for display purposes only."""
    return "\n".join(f"export {key}={shlex.quote(value)}" for key, value in envs.items())
