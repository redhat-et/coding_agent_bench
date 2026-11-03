import hashlib
import base64
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
import click

from coding_agent_bench.agents.configs import OpenCodeAgentConfig
from coding_agent_bench.builder import HarborCommandBuilder
from coding_agent_bench.cli import app
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.subagents import (
    MAX_SUBAGENT_PAYLOAD_BYTES,
    SUBAGENT_POLICY_INLINE_PREFIX,
    SUBAGENT_INLINE_PREFIX,
    encode_remote_path_arguments,
    load_subagent_definitions,
    materialize_inline_policy,
    policy_metadata,
    subagents_to_opencode_config,
)
from coding_agent_bench.utils import cmd_to_string
from scripts import calculate_metrics as metrics_script
from scripts.calculate_metrics import (
    _redact_json_text,
    _subagent_report_section,
    prettify_command,
    run_identity,
)


EXAMPLE_SUBAGENT = Path("examples/opencode/reviewer-subagent.md")
EXAMPLE_PROVIDER = Path("examples/opencode/reviewer-provider.json")
EXAMPLE_POLICY = Path("examples/opencode/reviewer-escalation-policy.md")


def plain_cli_output(output: str) -> str:
    """Normalize terminal styling and wrapping for semantic assertions."""
    return " ".join(click.unstyle(output).split())


def write_subagent(path: Path, name: str = "reviewer", mode: str = "subagent") -> Path:
    path.write_text(
        f"""---
name: {name}
description: Review code without editing it
mode: {mode}
model: vllm/primary-model
permission:
  edit: deny
  bash: deny
---
Review the implementation and report findings.
"""
    )
    return path


def test_valid_opencode_subagent_definition(tmp_path):
    path = write_subagent(tmp_path / "reviewer.md")
    definition = load_subagent_definitions([path])[0]

    assert definition.name == "reviewer"
    assert definition.mode == "subagent"
    assert definition.model == "vllm/primary-model"
    assert definition.prompt == "Review the implementation and report findings.\n"
    assert definition.metadata["permission"] == {"edit": "deny", "bash": "deny"}
    assert definition.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("markdown", "message"),
    [
        ("No frontmatter\n", "frontmatter"),
        ("---\ndescription: Review\nmode: subagent\n---\nBody\n", "'name'"),
        ("---\nname: reviewer\nmode: subagent\n---\nBody\n", "'description'"),
        ("---\nname: reviewer\ndescription: Review\n---\nBody\n", "mode: subagent"),
        (
            "---\nname: reviewer\ndescription: Review\nmode: primary\n---\nBody\n",
            "mode: subagent",
        ),
        (
            "---\nname: reviewer\ndescription: Review\nmode: subagent\n---\n",
            "instructions",
        ),
        (
            "---\nname: reviewer\ndescription: Review\nmode: subagent\nmodel: /\n---\nBody\n",
            "provider/model",
        ),
        (
            "---\nname: reviewer\ndescription: Review\nmode: subagent\nmodel: provider/\n---\nBody\n",
            "provider/model",
        ),
    ],
)
def test_invalid_opencode_subagent_definition(tmp_path, markdown, message):
    path = tmp_path / "invalid.md"
    path.write_text(markdown)

    with pytest.raises(ValueError, match=message):
        load_subagent_definitions([path])


def test_invalid_utf8_opencode_subagent(tmp_path):
    path = tmp_path / "invalid.md"
    path.write_bytes(b"---\nname: reviewer\n---\n\xff")

    with pytest.raises(ValueError, match="UTF-8"):
        load_subagent_definitions([path])


def test_non_json_opencode_subagent_metadata(tmp_path):
    path = tmp_path / "invalid.md"
    path.write_text(
        "---\n"
        "name: reviewer\n"
        "description: Review\n"
        "mode: subagent\n"
        "when: 2026-01-01\n"
        "---\n"
        "Review code.\n"
    )

    with pytest.raises(ValueError, match="JSON-compatible"):
        load_subagent_definitions([path])


