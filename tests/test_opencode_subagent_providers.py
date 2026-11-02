import base64
import json
import shlex

import pytest

from coding_agent_bench import api
from coding_agent_bench.agents.configs import OpenCodeAgentConfig
from coding_agent_bench.builder import HarborCommandBuilder
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.subagents import (
    SUBAGENT_PROVIDER_INLINE_PREFIX,
    encode_remote_path_arguments,
    inline_provider_argument,
    inline_subagent_argument,
    load_subagent_providers,
)
from scripts.calculate_metrics import run_identity


SUBAGENT_MARKDOWN = """---
name: reviewer
description: Review code
mode: subagent
model: reviewer/strong-model
permission:
  edit: deny
  bash: deny
---
Review the implementation.
"""

PROVIDER_DOCUMENT = {
    "reviewer": {
        "npm": "@ai-sdk/openai-compatible",
        "name": "Reviewer",
        "options": {
            "baseURL": "https://reviewer.example.com/api",
            "apiKey": "{env:OPENAI_API_KEY}",
        },
        "models": {
            "strong-model": {
                "name": "Strong model",
                "limit": {"context": 1000, "output": 250},
            }
        },
    }
}


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    subagent = tmp_path / "reviewer.md"
    subagent.write_text(SUBAGENT_MARKDOWN)
    provider = tmp_path / "reviewer.json"
    provider.write_text(json.dumps(PROVIDER_DOCUMENT))
    return subagent, provider


def test_independent_provider_preserves_endpoint_limits_and_credentials(inputs):
    subagent, provider = inputs

    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://primary:8000",
        model_max_len=1000,
        subagents=[subagent],
        subagent_providers=[provider],
    )
    config = result.agent_kwargs["opencode_config"]

    assert config["provider"]["vllm"]["options"]["baseURL"] == "http://primary:8000/v1"
    reviewer = config["provider"]["reviewer"]
    assert reviewer["options"]["baseURL"] == "https://reviewer.example.com/api/v1"
    assert reviewer["options"]["apiKey"] == "{env:OPENAI_API_KEY}"
    assert reviewer["models"]["strong-model"]["limit"] == {
        "context": 1000,
        "output": 250,
    }
    assert config["agent"]["reviewer"]["model"] == "reviewer/strong-model"
    metadata = result.agent_kwargs["subagent_metadata"]["providers"][0]
    assert metadata["name"] == "reviewer"
    assert metadata["sha256"] != metadata["configuration_sha256"]


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ({"vllm": {}}, "reserved"),
        ({"reviewer": {"npm": "x", "options": {"baseURL": "ftp://x"}}}, "HTTP"),
        (
            {"reviewer": {"npm": "x", "options": {"baseURL": "https://*.example"}}},
            "wildcard",
        ),
        (
            {"reviewer": {"npm": "x", "options": {"baseURL": "https://x:0"}}},
            "port",
        ),
        (
            {"reviewer": {"npm": "x", "options": {"apiKey": "raw-secret"}}},
            "must use",
        ),
        (
            {"reviewer": {"npm": "x", "options": {"apiKey": "{env:AWS_SECRET_ACCESS_KEY}"}}},
            "unsupported credential",
        ),
        (
            {
                "reviewer": {
                    "npm": "x",
                    "models": {"m": {"limit": {"context": 0}}},
                }
            },
            "positive integer",
        ),
        ({"reviewer": {"npm": "x"}}, "mapping"),
    ],
)
def test_invalid_provider_documents(document, message):
    with pytest.raises(ValueError, match=message):
        load_subagent_providers([document])


def test_duplicate_provider_names_are_rejected(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(PROVIDER_DOCUMENT))
    second.write_text(json.dumps(PROVIDER_DOCUMENT))

    with pytest.raises(ValueError, match="Duplicate OpenCode subagent provider name"):
        load_subagent_providers([first, second])


def test_provider_requires_subagent_and_opencode_harness(inputs):
    _, provider = inputs

    with pytest.raises(ValueError, match="require at least one --subagent"):
        HarborCommandBuilder().build(
            agent="opencode",
            dataset="example/dataset",
            model_name="primary-model",
            server_url="http://primary:8000",
            environment="docker",
            subagent_providers=[provider],
        )
    with pytest.raises(ValueError, match="only supported with --agent opencode"):
        HarborCommandBuilder().build(
            agent="oracle",
            dataset="example/dataset",
            model_name="primary-model",
            server_url="http://primary:8000",
            environment="docker",
            subagents=["unused"],
            subagent_providers=[provider],
        )


