import hashlib
import logging
import os
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from coding_agent_bench.intake.config import (
    AUTO_APPROVE,
    Column,
    Status,
    generate_job_name,
)
from coding_agent_bench.intake.sheets import SheetsClient
from coding_agent_bench.intake.validation import validate_row
from coding_agent_bench.utils import is_stage_environment

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    Status.COMPLETED.value,
    Status.FAILED.value,
    Status.CANCELLED.value,
    Status.NEEDS_REVIEW.value,
}


def _auto_approve_enabled() -> bool:
    """Read auto-approval after dotenv loading while preserving test overrides."""
    return AUTO_APPROVE or os.environ.get("AUTO_APPROVE", "false").lower() == "true"


def _queue_verify() -> str | bool:
    """Return the CA bundle for verifying the queue's TLS certificate.

    When the queue is reached over its in-cluster service address it presents
    an OpenShift service-serving certificate, whose CA is not in the public
    trust store. JOB_QUEUE_CA_BUNDLE points at that CA so verification stays
    on; absent it, fall back to the default public trust store.
    """
    return os.environ.get("JOB_QUEUE_CA_BUNDLE") or True


def _row_idempotency_key(row: list[str]) -> str:
    """Return a stable key for one form submission, independent of sheet row number."""
    identity_columns = (
        Column.TIMESTAMP,
        Column.AGENT,
        Column.DATASET,
        Column.MODEL_NAME,
        Column.SERVER_URL,
        Column.EMAIL,
    )
    identity = "\x1f".join(
        row[column].strip() if len(row) > column else "" for column in identity_columns
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"intake-{digest}"


def _submit_job(
    api_base_url: str,
    api_key: str,
    agent: str,
    dataset: str,
    model_name: str,
    server_url: str,
    job_name: str,
    idempotency_key: str | None = None,
) -> dict:
    """Submit one intake request to the queue API and return its JSON response."""
    payload = {
        "job_name": job_name,
        "agent": agent,
        "dataset": dataset,
        "model_name": model_name,
        "server_url": server_url,
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key

    response = httpx.post(
        f"{api_base_url.rstrip('/')}/jobs",
        json=payload,
        headers={"X-API-Key": api_key},
        timeout=30,
        verify=_queue_verify(),
    )
    response.raise_for_status()
    return response.json()


def _check_job_status(api_base_url: str, api_key: str, job_id: str) -> dict:
    """Fetch one job's current status from the queue API."""
    response = httpx.get(
        f"{api_base_url.rstrip('/')}/jobs/{job_id}",
        headers={"X-API-Key": api_key},
        timeout=30,
        verify=_queue_verify(),
    )
    response.raise_for_status()
    return response.json()


def process_rows(
    sheets: SheetsClient,
    api_base_url: str,
    api_key: str,
) -> None:
    """Process approved and in-flight rows, syncing status into the sheet."""
    stage = is_stage_environment()
    rows = sheets.get_all_rows()

    for i, row in enumerate(rows):
        row_num = i + 1

        try:
            status = row[Column.STATUS].strip()

            if status in TERMINAL_STATUSES:
                # Completed/failed rows get one final status check when the
                # terminal state was not yet reconciled into the sheet.
                if not stage and status in (Status.COMPLETED.value, Status.FAILED.value) and (
                    row[Column.NOTIFIED_DONE].strip().upper() != "TRUE"
                ):
                    _handle_inflight_row(sheets, row, row_num, api_base_url, api_key)
                continue

            if status == Status.APPROVED.value or (not status and _auto_approve_enabled()):
                _handle_new_row(sheets, row, row_num, api_base_url, api_key)
            elif not stage and status in (
                Status.QUEUED.value,
                Status.RUNNING.value,
                Status.PAUSED.value,
            ):
                _handle_inflight_row(sheets, row, row_num, api_base_url, api_key)
        except Exception:
            logger.exception("Failed to process row %d", row_num)


def _handle_new_row(
    sheets: SheetsClient,
    row: list[str],
    row_num: int,
    api_base_url: str,
    api_key: str,
) -> None:
    """Validate and submit one approved intake row."""
    agent = row[Column.AGENT].strip()
    dataset = row[Column.DATASET].strip()
    model_name = row[Column.MODEL_NAME].strip()
    server_url = row[Column.SERVER_URL].strip()

    existing_job_id = row[Column.JOB_ID].strip()
    if existing_job_id:
        sheets.update_cell(row_num, Column.STATUS, Status.QUEUED.value)
        return

    errors = validate_row(agent, dataset, server_url)
    if errors:
        sheets.update_cell(row_num, Column.STATUS, Status.NEEDS_REVIEW.value)
        sheets.update_cell(row_num, Column.ERROR, "; ".join(errors))
        return

    job_name = generate_job_name(agent, dataset, model_name)

    try:
        result = _submit_job(
            api_base_url,
            api_key,
            agent,
            dataset,
            model_name,
            server_url,
            job_name,
            idempotency_key=_row_idempotency_key(row),
        )
    except Exception as e:
        logger.exception("Failed to submit job for row %d", row_num)
        sheets.update_cell(row_num, Column.STATUS, Status.NEEDS_REVIEW.value)
        sheets.update_cell(row_num, Column.ERROR, f"API error: {e}")
        return

    job_id = result["job_id"]
    sheets.update_cell(row_num, Column.JOB_ID, job_id)
    sheets.update_cell(row_num, Column.STATUS, Status.QUEUED.value)


def _handle_inflight_row(
    sheets: SheetsClient,
    row: list[str],
    row_num: int,
    api_base_url: str,
    api_key: str,
) -> None:
    """Synchronize queue status back into the spreadsheet."""
    job_id = row[Column.JOB_ID].strip()
    current_status = row[Column.STATUS].strip()

    if not job_id:
        return

    try:
        job_data = _check_job_status(api_base_url, api_key, job_id)
    except Exception:
        logger.exception("Failed to check job status for row %d", row_num)
        return

    api_status = job_data["status"]

    if api_status in ("completed", "failed"):
        error = job_data.get("error")
        if api_status == "failed" and not error and not row[Column.ERROR].strip():
            error = "Unknown error"
        target = Status.COMPLETED.value if api_status == "completed" else Status.FAILED.value
        if current_status != target:
            sheets.update_cell(row_num, Column.STATUS, target)
        if error and row[Column.ERROR].strip() != error:
            sheets.update_cell(row_num, Column.ERROR, error)
        sheets.update_cell(row_num, Column.NOTIFIED_DONE, "TRUE")

    elif api_status in ("paused", "pausing"):
        # A Nebius preemption parks the job while the instance restarts; it
        # auto-resumes, so the sheet must not read it as terminal.
        error = job_data.get("error")
        if error and row[Column.ERROR].strip() != error:
            sheets.update_cell(row_num, Column.ERROR, error)
        if current_status != Status.PAUSED.value:
            sheets.update_cell(row_num, Column.STATUS, Status.PAUSED.value)

    elif api_status == "cancelled":
        error = job_data.get("error")
        if error and row[Column.ERROR].strip() != error:
            sheets.update_cell(row_num, Column.ERROR, error)
        if current_status != Status.CANCELLED.value:
            sheets.update_cell(row_num, Column.STATUS, Status.CANCELLED.value)
        sheets.update_cell(row_num, Column.NOTIFIED_DONE, "TRUE")

    elif api_status == "running" and current_status != Status.RUNNING.value:
        sheets.update_cell(row_num, Column.STATUS, Status.RUNNING.value)


def _validate_queue_url(api_base_url: str) -> None:
    """Require an encrypted queue endpoint unless insecure HTTP is explicitly opted in."""
    parsed = urlparse(api_base_url)
    if not parsed.netloc or parsed.scheme not in {"http", "https"}:
        raise ValueError("JOB_QUEUE_URL must be an absolute http(s) URL")
    if parsed.scheme == "https":
        return
    if os.environ.get("ALLOW_INSECURE_QUEUE_HTTP", "").lower() == "true":
        logger.warning("Using insecure HTTP for JOB_QUEUE_URL; this is intended for local development only")
        return
    raise ValueError(
        "JOB_QUEUE_URL must use https; set ALLOW_INSECURE_QUEUE_HTTP=true only for local development"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    load_dotenv()

    credentials_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    api_base_url = os.environ["JOB_QUEUE_URL"]
    _validate_queue_url(api_base_url)
    api_key = os.environ["API_KEY"]

    client = SheetsClient(credentials_path, sheet_id)
    process_rows(client, api_base_url, api_key)
    logger.info("Poller run complete")
