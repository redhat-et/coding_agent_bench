from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml


SUBAGENT_INLINE_PREFIX = "opencode-subagent:"
SUBAGENT_POLICY_INLINE_PREFIX = "opencode-subagent-policy:"
SUBAGENT_PROVIDER_INLINE_PREFIX = "opencode-subagent-provider:"
MAX_SUBAGENT_PAYLOAD_BYTES = 1024 * 1024
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.:-]+)+$")
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9_.:@-]+$")
_ENV_INTERPOLATION_RE = re.compile(r"^\{env:([A-Za-z_][A-Za-z0-9_]*)\}$")
ALLOWED_PROVIDER_API_KEY_ENVS = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "AZURE_API_KEY",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "MISTRAL_API_KEY",
        "OPENAI_API_KEY",
        "OPENCODE_API_KEY",
        "OPENROUTER_API_KEY",
        "XAI_API_KEY",
    }
)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


@dataclass(frozen=True)
class SubagentDefinition:
    name: str
    description: str
    mode: str
    model: str | None
    prompt: str
    metadata: dict[str, Any]
    markdown: str
    source: str
    sha256: str

    def to_opencode_config(self) -> dict[str, Any]:
        config = dict(self.metadata)
        config.pop("name", None)
        config["prompt"] = self.prompt
        return config

    def to_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "source": self.source,
            "markdown_sha256": self.sha256,
        }


@dataclass(frozen=True)
class SubagentProviderDefinition:
    name: str
    config: dict[str, Any]
    source: str
    sha256: str

    def to_metadata(self) -> dict[str, str]:
        return {
            "name": self.name,
            "source": self.source,
            "sha256": self.sha256,
            "configuration_sha256": self.configuration_sha256(),
        }

    def configuration_sha256(self) -> str:
        canonical = dict(self.config)
        options = canonical.get("options")
        if isinstance(options, dict):
            options = dict(options)
            options.pop("baseURL", None)
            canonical["options"] = options
        return hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def network_host(self) -> str | None:
        endpoint = (self.config.get("options") or {}).get("baseURL")
        if endpoint is None:
            return None
        return validate_provider_endpoint(endpoint).hostname


def _decode_inline(value: str, prefix: str) -> bytes:
    if not value.startswith(prefix):
        raise ValueError(f"Invalid inline subagent payload: {value!r}")
    try:
        return base64.b64decode(value[len(prefix) :], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid inline subagent payload encoding") from exc


def _read_subagent(source: str | Path) -> tuple[str, str, bytes]:
    value = str(source)
    if value.startswith(SUBAGENT_INLINE_PREFIX):
        payload = _decode_inline(value, SUBAGENT_INLINE_PREFIX)
        return "<inline remote payload>", _decode_payload(payload), payload
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"OpenCode subagent file not found: {path}")
    payload = path.read_bytes()
    return str(path.resolve()), _decode_payload(payload), payload