def test_local_command_adds_reviewer_network_host_and_serializes_json(inputs):
    subagent, provider = inputs

    command, _ = HarborCommandBuilder().build(
        agent="opencode",
        dataset="example/dataset",
        model_name="primary-model",
        server_url="http://primary:8000",
        environment="docker",
        subagents=[subagent],
        subagent_providers=[provider],
    )

    assert command[command.index("--allow-agent-host") + 1] == "reviewer.example.com"
    argument = next(
        value
        for flag, value in zip(command, command[1:])
        if flag == "--ak" and value.startswith("opencode_config=")
    )
    key, value = argument.split("=", 1)
    assert key == "opencode_config"
    assert json.loads(value)["provider"]["reviewer"]["options"]["apiKey"] == (
        "{env:OPENAI_API_KEY}"
    )


def test_remote_provider_is_encoded_and_openrouter_secret_is_scoped(inputs):
    _, provider = inputs
    arguments = encode_remote_path_arguments(
        ["coding-agent-bench", "run", "--subagent-provider", str(provider)],
        "--subagent-provider",
        SUBAGENT_PROVIDER_INLINE_PREFIX,
    )
    encoded = arguments[-1]
    assert encoded.startswith(SUBAGENT_PROVIDER_INLINE_PREFIX)
    assert load_subagent_providers([encoded])[0].name == "reviewer"

    openrouter_document = {
        "reviewer": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {
                "baseURL": "https://openrouter.ai/api/v1",
                "apiKey": "{env:OPENROUTER_API_KEY}",
            },
            "models": {"model": {}},
        }
    }
    command = [
        "coding-agent-bench",
        "run",
        "--subagent-provider",
        inline_provider_argument(openrouter_document),
    ]
    env = OpenshiftJob("provider-test")._job_spec(command)["spec"]["template"][
        "spec"
    ]["containers"][0]["env"]
    names = [item["name"] for item in env]
    assert "OPENROUTER_API_KEY" in names
    assert shlex.join(command) in OpenshiftJob("provider-test")._job_spec(command)[
        "spec"
    ]["template"]["spec"]["containers"][0]["args"][0]


def test_api_and_ui_support_provider_configuration():
    request = api.CreateJobRequest(
        job_name="provider-job",
        agent="opencode",
        dataset="example/dataset",
        model_name="primary-model",
        server_url="http://primary:8000",
        subagents=[SUBAGENT_MARKDOWN],
        subagent_providers=[PROVIDER_DOCUMENT],
    )
    command = api.build_cli_command(request)

    assert command[command.index("--subagent") + 1].startswith(
        "opencode-subagent:"
    )
    provider_argument = command[command.index("--subagent-provider") + 1]
    assert base64.b64decode(provider_argument.removeprefix(
        SUBAGENT_PROVIDER_INLINE_PREFIX
    )) == json.dumps(
        PROVIDER_DOCUMENT, sort_keys=True, separators=(",", ":")
    ).encode()
    assert api.inline_subagent_argument is inline_subagent_argument

    page = api.build_submit_form_html(["primary-model"], ["opencode"], [], False)
    assert "opencode_subagent_provider" in page


def _write_identity(path, endpoint, output_limit=250):
    path.mkdir(parents=True)
    (path / "config.json").write_text(
        json.dumps(
            {
                "datasets": [{"name": "example/dataset"}],
                "agents": [
                    {
                        "name": "opencode",
                        "model_name": "vllm/primary-model",
                        "kwargs": {
                            "version": "1.18.1",
                            "subagent_metadata": {
                                "definitions": [
                                    {
                                        "name": "reviewer",
                                        "model": "reviewer/strong-model",
                                        "markdown_sha256": "definition-hash",
                                    }
                                ],
                                "providers": [
                                    {
                                        "name": "reviewer",
                                        "source": "source",
                                        "sha256": "source-hash",
                                        "configuration_sha256": "provider-config-hash",
                                    }
                                ],
                            },
                            "opencode_config": {
                                "provider": {
                                    "reviewer": {
                                        "options": {"baseURL": endpoint},
                                        "models": {
                                            "strong-model": {
                                                "limit": {
                                                    "context": 1000,
                                                    "output": output_limit,
                                                }
                                            }
                                        },
                                    }
                                }
                            },
                        },
                    }
                ],
            }
        )
    )


