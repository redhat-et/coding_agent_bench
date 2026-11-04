"""Tests for arbitrary Harbor argument passthrough."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

os.environ.setdefault(
    "JOB_STORE_PATH", str(Path(tempfile.gettempdir()) / "cab-test-passthrough.db")
)

from coding_agent_bench.api import CreateJobRequest, build_cli_command
from coding_agent_bench.builder import HarborCommandBuilder, SupportedAgent
from coding_agent_bench.cli import app, get_cab_option_names
from coding_agent_bench.ui import build_submit_form_html
from coding_agent_bench.utils import (
    parse_extra_harbor_lines,
    validate_extra_harbor_flags,
)


def _request(**overrides) -> CreateJobRequest:
    values = dict(
        job_name="passthrough-test",
        agent=SupportedAgent.oracle,
        dataset="example/dataset",
        model_name="example-model",
        server_url="http://model.example",
    )
    values.update(overrides)
    return CreateJobRequest(**values)


class ParsingTests(unittest.TestCase):
    def test_lines_are_split_into_ordered_tokens(self):
        self.assertEqual(
            parse_extra_harbor_lines(
                ["--future=value", "--ae 'KEY=value with spaces'", "--boolean"]
            ),
            ["--future=value", "--ae", "KEY=value with spaces", "--boolean"],
        )

    def test_malformed_quotes_are_rejected(self):
        with pytest.raises(ValueError, match="Invalid extra Harbor flags line"):
            parse_extra_harbor_lines(["--future 'unterminated"])

    def test_policy_uses_dynamic_cab_options(self):
        self.assertIn("--agent", get_cab_option_names())
        with pytest.raises(ValueError, match="already supported"):
            validate_extra_harbor_flags(["--agent=oracle"], get_cab_option_names())

    def test_generated_harbor_flags_are_blocked(self):
        blocked = [
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
        ]
        for flag in blocked:
            with self.subTest(flag=flag):
                with pytest.raises(ValueError, match="blocked"):
                    validate_extra_harbor_flags([f"{flag}=value"], set())

    def test_short_blocked_flags_with_attached_values_are_rejected(self):
        with pytest.raises(ValueError, match="blocked"):
            validate_extra_harbor_flags(["-o/tmp/other"], set())
        with pytest.raises(ValueError, match="blocked"):
            validate_extra_harbor_flags(["-p/tasks"], set())

    def test_future_blocked_flags_can_be_added_to_policy(self):
        from coding_agent_bench import utils

        with patch.object(utils, "BLOCKED_HARBOR_FLAGS", frozenset({"--blocked"})):
            with pytest.raises(ValueError, match="blocked"):
                validate_extra_harbor_flags(["--blocked=value"], set())


class BuilderPassthroughTests(unittest.TestCase):
    def test_extra_args_are_appended_after_generated_arguments(self):
        command = HarborCommandBuilder()._build_command(
            agent="oracle",
            dataset="example/dataset",
            model="example-model",
            environment="docker",
            extra_harbor_args=["--future=value", "--boolean"],
        )
        self.assertEqual(command.index("--future=value"), len(command) - 2)
        self.assertEqual(command[-1], "--boolean")

    def test_build_forwards_extra_args(self):
        with patch.object(HarborCommandBuilder, "_build_command", return_value=["harbor", "run"]) as build:
            HarborCommandBuilder().build(
                agent="oracle",
                dataset="example/dataset",
                model_name="example-model",
                server_url="http://model.example",
                environment="docker",
                extra_harbor_args=["--future=value"],
            )
        self.assertEqual(build.call_args.kwargs["extra_harbor_args"], ["--future=value"])


class CliPassthroughTests(unittest.TestCase):
    required = [
        "run", "--agent", "oracle", "--dataset", "example/dataset",
        "--model-name", "example-model", "--server-url", "http://model.example",
        "--dry-run",
    ]

    def test_unknown_options_are_captured_without_wrapper_flag(self):
        with patch.object(
            HarborCommandBuilder, "build", return_value=([] , Path("jobs/test"))
        ) as build:
            result = CliRunner().invoke(
                app,
                self.required
                + [
                    "--future=value",
                    "--boolean",
                    "--agent-timeout-multiplier=3",
                    "--allow-agent-host=api.example.com",
                ],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            build.call_args.kwargs["extra_harbor_args"],
            [
                "--future=value",
                "--boolean",
                "--agent-timeout-multiplier=3",
                "--allow-agent-host=api.example.com",
            ],
        )

    def test_explicit_delimiter_can_repeat_a_cab_flag_and_is_rejected(self):
        result = CliRunner().invoke(app, self.required + ["--", "--agent", "other"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already supported", result.output)

    def test_duplicate_non_repeatable_options_are_rejected(self):
        result = CliRunner().invoke(
            app,
            self.required[:-1]
            + ["--server-url", "testing", "--dry-run"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("provided more than once", str(result.exception))

    def test_repeatable_options_are_allowed(self):
        with patch.object(
            HarborCommandBuilder, "build", return_value=([], Path("jobs/test"))
        ) as build:
            result = CliRunner().invoke(
                app,
                self.required[:-1]
                + ["--dry-run", "--skill", "org/one", "--skill", "org/two"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(build.call_args.kwargs["skills"], ["org/one", "org/two"])

    def test_registered_options_still_parse_normally(self):
        with patch.object(
            HarborCommandBuilder, "build", return_value=([], Path("jobs/test"))
        ) as build:
            result = CliRunner().invoke(
                app, self.required[:-1] + ["--dry-run", "--n-tasks", "2"]
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(build.call_args.kwargs["n_tasks"], 2)
        self.assertEqual(build.call_args.kwargs["extra_harbor_args"], [])


class QueuePassthroughTests(unittest.TestCase):
    def test_queue_serializes_raw_args_without_wrapper_option(self):
        command = build_cli_command(
            _request(extra_harbor_flags=["--future=value", "--ae 'KEY=value with spaces'"])
        )
        delimiter = command.index("--")
        self.assertEqual(
            command[delimiter + 1 :],
            ["--future=value", "--ae", "KEY=value with spaces"],
        )
        self.assertNotIn("--harbor-flag", command)

    def test_queue_rejects_cab_owned_extra_flag(self):
        with pytest.raises(ValidationError, match="already supported"):
            _request(extra_harbor_flags=["--agent=oracle"])



class UiTests(unittest.TestCase):
    def test_advanced_form_has_single_extra_flags_field(self):
        html = build_submit_form_html(["model"], ["oracle"], [], False)
        self.assertIn("Extra Harbor Flags", html)
        self.assertIn("extra_harbor_flags", html)
        self.assertNotIn('id="agent_env"', html)
        self.assertNotIn('id="agent_kwargs"', html)
        self.assertNotIn('id="env_kwargs"', html)
        self.assertNotIn('id="agent_timeout_multiplier"', html)
        self.assertNotIn('id="allow_agent_host"', html)


if __name__ == "__main__":
    unittest.main()
