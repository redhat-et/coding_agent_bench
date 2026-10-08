import pytest

from coding_agent_bench.utils import is_stage_environment

def test_environment_must_be_explicitly_supported(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(ValueError, match="ENVIRONMENT"):
        is_stage_environment()

    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(ValueError, match="ENVIRONMENT"):
        is_stage_environment()