def test_run_identity_ignores_only_provider_endpoint_changes(tmp_path):
    _write_identity(tmp_path / "one", "https://one.example.com/v1")
    _write_identity(tmp_path / "two", "https://two.example.com/v1")
    _write_identity(tmp_path / "limits", "https://one.example.com/v1", 300)

    assert run_identity(tmp_path / "one") == run_identity(tmp_path / "two")
    assert run_identity(tmp_path / "one") != run_identity(tmp_path / "limits")


def test_local_primary_forwards_exact_reviewer_credential(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-credential-test")
    subagent = tmp_path / "reviewer.md"
    subagent.write_text(
        SUBAGENT_MARKDOWN.replace("reviewer/strong-model", "reviewer/zai-org/glm-5-3")
    )
    provider = {
        "reviewer": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {
                "baseURL": "https://openrouter.ai/api/v1",
                "apiKey": "{env:OPENROUTER_API_KEY}",
            },
            "models": {"zai-org/glm-5-3": {"name": "GLM"}},
        }
    }

    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://primary:8000",
        subagents=[subagent],
        subagent_providers=[provider],
    )

    config = result.agent_kwargs["opencode_config"]
    assert result.agent_env["OPENROUTER_API_KEY"] == "sk-or-credential-test"
    assert config["provider"]["reviewer"]["options"]["apiKey"] == (
        "{env:OPENROUTER_API_KEY}"
    )
    assert config["agent"]["reviewer"]["model"] == "reviewer/zai-org/glm-5-3"
    assert "sk-or-credential-test" not in json.dumps(config)


def test_missing_reviewer_credential_is_rejected(inputs, monkeypatch):
    subagent, provider = inputs
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="requires OPENAI_API_KEY"):
        OpenCodeAgentConfig().configure(
            model_name="primary-model",
            server_url="http://primary:8000",
            subagents=[subagent],
            subagent_providers=[provider],
        )


def test_nested_header_credentials_are_forwarded(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "anthropic-header-test")
    provider = {
        "reviewer": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {
                "baseURL": "https://reviewer.example.com/api",
                "headers": {"Authorization": "{env:ANTHROPIC_AUTH_TOKEN}"},
            },
            "models": {"strong-model": {"name": "Strong model"}},
        }
    }

    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://primary:8000",
        subagents=[inline_subagent_argument(SUBAGENT_MARKDOWN)],
        subagent_providers=[provider],
    )

    assert result.agent_env["ANTHROPIC_AUTH_TOKEN"] == "anthropic-header-test"
    assert result.agent_kwargs["opencode_config"]["provider"]["reviewer"]["options"][
        "headers"
    ]["Authorization"] == "{env:ANTHROPIC_AUTH_TOKEN}"


def test_hierarchical_model_ids_are_preserved(inputs):
    subagent, provider = inputs
    subagent.write_text(
        subagent.read_text().replace("reviewer/strong-model", "reviewer/zai-org/glm-5-3")
    )
    provider.write_text(
        json.dumps(
            {
                "reviewer": {
                    "npm": "@ai-sdk/openai-compatible",
                    "options": {
                        "baseURL": "https://reviewer.example.com/api",
                        "apiKey": "{env:OPENAI_API_KEY}",
                    },
                    "models": {"zai-org/glm-5-3": {"name": "GLM"}},
                }
            }
        )
    )

    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://primary:8000",
        subagents=[subagent],
        subagent_providers=[provider],
    )

    config = result.agent_kwargs["opencode_config"]
    assert config["provider"]["reviewer"]["models"] == {
        "zai-org/glm-5-3": {"name": "GLM"}
    }
    assert config["agent"]["reviewer"]["model"] == "reviewer/zai-org/glm-5-3"


def test_invalid_model_reference_segments_are_rejected():
    with pytest.raises(ValueError, match="provider/model format"):
        api.CreateJobRequest(
            job_name="invalid-model",
            agent="opencode",
            dataset="example/dataset",
            model_name="primary-model",
            server_url="http://primary:8000",
            subagents=[SUBAGENT_MARKDOWN.replace("reviewer/strong-model", "reviewer//model")],
        )


