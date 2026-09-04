import os
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

os.environ.setdefault(
    "JOB_STORE_PATH", str(Path(tempfile.gettempdir()) / "cab-test-skills.db")
)

from coding_agent_bench.api import CreateJobRequest, build_cli_command
from coding_agent_bench.builder import HarborCommandBuilder, SupportedAgent
from coding_agent_bench.cli import app
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.utils import validate_remote_skill_sources


class BuilderSkillTests(unittest.TestCase):
    def test_builder_emits_repeated_skill_flags_in_order(self):
        command = HarborCommandBuilder()._build_command(
            agent="oracle",
            dataset="example/dataset",
            model="example-model",
            environment="docker",
            skills=["./local-skills", "obra/superpowers@main"],
        )

        pairs = [
            command[index : index + 2]
            for index, value in enumerate(command)
            if value == "--skill"
        ]
        self.assertEqual(
            pairs,
            [
                ["--skill", "./local-skills"],
                ["--skill", "obra/superpowers@main"],
            ],
        )

    def test_builder_omits_skill_flags_by_default(self):
        command = HarborCommandBuilder()._build_command(
            agent="oracle",
            dataset="example/dataset",
            model="example-model",
            environment="docker",
        )

        self.assertNotIn("--skill", command)


class CliSkillTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.required_args = [
            "--agent",
            "oracle",
            "--dataset",
            "example/dataset",
            "--model-name",
            "example-model",
            "--server-url",
            "http://model.example",
        ]

    def test_cli_accepts_both_skill_aliases_and_forwards_values(self):
        with patch.object(
            HarborCommandBuilder,
            "build",
            return_value=(["harbor", "run"], Path("jobs/test")),
        ) as build:
            result = self.runner.invoke(
                app,
                [
                    "run",
                    *self.required_args,
                    "--skill",
                    "./local-skills",
                    "--skills",
                    "obra/superpowers",
                    "--dry-run",
                ],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            build.call_args.kwargs["skills"],
            ["./local-skills", "obra/superpowers"],
        )

    def test_remote_cli_rejects_local_skill_path(self):
        result = self.runner.invoke(
            app,
            [
                "run",
                *self.required_args,
                "--environment",
                "openshift",
                "--remote",
                "--skill",
                "./local-skills",
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Remote skill source './local-skills'", result.output)
        self.assertIn("Use org/name[@ref]", result.output)


class QueueSkillTests(unittest.TestCase):
    def test_queue_command_serializes_each_skill(self):
        request = CreateJobRequest(
            job_name="skill-test",
            agent=SupportedAgent.oracle,
            dataset="example/dataset",
            model_name="example-model",
            server_url="http://model.example",
            skills=["obra/superpowers", "juliusbrussee/caveman@main"],
        )

        command = build_cli_command(request)
        pairs = [
            command[index : index + 2]
            for index, value in enumerate(command)
            if value == "--skill"
        ]
        self.assertEqual(
            pairs,
            [
                ["--skill", "obra/superpowers"],
                ["--skill", "juliusbrussee/caveman@main"],
            ],
        )


class RemoteSkillValidationTests(unittest.TestCase):
    def test_accepts_harbor_git_source_forms(self):
        validate_remote_skill_sources(
            [
                "obra/superpowers",
                "obra/superpowers@v1.0.0",
                "https://github.com/obra/superpowers",
                "https://github.com/obra/superpowers/tree/main/skills",
            ]
        )

    def test_rejects_local_paths(self):
        for source in (
            "./skills",
            "/tmp/skills",
            "~/skills",
            "tests/test_skills.py",
        ):
            with self.subTest(source=source), self.assertRaisesRegex(
                ValueError, "is not a Git source"
            ):
                validate_remote_skill_sources([source])


class OpenshiftJobSkillTests(unittest.TestCase):
    def test_job_spec_shell_quotes_skill_arguments(self):
        command = [
            "coding-agent-bench",
            "run",
            "--skill",
            "https://github.com/org/repo/tree/feature branch/skills",
        ]

        spec = OpenshiftJob("skill-test")._job_spec(command)
        shell_command = spec["spec"]["template"]["spec"]["containers"][0]["args"][0]

        self.assertIn(shlex.join(command), shell_command)


if __name__ == "__main__":
    unittest.main()
