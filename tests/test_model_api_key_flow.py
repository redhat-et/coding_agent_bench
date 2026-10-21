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
