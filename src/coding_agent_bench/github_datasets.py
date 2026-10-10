"""Download GitHub datasets inside job pods; credentials arrive only via stdin."""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile, ZipInfo

from pydantic import BaseModel, Field, field_validator


DEFAULT_MAX_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 50_000
DATASET_ROOT = Path("/tmp/cab-github-dataset")
DATASET_SOURCE = DATASET_ROOT / "source"
GITHUB_ARCHIVE_REDIRECT_HOSTS = {
    "codeload.github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
}
_GITHUB_REPOSITORY_COMPONENT = re.compile(r"[A-Za-z0-9_.-]+")


class DatasetArchiveError(ValueError):
    """Raised when a GitHub repository archive is invalid or unsafe."""


class GitHubArchiveFetchError(ValueError):
    """Raised when GitHub cannot provide a repository archive."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubDataset(BaseModel):
    """Persistable source metadata. Never contains authentication credentials."""

    repository_url: str = Field(max_length=2048)
    ref: str = Field(default="", max_length=512)
    subdirectory: str = Field(default="tasks", max_length=1024, validate_default=True)
    commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")

    @field_validator("repository_url")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        owner, repository = parse_github_repository_url(value)
        return f"https://github.com/{owner}/{repository}"

    @field_validator("subdirectory")
    @classmethod
    def validate_subdirectory(cls, value: str) -> str:
        return normalize_dataset_subdirectory(value)

    @field_validator("ref")
    @classmethod
    def validate_ref(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("GitHub ref is invalid")
        return value

    @property
    def local_path(self) -> str:
        return str(DATASET_SOURCE / self.subdirectory)


def normalize_dataset_subdirectory(value: str | None) -> str:
    """Validate a repository-relative directory path, where empty means root."""
    if value is None or not value.strip():
        return ""
    value = value.strip()
    if value in (".", "./"):
        return ""
    path = PurePosixPath(value)
    if (
        "\\" in value
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in path.parts)
        or any(ord(char) < 32 for char in value)
    ):
        raise DatasetArchiveError("Dataset subdirectory must be a safe relative path")
    return path.as_posix()


def parse_github_repository_url(value: str) -> tuple[str, str]:
    """Accept only a plain HTTPS github.com owner/repository URL."""
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError as exc:
        raise GitHubArchiveFetchError("Repository URL is invalid") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise GitHubArchiveFetchError("Repository must be an HTTPS github.com URL")
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2:
        raise GitHubArchiveFetchError(
            "Repository URL must have the form https://github.com/owner/repo"
        )
    owner, repository = parts
    repository = repository.removesuffix(".git")
    if (
        not owner
        or not repository
        or owner in (".", "..")
        or repository in (".", "..")
        or _GITHUB_REPOSITORY_COMPONENT.fullmatch(owner) is None
        or _GITHUB_REPOSITORY_COMPONENT.fullmatch(repository) is None
    ):
        raise GitHubArchiveFetchError(
            "Repository URL contains an invalid owner or repository"
        )
    return owner, repository


def resolve_github_commit(source: GitHubDataset, token: str) -> str:
    if source.commit:
        return source.commit
    owner, repository = parse_github_repository_url(source.repository_url)
    url = f"https://api.github.com/repos/{owner}/{repository}/commits/{quote(source.ref or 'HEAD', safe='')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "coding-agent-bench",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with build_opener(_NoRedirect).open(
            Request(url, headers=headers), timeout=60
        ) as response:
            data = json.loads(response.read(1024 * 1024))
        commit = data.get("sha", "")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Invalid commit")
        return commit
    except Exception:
        raise GitHubArchiveFetchError(
            "Could not resolve the GitHub repository/ref"
        ) from None


def fetch_github_archive(
    repository_url: str,
    ref: str,
    token: str,
    archive_path: Path,
    max_archive_bytes: int,
) -> int:
    """Fetch a GitHub ZIP to disk, using the token only for the API request.

    Redirects are handled explicitly so the Authorization header is never sent
    to GitHub's archive CDN. The body is streamed and size-limited.
    """
    owner, repository = parse_github_repository_url(repository_url)
    if len(ref) > 512 or any(ord(char) < 32 for char in ref):
        raise GitHubArchiveFetchError("GitHub ref is invalid")

    api_url = f"https://api.github.com/repos/{quote(owner)}/{quote(repository)}/zipball"
    if ref:
        api_url += f"/{quote(ref, safe='')}"

    opener = build_opener(_NoRedirect)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "coding-agent-bench",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    current_url = api_url
    response = None
    for redirect_count in range(4):
        request = Request(current_url, headers=headers)
        try:
            response = opener.open(request, timeout=60)
            break
        except HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                exc.close()
                raise GitHubArchiveFetchError(
                    f"GitHub rejected the repository, ref, or token (HTTP {exc.code})"
                ) from None
            location = exc.headers.get("Location")
            exc.close()
            if not location or redirect_count == 3:
                raise GitHubArchiveFetchError(
                    "GitHub returned an invalid archive redirect"
                ) from None
            redirected_url = urljoin(current_url, location)
            parsed_redirect = urlparse(redirected_url)
            if (
                parsed_redirect.scheme != "https"
                or parsed_redirect.hostname not in GITHUB_ARCHIVE_REDIRECT_HOSTS
                or parsed_redirect.username is not None
                or parsed_redirect.password is not None
                or parsed_redirect.port not in (None, 443)
            ):
                raise GitHubArchiveFetchError(
                    "GitHub returned an untrusted archive redirect"
                )
            current_url = redirected_url
            # Only the api.github.com request receives the user's token.
            headers = {"Accept": "application/zip", "User-Agent": "coding-agent-bench"}
        except (URLError, TimeoutError, OSError):
            raise GitHubArchiveFetchError(
                "Could not connect to GitHub to fetch the archive"
            ) from None

    if response is None:
        raise GitHubArchiveFetchError("GitHub did not return a repository archive")

    try:
        with response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_archive_bytes:
                raise DatasetArchiveError(
                    "Dataset archive exceeds the download size limit"
                )
            total = 0
            with Path(archive_path).open("xb") as output:
                os.chmod(archive_path, 0o600)
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_archive_bytes:
                        raise DatasetArchiveError(
                            "Dataset archive exceeds the download size limit"
                        )
                    output.write(chunk)
        if total == 0:
            raise GitHubArchiveFetchError("GitHub returned an empty repository archive")
        return total
    except (HTTPError, URLError, TimeoutError, OSError):
        raise GitHubArchiveFetchError(
            "Could not download the GitHub repository archive"
        ) from None


def extract_github_archive(
    archive_path: Path,
    destination: Path,
    max_unpacked_bytes: int = DEFAULT_MAX_UNPACKED_BYTES,
    subdirectory: str = "",
) -> Path:
    """Safely extract a GitHub ZIP archive, stripping its generated root folder.

    ZIP paths are validated before writing, symlinks and special files are
    rejected, and the total expanded size is bounded to prevent ZIP-slip and
    ZIP-bomb attacks. Returns the resulting dataset directory.
    """
    archive_path = Path(archive_path)
    destination = Path(destination)
    if destination.exists():
        raise DatasetArchiveError("Dataset extraction destination already exists")

    try:
        archive = ZipFile(archive_path)
    except (BadZipFile, OSError) as exc:
        raise DatasetArchiveError(
            "The downloaded GitHub archive is not a valid ZIP"
        ) from exc

    try:
        with archive:
            entries = archive.infolist()
            if not entries:
                raise DatasetArchiveError("The GitHub archive is empty")
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise DatasetArchiveError("The GitHub archive contains too many files")

            parsed: list[tuple[ZipInfo, tuple[str, ...], int]] = []
            roots: set[str] = set()
            total_unpacked = 0
            for info in entries:
                parts = PurePosixPath(info.filename).parts
                if (
                    not parts
                    or PurePosixPath(info.filename).is_absolute()
                    or ".." in parts
                ):
                    raise DatasetArchiveError(
                        "The GitHub archive contains an unsafe path"
                    )
                if any(part in ("", ".") for part in parts):
                    raise DatasetArchiveError(
                        "The GitHub archive contains an unsafe path"
                    )

                mode = (info.external_attr >> 16) & 0xFFFF
                kind = stat.S_IFMT(mode)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise DatasetArchiveError(
                        "The GitHub archive contains a symlink or special file"
                    )
                if info.is_dir() and kind not in (0, stat.S_IFDIR):
                    raise DatasetArchiveError(
                        "The GitHub archive contains an invalid directory entry"
                    )

                total_unpacked += info.file_size
                if info.file_size < 0 or total_unpacked > max_unpacked_bytes:
                    raise DatasetArchiveError(
                        "The GitHub archive expands beyond the allowed size"
                    )
                roots.add(parts[0])
                parsed.append((info, parts, mode))

            strip_root = len(roots) == 1 and any(
                len(parts) > 1 for _, parts, _ in parsed
            )
            destination.mkdir(parents=True, mode=0o700)
            destination_resolved = destination.resolve()

            for info, original_parts, mode in parsed:
                parts = original_parts[1:] if strip_root else original_parts
                if not parts:
                    continue
                target = destination.joinpath(*parts)
                if not target.resolve().is_relative_to(destination_resolved):
                    raise DatasetArchiveError(
                        "The GitHub archive contains an unsafe path"
                    )

                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True, mode=0o755)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                written = 0
                with archive.open(info) as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        if written > info.file_size or written > max_unpacked_bytes:
                            raise DatasetArchiveError(
                                "The GitHub archive expands beyond the allowed size"
                            )
                        output.write(chunk)
                target.chmod(0o755 if mode & 0o111 else 0o644)

            selected_directory = (
                destination.joinpath(
                    *normalize_dataset_subdirectory(subdirectory).split("/")
                )
                if subdirectory
                else destination
            )
            if not selected_directory.is_dir():
                raise DatasetArchiveError(
                    f"Dataset subdirectory does not exist in the repository: {subdirectory}"
                )
            return selected_directory
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def prepare_dataset(
    source: GitHubDataset, token: str, root: Path = DATASET_ROOT
) -> str:
    """Download completely, then extract and validate before releasing Harbor."""
    from harbor.models.task.task import Task

    # Own a child directory, never chmod the root-owned emptyDir mount itself.
    work = root / "download"
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    partial = work / "archive.partial"
    archive = work / "archive.zip"
    destination = root / "source"
    try:
        commit = resolve_github_commit(source, token)
        fetch_github_archive(
            source.repository_url, commit, token, partial, MAX_ARCHIVE_BYTES
        )
        token = ""
        partial.replace(archive)
        selected = extract_github_archive(
            archive, destination, subdirectory=source.subdirectory
        )
        if not Task.is_valid_dir(selected) and not any(
            path.is_dir() and Task.is_valid_dir(path) for path in selected.iterdir()
        ):
            raise DatasetArchiveError(
                "Selected directory contains no valid Harbor tasks"
            )
        (root / "prepared").touch()
        return commit
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        token = ""
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    # No traceback or request data on errors: stdout is a small, safe protocol.
    try:
        payload = json.loads(sys.stdin.buffer.read(16385))
        token = payload.pop("token", "")
        source = GitHubDataset.model_validate(payload)
        commit = prepare_dataset(source, token)
        print(json.dumps({"commit": commit}))
    except GitHubArchiveFetchError:
        print(json.dumps({"error": "github_fetch_failed"}))
        raise SystemExit(1) from None
    except DatasetArchiveError:
        print(json.dumps({"error": "invalid_dataset_archive"}))
        raise SystemExit(1) from None
    except Exception:
        print(json.dumps({"error": "preparation_failed"}))
        raise SystemExit(1) from None
    finally:
        token = ""


if __name__ == "__main__":
    main()
