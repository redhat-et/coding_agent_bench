import logging
import os

import httpx

from coding_agent_bench.intake.config import (
    AUTO_APPROVE,
    Column,
    Status,
    DEFAULT_MODEL_MAX_LEN,
    DEFAULT_N_CONCURRENT,
    generate_job_name,
)
from coding_agent_bench.intake.notify import (
    send_completed_email,
    send_failed_email,
    send_queued_email,
)
from coding_agent_bench.intake.sheets import SheetsClient
from coding_agent_bench.intake.validation import validate_row

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {Status.COMPLETED.value, Status.FAILED.value, Status.NEEDS_REVIEW.value}


def _submit_job(
    api_base_url: str,
    api_key: str,
    agent: str,
    dataset: str,
    model_name: str,
    server_url: str,
    job_name: str,
) -> dict:
    response = httpx.post(
        f"{api_base_url}/jobs",
        json={
            "job_name": job_name,
            "agent": agent,
            "dataset": dataset,
            "model_name": model_name,
            "server_url": server_url,
            "n_concurrent": DEFAULT_N_CONCURRENT,
            "model_max_len": DEFAULT_MODEL_MAX_LEN,
        },
        headers={"X-API-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _check_job_status(api_base_url: str, api_key: str, job_id: str) -> dict:
    response = httpx.get(
        f"{api_base_url}/jobs/{job_id}",
        headers={"X-API-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def process_rows(
    sheets: SheetsClient,
    api_base_url: str,
    api_key: str,
    sender_email: str,
    gmail_credentials_path: str,
) -> None:
    rows = sheets.get_all_rows()

    for i, row in enumerate(rows):
        row_num = i + 1

        try:
            status = row[Column.STATUS].strip()

            if status in TERMINAL_STATUSES:
                continue

            if status == Status.APPROVED.value or (not status and AUTO_APPROVE):
                _handle_new_row(
                    sheets, row, row_num, api_base_url, api_key,
                    sender_email, gmail_credentials_path,
                )
            elif status in (Status.QUEUED.value, Status.RUNNING.value):
                _handle_inflight_row(
                    sheets, row, row_num, api_base_url, api_key,
                    sender_email, gmail_credentials_path,
                )
        except Exception:
            logger.exception("Failed to process row %d", row_num)


def _handle_new_row(
    sheets: SheetsClient,
    row: list[str],
    row_num: int,
    api_base_url: str,
    api_key: str,
    sender_email: str,
    gmail_credentials_path: str,
) -> None:
    agent = row[Column.AGENT].strip()
    dataset = row[Column.DATASET].strip()
    model_name = row[Column.MODEL_NAME].strip()
    server_url = row[Column.SERVER_URL].strip()
    email = row[Column.EMAIL].strip()

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
        result = _submit_job(api_base_url, api_key, agent, dataset, model_name, server_url, job_name)
    except Exception as e:
        logger.exception("Failed to submit job for row %d", row_num)
        sheets.update_cell(row_num, Column.STATUS, Status.NEEDS_REVIEW.value)
        sheets.update_cell(row_num, Column.ERROR, f"API error: {e}")
        return

    job_id = result["job_id"]
    sheets.update_cell(row_num, Column.JOB_ID, job_id)
    sheets.update_cell(row_num, Column.STATUS, Status.QUEUED.value)

    try:
        send_queued_email(email, agent, dataset, model_name, job_id, sender_email, gmail_credentials_path)
        sheets.update_cell(row_num, Column.NOTIFIED_QUEUED, "TRUE")
    except Exception:
        logger.exception("Failed to send queued email for row %d", row_num)


def _handle_inflight_row(
    sheets: SheetsClient,
    row: list[str],
    row_num: int,
    api_base_url: str,
    api_key: str,
    sender_email: str,
    gmail_credentials_path: str,
) -> None:
    job_id = row[Column.JOB_ID].strip()
    email = row[Column.EMAIL].strip()
    current_status = row[Column.STATUS].strip()
    notified_done = row[Column.NOTIFIED_DONE].strip().upper() == "TRUE"

    if not job_id:
        return

    try:
        job_data = _check_job_status(api_base_url, api_key, job_id)
    except Exception:
        logger.exception("Failed to check job status for row %d", row_num)
        return

    api_status = job_data["status"]

    if api_status == "completed" and current_status != Status.COMPLETED.value:
        sheets.update_cell(row_num, Column.STATUS, Status.COMPLETED.value)
        if not notified_done:
            try:
                send_completed_email(email, job_id, sender_email, gmail_credentials_path)
                sheets.update_cell(row_num, Column.NOTIFIED_DONE, "TRUE")
            except Exception:
                logger.exception("Failed to send completed email for row %d", row_num)

    elif api_status == "failed" and current_status != Status.FAILED.value:
        error = job_data.get("error", "Unknown error")
        sheets.update_cell(row_num, Column.STATUS, Status.FAILED.value)
        sheets.update_cell(row_num, Column.ERROR, error)
        if not notified_done:
            try:
                send_failed_email(email, job_id, error, sender_email, gmail_credentials_path)
                sheets.update_cell(row_num, Column.NOTIFIED_DONE, "TRUE")
            except Exception:
                logger.exception("Failed to send failed email for row %d", row_num)

    elif api_status == "running" and current_status != Status.RUNNING.value:
        sheets.update_cell(row_num, Column.STATUS, Status.RUNNING.value)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    credentials_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    api_base_url = os.environ.get("JOB_QUEUE_URL", "http://job-queue-service")
    api_key = os.environ["API_KEY"]
    sender_email = os.environ["SENDER_EMAIL"]

    client = SheetsClient(credentials_path, sheet_id)
    process_rows(client, api_base_url, api_key, sender_email, credentials_path)
    logger.info("Poller run complete")
