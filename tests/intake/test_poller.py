from unittest.mock import MagicMock, patch

from coding_agent_bench.intake.config import Column, Status
from coding_agent_bench.intake.poller import (
    _row_idempotency_key,
    _validate_queue_url,
    process_rows,
)


def _make_row(**overrides) -> list[str]:
    """Build a representative Queue row with optional column overrides."""
    row = [""] * len(Column)
    row[Column.TIMESTAMP] = "2026-08-17 10:00:00"
    row[Column.AGENT] = "codex"
    row[Column.DATASET] = "swe-bench/swe-bench-verified"
    row[Column.MODEL_NAME] = "Qwen/Qwen3-32B"
    row[Column.SERVER_URL] = "https://vllm.example.com"
    row[Column.EMAIL] = "user@example.com"
    for col_name, value in overrides.items():
        row[Column[col_name]] = value
    return row


@patch("coding_agent_bench.intake.poller.send_queued_email")
@patch("coding_agent_bench.intake.poller.httpx")
def test_approved_row_is_submitted(mock_httpx, mock_email):
    """Submit an approved row and persist the returned queue job ID."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "job_id": "uuid-123",
        "job_name": "codex_swe-bench/swe-bench-verified_Qwen3-32B",
        "message": "Job created.",
        "command": ["coding-agent-bench", "run"],
    }
    mock_httpx.post.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [_make_row(STATUS=Status.APPROVED.value)]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    mock_httpx.post.assert_called_once()
    post_call = mock_httpx.post.call_args
    assert "/jobs" in post_call[0][0]
    assert post_call.kwargs["json"]["idempotency_key"] == _row_idempotency_key(
        sheets.get_all_rows.return_value[0]
    )
    assert "n_concurrent" not in post_call.kwargs["json"]
    assert "model_max_len" not in post_call.kwargs["json"]

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.QUEUED.value)
    sheets.update_cell.assert_any_call(1, Column.JOB_ID, "uuid-123")


@patch("coding_agent_bench.intake.poller.httpx")
def test_empty_status_row_skipped_in_manual_mode(mock_httpx):
    """Leave blank-status rows untouched when manual approval is enabled."""
    sheets = MagicMock()
    sheets.get_all_rows.return_value = [_make_row()]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    mock_httpx.post.assert_not_called()
    sheets.update_cell.assert_not_called()


@patch("coding_agent_bench.intake.poller.AUTO_APPROVE", True)
@patch("coding_agent_bench.intake.poller.send_queued_email")
@patch("coding_agent_bench.intake.poller.httpx")
def test_empty_status_row_submitted_when_auto_approve(mock_httpx, mock_email):
    """Submit blank-status rows when auto-approval is enabled."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "job_id": "uuid-456",
        "job_name": "codex_swe-bench/swe-bench-verified_Qwen3-32B",
        "message": "Job created.",
        "command": ["coding-agent-bench", "run"],
    }
    mock_httpx.post.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [_make_row()]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    mock_httpx.post.assert_called_once()
    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.QUEUED.value)
    sheets.update_cell.assert_any_call(1, Column.JOB_ID, "uuid-456")


@patch("coding_agent_bench.intake.poller.send_queued_email")
@patch("coding_agent_bench.intake.poller.httpx")
def test_invalid_approved_row_marked_needs_review(mock_httpx, mock_email):
    """Mark invalid approved rows for manual review without calling the API."""
    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.APPROVED.value, AGENT="bad-agent"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    mock_httpx.post.assert_not_called()
    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.NEEDS_REVIEW.value)


@patch("coding_agent_bench.intake.poller.httpx")
def test_approved_row_with_existing_job_id_skips_resubmission(mock_httpx):
    """Avoid resubmitting a row that already has a queue job ID."""
    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.APPROVED.value, JOB_ID="uuid-existing"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    mock_httpx.post.assert_not_called()
    sheets.update_cell.assert_called_once_with(1, Column.STATUS, Status.QUEUED.value)


@patch("coding_agent_bench.intake.poller.send_completed_email")
@patch("coding_agent_bench.intake.poller.httpx")
def test_queued_row_updated_to_completed(mock_httpx, mock_email):
    """Move a queued row to completed and send its completion notification."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "job_id": "uuid-123",
        "job_name": "test",
        "agent": "codex",
        "dataset": "swe-bench/swe-bench-verified",
        "model_name": "Qwen/Qwen3-32B",
        "command": "[]",
        "status": "completed",
        "error": None,
    }
    mock_httpx.get.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.QUEUED.value, JOB_ID="uuid-123"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.COMPLETED.value)


@patch("coding_agent_bench.intake.poller.send_failed_email")
@patch("coding_agent_bench.intake.poller.httpx")
def test_running_row_updated_to_failed(mock_httpx, mock_email):
    """Move a running row to failed and send its failure notification."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "job_id": "uuid-123",
        "job_name": "test",
        "agent": "codex",
        "dataset": "swe-bench/swe-bench-verified",
        "model_name": "Qwen/Qwen3-32B",
        "command": "[]",
        "status": "failed",
        "error": "Pod crashed",
    }
    mock_httpx.get.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.RUNNING.value, JOB_ID="uuid-123"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.FAILED.value)


@patch("coding_agent_bench.intake.poller.httpx")
def test_already_completed_row_is_skipped(mock_httpx):
    """Skip a completed row after its terminal notification was recorded."""
    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.COMPLETED.value, JOB_ID="uuid-123", NOTIFIED_DONE="TRUE"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    mock_httpx.post.assert_not_called()
    mock_httpx.get.assert_not_called()
    sheets.update_cell.assert_not_called()


@patch("coding_agent_bench.intake.poller.send_completed_email")
@patch("coding_agent_bench.intake.poller.httpx")
def test_completed_row_with_pending_notification_is_retried(mock_httpx, mock_email):
    """Retry a completion email when the terminal status was saved first."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "completed"}
    mock_httpx.get.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.COMPLETED.value, JOB_ID="uuid-123"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    mock_httpx.get.assert_called_once()
    mock_email.assert_called_once()
    sheets.update_cell.assert_called_once_with(1, Column.NOTIFIED_DONE, "TRUE")


@patch("coding_agent_bench.intake.poller.send_failed_email")
@patch("coding_agent_bench.intake.poller.httpx")
def test_failed_row_with_pending_notification_is_retried(mock_httpx, mock_email):
    """Retry a failure email when the terminal status was saved first."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "failed", "error": "Pod crashed"}
    mock_httpx.get.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(
            STATUS=Status.FAILED.value,
            JOB_ID="uuid-123",
            ERROR="Pod crashed",
        ),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
        sender_email="bench@example.com",
    )

    mock_httpx.get.assert_called_once()
    mock_email.assert_called_once()
    sheets.update_cell.assert_called_once_with(1, Column.NOTIFIED_DONE, "TRUE")


def test_queue_url_requires_https(monkeypatch):
    """Reject plaintext queue URLs unless local development opts in explicitly."""
    monkeypatch.delenv("ALLOW_INSECURE_QUEUE_HTTP", raising=False)

    try:
        _validate_queue_url("http://job-queue-service")
    except ValueError as exc:
        assert "https" in str(exc)
    else:
        raise AssertionError("plaintext queue URL should be rejected")


def test_queue_url_allows_explicit_local_http(monkeypatch):
    """Allow a local HTTP queue only with the documented explicit override."""
    monkeypatch.setenv("ALLOW_INSECURE_QUEUE_HTTP", "true")
    _validate_queue_url("http://localhost:8000")
