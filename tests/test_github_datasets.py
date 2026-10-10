import asyncio
import io
import json
import sqlite3
import stat
import subprocess
from unittest.mock import AsyncMock
from urllib.error import HTTPError
from zipfile import ZipFile, ZipInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from coding_agent_bench import api, github_datasets as datasets
from coding_agent_bench.job import OpenshiftJob
from coding_agent_bench.ui import build_submit_form_html


COMMIT = "a" * 40
TOKEN = "ghp-review-secret"


def make_zip(entries):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def task_archive():
    return make_zip(
        {
            "repo/benchmarks/tasks/one/task.toml": 'version = "1.0"',
            "repo/benchmarks/tasks/one/instruction.md": "Do the task.",
            "repo/benchmarks/tasks/one/environment/Dockerfile": "FROM busybox",
            "repo/benchmarks/tasks/one/tests/test.sh": "#!/bin/sh\nexit 0",
        }
    )


def source(**kwargs):
    return datasets.GitHubDataset(
        repository_url="https://github.com/acme/data",
        subdirectory="benchmarks/tasks",
        **kwargs,
    )


def test_github_dataset_defaults_to_tasks_subdirectory():
    source = datasets.GitHubDataset(repository_url="https://github.com/acme/data")
    assert source.subdirectory == "tasks"
    assert source.local_path == str(datasets.DATASET_SOURCE / "tasks")


@pytest.mark.parametrize("value", ["../secret", "/absolute", "a\\b", "a/../b"])
def test_reject_unsafe_subdirectories(value):
    with pytest.raises(datasets.DatasetArchiveError):
        datasets.normalize_dataset_subdirectory(value)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/data",
        "https://example.com/acme/data",
        "https://secret@github.com/acme/data",
        "https://github.com/../data",
    ],
)
def test_reject_unsafe_repository_urls(url):
    with pytest.raises(ValueError):
        datasets.GitHubDataset(repository_url=url)


@pytest.mark.parametrize("token", ["", TOKEN])
def test_download_public_or_private_without_forwarding_auth_to_cdn(
    tmp_path, monkeypatch, token
):
    content = task_archive()
    requests = []

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(content))}

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            if request.full_url.startswith("https://api.github.com/"):
                raise HTTPError(
                    request.full_url,
                    302,
                    "Found",
                    {"Location": "https://codeload.github.com/acme/data/zip/abc"},
                    io.BytesIO(),
                )
            return Response(content)

    monkeypatch.setattr(datasets, "build_opener", lambda _: Opener())
    target = tmp_path / "archive.partial"
    datasets.fetch_github_archive(
        source().repository_url, COMMIT, token, target, len(content)
    )
    assert target.read_bytes() == content
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert requests[0].get_header("Authorization") == (
        f"Bearer {token}" if token else None
    )
    assert requests[1].get_header("Authorization") is None
    assert TOKEN not in requests[0].full_url


def test_streaming_download_enforces_limit_without_content_length(
    tmp_path, monkeypatch
):
    class Response(io.BytesIO):
        headers = {}

    opener = type(
        "Opener", (), {"open": lambda *_args, **_kwargs: Response(b"x" * 20)}
    )()
    monkeypatch.setattr(datasets, "build_opener", lambda _: opener)
    with pytest.raises(datasets.DatasetArchiveError, match="size limit"):
        datasets.fetch_github_archive(
            source().repository_url, COMMIT, "", tmp_path / "partial", 10
        )


def test_pinned_resume_does_not_resolve_moving_branch(monkeypatch):
    monkeypatch.setattr(
        datasets, "build_opener", lambda _: pytest.fail("must use pinned commit")
    )
    assert (
        datasets.resolve_github_commit(source(ref="main", commit=COMMIT), "") == COMMIT
    )


