from coding_agent_bench.intake.config import (
    ALLOWED_AGENTS,
    ALLOWED_DATASETS,
    AUTO_APPROVE,
    Column,
    Status,
    generate_job_name,
)


def test_allowed_agents_contains_known_agents():
    """Expose every supported agent in intake validation."""
    assert "claude-code" in ALLOWED_AGENTS
    assert "codex" in ALLOWED_AGENTS
    assert "pi" in ALLOWED_AGENTS
    assert "oracle" in ALLOWED_AGENTS
    assert "openclaw" in ALLOWED_AGENTS
    assert "opencode" in ALLOWED_AGENTS


def test_allowed_agents_matches_supported_agent_enum():
    """Keep intake agent choices synchronized with the builder enum."""
    from coding_agent_bench.builder import SupportedAgent

    enum_values = {a.value for a in SupportedAgent}
    assert ALLOWED_AGENTS == enum_values


def test_allowed_datasets_is_nonempty_set():
    """Ensure the intake dataset allowlist is populated."""
    assert isinstance(ALLOWED_DATASETS, set)
    assert len(ALLOWED_DATASETS) > 0


def test_column_enum_has_all_columns():
    """Keep the worksheet column schema complete."""
    expected = [
        "TIMESTAMP", "AGENT", "DATASET", "MODEL_NAME", "SERVER_URL",
        "EMAIL", "STATUS", "JOB_ID", "ERROR", "NOTIFIED_QUEUED", "NOTIFIED_DONE",
    ]
    for col in expected:
        assert hasattr(Column, col)


def test_auto_approve_defaults_to_false():
    """Require explicit opt-in before submitting blank-status rows."""
    assert AUTO_APPROVE is False


def test_status_enum_values():
    """Expose the spreadsheet status values used by the poller."""
    assert Status.APPROVED.value == "Approved"
    assert Status.QUEUED.value == "Queued"
    assert Status.RUNNING.value == "Running"
    assert Status.COMPLETED.value == "Completed"
    assert Status.FAILED.value == "Failed"
    assert Status.NEEDS_REVIEW.value == "Needs Review"


def test_generate_job_name_simple():
    """Include the model's short name in generated job names."""
    result = generate_job_name("codex", "swe-bench/swe-bench-verified", "Qwen/Qwen3-32B")
    assert result == "codex_swe-bench/swe-bench-verified_Qwen3-32B"


def test_generate_job_name_no_org_prefix():
    """Handle model names that do not contain an organization prefix."""
    result = generate_job_name("pi", "swe-bench/swe-bench-verified", "Qwen3-32B")
    assert result == "pi_swe-bench/swe-bench-verified_Qwen3-32B"