def test_oversized_inline_opencode_subagent():
    payload = SUBAGENT_INLINE_PREFIX + base64.b64encode(
        b"x" * (MAX_SUBAGENT_PAYLOAD_BYTES + 1)
    ).decode()

    with pytest.raises(ValueError, match="exceeds"):
        load_subagent_definitions([payload])


def test_oversized_opencode_policy(tmp_path):
    path = tmp_path / "policy.md"
    path.write_bytes(b"x" * (MAX_SUBAGENT_PAYLOAD_BYTES + 1))

    with pytest.raises(ValueError, match="exceeds"):
        policy_metadata(path)


def test_duplicate_opencode_subagent_names(tmp_path):
    first = write_subagent(tmp_path / "first.md", name="reviewer")
    second = write_subagent(tmp_path / "second.md", name="reviewer")

    with pytest.raises(ValueError, match="Duplicate OpenCode subagent name: reviewer"):
        load_subagent_definitions([first, second])


def test_subagents_reject_non_opencode_harness(tmp_path):
    subagent = write_subagent(tmp_path / "reviewer.md")

    with pytest.raises(ValueError, match="only supported with --agent opencode"):
        HarborCommandBuilder().build(
            agent="oracle",
            dataset="example/dataset",
            model_name="model",
            server_url="http://vllm:8000",
            environment="docker",
            subagents=[subagent],
        )


def test_multiple_subagents_preserve_models_and_instructions(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    first = write_subagent(tmp_path / "reviewer.md", name="reviewer")
    second = write_subagent(tmp_path / "debugger.md", name="debugger")
    second.write_text(
        second.read_text().replace(
            "vllm/primary-model",
            "vllm/primary-model",
        )
    )

    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://vllm:8000",
        model_max_len=100000,
        subagents=[first, second],
        subagent_policy=EXAMPLE_POLICY,
    )
    config = result.agent_kwargs["opencode_config"]
    metadata = result.agent_kwargs["subagent_metadata"]

    assert config["agent"]["reviewer"]["model"] == "vllm/primary-model"
    assert config["agent"]["debugger"]["model"] == "vllm/primary-model"
    assert config["agent"]["reviewer"]["prompt"] == (
        "Review the implementation and report findings.\n"
    )
    assert [item["name"] for item in metadata["definitions"]] == [
        "reviewer",
        "debugger",
    ]
    assert metadata["escalation_policy"] == policy_metadata(EXAMPLE_POLICY)


