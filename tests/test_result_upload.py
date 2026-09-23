"""Execute generated Bash pod commands against a filesystem-backed fake S3 CLI."""

import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest

from coding_agent_bench.job import OpenshiftJob, _build_logged_shell_step


SHELL_STUBS = r'''
record() {
    printf '%s\n' "$1" >> "$TRACE"
    if [ "$FAIL_STAGE" = "$1" ]; then return 23; fi
}
before() { record before; }
uv() {
    shift 3
    case "$1" in
        python)
            case "$4" in
                parent) record parent ;;
                endpoint) record url ;;
                *) return 99 ;;
            esac
            ;;
        harbor)
            record harbor
            printf 'Harbor stdout\n'
            printf 'Harbor stderr\n' >&2
            printf '{"resumed": true}\n' > "$JOB_DIR/config.json"
            printf 'updated result\n' > "$JOB_DIR/result.json"
            rm -rf "$JOB_DIR/stale-trial"
            return "$HARBOR_RC"
            ;;
        aws)
            [ "$AWS_ACCESS_KEY_ID" = "$MINIO_ROOT_USER" ] || return 99
            [ "$AWS_SECRET_ACCESS_KEY" = "$MINIO_ROOT_PASSWORD" ] || return 99
            [ "$AWS_DEFAULT_REGION" = us-east-1 ] || return 99
            [ "$AWS_EC2_METADATA_DISABLED" = true ] || return 99
            shift 3
            "$TEST_PYTHON" "$FAKE_S3" "$@"
            ;;
        *) return 99 ;;
    esac
}
'''


