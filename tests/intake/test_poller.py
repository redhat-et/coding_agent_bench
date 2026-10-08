from unittest.mock import MagicMock, patch

from coding_agent_bench.intake.config import Column, Status
from coding_agent_bench.intake.poller import (
    _queue_verify,
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


@patch("coding_agent_bench.intake.poller.httpx")
def test_approved_row_is_submitted(mock_httpx):
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
    )

    mock_httpx.post.assert_not_called()
    sheets.update_cell.assert_not_called()


@patch("coding_agent_bench.intake.poller.AUTO_APPROVE", True)
@patch("coding_agent_bench.intake.poller.httpx")
def test_empty_status_row_submitted_when_auto_approve(mock_httpx):
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
    )

    mock_httpx.post.assert_called_once()
    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.QUEUED.value)
    sheets.update_cell.assert_any_call(1, Column.JOB_ID, "uuid-456")


@patch("coding_agent_bench.intake.poller.httpx")
def test_stage_submission_does_not_reconcile_rows(mock_httpx, monkeypatch):
    """Submit stage test rows without syncing terminal state into the sheet."""
    monkeypatch.setenv("ENVIRONMENT", "stage")
    mock_response = MagicMock()
    mock_response.json.return_value = {"job_id": "uuid-stage"}
    mock_httpx.post.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [_make_row(STATUS=Status.APPROVED.value)]

    process_rows(sheets, "http://job-queue-service", "test-key")

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.QUEUED.value)
    sheets.update_cell.assert_any_call(1, Column.JOB_ID, "uuid-stage")
    assert all(
        call.args != (1, Column.NOTIFIED_QUEUED, "TRUE")
        for call in sheets.update_cell.call_args_list
    )


@patch("coding_agent_bench.intake.poller.httpx")
def test_stage_does_not_reconcile_inflight_rows(mock_httpx, monkeypatch):
    """Leave stage jobs non-terminal and untouched by status syncing."""
    monkeypatch.setenv("ENVIRONMENT", "stage")
    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.QUEUED.value, JOB_ID="uuid-stage")
    ]

    process_rows(sheets, "http://job-queue-service", "test-key")

    mock_httpx.get.assert_not_called()
    sheets.update_cell.assert_not_called()


@patch("coding_agent_bench.intake.poller.httpx")
def test_invalid_approved_row_marked_needs_review(mock_httpx):
    """Mark invalid approved rows for manual review without calling the API."""
    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.APPROVED.value, AGENT="bad-agent"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
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
    )

    mock_httpx.post.assert_not_called()
    sheets.update_cell.assert_called_once_with(1, Column.STATUS, Status.QUEUED.value)


@patch("coding_agent_bench.intake.poller.httpx")
def test_queued_row_updated_to_completed(mock_httpx):
    """Move a queued row to completed once the queue reports it finished."""
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
    )

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.COMPLETED.value)


@patch("coding_agent_bench.intake.poller.httpx")
def test_running_row_updated_to_failed(mock_httpx):
    """Move a running row to failed and record the queue's error message."""
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
    )

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.FAILED.value)
    sheets.update_cell.assert_any_call(1, Column.ERROR, "Pod crashed")


@patch("coding_agent_bench.intake.poller.httpx")
def test_running_row_updated_to_failed_with_unknown_error_fallback(mock_httpx):
    """Record a placeholder error when a failed response carries no error."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "failed", "error": None}
    mock_httpx.get.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.RUNNING.value, JOB_ID="uuid-123"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
    )

    sheets.update_cell.assert_any_call(1, Column.ERROR, "Unknown error")


@patch("coding_agent_bench.intake.poller.httpx")
def test_failed_row_preserves_existing_sheet_error(mock_httpx):
    """Keep an error already recorded in the sheet over an empty API error."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "failed", "error": None}
    mock_httpx.get.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.RUNNING.value, JOB_ID="uuid-123", ERROR="Pod crashed"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
    )

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.FAILED.value)
    assert all(
        call.args != (1, Column.ERROR, "Unknown error")
        for call in sheets.update_cell.call_args_list
    )