def test_local_command_generation_with_subagent_policy(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    subagent = write_subagent(tmp_path / "reviewer.md")

    command, _ = HarborCommandBuilder().build(
        agent="opencode",
        dataset="example/dataset",
        model_name="primary-model",
        server_url="http://vllm:8000",
        environment="docker",
            subagents=[subagent],
        subagent_policy=EXAMPLE_POLICY,
    )

    assert "--extra-instruction-path" in command
    policy_index = command.index("--extra-instruction-path") + 1
    assert Path(command[policy_index]).resolve() == EXAMPLE_POLICY.resolve()
    opencode_arguments = [
        value for flag, value in zip(command, command[1:]) if flag == "--ak"
    ]
    opencode_argument = next(
        argument
        for argument in opencode_arguments
        if argument.startswith("opencode_config=")
    )
    assert json.loads(opencode_argument.removeprefix("opencode_config="))["agent"][
        "reviewer"
    ]["model"] == "vllm/primary-model"


def test_remote_opencode_subagents_are_encoded_and_shell_safe(tmp_path):
    subagent = write_subagent(tmp_path / "reviewer.md")
    arguments = encode_remote_path_arguments(
        [
            "coding-agent-bench",
            "run",
            "--subagent",
            str(subagent),
            "--subagent-policy",
            str(EXAMPLE_POLICY),
        ],
        "--subagent",
        SUBAGENT_INLINE_PREFIX,
    )
    arguments = encode_remote_path_arguments(
        arguments, "--subagent-policy", "opencode-subagent-policy:"
    )

    assert arguments[3].startswith(SUBAGENT_INLINE_PREFIX)
    definition = load_subagent_definitions([arguments[3]])[0]
    assert definition.name == "reviewer"
    assert definition.source == "<inline remote payload>"
    spec = OpenshiftJob("subagent-test")._job_spec(arguments)
    shell = spec["spec"]["template"]["spec"]["containers"][0]["args"][0]
    assert shlex.join(arguments) in shell


def test_remote_policy_metadata_stays_reproducible(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    arguments = encode_remote_path_arguments(
        ["--subagent", str(EXAMPLE_SUBAGENT)], "--subagent", SUBAGENT_INLINE_PREFIX
    )
    policy_argument = (
        "opencode-subagent-policy:"
        + base64.b64encode(EXAMPLE_POLICY.read_bytes()).decode()
    )

    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://vllm:8000",
        subagents=[arguments[1]],
        subagent_providers=[EXAMPLE_PROVIDER],
        subagent_policy=policy_argument,
    )
    metadata = result.agent_kwargs["subagent_metadata"]["escalation_policy"]

    assert metadata["source"] == "<inline remote payload>"
    assert metadata["sha256"] == hashlib.sha256(EXAMPLE_POLICY.read_bytes()).hexdigest()


@pytest.mark.parametrize("return_code", [0, 1])
def test_remote_policy_temp_file_is_cleaned_after_local_execution(
    monkeypatch, return_code
):
    from typer.testing import CliRunner

    inline_subagent = (
        SUBAGENT_INLINE_PREFIX
        + base64.b64encode(EXAMPLE_SUBAGENT.read_bytes()).decode()
    )
    inline_policy = (
        "opencode-subagent-policy:"
        + base64.b64encode(EXAMPLE_POLICY.read_bytes()).decode()
    )
    captured_command = None
    captured_policy = None

    class FakeProcess:
        returncode = return_code

        def wait(self):
            return 0

    def fake_popen(command, *_args, **_kwargs):
        nonlocal captured_command, captured_policy
        captured_command = command
        policy_path = Path(command[command.index("--extra-instruction-path") + 1])
        captured_policy = policy_path.read_text()
        return FakeProcess()

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr("coding_agent_bench.cli.subprocess.Popen", fake_popen)
    result = CliRunner(env={"COLUMNS": "240"}).invoke(
        app,
        [
            "run",
            "--agent",
            "opencode",
            "--dataset",
            "example/dataset",
            "--model-name",
            "primary-model",
            "--server-url",
            "http://vllm:8000",
            "--subagent",
            inline_subagent,
            "--subagent-provider",
            str(EXAMPLE_PROVIDER),
            "--subagent-policy",
            inline_policy,
        ],
    )

    assert result.exit_code == return_code
    policy_path = Path(
        captured_command[captured_command.index("--extra-instruction-path") + 1]
    )
    assert captured_policy == EXAMPLE_POLICY.read_text()
    assert not policy_path.exists()


def test_remote_policy_temp_file_is_cleaned_after_dry_run(monkeypatch):
    from typer.testing import CliRunner

    inline_subagent = (
        SUBAGENT_INLINE_PREFIX
        + base64.b64encode(EXAMPLE_SUBAGENT.read_bytes()).decode()
    )
    inline_policy = (
        SUBAGENT_POLICY_INLINE_PREFIX
        + base64.b64encode(EXAMPLE_POLICY.read_bytes()).decode()
    )
    captured_command = None

    def fake_cmd_to_string(command):
        nonlocal captured_command
        captured_command = command
        return ""

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr("coding_agent_bench.cli.cmd_to_string", fake_cmd_to_string)
    result = CliRunner(env={"COLUMNS": "240"}).invoke(
        app,
        [
            "run",
            "--agent",
            "opencode",
            "--dataset",
            "example/dataset",
            "--model-name",
            "primary-model",
            "--server-url",
            "http://vllm:8000",
            "--subagent",
            inline_subagent,
            "--subagent-provider",
            str(EXAMPLE_PROVIDER),
            "--subagent-policy",
            inline_policy,
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    policy_path = Path(
        captured_command[captured_command.index("--extra-instruction-path") + 1]
    )
    assert not policy_path.exists()


def test_remote_policy_temp_file_is_cleaned_when_process_launch_fails(monkeypatch):
    from typer.testing import CliRunner

    inline_subagent = (
        SUBAGENT_INLINE_PREFIX
        + base64.b64encode(EXAMPLE_SUBAGENT.read_bytes()).decode()
    )
    inline_policy = (
        SUBAGENT_POLICY_INLINE_PREFIX
        + base64.b64encode(EXAMPLE_POLICY.read_bytes()).decode()
    )
    captured_command = None

    def fake_popen(command, *_args, **_kwargs):
        nonlocal captured_command
        captured_command = command
        raise RuntimeError("launch failed")

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr("coding_agent_bench.cli.subprocess.Popen", fake_popen)
    result = CliRunner(env={"COLUMNS": "240"}).invoke(
        app,
        [
            "run",
            "--agent",
            "opencode",
            "--dataset",
            "example/dataset",
            "--model-name",
            "primary-model",
            "--server-url",
            "http://vllm:8000",
            "--subagent",
            inline_subagent,
            "--subagent-provider",
            str(EXAMPLE_PROVIDER),
            "--subagent-policy",
            inline_policy,
        ],
    )

    assert result.exit_code != 0
    policy_path = Path(
        captured_command[captured_command.index("--extra-instruction-path") + 1]
    )
    assert not policy_path.exists()


def test_remote_policy_temp_file_is_cleaned_when_command_construction_fails(
    monkeypatch,
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    inline_policy = (
        SUBAGENT_POLICY_INLINE_PREFIX
        + base64.b64encode(EXAMPLE_POLICY.read_bytes()).decode()
    )
    materialized_paths = []
    real_materialize = materialize_inline_policy

    def materialize(source):
        path = real_materialize(source)
        materialized_paths.append(path)
        return path

    def fail_build_command(*_args, **_kwargs):
        raise RuntimeError("command construction failed")

    monkeypatch.setattr(
        "coding_agent_bench.builder.materialize_inline_policy", materialize
    )
    monkeypatch.setattr(HarborCommandBuilder, "_build_command", fail_build_command)

    with pytest.raises(RuntimeError, match="command construction failed"):
        HarborCommandBuilder().build(
            agent="opencode",
            dataset="example/dataset",
            model_name="primary-model",
            server_url="http://vllm:8000",
            environment="docker",
            subagents=[EXAMPLE_SUBAGENT],
            subagent_providers=[EXAMPLE_PROVIDER],
            subagent_policy=inline_policy,
        )

    assert materialized_paths
    assert not materialized_paths[0].exists()


def test_cli_rejects_policy_without_subagent():
    from typer.testing import CliRunner

    result = CliRunner(env={"COLUMNS": "240"}).invoke(
        app,
        [
            "run",
            "--agent",
            "opencode",
            "--dataset",
            "example/dataset",
            "--model-name",
            "primary-model",
            "--server-url",
            "http://vllm:8000",
            "--subagent-policy",
            str(EXAMPLE_POLICY),
            "--dry-run",
        ],
    )

    assert result.exit_code != 0
    assert (
        "--subagent-policy and --subagent-provider require at least one --subagent"
        in plain_cli_output(result.output)
    )


def test_subagents_are_absent_by_default(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    command, _ = HarborCommandBuilder().build(
        agent="opencode",
        dataset="example/dataset",
        model_name="primary-model",
        server_url="http://vllm:8000",
        environment="docker",
    )

    assert "--extra-instruction-path" not in command
    assert not any(
        argument.startswith("opencode_config=")
        for argument in command
    )


def test_cli_rejects_subagents_for_other_harnesses(tmp_path):
    from typer.testing import CliRunner

    subagent = write_subagent(tmp_path / "reviewer.md")
    runner = CliRunner(env={"COLUMNS": "240"})
    result = runner.invoke(
        app,
        [
            "run",
            "--agent",
            "oracle",
            "--dataset",
            "example/dataset",
            "--model-name",
            "model",
            "--server-url",
            "http://vllm:8000",
            "--subagent",
            str(subagent),
            "--dry-run",
        ],
    )

    assert result.exit_code != 0
    assert "only supported with --agent opencode" in plain_cli_output(result.output)


@pytest.mark.skipif(
    shutil.which("opencode") is None and os.environ.get("OPENCODE_BINARY") is None,
    reason="OpenCode CLI is required",
)
def test_opencode_discovers_configured_subagent(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    definitions = load_subagent_definitions([EXAMPLE_SUBAGENT])
    config = {
        "agent": {
            definition.name: {
                **definition.to_opencode_config(),
            }
            for definition in definitions
        }
    }
    home = tmp_path / "home"
    config_dir = home / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    (config_dir / "opencode.json").write_text(json.dumps(config))

    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment["XDG_CONFIG_HOME"] = str(home / ".config")
    environment["XDG_DATA_HOME"] = str(home / ".local" / "share")
    environment["XDG_CACHE_HOME"] = str(home / ".cache")
    opencode_binary = os.environ.get("OPENCODE_BINARY") or "opencode"
    result = subprocess.run(
        [opencode_binary, "agent", "list"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "reviewer (subagent)" in result.stdout


def test_harbor_writes_subagents_to_opencode_config_path(tmp_path):
    from harbor.agents.installed.opencode import OpenCode

    definitions = load_subagent_definitions([EXAMPLE_SUBAGENT])
    opencode_agent = OpenCode(
        logs_dir=tmp_path,
        model_name="vllm/primary-model",
        opencode_config={"agent": subagents_to_opencode_config(definitions)},
    )
    command = opencode_agent._build_register_config_command()

    assert "mkdir -p ~/.config/opencode" in command
    assert "> ~/.config/opencode/opencode.json" in command


def test_report_records_subagent_reproducibility_metadata(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="http://vllm:8000",
        subagents=[EXAMPLE_SUBAGENT],
        subagent_providers=[EXAMPLE_PROVIDER],
        subagent_policy=EXAMPLE_POLICY,
    )
    section = _subagent_report_section(
        {
            "name": "opencode",
            "model_name": "vllm/primary-model",
            "kwargs": {
                "version": "1.18.1",
                "subagent_metadata": result.agent_kwargs["subagent_metadata"],
            },
        }
    )

    assert "**Harness Version:** 1.18.1" in section
    assert "**reviewer:** openrouter/REPLACE_WITH_REVIEWER_MODEL_ID" in section
    assert hashlib.sha256(EXAMPLE_SUBAGENT.read_bytes()).hexdigest() in section
    assert hashlib.sha256(EXAMPLE_POLICY.read_bytes()).hexdigest() in section
    assert "not collected by Harbor's OpenCode adapter" in section
    assert "inspect OpenCode tool errors" in section

    aggregated_section = _subagent_report_section(
        {
            "kwargs": {
                "version": "1.18.1",
                "subagent_metadata": result.agent_kwargs["subagent_metadata"],
            }
        },
        n_runs=2,
    )
    assert "**Aggregated Runs:** 2" in aggregated_section


def test_openrouter_credentials_are_not_embedded_in_opencode_metadata(monkeypatch):
    fake_key = "sk-or-distinctive-fake-key"
    monkeypatch.setenv("OPENROUTER_API_KEY", fake_key)

    result = OpenCodeAgentConfig().configure(
        model_name="primary-model",
        server_url="openrouter",
        subagents=[EXAMPLE_SUBAGENT],
        subagent_providers=[EXAMPLE_PROVIDER],
        subagent_policy=EXAMPLE_POLICY,
    )
    command, _ = HarborCommandBuilder().build(
        agent="opencode",
        dataset="example/dataset",
        model_name="primary-model",
        server_url="openrouter",
        environment="docker",
        subagents=[EXAMPLE_SUBAGENT],
        subagent_providers=[EXAMPLE_PROVIDER],
        subagent_policy=EXAMPLE_POLICY,
    )
    opencode_arguments = [
        value for flag, value in zip(command, command[1:]) if flag == "--ak"
    ]

    assert result.agent_kwargs["opencode_config"]["provider"]["vllm"]["options"][
        "apiKey"
    ] == "{env:OPENROUTER_API_KEY}"
    assert fake_key not in json.dumps(result.agent_kwargs)
    assert fake_key not in result.agent_env["OPENCODE_CONFIG_CONTENT"]
    assert fake_key not in cmd_to_string(command)
    assert not any(fake_key in argument for argument in opencode_arguments)


def test_report_rendering_redacts_credentials():
    fake_key = "sk-or-distinctive-fake-key"
    command = prettify_command(
        [
            "harbor",
            "run",
            "--ae",
            f"OPENROUTER_API_KEY={fake_key}",
            "--ak",
            f'opencode_config={{"provider":{{"options":{{"apiKey":"{fake_key}"}}}}}}',
        ]
    )
    config = _redact_json_text(
        json.dumps(
            {
                "env": {"OPENROUTER_API_KEY": fake_key},
                "provider": {"options": {"apiKey": fake_key}},
            }
        )
    )

    assert fake_key not in command
    assert fake_key not in config
    assert "<redacted>" in command
    assert "<redacted>" in config


def _write_identity_config(path: Path, reviewer_model: str, policy_hash: str):
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
                                        "model": reviewer_model,
                                        "markdown_sha256": "definition-hash",
                                    }
                                ],
                                "escalation_policy": {
                                    "sha256": policy_hash,
                                },
                            },
                            "opencode_config": {
                                "agent": {
                                    "reviewer": {"model": reviewer_model}
                                }
                            },
                        },
                    }
                ],
                "environment": {"type": "docker"},
            }
        )
    )
    (path / "lock.json").write_text(
        json.dumps({"created_at": "2026-01-01T00:00:00+00:00"})
    )
    (path / "result.json").write_text(
        json.dumps(
            {
                "n_total_trials": 1,
                "stats": {
                    "n_input_tokens": 1,
                    "n_cache_tokens": 0,
                    "n_output_tokens": 1,
                    "n_errored_trials": 0,
                    "cost_usd": 0,
                    "evals": {
                        "evaluation": {
                            "metrics": [{"reward": 1}],
                            "exception_stats": {},
                        }
                    },
                },
            }
        )
    )