def run_shell(tmp_path, command, harbor_rc=0, fail_stage="", job_name=None, bucket_mode=""):
    """Run a pod script, retaining local and remote artifacts for assertions."""
    trace = tmp_path / "trace"
    remote = tmp_path / "remote"
    if job_name is None:
        job_name = "job with spaces" if "harbor jobs resume" in command else "test"
    original = remote / "results" / job_name
    original.mkdir(parents=True)
    (original / "result.json").write_text("original result\n")
    (original / "config.json").write_text("{}")
    (original / "console.log").write_text("earlier console output\n")
    (original / "stale-trial").mkdir()
    (original / "stale-trial" / "result.json").write_text("old trial")
    (remote / "results-staging").mkdir()
    command = command.replace("/app/jobs", str(tmp_path / "jobs"))
    result = subprocess.run(
        ["bash", "-c", SHELL_STUBS + command],
        env={
            **os.environ,
            "TRACE": str(trace),
            "HARBOR_RC": str(harbor_rc),
            "FAIL_STAGE": fail_stage,
            "BUCKET_MODE": bucket_mode,
            "TEST_PYTHON": sys.executable,
            "FAKE_S3": str(Path(__file__).with_name("fake_s3.py")),
            "REMOTE_DIR": str(remote),
            "JOB_DIR": str(tmp_path / "jobs" / job_name),
            "MINIO_ROOT_USER": "test user",
            "MINIO_ROOT_PASSWORD": "test password with spaces",
        },
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 99, result.stderr
    if "harbor" in trace.read_text().splitlines():
        assert "Harbor stdout" in result.stdout
        assert "Harbor stderr" in result.stdout
    return result.returncode, trace.read_text().splitlines()


@pytest.fixture
def queue_api(tmp_path, monkeypatch):
    """Isolate the API's database and in-memory dispatcher."""
    monkeypatch.setenv("JOB_STORE_PATH", str(tmp_path / "initial.db"))
    from coding_agent_bench import api

    monkeypatch.setattr(api, "job_store", api.JobStore(tmp_path / "jobs.db"))
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_job_event", asyncio.Event())
    return api


def enqueue_resume(api, server_url="https://old.models.example.com", new_url=None):
    """Build a real resume command for a failed job."""
    api.job_store.insert(
        "original", "job with spaces", "codex", "dataset", "model", server_url, []
    )
    api.job_store.update_status("original", api.JobStatus.FAILED)
    asyncio.run(
        api.resume_job("original", api.ResumeJobRequest(server_url=new_url))
    )
    return api._job_queue[-1]


@pytest.mark.parametrize("harbor_rc", [0, 1, 143])
@pytest.mark.parametrize("resume", [False, True])
def test_upload_runs_after_harbor_and_preserves_exit_status(
    tmp_path, queue_api, harbor_rc, resume
):
    """Always upload generated artifacts, then return Harbor's original status."""
    if resume:
        command = enqueue_resume(queue_api).command[2]
        expected = [
            "download", "parent", "url", "head", "backup", "backup-marker",
            "harbor", "upload", "upload-marker", "promote",
        ]
    else:
        spec = OpenshiftJob("test")._job_spec(["harbor", "run"])
        command = spec["spec"]["template"]["spec"]["containers"][0]["args"][0]
        expected = ["harbor", "head", "upload"]

    status, calls = run_shell(tmp_path, command, harbor_rc=harbor_rc)

    assert calls == expected
    assert status == harbor_rc


@pytest.mark.parametrize("harbor_rc", [0, 1])
@pytest.mark.parametrize("resume", [False, True])
def test_upload_failure_is_not_masked(tmp_path, queue_api, harbor_rc, resume):
    """Return a transfer failure even when Harbor completed successfully."""
    if resume:
        command = enqueue_resume(queue_api).command[2]
    else:
        spec = OpenshiftJob("test")._job_spec(["harbor", "run"])
        command = spec["spec"]["template"]["spec"]["containers"][0]["args"][0]

    status, calls = run_shell(
        tmp_path, command, harbor_rc=harbor_rc, fail_stage="upload"
    )

    assert calls[-1] == "upload"
    assert status == 23


@pytest.mark.parametrize("failure", ["download", "parent", "url"])
def test_failed_resume_setup_does_not_remove_remote_results(
    tmp_path, queue_api, failure
):
    """Never run Harbor or replace results after an incomplete restoration."""
    command = enqueue_resume(
        queue_api, new_url="https://new.models.example.com"
    ).command[2]

    status, calls = run_shell(tmp_path, command, fail_stage=failure)

    assert status == 23
    assert calls[-1] == failure
    assert "harbor" not in calls
    assert "promote" not in calls
    assert "upload" not in calls


def test_failed_before_script_stops_job(tmp_path):
    """Do not launch Harbor after its prerequisite script fails."""
    spec = OpenshiftJob("test")._job_spec(["harbor", "run"], ["before"])
    command = spec["spec"]["template"]["spec"]["containers"][0]["args"][0]

    status, calls = run_shell(tmp_path, command, fail_stage="before")

    assert status == 23
    assert calls == ["before"]


def test_missing_bucket_is_created_before_upload(tmp_path):
    """Create a missing results bucket before transferring job artifacts."""
    spec = OpenshiftJob("test")._job_spec(["harbor", "run"])
    command = spec["spec"]["template"]["spec"]["containers"][0]["args"][0]

    status, calls = run_shell(tmp_path, command, fail_stage="head")

    assert status == 0
    assert calls == ["harbor", "head", "bucket", "upload"]


@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize("bucket_mode", ["race", "unavailable"])
@pytest.mark.parametrize("harbor_rc", [0, 7])
def test_failed_bucket_create_rechecks_availability(
    tmp_path, queue_api, resume, bucket_mode, harbor_rc
):
    """Accept a concurrently created bucket, but stop on a genuine outage."""
    if resume:
        command = enqueue_resume(queue_api).command[2]
    else:
        spec = OpenshiftJob("test")._job_spec(["harbor", "run"])
        command = spec["spec"]["template"]["spec"]["containers"][0]["args"][0]

    status, calls = run_shell(
        tmp_path, command, harbor_rc=harbor_rc, bucket_mode=bucket_mode
    )

    head_index = calls.index("head")
    assert calls[head_index:head_index + 3] == ["head", "bucket", "head"]
    if bucket_mode == "race":
        assert status == harbor_rc
        assert "upload" in calls
        if resume:
            assert calls[-1] == "promote"
    else:
        assert status == 23
        assert "upload" not in calls
        assert "backup" not in calls
        assert "promote" not in calls
        assert calls[-1] == "head"


def test_managed_resume_updates_url_after_download(tmp_path, queue_api, monkeypatch):
    """Apply the provisioned model endpoint to the restored local configuration."""
    class Nebius:
        async def acquire_instance(self, *_args, **_kwargs):
            return "instance", "https://new.models.example.com"

        async def mark_job_started(self, _name):
            pass

        async def mark_job_completed(self, _name):
            pass

    commands = []

    async def capture_command(_job_id, command, **_kwargs):
        commands.append(command[2])

    monkeypatch.setattr(queue_api, "_nebius", Nebius())
    monkeypatch.setattr(queue_api, "_run_job", capture_command)
    queued = enqueue_resume(queue_api, server_url="nebius-h200")

    asyncio.run(queue_api._process_queued_job(queued))
    assert len(commands) == 1
    status, calls = run_shell(tmp_path, commands[0])

    assert status == 0
    assert calls == [
        "download", "parent", "url", "head", "backup", "backup-marker",
        "harbor", "upload", "upload-marker", "promote",
    ]


@pytest.mark.parametrize("failure", ["backup", "backup-marker", "upload", "upload-marker", "promote", ""])
def test_resume_keeps_recoverable_snapshots(tmp_path, queue_api, failure):
    """Partial transfer failures never remove the only complete remote copy."""
    queued = enqueue_resume(queue_api)
    status, calls = run_shell(tmp_path, queued.command[2], fail_stage=failure)
    canonical = tmp_path / "remote/results/job with spaces"
    snapshots = tmp_path / "remote/results-staging/job with spaces" / queued.job_id

    assert status == (23 if failure else 0)
    if failure in ("backup", "backup-marker", "upload", "upload-marker"):
        assert (canonical / "config.json").read_text() == "{}"
        assert (canonical / "result.json").read_text() == "original result\n"
        assert (canonical / "stale-trial/result.json").exists()
        assert "promote" not in calls
    if failure in ("backup", "backup-marker"):
        assert "harbor" not in calls
        assert not (snapshots / "original.complete").exists()
    else:
        assert (snapshots / "original/result.json").read_text() == "original result\n"
        assert (snapshots / "original/stale-trial/result.json").exists()
        assert (snapshots / "original.complete").exists()
    assert (snapshots / "updated.complete").exists() == (failure in ("promote", ""))
    if failure in ("promote", ""):
        assert (snapshots / "updated/result.json").read_text() == "updated result\n"
        assert not (snapshots / "updated/stale-trial").exists()
        log = (snapshots / "updated/console.log").read_text()
        assert "earlier console output" in log
        assert "Harbor stdout" in log
        assert "Harbor stderr" in log
    if failure == "promote":
        # The fake transfer copied one object before failing: both snapshots
        # remain usable even though the canonical prefix is now a mixed version.
        assert (canonical / "config.json").read_text() == '{"resumed": true}\n'
        assert (canonical / "result.json").read_text() == "original result\n"
    if not failure:
        assert (canonical / "result.json").read_text() == "updated result\n"
        assert not (canonical / "stale-trial").exists()
        assert (canonical / "console.log").read_text() == log


def test_each_resume_has_a_unique_snapshot_prefix(queue_api):
    """Recovery snapshots from different attempts cannot overwrite each other."""
    first = enqueue_resume(queue_api)
    asyncio.run(queue_api.resume_job("original"))
    second = queue_api._job_queue[-1]
    assert first.job_id != second.job_id
    for queued in (first, second):
        assert f"results-staging/job with spaces/{queued.job_id}/" in queued.command[2]


@pytest.mark.parametrize("equals_form", [False, True])
def test_new_job_log_is_uploaded_under_harbor_name(tmp_path, equals_form):
    """Use the artifact name rather than the queue UUID for console logs."""
    job_name = "name with spaces"
    args = [f"--job-name={job_name}"] if equals_form else ["--job-name", job_name]
    spec = OpenshiftJob("queue-uuid")._job_spec(["harbor", "run", *args])
    container = spec["spec"]["template"]["spec"]["containers"][0]
    assert container["command"] == ["bash", "-c"]

    status, _ = run_shell(tmp_path, container["args"][0], job_name=job_name)

    assert status == 0
    log = (tmp_path / "remote/results" / job_name / "console.log").read_text()
    assert "Harbor stdout" in log
    assert "Harbor stderr" in log
    assert not (tmp_path / "remote/results/queue-uuid").exists()


@pytest.mark.parametrize("harbor_rc,tee_rc,expected", [(0, 7, 7), (5, 0, 5), (5, 7, 5)])
def test_logging_pipeline_preserves_command_and_tee_errors(
    tmp_path, harbor_rc, tee_rc, expected
):
    """A successful tee cannot hide Harbor failure, nor vice versa."""
    log_step = _build_logged_shell_step(
        [sys.executable, "-c", f"print('output'); raise SystemExit({harbor_rc})"],
        str(tmp_path),
    )
    result = subprocess.run(
        ["bash", "-c", f"tee() {{ command cat; return {tee_rc}; }}; " + log_step + ' exit "$harbor_rc"'],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == expected
    assert "output" in result.stdout


def test_console_output_streams_before_command_finishes(tmp_path):
    """The live pod stream and the file receive data without waiting for exit."""
    child = "print('ready', flush=True); input(); print('done')"
    step = _build_logged_shell_step([sys.executable, "-c", child], str(tmp_path))
    with subprocess.Popen(
        ["bash", "-c", step + ' exit "$harbor_rc"'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    ) as process:
        assert process.stdout.readline() == "ready\n"
        assert process.poll() is None
        stdout, stderr = process.communicate(input="\n", timeout=10)
    assert process.returncode == 0, stderr
    assert stdout == "done\n"
    assert (tmp_path / "console.log").read_text() == "ready\ndone\n"


@pytest.mark.parametrize("returncode,expected", [(0, 0), (5, 5), (-15, 143)])
def test_local_cli_propagates_harbor_exit_status(monkeypatch, returncode, expected):
    """The outer upload wrapper must see the real Harbor subprocess status."""
    from typer.testing import CliRunner
    from coding_agent_bench import cli

    class Process:
        def __init__(self, *_args, **_kwargs):
            self.returncode = returncode

        def wait(self):
            return self.returncode

    monkeypatch.setattr(cli.subprocess, "Popen", Process)
    monkeypatch.setattr(
        cli.HarborCommandBuilder, "build",
        lambda *_args, **_kwargs: (["harbor", "run"], Path("jobs/test")),
    )
    result = CliRunner().invoke(cli.app, [
        "run", "--agent", "oracle", "--dataset", "dataset",
        "--model-name", "model", "--server-url", "https://example.com",
    ])
    assert result.exit_code == expected, result.output