@patch("coding_agent_bench.intake.poller.httpx")
def test_running_row_updated_to_paused_on_preemption(mock_httpx):
    """Show a Nebius-preempted job as paused, not terminal, in the sheet."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "paused",
        "error": "Nebius instance preempted",
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
    )

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.PAUSED.value)
    sheets.update_cell.assert_any_call(1, Column.ERROR, "Nebius instance preempted")
    assert all(
        call.args != (1, Column.NOTIFIED_DONE, "TRUE")
        for call in sheets.update_cell.call_args_list
    )


@patch("coding_agent_bench.intake.poller.httpx")
def test_paused_row_resumes_to_running(mock_httpx):
    """Clear the paused sheet status once the queue resumes the job."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "running", "error": None}
    mock_httpx.get.return_value = mock_response

    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(STATUS=Status.PAUSED.value, JOB_ID="uuid-123"),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
    )

    mock_httpx.get.assert_called_once()
    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.RUNNING.value)


@patch("coding_agent_bench.intake.poller.httpx")
def test_running_row_updated_to_cancelled(mock_httpx):
    """Reflect a user-initiated cancellation in the sheet."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "cancelled",
        "error": "Cancelled by user",
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
    )

    sheets.update_cell.assert_any_call(1, Column.STATUS, Status.CANCELLED.value)
    sheets.update_cell.assert_any_call(1, Column.ERROR, "Cancelled by user")


@patch("coding_agent_bench.intake.poller.httpx")
def test_already_completed_row_is_skipped(mock_httpx):
    """Skip a terminal row once its status has been reconciled into the sheet."""
    sheets = MagicMock()
    sheets.get_all_rows.return_value = [
        _make_row(
            STATUS=Status.COMPLETED.value, JOB_ID="uuid-123", NOTIFIED_DONE="TRUE"
        ),
    ]

    process_rows(
        sheets=sheets,
        api_base_url="http://job-queue-service",
        api_key="test-key",
    )

    mock_httpx.post.assert_not_called()
    mock_httpx.get.assert_not_called()
    sheets.update_cell.assert_not_called()


@patch("coding_agent_bench.intake.poller.httpx")
def test_completed_row_with_pending_status_is_reconciled(mock_httpx):
    """Re-check a completed row whose terminal status was never reconciled."""
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
    )

    mock_httpx.get.assert_called_once()
    sheets.update_cell.assert_called_once_with(1, Column.NOTIFIED_DONE, "TRUE")


@patch("coding_agent_bench.intake.poller.httpx")
def test_failed_row_with_pending_status_is_reconciled(mock_httpx):
    """Re-check a failed row whose terminal status was never reconciled."""
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
    )

    mock_httpx.get.assert_called_once()
    sheets.update_cell.assert_called_once_with(1, Column.NOTIFIED_DONE, "TRUE")


def test_queue_verify_defaults_to_public_trust_store(monkeypatch):
    """Fall back to the default trust store when no CA bundle is configured."""
    monkeypatch.delenv("JOB_QUEUE_CA_BUNDLE", raising=False)
    assert _queue_verify() is True


def test_queue_verify_uses_configured_ca_bundle(monkeypatch):
    """Use the configured CA bundle path when set (e.g. the service-serving CA)."""
    monkeypatch.setenv("JOB_QUEUE_CA_BUNDLE", "/etc/ssl/service-ca/service-ca.crt")
    assert _queue_verify() == "/etc/ssl/service-ca/service-ca.crt"


def test_approved_row_submit_verifies_queue_tls(monkeypatch):
    """Pass the configured CA bundle to the queue POST so TLS stays verified."""
    monkeypatch.setenv("JOB_QUEUE_CA_BUNDLE", "/etc/ssl/service-ca/service-ca.crt")

    with patch("coding_agent_bench.intake.poller.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.json.return_value = {"job_id": "uuid-tls"}
        mock_httpx.post.return_value = mock_response

        sheets = MagicMock()
        sheets.get_all_rows.return_value = [_make_row(STATUS=Status.APPROVED.value)]

        process_rows(
            sheets=sheets,
            api_base_url="https://job-queue-service.coding-agent-leaderboard.svc",
            api_key="test-key",
        )

        assert mock_httpx.post.call_args.kwargs["verify"] == (
            "/etc/ssl/service-ca/service-ca.crt"
        )


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
