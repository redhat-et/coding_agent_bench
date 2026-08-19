from coding_agent_bench.intake.validation import validate_row


def test_valid_row_returns_no_errors():
    errors = validate_row(
        agent="codex",
        dataset="swe-bench/swe-bench-verified",
        server_url="https://vllm.example.com",
    )
    assert errors == []


def test_unknown_agent():
    errors = validate_row(
        agent="not-a-real-agent",
        dataset="swe-bench/swe-bench-verified",
        server_url="https://vllm.example.com",
    )
    assert len(errors) == 1
    assert "agent" in errors[0].lower()


def test_unknown_dataset():
    errors = validate_row(
        agent="codex",
        dataset="fake-dataset-999",
        server_url="https://vllm.example.com",
    )
    assert len(errors) == 1
    assert "dataset" in errors[0].lower()


def test_invalid_url_no_scheme():
    errors = validate_row(
        agent="codex",
        dataset="swe-bench/swe-bench-verified",
        server_url="vllm.example.com",
    )
    assert len(errors) == 1
    assert "url" in errors[0].lower()


def test_invalid_url_http_not_https():
    errors = validate_row(
        agent="codex",
        dataset="swe-bench/swe-bench-verified",
        server_url="http://vllm.example.com",
    )
    assert len(errors) == 1
    assert "https" in errors[0].lower()


def test_empty_url():
    errors = validate_row(
        agent="codex",
        dataset="swe-bench/swe-bench-verified",
        server_url="",
    )
    assert len(errors) >= 1


def test_openrouter_url_accepted():
    errors = validate_row(
        agent="codex",
        dataset="swe-bench/swe-bench-verified",
        server_url="openrouter",
    )
    assert errors == []


def test_multiple_errors():
    errors = validate_row(
        agent="bad-agent",
        dataset="bad-dataset",
        server_url="not-a-url",
    )
    assert len(errors) == 3
