import os
import smtplib
from email.message import EmailMessage

SMTP_DEFAULT_HOST = "smtp.corp.redhat.com"
SMTP_DEFAULT_PORT = 25
SMTP_TIMEOUT_SECONDS = 30


def _smtp_settings() -> tuple[str, int, bool]:
    """Read SMTP connection settings from the environment.

    The default relay is reachable from the internal network and does not
    require mailbox credentials. STARTTLS remains opt-in for environments
    where the relay requires it.
    """
    host = os.environ.get("SMTP_HOST", SMTP_DEFAULT_HOST)
    try:
        port = int(os.environ.get("SMTP_PORT", str(SMTP_DEFAULT_PORT)))
    except ValueError as exc:
        raise ValueError("SMTP_PORT must be an integer") from exc
    starttls = os.environ.get("SMTP_STARTTLS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return host, port, starttls


def _send_email(sender: str, to: str, subject: str, body_text: str) -> None:
    """Send a plain-text message through the internal SMTP relay."""
    message = EmailMessage()
    message["To"] = to
    message["From"] = sender
    message["Subject"] = subject
    message.set_content(body_text)

    smtp_host, smtp_port, starttls = _smtp_settings()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as server:
        if starttls:
            server.starttls()
        server.send_message(message)


def send_queued_email(
    to: str,
    agent: str,
    dataset: str,
    model_name: str,
    job_id: str,
    sender: str,
) -> None:
    """Notify a requester that their benchmark has entered the queue."""
    subject = f"Benchmark request queued: {agent} / {dataset}"
    body = (
        f"Your benchmark request has been queued.\n\n"
        f"Agent: {agent}\n"
        f"Dataset: {dataset}\n"
        f"Model: {model_name}\n"
        f"Job ID: {job_id}\n"
    )
    _send_email(sender, to, subject, body)


def send_completed_email(
    to: str,
    job_id: str,
    sender: str,
) -> None:
    """Notify a requester that their benchmark completed and link to results."""
    subject = f"Benchmark job completed: {job_id}"
    body = (
        f"Your benchmark job {job_id} has completed.\n\n"
        f"You can view the results on the Coding Agent Leaderboard:\n"
        f"https://huggingface.co/spaces/taagarwa/coding-agent-leaderboard\n"
    )
    _send_email(sender, to, subject, body)


def send_failed_email(
    to: str,
    job_id: str,
    error: str,
    sender: str,
) -> None:
    """Notify a requester that their benchmark failed and explain how to get help."""
    subject = f"Benchmark job failed: {job_id}"
    body = (
        f"Your benchmark job {job_id} has failed.\n\n"
        f"Error: {error}\n\n"
        f"Reply to this email and the team will look into it or help you resubmit.\n"
    )
    _send_email(sender, to, subject, body)
