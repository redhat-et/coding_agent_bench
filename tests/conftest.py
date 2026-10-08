import pytest

@pytest.fixture(autouse=True)
def production_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
