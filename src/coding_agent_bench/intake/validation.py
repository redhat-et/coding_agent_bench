from urllib.parse import urlparse

from coding_agent_bench.intake.config import ALLOWED_AGENTS, ALLOWED_DATASETS


def validate_row(agent: str, dataset: str, server_url: str) -> list[str]:
    errors = []

    if agent not in ALLOWED_AGENTS:
        allowed = ", ".join(sorted(ALLOWED_AGENTS))
        errors.append(f"Unknown agent '{agent}'. Allowed: {allowed}")

    if dataset not in ALLOWED_DATASETS:
        allowed = ", ".join(sorted(ALLOWED_DATASETS))
        errors.append(f"Unknown dataset '{dataset}'. Allowed: {allowed}")

    if not server_url:
        errors.append("Server URL is empty")
    elif server_url.lower() != "openrouter":
        parsed = urlparse(server_url)
        if parsed.scheme != "https":
            errors.append(f"Server URL must use https scheme, got '{parsed.scheme or 'none'}'")
        elif not parsed.netloc:
            errors.append("Server URL is not a valid URL")

    return errors