def test_subagent_identity_prevents_incompatible_run_averaging(tmp_path, monkeypatch):
    _write_identity_config(tmp_path / "one", "mock/reviewer-one", "policy-one")
    _write_identity_config(tmp_path / "same", "mock/reviewer-one", "policy-one")
    _write_identity_config(tmp_path / "model", "mock/reviewer-two", "policy-one")
    _write_identity_config(tmp_path / "policy", "mock/reviewer-one", "policy-two")
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "config.json").write_text(
        json.dumps(
            {
                "datasets": [{"name": "example/dataset"}],
                "agents": [
                    {"name": "opencode", "model_name": "vllm/primary-model"}
                ],
                "environment": {"type": "docker"},
            }
        )
    )

    assert run_identity(tmp_path / "one") == run_identity(tmp_path / "same")
    assert run_identity(tmp_path / "one") != run_identity(tmp_path / "model")
    assert run_identity(tmp_path / "one") != run_identity(tmp_path / "policy")
    assert run_identity(tmp_path / "one") != run_identity(legacy)

    monkeypatch.setattr(
        "sys.argv",
        [
            "calculate_metrics.py",
            str(tmp_path / "one"),
            str(tmp_path / "model"),
        ],
    )
    with pytest.raises(SystemExit, match="Inconsistent runs"):
        metrics_script.main()