def test_preparation_waits_for_complete_download_and_validates_real_harbor_tasks(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(datasets, "resolve_github_commit", lambda *_: COMMIT)

    def download(url, ref, token, path, limit):
        assert ref == COMMIT and token == TOKEN
        assert path.name == "archive.partial"
        path.write_bytes(task_archive()[:4])
        assert not (tmp_path / "source").exists()
        assert not (tmp_path / "ready").exists()
        path.write_bytes(task_archive())

    monkeypatch.setattr(datasets, "fetch_github_archive", download)
    assert datasets.prepare_dataset(source(ref="main"), TOKEN, tmp_path) == COMMIT
    assert (tmp_path / "source/benchmarks/tasks/one/task.toml").is_file()
    from harbor.models.job.config import DatasetConfig
    from coding_agent_bench.builder import HarborCommandBuilder

    selected = tmp_path / "source/benchmarks/tasks"
    tasks = asyncio.run(DatasetConfig(path=selected).get_task_configs())
    assert len(tasks) == 1 and tasks[0].path == selected / "one"
    command = HarborCommandBuilder()._build_command(
        agent="oracle", dataset=str(selected), model="model", environment="openshift"
    )
    assert command[command.index("-p") + 1] == str(selected)
    assert not (tmp_path / "download").exists()
    assert (tmp_path / "prepared").is_file()
    # Only the API may release Harbor after persisting the resolved commit.
    assert not (tmp_path / "ready").exists()


def test_release_requires_successful_preparation(tmp_path, monkeypatch):
    from coding_agent_bench import job as job_module

    monkeypatch.setattr(job_module, "DATASET_ROOT", tmp_path)
    job = OpenshiftJob("test")

    async def oc(command, **kwargs):
        if command[0] == "get":
            return "pod", ""
        result = subprocess.run(command[command.index("--") + 1 :], capture_output=True)
        if result.returncode:
            raise RuntimeError("dataset is not prepared")
        return "", ""

    monkeypatch.setattr(job, "_run_oc_command", oc)
    with pytest.raises(RuntimeError, match="not prepared"):
        asyncio.run(job.release_github_dataset())
    assert not (tmp_path / "ready").exists()
    (tmp_path / "prepared").touch()
    asyncio.run(job.release_github_dataset())
    assert (tmp_path / "ready").exists()


@pytest.mark.parametrize("failure", ["download", "invalid_tasks", "missing_directory"])
def test_failed_preparation_cleans_up_and_does_not_release_harbor(
    tmp_path, monkeypatch, failure
):
    monkeypatch.setattr(datasets, "resolve_github_commit", lambda *_: COMMIT)

    def download(url, ref, token, path, limit):
        path.write_bytes(b"partial")
        if failure == "download":
            raise datasets.GitHubArchiveFetchError("download failed")
        path.write_bytes(
            make_zip(
                {
                    (
                        "repo/benchmarks/tasks/README.md"
                        if failure == "invalid_tasks"
                        else "repo/README.md"
                    ): "docs"
                }
            )
        )

    monkeypatch.setattr(datasets, "fetch_github_archive", download)
    with pytest.raises(ValueError):
        datasets.prepare_dataset(source(), TOKEN, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ["traversal", "symlink", "oversized"])
def test_reject_unsafe_archives(tmp_path, kind):
    path = tmp_path / "archive.zip"
    info = ZipInfo("repo/link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    path.write_bytes(
        make_zip(
            {
                (
                    "repo/../../outside"
                    if kind == "traversal"
                    else info
                    if kind == "symlink"
                    else "repo/file"
                ): "12345"
            }
        )
    )
    with pytest.raises(datasets.DatasetArchiveError):
        datasets.extract_github_archive(
            path,
            tmp_path / "source",
            max_unpacked_bytes=4 if kind == "oversized" else 100,
        )
    assert not (tmp_path / "source").exists()
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("resume", [False, True])
def test_pod_gate_ignores_partial_archives_and_runs_only_after_ready(tmp_path, resume):
    job = OpenshiftJob("test")
    spec = job._resume_job_spec("true") if resume else job._job_spec(["true"])
    spec["spec"]["template"]["spec"]["containers"][0]["args"] = ["touch ran"]
    spec = job.with_github_dataset(spec)
    command = spec["spec"]["template"]["spec"]["containers"][0]["args"][0]
    command = command.replace(str(datasets.DATASET_ROOT), str(tmp_path)).replace(
        '"$attempt" -lt 900', '"$attempt" -lt 0'
    )
    (tmp_path / "archive.zip").write_bytes(b"partial")
    result = subprocess.run(["sh", "-c", command], cwd=tmp_path, capture_output=True)
    assert result.returncode != 0
    assert not (tmp_path / "ran").exists()
    (tmp_path / "ready").touch()
    subprocess.run(["sh", "-c", command], cwd=tmp_path, check=True)
    assert (tmp_path / "ran").exists()
    assert spec["spec"]["backoffLimit"] == 0
    assert spec["spec"]["template"]["spec"]["securityContext"] == {"fsGroup": 1001}
    assert "github-dataset" in json.dumps(spec)


def test_exec_sends_token_only_on_stdin(monkeypatch):
    job = OpenshiftJob("test")
    calls = []

    async def oc(command, **kwargs):
        calls.append((command, kwargs))
        return (
            ("pod-test", "")
            if command[0] == "get"
            else (json.dumps({"commit": COMMIT}), "")
        )

    monkeypatch.setattr(job, "_run_oc_command", oc)
    assert asyncio.run(job.prepare_github_dataset(source(), SecretStr(TOKEN))) == COMMIT
    command, kwargs = calls[-1]
    assert command[:3] == ["exec", "-i", "pod-test"]
    assert TOKEN not in str(command)
    assert json.loads(kwargs["stdin_data"])["token"] == TOKEN
    assert not any("touch" in call[0] for call in calls)


def test_exec_errors_cannot_leak_token(monkeypatch):
    job = OpenshiftJob("test")

    async def oc(command, **kwargs):
        if command[0] == "get":
            return "pod", ""
        raise RuntimeError(f"accidental stderr: {TOKEN}")

    monkeypatch.setattr(job, "_run_oc_command", oc)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(job.prepare_github_dataset(source(), SecretStr(TOKEN)))
    assert TOKEN not in str(caught.value)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "queue-key")
    monkeypatch.setattr(api, "job_store", api.JobStore(tmp_path / "jobs.db"))
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_job_event", asyncio.Event())
    monkeypatch.setattr(api, "validate_server_url", lambda _: [])
    monkeypatch.setattr(
        api.HarborCommandBuilder, "build", lambda *_args, **_kwargs: ([], tmp_path)
    )
    return TestClient(api.app)


