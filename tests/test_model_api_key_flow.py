import asyncio
import json

from coding_agent_bench.builder import HarborCommandBuilder


def test_model_api_key_is_passed_as_agent_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    command, _ = HarborCommandBuilder().build(
        agent="claude-code",
        dataset="example-dataset",
        model_name="example-model",
        server_url="https://model.example.com",
        environment="docker",
        api_key="model-key",
    )

    ae_values = [command[index + 1] for index, value in enumerate(command) if value == "--ae"]
    assert "CAB_MODEL_API_KEY=model-key" in ae_values


def test_cleanup_deletes_only_inactive_queue_owned_secrets(monkeypatch):
    from coding_agent_bench import api

    class Store:
        def list(self):
            return [{"job_id": "active-job", "status": api.JobStatus.RUNNING.value}]

    secrets = {
        "items": [
            {"metadata": {"name": "queue-old", "labels": {
                "coding-agent-bench-owner": "queue",
                "coding-agent-bench-job": "old-job",
            }}},
            {"metadata": {"name": "queue-active", "labels": {
                "coding-agent-bench-owner": "queue",
                "coding-agent-bench-job": "active-job",
            }}},
            {"metadata": {"name": "cli-old", "labels": {
                "coding-agent-bench-job": "old-job",
            }}},
        ]
    }
    deleted = []

    async def run_oc(command, **_kwargs):
        if command[:4] == ["get", "secrets", "-l", "coding-agent-bench-purpose=model-api-key"]:
            return json.dumps(secrets)
        deleted.append(command)
        return ""

    monkeypatch.setattr(api, "job_store", Store())
    monkeypatch.setattr(api, "_run_oc", run_oc)

    asyncio.run(api._cleanup_model_api_key_secrets())

    assert deleted == [["delete", "secret", "queue-old", "--ignore-not-found"]]