def test_missing_primary_model_reference_rejects_cli_api_and_configuration(inputs):
    subagent, _ = inputs
    subagent.write_text(
        subagent.read_text().replace("reviewer/strong-model", "vllm/missing-model")
    )

    with pytest.raises(ValueError, match="does not define subagent model"):
        HarborCommandBuilder().build(
            agent="opencode",
            dataset="example/dataset",
            model_name="primary-model",
            server_url="http://primary:8000",
            environment="docker",
            subagents=[subagent],
        )
    with pytest.raises(ValueError, match="does not define subagent model"):
        api.CreateJobRequest(
            job_name="invalid-primary-reference",
            agent="opencode",
            dataset="example/dataset",
            model_name="primary-model",
            server_url="http://primary:8000",
            subagents=[subagent.read_text()],
        )
    with pytest.raises(ValueError, match="does not define subagent model"):
        OpenCodeAgentConfig().configure(
            model_name="primary-model",
            server_url="http://primary:8000",
            subagents=[subagent],
        )


def test_central_validation_allows_no_subagents_or_providers():
    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://primary:8000",
    )

    assert result.agent_kwargs is None
    assert result.agent_env["OPENCODE_CONFIG_CONTENT"]


def test_empty_subagent_policy_is_rejected_by_api():
    with pytest.raises(ValueError, match="must not be empty"):
        api.CreateJobRequest(
            job_name="empty-policy",
            agent="opencode",
            dataset="example/dataset",
            model_name="primary-model",
            server_url="http://primary:8000",
            subagents=[SUBAGENT_MARKDOWN],
            subagent_policy="  \n",
        )


def test_multiple_providers_are_all_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    provider = {
        **PROVIDER_DOCUMENT,
        "reviewer-two": PROVIDER_DOCUMENT["reviewer"],
    }
    second_markdown = SUBAGENT_MARKDOWN.replace(
        "name: reviewer", "name: reviewer-two"
    ).replace("reviewer/strong-model", "reviewer-two/strong-model")
    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://primary:8000",
        subagents=[
            inline_subagent_argument(SUBAGENT_MARKDOWN),
            inline_subagent_argument(second_markdown),
        ],
        subagent_providers=[provider],
    )

    assert set(result.agent_kwargs["opencode_config"]["provider"]) == {
        "vllm", "reviewer", "reviewer-two"
    }


def test_nested_credential_fields_and_endpoint_components_are_rejected():
    document = {
        "reviewer": {
            "npm": "@ai-sdk/openai-compatible",
            "options": {
                "baseURL": "https://reviewer.example.com/api",
                "headers": {"Authorization": "Bearer literal-secret"},
            },
            "models": {"model": {}},
        }
    }
    with pytest.raises(ValueError, match="without a literal secret"):
        load_subagent_providers([document])

    document["reviewer"]["options"]["headers"] = {"X-API-Key": "literal-secret"}
    with pytest.raises(ValueError, match="without a literal secret"):
        load_subagent_providers([document])

    for endpoint in (
        "https://user:pass@reviewer.example.com/api",
        "https://reviewer.example.com/api?query=1",
        "https://reviewer.example.com/api#fragment",
    ):
        with pytest.raises(ValueError, match="endpoint must not contain"):
            load_subagent_providers(
                [{**PROVIDER_DOCUMENT, "reviewer": {
                    **PROVIDER_DOCUMENT["reviewer"],
                    "options": {"baseURL": endpoint},
                }}]
            )


def test_api_create_and_list_responses_redact_credentials():
    command = [
        "coding-agent-bench",
        "ANTHROPIC_AUTH_TOKEN=anthropic-secret",
        "opencode_config={\"provider\":{\"r\":{\"options\":{\"apiKey\":\"nested-secret\",\"Authorization\":\"Bearer nested-secret\",\"X-API-Key\":\"header-secret\"}}}}",
    ]
    row = {
        "job_id": "redaction-job",
        "job_name": "redaction-job",
        "agent": "opencode",
        "dataset": "dataset",
        "model_name": "model",
        "server_url": "http://primary:8000",
        "status": "queued",
        "command": json.dumps(command),
    }
    created = api._job_create_response(row, "Job created.")
    listed = api._job_response(row)

    assert "anthropic-secret" not in str(created.command)
    assert "nested-secret" not in str(created.command)
    assert "header-secret" not in str(created.command)
    assert "anthropic-secret" not in listed.command
    assert "nested-secret" not in listed.command
    assert "header-secret" not in listed.command