def submit(client, token=TOKEN):
    return client.post(
        "/jobs",
        headers={"X-API-Key": "queue-key", "X-GitHub-Token": token},
        json={
            "job_name": "private-data",
            "agent": "oracle",
            "dataset": "acme/data",
            "model_name": "model",
            "server_url": "https://model.example",
            "github_dataset": source(ref="main").model_dump(),
        },
    )


def test_submission_stores_only_metadata_and_cancel_drops_credential(client):
    response = submit(client)
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    queued = api._job_queue[0]
    assert queued.github_token.get_secret_value() == TOKEN
    assert TOKEN not in repr(queued)
    row = api.job_store.get(job_id)
    assert TOKEN not in json.dumps(row)
    assert TOKEN.encode() not in api.job_store._db_path.read_bytes()
    assert row["dataset"] == "acme/data"
    assert source().local_path in json.loads(row["command"])
    assert (
        client.delete(f"/jobs/{job_id}", headers={"X-API-Key": "queue-key"}).status_code
        == 200
    )
    assert queued.github_token is None and not api._job_queue


def test_validation_errors_do_not_echo_token_header(client):
    response = client.post(
        "/jobs", json={}, headers={"X-API-Key": "queue-key", "X-GitHub-Token": TOKEN}
    )
    assert response.status_code == 422
    assert TOKEN not in response.text


def test_public_submission_does_not_require_github_token(client):
    response = submit(client, token="")
    assert response.status_code == 200
    assert api._job_queue[-1].github_token is None


def test_unused_github_token_does_not_reject_non_github_job(client):
    response = client.post(
        "/jobs",
        headers={"X-API-Key": "queue-key", "X-GitHub-Token": TOKEN},
        json={
            "job_name": "ordinary-job",
            "agent": "oracle",
            "dataset": "example-dataset",
            "model_name": "model",
            "server_url": "https://model.example",
        },
    )

    assert response.status_code == 200, response.text
    assert api._job_queue[-1].github_dataset is None
    assert api._job_queue[-1].github_token is None


def test_unused_github_token_does_not_block_non_github_resume(client):
    api.job_store.insert(
        "ordinary-job",
        "ordinary-job",
        "oracle",
        "example-dataset",
        "model",
        "https://model.example",
        ["coding-agent-bench", "run"],
    )
    api.job_store.update_status("ordinary-job", api.JobStatus.FAILED)

    response = client.post(
        "/jobs/ordinary-job/resume",
        json={},
        headers={"X-API-Key": "queue-key", "X-GitHub-Token": TOKEN},
    )

    assert response.status_code == 200, response.text
    assert api._job_queue[-1].github_dataset is None
    assert api._job_queue[-1].github_token is None


def test_existing_database_gets_source_metadata_column(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE jobs (job_id TEXT PRIMARY KEY, job_name TEXT, agent TEXT, dataset TEXT, model_name TEXT, command TEXT, status TEXT, error TEXT)"
        )
        conn.execute(
            "INSERT INTO jobs VALUES ('old', 'old-job', 'oracle', 'data', 'model', '[]', 'completed', NULL)"
        )
    store = api.JobStore(path)
    assert store.get("old")["github_dataset"] is None
    store.pin_github_dataset("old", source(commit=COMMIT))
    assert json.loads(store.get("old")["github_dataset"])["commit"] == COMMIT


