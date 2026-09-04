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
