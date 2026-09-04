from unittest.mock import MagicMock, patch

from coding_agent_bench.intake.notify import (
    SMTP_DEFAULT_HOST,
    SMTP_DEFAULT_PORT,
    SMTP_TIMEOUT_SECONDS,
    send_queued_email,
    send_completed_email,
    send_failed_email,
)


def _get_smtp_server(mock_smtp: MagicMock) -> MagicMock:
    """Return the mocked SMTP server used inside the context manager."""
    return mock_smtp.return_value.__enter__.return_value


def _assert_default_smtp_connection(mock_smtp: MagicMock) -> MagicMock:
    mock_smtp.assert_called_once_with(
        SMTP_DEFAULT_HOST,
        SMTP_DEFAULT_PORT,
        timeout=SMTP_TIMEOUT_SECONDS,
    )
    server = _get_smtp_server(mock_smtp)
    server.send_message.assert_called_once()
    return server


@patch("coding_agent_bench.intake.notify.smtplib.SMTP")
def test_send_queued_email_contains_job_details(mock_smtp):
    """Include request details in the queued notification."""
    send_queued_email(
        to="user@example.com",
        agent="codex",
        dataset="swe-bench/swe-bench-verified",
        model_name="Qwen/Qwen3-32B",
        job_id="abc-123",
        sender="bench@example.com",
    )

    server = _assert_default_smtp_connection(mock_smtp)
    message = server.send_message.call_args.args[0]
    body = message.get_content()
    assert message["To"] == "user@example.com"
    assert message["From"] == "bench@example.com"
    assert "codex" in body
    assert "swe-bench/swe-bench-verified" in body
    assert "abc-123" in body


@patch("coding_agent_bench.intake.notify.smtplib.SMTP")
def test_send_completed_email_contains_job_id(mock_smtp):
    """Include the job ID and completion state in the completion email."""
    send_completed_email(
        to="user@example.com",
        job_id="abc-123",
        sender="bench@example.com",
    )

    server = _assert_default_smtp_connection(mock_smtp)
    message = server.send_message.call_args.args[0]
    body = message.get_content()
    assert "abc-123" in body
    assert "completed" in body.lower()


@patch("coding_agent_bench.intake.notify.smtplib.SMTP")
def test_send_failed_email_contains_error(mock_smtp):
    """Include the queue error in the failure notification."""
    send_failed_email(
        to="user@example.com",
        job_id="abc-123",
        error="Pod crashed",
        sender="bench@example.com",
    )

    server = _assert_default_smtp_connection(mock_smtp)
    message = server.send_message.call_args.args[0]
    body = message.get_content()
    assert "abc-123" in body
    assert "Pod crashed" in body


@patch("coding_agent_bench.intake.notify.smtplib.SMTP")
def test_send_email_honors_smtp_environment(mock_smtp, monkeypatch):
    """Allow deployments to select a relay and opt into STARTTLS."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_STARTTLS", "true")

    send_completed_email("user@example.com", "abc-123", "bench@example.com")

    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=SMTP_TIMEOUT_SECONDS)
    server = _get_smtp_server(mock_smtp)
    server.starttls.assert_called_once_with()
    server.send_message.assert_called_once()