@pytest.mark.parametrize("token", ["", TOKEN])
def test_resume_restores_same_commit_with_fresh_optional_token(client, token):
    job_id = submit(client).json()["job_id"]
    api.job_store.pin_github_dataset(job_id, source(ref="main", commit=COMMIT))
    api.job_store.update_status(job_id, api.JobStatus.FAILED)
    response = client.post(
        f"/jobs/{job_id}/resume",
        json={},
        headers={
            "X-API-Key": "queue-key",
            "X-GitHub-Token": token,
        },
    )
    assert response.status_code == 200, response.text
    queued = api._job_queue[-1]
    assert queued.github_dataset.commit == COMMIT
    assert queued.github_dataset.local_path == source().local_path
    assert (
        queued.github_token.get_secret_value() if queued.github_token else ""
    ) == token
    assert TOKEN not in json.dumps(api.job_store.get(queued.job_id))


def test_resume_requires_successful_initial_preparation(client):
    job_id = submit(client).json()["job_id"]
    api.job_store.update_status(job_id, api.JobStatus.FAILED)
    response = client.post(
        f"/jobs/{job_id}/resume", json={}, headers={"X-API-Key": "queue-key"}
    )
    assert response.status_code == 400


def test_github_resume_preserves_results_identity_across_repeated_resumes(client):
    api.job_store.insert(
        "original",
        "benchmark--resume",
        "oracle",
        "data",
        "model",
        "https://model.example",
        ["coding-agent-bench", "run"],
        github_dataset=source(commit=COMMIT),
    )
    job_id = "original"
    for _ in range(2):
        api.job_store.update_status(job_id, api.JobStatus.FAILED)
        response = client.post(
            f"/jobs/{job_id}/resume",
            json={},
            headers={
                "X-API-Key": "queue-key",
                "X-GitHub-Token": TOKEN,
            },
        )
        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]
        row = api.job_store.get(job_id)
        assert row["results_job_name"] == "benchmark--resume"
        assert api.resume_options(row["command"])["paths"] == [
            "/app/jobs/benchmark--resume"
        ]
        assert json.loads(row["github_dataset"])["commit"] == COMMIT


def test_manual_paused_resume_replaces_scheduled_recovery_with_fresh_token(client):
    job_id = submit(client).json()["job_id"]
    api.job_store.pin_github_dataset(job_id, source(commit=COMMIT))
    api.job_store.update_status(job_id, api.JobStatus.PAUSED)
    scheduled = api.QueuedJob(
        job_id, [], "https://model.example", "model", adopt_existing=True
    )
    api._job_queue[:] = [scheduled]
    response = client.post(
        f"/jobs/{job_id}/resume",
        json={},
        headers={
            "X-API-Key": "queue-key",
            "X-GitHub-Token": "fresh-token",
        },
    )
    assert response.status_code == 200, response.text
    assert len(api._job_queue) == 1
    queued = api._job_queue[0]
    assert queued is not scheduled
    assert queued.github_token.get_secret_value() == "fresh-token"
    assert queued.github_dataset.commit == COMMIT