def validate_provider_endpoint(endpoint: str):
    """Validate and normalize an OpenCode provider HTTP(S) endpoint."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("OpenCode provider endpoint must be an HTTP(S) URL")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("OpenCode provider endpoint must be an HTTP(S) URL")
    if "*" in unquote(parsed.hostname) or "*" in unquote(parsed.path):
        raise ValueError("OpenCode provider endpoint must not contain wildcards")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("OpenCode provider endpoint contains an invalid port") from exc
    if port == 0:
        raise ValueError("OpenCode provider endpoint port must be between 1 and 65535")
    return parsed


def _decode_payload(payload: bytes) -> str:
    if len(payload) > MAX_SUBAGENT_PAYLOAD_BYTES:
        raise ValueError(
            f"OpenCode subagent payload exceeds {MAX_SUBAGENT_PAYLOAD_BYTES} bytes"
        )
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("OpenCode subagent payload must be UTF-8") from exc


def _parse_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(markdown)
    if not match:
        raise ValueError("OpenCode subagent must start with YAML frontmatter")
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid OpenCode subagent frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("OpenCode subagent frontmatter must be a mapping")
    return metadata, markdown[match.end() :]


def load_subagent_definition(source: str | Path) -> SubagentDefinition:
    source_reference, markdown, payload = _read_subagent(source)
    metadata, prompt = _parse_frontmatter(markdown)

    name = metadata.get("name")
    description = metadata.get("description")
    mode = metadata.get("mode")
    model = metadata.get("model")

    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError(
            "OpenCode subagent frontmatter 'name' is required and may contain "
            "only letters, numbers, underscores, and hyphens"
        )
    if not isinstance(description, str) or not description.strip():
        raise ValueError(
            f"OpenCode subagent {name!r} requires a non-empty 'description'"
        )
    if mode != "subagent":
        raise ValueError(
            f"OpenCode subagent {name!r} must set mode: subagent"
        )
    if model is not None and (
        not isinstance(model, str)
        or not model.strip()
        or _MODEL_RE.fullmatch(model) is None
    ):
        raise ValueError(
            f"OpenCode subagent {name!r} model must be in provider/model format"
        )
    if not prompt.strip():
        raise ValueError(f"OpenCode subagent {name!r} requires Markdown instructions")
    if "permission" in metadata and not isinstance(metadata["permission"], dict):
        raise ValueError(
            f"OpenCode subagent {name!r} permission metadata must be a mapping"
        )
    try:
        json.dumps(metadata, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"OpenCode subagent {name!r} frontmatter must contain "
            "JSON-compatible values"
        ) from exc

    return SubagentDefinition(
        name=name,
        description=description,
        mode=mode,
        model=model,
        prompt=prompt,
        metadata=metadata,
        markdown=markdown,
        source=source_reference,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def load_subagent_definitions(sources: list[str | Path] | None) -> list[SubagentDefinition]:
    definitions: list[SubagentDefinition] = []
    names: set[str] = set()
    for source in sources or []:
        definition = load_subagent_definition(source)
        if definition.name in names:
            raise ValueError(
                f"Duplicate OpenCode subagent name: {definition.name}"
            )
        names.add(definition.name)
        definitions.append(definition)
    return definitions


def _read_provider_document(source: str | Path) -> tuple[str, bytes, str]:
    value = str(source)
    if value.startswith(SUBAGENT_PROVIDER_INLINE_PREFIX):
        payload = _decode_inline(value, SUBAGENT_PROVIDER_INLINE_PREFIX)
        return "<inline remote payload>", payload, _decode_payload(payload)
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"OpenCode subagent provider file not found: {path}")
    payload = path.read_bytes()
    return str(path.resolve()), payload, _decode_payload(payload)


def _parse_provider_document(markdown: str) -> dict[str, Any]:
    try:
        if markdown.lstrip().startswith("{"):
            document = json.loads(markdown)
        else:
            document = yaml.safe_load(markdown)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid OpenCode subagent provider document: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("OpenCode subagent provider document must be a mapping")
    return document


def validate_subagent_provider_document(
    document: dict[str, Any],
) -> list[SubagentProviderDefinition]:
    """Validate an OpenCode provider mapping without embedding credentials."""
    definitions: list[SubagentProviderDefinition] = []
    try:
        json.dumps(document, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "OpenCode subagent provider document must contain JSON-compatible values"
        ) from exc
    for name, config in document.items():
        if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
            raise ValueError(
                "OpenCode provider names may contain only letters, numbers, "
                "underscores, and hyphens"
            )
        if name == "vllm":
            raise ValueError("OpenCode provider 'vllm' is reserved for the primary model")
        if not isinstance(config, dict):
            raise ValueError(f"OpenCode provider {name!r} must be a mapping")
        if not isinstance(config.get("npm"), str) or not config["npm"].strip():
            raise ValueError(f"OpenCode provider {name!r} requires a non-empty 'npm'")
        options = config.get("options", {})
        if not isinstance(options, dict):
            raise ValueError(f"OpenCode provider {name!r} options must be a mapping")
        if "baseURL" in options:
            endpoint = validate_provider_endpoint(options["baseURL"])
            if endpoint.path.rstrip("/").endswith("/v1"):
                normalized = options["baseURL"].rstrip("/")
            else:
                normalized = options["baseURL"].rstrip("/") + "/v1"
            options["baseURL"] = normalized
        if "apiKey" in options and (
            not isinstance(options["apiKey"], str)
            or _ENV_INTERPOLATION_RE.fullmatch(options["apiKey"]) is None
        ):
            raise ValueError(
                f"OpenCode provider {name!r} apiKey must use {{env:VARIABLE_NAME}}"
            )
        if "apiKey" in options:
            match = _ENV_INTERPOLATION_RE.fullmatch(options["apiKey"])
            if match is None or match.group(1) not in ALLOWED_PROVIDER_API_KEY_ENVS:
                raise ValueError(
                    f"OpenCode provider {name!r} apiKey references an unsupported "
                    "credential environment variable"
                )
        models = config.get("models")
        if not isinstance(models, dict) or not models:
            raise ValueError(
                f"OpenCode provider {name!r} models must be a non-empty mapping"
            )
        for model_id, model_config in models.items():
            if not isinstance(model_id, str) or not _MODEL_ID_RE.fullmatch(model_id):
                raise ValueError(
                    f"OpenCode provider {name!r} contains an invalid model ID"
                )
            if not isinstance(model_config, dict):
                raise ValueError(
                    f"OpenCode provider {name!r} model {model_id!r} must be a mapping"
                )
            limit = model_config.get("limit")
            if limit is not None:
                if not isinstance(limit, dict):
                    raise ValueError(
                        f"OpenCode provider {name!r} model {model_id!r} limit must be a mapping"
                    )
                for key in ("context", "output"):
                    value = limit.get(key)
                    if value is not None and (type(value) is not int or value < 1):
                        raise ValueError(
                            f"OpenCode provider {name!r} model {model_id!r} "
                            f"{key} limit must be a positive integer"
                        )
        definitions.append(
            SubagentProviderDefinition(
                name=name,
                config=config,
                source="<inline document>",
                sha256=hashlib.sha256(
                    json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            )
        )
    if not definitions:
        raise ValueError("OpenCode subagent provider document must define a provider")
    return definitions


def load_subagent_providers(
    sources: list[str | Path | dict[str, Any]] | None,
) -> list[SubagentProviderDefinition]:
    definitions: list[SubagentProviderDefinition] = []
    names: set[str] = set()
    for source in sources or []:
        if isinstance(source, dict):
            source_payload = json.dumps(
                source, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            if len(source_payload) > MAX_SUBAGENT_PAYLOAD_BYTES:
                raise ValueError(
                    f"OpenCode subagent provider payload exceeds "
                    f"{MAX_SUBAGENT_PAYLOAD_BYTES} bytes"
                )
            document_definitions = validate_subagent_provider_document(source)
            source_reference = "<inline API document>"
        else:
            source_reference, payload, document = _read_provider_document(source)
            source_payload = payload
            try:
                document_definitions = validate_subagent_provider_document(
                    _parse_provider_document(document)
                )
            except ValueError:
                raise
        for definition in document_definitions:
            if definition.name in names:
                raise ValueError(
                    f"Duplicate OpenCode subagent provider name: {definition.name}"
                )
            names.add(definition.name)
            if not isinstance(source, dict):
                definitions.append(
                    SubagentProviderDefinition(
                        name=definition.name,
                        config=definition.config,
                        source=source_reference,
                        sha256=hashlib.sha256(source_payload).hexdigest(),
                    )
                )
            else:
                definitions.append(
                    SubagentProviderDefinition(
                        name=definition.name,
                        config=definition.config,
                        source=source_reference,
                        sha256=definition.sha256,
                    )
                )
    return definitions


def subagents_to_opencode_config(definitions: list[SubagentDefinition]) -> dict[str, Any]:
    return {
        definition.name: definition.to_opencode_config()
        for definition in definitions
    }


def policy_metadata(source: str | Path) -> dict[str, str]:
    value = str(source)
    if value.startswith(SUBAGENT_POLICY_INLINE_PREFIX):
        payload = _decode_inline(value, SUBAGENT_POLICY_INLINE_PREFIX)
        source_reference = "<inline remote payload>"
    else:
        path = Path(value)
        if not path.is_file():
            raise ValueError(f"OpenCode subagent policy file not found: {path}")
        payload = path.read_bytes()
        source_reference = str(path.resolve())
    _decode_payload(payload)
    if len(payload) > MAX_SUBAGENT_PAYLOAD_BYTES:
        raise ValueError(
            f"OpenCode subagent policy exceeds {MAX_SUBAGENT_PAYLOAD_BYTES} bytes"
        )
    return {
        "source": source_reference,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def materialize_inline_policy(source: str | Path) -> Path:
    value = str(source)
    if not value.startswith(SUBAGENT_POLICY_INLINE_PREFIX):
        return Path(value)
    payload = _decode_inline(value, SUBAGENT_POLICY_INLINE_PREFIX)
    policy_path = None
    try:
        policy_file = tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        )
        policy_path = Path(policy_file.name)
        with policy_file:
            policy_file.write(_decode_payload(payload))
        return policy_path
    except Exception:
        if policy_path is not None:
            policy_path.unlink(missing_ok=True)
        raise


def inline_subagent_argument(markdown: str) -> str:
    return SUBAGENT_INLINE_PREFIX + base64.b64encode(markdown.encode("utf-8")).decode("ascii")


def inline_policy_argument(markdown: str) -> str:
    return SUBAGENT_POLICY_INLINE_PREFIX + base64.b64encode(
        markdown.encode("utf-8")
    ).decode("ascii")


def inline_provider_argument(document: dict[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return SUBAGENT_PROVIDER_INLINE_PREFIX + base64.b64encode(payload).decode("ascii")


def encode_remote_path_arguments(
    arguments: list[str], option: str, prefix: str
) -> list[str]:
    encoded: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == option and index + 1 < len(arguments):
            path = Path(arguments[index + 1])
            if not path.is_file():
                raise ValueError(f"File not found for {option}: {path}")
            encoded.extend(
                [
                    option,
                    prefix
                    + base64.b64encode(path.read_bytes()).decode("ascii"),
                ]
            )
            index += 2
            continue
        if argument.startswith(f"{option}="):
            path = Path(argument.split("=", 1)[1])
            if not path.is_file():
                raise ValueError(f"File not found for {option}: {path}")
            encoded.append(
                option
                + "="
                + prefix
                + base64.b64encode(path.read_bytes()).decode("ascii")
            )
            index += 1
            continue
        encoded.append(argument)
        index += 1
    return encoded
