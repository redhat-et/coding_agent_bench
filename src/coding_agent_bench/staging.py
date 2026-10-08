"""Record snapshot ownership and remove only explicitly owned staging objects."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from coding_agent_bench.utils import storage_endpoint_url


BUCKET = "results-staging"
PHASES = ("original", "updated")


def snapshot_manifest(job_dir: Path, job_name: str, attempt: str, phase: str) -> dict:
    """Inventory the local files copied into one snapshot, not a remote prefix."""
    if phase not in PHASES or not attempt or "/" in attempt:
        raise ValueError("Invalid snapshot phase or attempt")
    return {
        "version": 1, "job_name": job_name, "attempt": attempt, "phase": phase,
        "files": sorted(
            path.relative_to(job_dir).as_posix()
            for path in job_dir.rglob("*") if path.is_file()
        ),
    }


def _aws(*args: str) -> str:
    """Use the worker's configured AWS credentials and installed CLI."""
    return subprocess.run(
        ["aws", "--endpoint-url", storage_endpoint_url(), *args],
        check=True, capture_output=True, text=True, timeout=120,
    ).stdout


def _delete_keys(keys: list[str]) -> None:
    """Delete exact keys in batches, rejecting even partial S3 deletion errors."""
    with tempfile.TemporaryDirectory(prefix="cab-staging-") as directory:
        payload = Path(directory) / "delete.json"
        for offset in range(0, len(keys), 1000):
            payload.write_text(json.dumps({
                "Objects": [{"Key": key} for key in keys[offset:offset + 1000]],
                "Quiet": True,
            }))
            result = json.loads(_aws(
                "s3api", "delete-objects", "--bucket", BUCKET,
                "--delete", f"file://{payload}", "--output", "json",
            ))
            if result.get("Errors"):
                raise RuntimeError(f"Staging object deletion failed: {result['Errors']}")


def cleanup_job_staging(job_name: str) -> None:
    """Delete manifest-owned files, preserving nested jobs and legacy snapshots.

    The CLI auto-paginates this listing. Only direct attempt markers belonging
    to this exact job are eligible. Markers are removed last so a partial
    deletion can be retried; unlisted files are never deleted recursively.
    """
    if not job_name:
        return
    prefix = f"{job_name}/"
    listing = json.loads(_aws(
        "s3api", "list-objects-v2", "--bucket", BUCKET,
        "--prefix", prefix, "--output", "json",
    ))
    for item in listing.get("Contents", []):
        marker = item["Key"]
        if not marker.startswith(prefix):
            continue
        parts = marker[len(prefix):].split("/")
        if len(parts) != 2 or parts[1] not in ("original.complete", "updated.complete"):
            continue
        attempt, filename = parts
        phase = filename.removesuffix(".complete")
        try:
            manifest = json.loads(_aws("s3", "cp", f"s3://{BUCKET}/{marker}", "-"))
        except json.JSONDecodeError:
            continue  # Legacy 'complete' markers do not prove object ownership.
        if not isinstance(manifest, dict) or any(
            manifest.get(key) != value for key, value in {
                "version": 1, "job_name": job_name, "attempt": attempt, "phase": phase,
            }.items()
        ):
            continue
        files = manifest.get("files")
        if not isinstance(files, list) or not all(
            isinstance(name, str) and name
            and all(part not in ("", ".", "..") for part in name.split("/"))
            for name in files
        ):
            continue
        _delete_keys([f"{prefix}{attempt}/{phase}/{name}" for name in files])
        _delete_keys([marker])


def main() -> None:
    """Build a snapshot marker on stdout, or clean a completed job's snapshots."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    manifest = commands.add_parser("manifest")
    manifest.add_argument("job_dir", type=Path)
    manifest.add_argument("job_name")
    manifest.add_argument("attempt")
    manifest.add_argument("phase", choices=PHASES)
    cleanup = commands.add_parser("cleanup")
    cleanup.add_argument("job_name")
    args = parser.parse_args()
    if args.operation == "manifest":
        print(json.dumps(snapshot_manifest(args.job_dir, args.job_name, args.attempt, args.phase)))
    else:
        cleanup_job_staging(args.job_name)


if __name__ == "__main__":
    main()