@pytest.mark.parametrize("pinned", [False, True])
def test_restart_adopts_only_prepared_github_dataset(client, monkeypatch, pinned):
    job_id = submit(client).json()["job_id"]
    queued = api._job_queue[0]
    queued.github_token = None
    if pinned:
        queued.github_dataset = source(commit=COMMIT)
        api.job_store.pin_github_dataset(job_id, queued.github_dataset)
    api.job_store.update_status(job_id, api.JobStatus.RUNNING)
    get_job = AsyncMock(
        side_effect=[
            {},
            {
                "status": {
                    "conditions": [
                        {"type": "Complete", "status": "True"},
                    ]
                }
            },
        ]
    )
    release, prepare = AsyncMock(), AsyncMock()
    monkeypatch.setattr(OpenshiftJob, "_get_job", get_job)
    monkeypatch.setattr(OpenshiftJob, "_wait_for_job_pod_ready", AsyncMock())
    monkeypatch.setattr(OpenshiftJob, "_delete_job", AsyncMock())
    monkeypatch.setattr(OpenshiftJob, "release_github_dataset", release)
    monkeypatch.setattr(OpenshiftJob, "prepare_github_dataset", prepare)
    asyncio.run(
        api._run_job(job_id, queued.command, adopt_existing=True, queued_job=queued)
    )
    prepare.assert_not_awaited()
    if pinned:
        release.assert_awaited_once()
        assert api.job_store.get(job_id)["status"] == "completed"
    else:
        release.assert_not_awaited()
        assert "preparation was interrupted" in api.job_store.get(job_id)["error"]


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("resume", [False, True])
def test_worker_pins_commit_before_release_and_always_drops_token(
    client, monkeypatch, fail, resume
):
    job_id = submit(client).json()["job_id"]
    queued = api._job_queue[0]
    if resume:
        queued.command = ["sh", "-c", "echo resume"]
        queued.github_dataset = source(commit=COMMIT)
    events = []

    async def oc(self, command, **kwargs):
        if command[0] == "apply":
            assert TOKEN.encode() not in kwargs["stdin_data"]
        return json.dumps(
            {"status": {"conditions": [{"type": "Complete", "status": "True"}]}}
        ), ""

    async def prepare(self, src, token):
        assert token.get_secret_value() == TOKEN
        events.append("prepare")
        if fail:
            raise RuntimeError("download failed")
        return COMMIT

    async def release(self):
        assert (
            json.loads(api.job_store.get(job_id)["github_dataset"])["commit"] == COMMIT
        )
        assert queued.github_token is None
        events.append("release")

    monkeypatch.setattr(OpenshiftJob, "_run_oc_command", oc)
    monkeypatch.setattr(OpenshiftJob, "_wait_for_job_pod_ready", AsyncMock())
    monkeypatch.setattr(OpenshiftJob, "prepare_github_dataset", prepare)
    monkeypatch.setattr(OpenshiftJob, "release_github_dataset", release)
    monkeypatch.setattr(OpenshiftJob, "_delete_job", AsyncMock())
    asyncio.run(api._run_job(job_id, queued.command, queued_job=queued))
    assert queued.github_token is None
    assert events == (["prepare"] if fail else ["prepare", "release"])
    assert api.job_store.get(job_id)["status"] == ("failed" if fail else "completed")


def test_cancel_during_preparation_deletes_pod_and_drops_token(client, monkeypatch):
    job_id = submit(client).json()["job_id"]
    queued = api._job_queue[0]
    monkeypatch.setattr(api, "_shutting_down", False)
    monkeypatch.setattr(
        OpenshiftJob, "_run_oc_command", AsyncMock(return_value=("", ""))
    )
    monkeypatch.setattr(OpenshiftJob, "_wait_for_job_pod_ready", AsyncMock())
    monkeypatch.setattr(
        OpenshiftJob,
        "prepare_github_dataset",
        AsyncMock(side_effect=asyncio.CancelledError),
    )
    signal, delete, release = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(OpenshiftJob, "_signal_job_pod", signal)
    monkeypatch.setattr(OpenshiftJob, "_delete_job", delete)
    monkeypatch.setattr(OpenshiftJob, "release_github_dataset", release)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(api._run_job(job_id, queued.command, queued_job=queued))
    assert queued.github_token is None
    assert api.job_store.get(job_id)["status"] == "cancelled"
    delete.assert_awaited_once()
    release.assert_not_awaited()


def test_ui_submits_directly_without_archive_staging():
    html = build_submit_form_html(["model"], ["oracle"], [], False)
    assert "/datasets/stage" not in html
    assert "X-GitHub-Token" in html
    assert "github_token:" not in html
    assert "formData.github_dataset" in html
    assert 'id="github-dataset-fields"' in html
    assert 'id="github-dataset-fields" style="grid-column: 1 / -1; display: grid;' in html
    assert html.index('id="advanced-fields"') < html.index('id="github-dataset-fields"')
    assert html.index('id="github-dataset-fields"') < html.index('id="submit-btn"')
    assert 'id="github_subdirectory"' in html
    assert 'id="github_subdirectory" autocomplete="off"' in html
    assert 'value="tasks"' in html
    assert 'id="github_repo" autocomplete="off"' in html
    assert 'placeholder="owner/repository or https://github.com/owner/repository"' in html
    assert "repository_url: githubRepositoryUrl" in html
    assert html.index("const formData = {") < html.index("if (skills.length) formData.skills = skills;")


def test_pod_helper_errors_never_emit_credentials(monkeypatch, capsys):
    from types import SimpleNamespace

    payload = {**source().model_dump(), "token": TOKEN}
    monkeypatch.setattr(
        datasets.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode())),
    )

    def fail(*_args):
        raise RuntimeError(f"upstream failure containing {TOKEN}")

    monkeypatch.setattr(datasets, "prepare_dataset", fail)
    with pytest.raises(SystemExit) as caught:
        datasets.main()
    assert caught.value.code == 1
    output = capsys.readouterr()
    assert TOKEN not in output.out + output.err
    assert json.loads(output.out) == {"error": "preparation_failed"}
