import os
from enum import Enum

from coding_agent_bench.builder import SupportedAgent


ALLOWED_AGENTS: set[str] = {a.value for a in SupportedAgent}

ALLOWED_DATASETS: set[str] = {
    "swe-bench/swe-bench-verified",
    "scale-ai/swe-bench-pro",
}

AUTO_APPROVE: bool = os.environ.get("AUTO_APPROVE", "false").lower() == "true"

# Worksheet the poller reads. A scheduled Apps Script macro copies Form Responses
# into this tab in Column order (see scripts/manual/intake_queue_sync.gs), so the
# poller stays decoupled from the raw form's column ordering.
QUEUE_TAB: str = "Queue"


class Column(int, Enum):
    TIMESTAMP = 0
    AGENT = 1
    DATASET = 2
    MODEL_NAME = 3
    SERVER_URL = 4
    EMAIL = 5
    STATUS = 6
    JOB_ID = 7
    ERROR = 8
    NOTIFIED_QUEUED = 9
    NOTIFIED_DONE = 10


class Status(str, Enum):
    APPROVED = "Approved"
    QUEUED = "Queued"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    NEEDS_REVIEW = "Needs Review"


def generate_job_name(agent: str, dataset: str, model_name: str) -> str:
    """Build a readable, deterministic job name from the intake fields."""
    short_name = model_name.rsplit("/", 1)[-1]
    return f"{agent}_{dataset}_{short_name}"
