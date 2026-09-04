"""Validation helpers for intake requests and model server URLs."""

import ipaddress
import socket
from urllib.parse import urlparse

from coding_agent_bench.intake.config import ALLOWED_AGENTS, ALLOWED_DATASETS
from coding_agent_bench.nebius_utils import RESOURCE_CONFIG_REGISTRY

NEBIUS_PREFIX = "nebius-"


def _resolve_server_host(host: str, port: int | None) -> set[str]:
    """Resolve a hostname and return its addresses, raising on DNS failure."""
    try:
        results = socket.getaddrinfo(host, 443 if port is None else port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Server hostname '{host}' could not be resolved") from exc
    return {result[4][0] for result in results}


def _is_private_or_reserved(address: str) -> bool:
    """Return whether an address is unsafe for an externally hosted model server."""
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return True
    return any(
        (
            parsed.is_private,
            parsed.is_loopback,
            parsed.is_link_local,
            parsed.is_reserved,
            parsed.is_multicast,
            parsed.is_unspecified,
            not parsed.is_global,
        )
    )


def _is_ip_literal(host: str) -> bool:
    """Return whether a hostname string is an IPv4 or IPv6 literal."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def validate_server_url(
    server_url: str,
    require_https: bool = True,
) -> list[str]:
    """Validate a model URL without requiring a configured hostname allowlist.

    Hostnames are resolved during validation so private, loopback, link-local, and
    reserved addresses cannot be submitted as model endpoints. Callers should
    revalidate immediately before worker creation because DNS can change after
    this check. Managed endpoints may opt out of the HTTPS-only check when the
    provider returns a public HTTP endpoint; ordinary intake URLs remain
    HTTPS-only.
    """
    errors: list[str] = []
    parsed = urlparse(server_url)

    allowed_schemes = {"https"} if require_https else {"http", "https"}
    if parsed.scheme not in allowed_schemes:
        expected = "https" if require_https else "http(s)"
        errors.append(f"Server URL must use {expected} scheme, got '{parsed.scheme or 'none'}'")
        return errors
    if not parsed.netloc or parsed.hostname is None:
        errors.append("Server URL is not a valid URL")
        return errors
    if parsed.username or parsed.password:
        errors.append("Server URL must not contain username or password credentials")
        return errors

    try:
        port = parsed.port
    except ValueError:
        errors.append("Server URL contains an invalid port")
        return errors

    host = parsed.hostname.rstrip(".").lower()

    try:
        addresses = {host} if _is_ip_literal(host) else _resolve_server_host(host, port)
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    if not addresses:
        errors.append(f"Server hostname '{host}' did not resolve to an address")
        return errors

    blocked = sorted(address for address in addresses if _is_private_or_reserved(address))
    if blocked:
        errors.append(
            f"Server hostname '{host}' resolves to private or reserved address(es): "
            + ", ".join(blocked)
        )
    return errors


def _validate_nebius_resource(server_url: str) -> list[str] | None:
    """Validate a managed-Nebius token without requiring a requester URL."""
    if not server_url.lower().startswith(NEBIUS_PREFIX):
        return None
    resource = server_url[len(NEBIUS_PREFIX):].lower()
    if resource not in RESOURCE_CONFIG_REGISTRY:
        allowed = ", ".join(sorted(RESOURCE_CONFIG_REGISTRY))
        return [f"Unknown Nebius resource '{resource}'. Allowed: {allowed}"]
    return []


def validate_row(
    agent: str,
    dataset: str,
    server_url: str,
) -> list[str]:
    """Return human-readable validation errors for one intake spreadsheet row."""
    errors: list[str] = []

    if agent not in ALLOWED_AGENTS:
        allowed = ", ".join(sorted(ALLOWED_AGENTS))
        errors.append(f"Unknown agent '{agent}'. Allowed: {allowed}")

    if dataset not in ALLOWED_DATASETS:
        allowed = ", ".join(sorted(ALLOWED_DATASETS))
        errors.append(f"Unknown dataset '{dataset}'. Allowed: {allowed}")

    if not server_url:
        errors.append("Server URL is empty")
    elif server_url.lower() != "openrouter":
        nebius_errors = _validate_nebius_resource(server_url)
        if nebius_errors is not None:
            errors.extend(nebius_errors)
        else:
            errors.extend(validate_server_url(server_url))

    return errors
