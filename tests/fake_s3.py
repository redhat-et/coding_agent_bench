"""Filesystem-backed AWS CLI stand-in for result-transfer integration tests.

Only implements the operations used by the generated scripts. Transfer failures
copy one object before exiting, exercising recovery from partial uploads.
"""

import json
import os
from pathlib import Path
import shutil
import sys


def resolve(value: str) -> Path:
    """Map an S3 URI into the isolated test bucket directory."""
    if value.startswith("s3://"):
        return Path(os.environ["REMOTE_DIR"]) / value.removeprefix("s3://")
    return Path(value)


def main() -> int:
    """Apply one fake AWS request and record its stage for ordering assertions."""
    argv = sys.argv[1:]
    if argv[:1] == ["--endpoint-url"]:
        argv = argv[2:]
    service, operation, *args = argv
    if operation == "list-objects-v2":
        bucket = args[args.index("--bucket") + 1]
        prefix = args[args.index("--prefix") + 1]
        root = resolve(f"s3://{bucket}")
        print(json.dumps({"Contents": [
            {"Key": path.relative_to(root).as_posix()}
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.relative_to(root).as_posix().startswith(prefix)
        ]}))
        return 0
    if operation == "delete-objects":
        bucket = args[args.index("--bucket") + 1]
        payload = Path(args[args.index("--delete") + 1].removeprefix("file://"))
        root = resolve(f"s3://{bucket}")
        for item in json.loads(payload.read_text())["Objects"]:
            path = root / item["Key"]
            path.unlink(missing_ok=True)
            while path.parent != root:
                path = path.parent
                try:
                    path.rmdir()
                except OSError:
                    break
        print("{}")
        return 0
    if operation == "cp" and args[-1] == "-":
        print(resolve(args[-2]).read_text(), end="")
        return 0
    if (service, operation) == ("s3api", "head-bucket"):
        stage = "head"
    elif operation == "mb":
        stage = "bucket"
    elif operation == "sync":
        stage = "promote"
    elif operation == "cp":
        source, target = args[-2:]
        stage = "upload"
        if source == "-":
            stage = "backup-marker" if target.endswith("/original.complete") else "upload-marker"
        elif source.startswith("s3://"):
            stage = "backup" if target.startswith("s3://") else "download"
    else:
        return 99

    with Path(os.environ["TRACE"]).open("a") as trace:
        trace.write(stage + "\n")
    fail = os.environ.get("FAIL_STAGE") == stage
    bucket_mode = os.environ.get("BUCKET_MODE", "")
    concurrent_create = Path(os.environ["REMOTE_DIR"]) / "concurrent-create"
    if stage == "head":
        if bucket_mode:
            return 0 if concurrent_create.exists() else 23
        return 23 if fail else 0
    if stage == "bucket":
        if bucket_mode:
            if bucket_mode == "race":
                concurrent_create.touch()
            return 23
        if not fail:
            resolve(args[0]).mkdir(parents=True, exist_ok=True)
        return 23 if fail else 0
    if stage in ("backup-marker", "upload-marker"):
        if not fail:
            marker = resolve(args[-1])
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(sys.stdin.read())
        return 23 if fail else 0

    source, target = map(resolve, args[-2:])
    # cp leaves stale keys intact; sync --delete removes them after copying.
    files = sorted(p for p in source.rglob("*") if p.is_file())
    for path in files[:1] if fail else files:
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    if fail:
        return 23
    if stage == "promote":
        for path in sorted(target.rglob("*"), reverse=True):
            if not (source / path.relative_to(target)).exists():
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
