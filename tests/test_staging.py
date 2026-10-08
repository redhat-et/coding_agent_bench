"""Ownership and partial-deletion guards for object-storage snapshot cleanup."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from coding_agent_bench import staging
from coding_agent_bench.utils import storage_endpoint_url


def test_aws_uses_configured_storage_endpoint(monkeypatch):
    monkeypatch.setenv("STORAGE_ENDPOINT_URL", "https://storage.example.test:9443/")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="{}")

    monkeypatch.setattr(staging.subprocess, "run", run)

    assert staging._aws("s3api", "list-objects-v2") == "{}"
    assert calls[0][0] == [
        "aws", "--endpoint-url", "https://storage.example.test:9443",
        "s3api", "list-objects-v2",
    ]


def test_storage_endpoint_defaults_to_rustfs(monkeypatch):
    monkeypatch.delenv("STORAGE_ENDPOINT_URL", raising=False)
    assert storage_endpoint_url() == "http://harbor-storage:9000"


def mock_storage(monkeypatch, manifest, delete_error=False):
    marker = "parent/current/original.complete"
    deletes = []

    def aws(*args):
        if "list-objects-v2" in args:
            return json.dumps({"Contents": [{"Key": marker}]})
        if args[:2] == ("s3", "cp"):
            return manifest
        if "delete-objects" in args:
            path = Path(args[args.index("--delete") + 1].removeprefix("file://"))
            keys = [item["Key"] for item in json.loads(path.read_text())["Objects"]]
            deletes.append(keys)
            if delete_error:
                return json.dumps({"Errors": [{"Key": keys[0], "Code": "AccessDenied"}]})
            return "{}"
        raise AssertionError(args)

    monkeypatch.setattr(staging, "_aws", aws)
    return marker, deletes


@pytest.mark.parametrize("change", [
    {"job_name": "another-job"}, {"attempt": "other-attempt"}, {"phase": "updated"},
    {"version": 2}, {"files": ["../neighbor"]}, {"files": ["/absolute"]},
    {"files": "result.json"}, {"files": [None]},
])
def test_invalid_ownership_never_deletes_objects(monkeypatch, change):
    manifest = {
        "version": 1, "job_name": "parent", "attempt": "current",
        "phase": "original", "files": ["result.json"], **change,
    }
    _, deletes = mock_storage(monkeypatch, json.dumps(manifest))
    staging.cleanup_job_staging("parent")
    assert deletes == []


@pytest.mark.parametrize("marker", ["complete\n", "null", "[]", "{}"])
def test_legacy_or_malformed_markers_are_retained(monkeypatch, marker):
    _, deletes = mock_storage(monkeypatch, marker)
    staging.cleanup_job_staging("parent")
    assert deletes == []


def test_partial_delete_error_retains_ownership_marker(monkeypatch):
    manifest = {
        "version": 1, "job_name": "parent", "attempt": "current",
        "phase": "original", "files": ["result.json"],
    }
    marker, deletes = mock_storage(monkeypatch, json.dumps(manifest), delete_error=True)
    with pytest.raises(RuntimeError, match="AccessDenied"):
        staging.cleanup_job_staging("parent")
    assert deletes == [["parent/current/original/result.json"]]
    assert not any(marker in batch for batch in deletes)


def test_large_snapshot_is_batched_and_marker_deleted_last(monkeypatch):
    files = [f"trial-{index}/result.json" for index in range(1001)]
    manifest = {
        "version": 1, "job_name": "parent", "attempt": "current",
        "phase": "original", "files": files,
    }
    marker, deletes = mock_storage(monkeypatch, json.dumps(manifest))
    staging.cleanup_job_staging("parent")
    assert [len(batch) for batch in deletes] == [1000, 1, 1]
    assert deletes[-1] == [marker]
    assert deletes[0] + deletes[1] == [f"parent/current/original/{name}" for name in files]
