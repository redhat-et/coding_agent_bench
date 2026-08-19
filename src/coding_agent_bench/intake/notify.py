import base64
from email.mime.text import MIMEText
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _build_gmail_service(credentials_path: str, sender: str) -> Any:
    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=GMAIL_SCOPES,
        subject=sender,
    )
    return build("gmail", "v1", credentials=creds)


def _send_email(service, sender: str, to: str, subject: str, body_text: str) -> None:
    message = MIMEText(body_text)
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def send_queued_email(
    to: str,
    agent: str,
    dataset: str,
    model_name: str,
    job_id: str,
    sender: str,
    gmail_credentials_path: str,
) -> None:
    service = _build_gmail_service(gmail_credentials_path, sender)
    subject = f"Benchmark request submitted: {agent} / {dataset}"
    body = (
        f"Your benchmark request has been submitted.\n\n"
        f"Agent: {agent}\n"
        f"Dataset: {dataset}\n"
        f"Model: {model_name}\n"
        f"Job ID: {job_id}\n"
    )
    _send_email(service, sender, to, subject, body)


def send_completed_email(
    to: str,
    job_id: str,
    sender: str,
    gmail_credentials_path: str,
) -> None:
    service = _build_gmail_service(gmail_credentials_path, sender)
    subject = f"Benchmark job completed: {job_id}"
    body = f"Your benchmark job {job_id} has completed.\n"
    _send_email(service, sender, to, subject, body)


def send_failed_email(
    to: str,
    job_id: str,
    error: str,
    sender: str,
    gmail_credentials_path: str,
) -> None:
    service = _build_gmail_service(gmail_credentials_path, sender)
    subject = f"Benchmark job failed: {job_id}"
    body = f"Your benchmark job {job_id} has failed.\n\nError: {error}\n"
    _send_email(service, sender, to, subject, body)
