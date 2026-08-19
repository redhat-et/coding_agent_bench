from coding_agent_bench.intake.config import (
    ALLOWED_AGENTS,
    ALLOWED_DATASETS,
    AUTO_APPROVE,
    DEFAULT_N_CONCURRENT,
    DEFAULT_MODEL_MAX_LEN,
    Column,
    Status,
    generate_job_name,
)


def test_allowed_agents_contains_known_agents():
    assert "claude-code" in ALLOWED_AGENTS
    assert "codex" in ALLOWED_AGENTS
    assert "pi" in ALLOWED_AGENTS
    assert "oracle" in ALLOWED_AGENTS
    assert "openclaw" in ALLOWED_AGENTS
    assert "opencode" in ALLOWED_AGENTS


def test_allowed_agents_matches_supported_agent_enum():
    from coding_agent_bench.builder import SupportedAgent

    enum_values = {a.value for a in SupportedAgent}
    assert ALLOWED_AGENTS == enum_values


def test_allowed_datasets_is_nonempty_set():
    assert isinstance(ALLOWED_DATASETS, set)
    assert len(ALLOWED_DATASETS) > 0


def test_defaults():
    assert DEFAULT_N_CONCURRENT == 1
    assert DEFAULT_MODEL_MAX_LEN == 262000


def test_column_enum_has_all_columns():
    expected = [
        "TIMESTAMP", "AGENT", "DATASET", "MODEL_NAME", "SERVER_URL",
        "EMAIL", "STATUS", "JOB_ID", "ERROR", "NOTIFIED_QUEUED", "NOTIFIED_DONE",
    ]
    for col in expected:
        assert hasattr(Column, col)


def test_auto_approve_defaults_to_false():
    assert AUTO_APPROVE is False


def test_status_enum_values():
    assert Status.APPROVED.value == "Approved"
    assert Status.QUEUED.value == "Queued"
    assert Status.RUNNING.value == "Running"
    assert Status.COMPLETED.value == "Completed"
    assert Status.FAILED.value == "Failed"
    assert Status.NEEDS_REVIEW.value == "Needs Review"


def test_generate_job_name_simple():
    result = generate_job_name("codex", "swe-bench/swe-bench-verified", "Qwen/Qwen3-32B")
    assert result == "codex_swe-bench/swe-bench-verified_Qwen3-32B"


def test_generate_job_name_no_org_prefix():
    result = generate_job_name("pi", "swe-bench/swe-bench-verified", "Qwen3-32B")
    assert result == "pi_swe-bench/swe-bench-verified_Qwen3-32B"
