"""Experiment options specific to OpenCode's optional reviewer."""

from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from coding_agent_bench.providers import OPENROUTER_BASE_URL, is_openrouter


class OpenCodeSubagentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    model_name: str = Field(min_length=1)
    server_url: str | None = None
    model_max_len: int = Field(default=262000, ge=4, strict=True)
    description: str = Field(
        default="Consult this stronger reviewer when stuck, uncertain about a solution, "
        "or needing a code review before finishing.",
        min_length=1,
    )
    prompt: str = Field(
        default="Review the primary agent's question and code. Identify mistakes and "
        "suggest concrete next steps. Return advice without modifying files.",
        min_length=1,
    )

    @field_validator("server_url")
    @classmethod
    def validate_endpoint(cls, value: str | None) -> str | None:
        if value is not None and value != "openrouter":
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("subagent server_url must be HTTP(S) or 'openrouter'")
            if "*" in unquote(parsed.hostname):
                raise ValueError(
                    "subagent server_url must not contain a wildcard hostname"
                )
            try:
                port = parsed.port
            except ValueError as exc:
                raise ValueError(
                    "subagent server_url contains an invalid port"
                ) from exc
            if port == 0:
                raise ValueError("subagent server_url port must be between 1 and 65535")
        return value

    @classmethod
    def from_command(cls, command: list[str]) -> "OpenCodeSubagentConfig | None":
        """Read and normalize the reviewer's CLI option, including the equals form."""
        reviewer = None
        for index, argument in enumerate(command):
            if argument == "--opencode-subagent":
                if index + 1 == len(command):
                    raise ValueError("--opencode-subagent requires a JSON object")
                reviewer = cls.model_validate_json(command[index + 1])
            elif argument.startswith("--opencode-subagent="):
                reviewer = cls.model_validate_json(argument.split("=", 1)[1])
        return reviewer

    def network_host(self, primary_url: str) -> str:
        """Allow only the reviewer endpoint's host during the agent phase."""
        endpoint = self.server_url or primary_url
        if is_openrouter(endpoint):
            endpoint = OPENROUTER_BASE_URL
        # Also guard an inherited primary endpoint before deriving its allowance.
        self.validate_endpoint(endpoint)
        host = urlsplit(endpoint).hostname
        if not host:
            raise ValueError("OpenCode reviewer endpoint must have a hostname")
        return host
