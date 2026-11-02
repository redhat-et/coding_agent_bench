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

import yaml


SUBAGENT_INLINE_PREFIX = "opencode-subagent:"
SUBAGENT_POLICY_INLINE_PREFIX = "opencode-subagent-policy:"
MAX_SUBAGENT_PAYLOAD_BYTES = 1024 * 1024
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.:-]+)+$")
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
