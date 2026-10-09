"""Tests for Nebius resource/model concurrency and launch configuration."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from coding_agent_bench import api
from coding_agent_bench.nebius_utils import (
    NebiusInstanceManager,
    get_model_max_concurrency,
)


@pytest.fixture(scope="module")
def client():
    """Use one client because the API owns module-level async state."""
    with TestClient(api.app) as test_client:
        yield test_client


def test_get_model_max_concurrency_returns_configured_value():
    assert get_model_max_concurrency(
        gpu_config="b200",
        model_name="Qwen/Qwen3.8-27B",
    ) == 12


def test_get_model_max_concurrency_uses_inherited_regional_config():
    assert get_model_max_concurrency(
        gpu_config="b200a",
        model_name="Qwen/Qwen3.8-27B",
    ) == 12
    assert get_model_max_concurrency(
        gpu_config="b200x8a",
        model_name="RedHatAI/DeepSeek-V4-Flash",
    ) == 14


@pytest.mark.parametrize(
    ("gpu_config", "model_name"),
    [
        ("not-a-config", "Qwen/Qwen3.8-27B"),
        ("h200", "Qwen/Qwen3.8-27B"),
        ("b200", "not-a-model"),
    ],
)
def test_get_model_max_concurrency_rejects_unknown_or_unsupported_pairs(
    gpu_config, model_name,
):
    with pytest.raises(ValueError):
        get_model_max_concurrency(gpu_config=gpu_config, model_name=model_name)


def test_model_max_concurrency_endpoint_returns_integer(client):
    response = client.get(
        "/api/model-max-concurrency",
        params={"model_name": "Qwen/Qwen3.8-27B", "gpu_config": "b200"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "model_name": "Qwen/Qwen3.8-27B",
        "gpu_config": "b200",
        "max_concurrency": 12,
    }


@pytest.mark.parametrize(
    ("model_name", "gpu_config"),
    [
        ("not-a-model", "b200"),
        ("Qwen/Qwen3.8-27B", "not-a-config"),
        ("Qwen/Qwen3.8-27B", "h200"),
    ],
)
def test_model_max_concurrency_endpoint_returns_not_found_for_invalid_pairs(
    client, model_name, gpu_config,
):
    response = client.get(
        "/api/model-max-concurrency",
        params={"model_name": model_name, "gpu_config": gpu_config},
    )

    assert response.status_code == 404


def test_start_model_uses_resource_tensor_parallelism_and_extra_args(monkeypatch):
    manager = object.__new__(NebiusInstanceManager)
    commands = []

    async def get_instance(_instance_name):
        return {
            "spec": {
                "resources": {
                    "platform": "gpu-b200-sxm",
                    "preset": "8gpu-160vcpu-1792gb",
                },
            },
        }

    async def instance_exec(**kwargs):
        commands.append(kwargs["command"])

    monkeypatch.setattr(manager, "get_instance", get_instance)
    monkeypatch.setattr(manager, "instance_exec", instance_exec)

    asyncio.run(manager.start_model("instance", "RedHatAI/DeepSeek-V4-Flash"))

    shell_command = commands[0][2]
    assert "--tensor-parallel-size 8" in shell_command
    assert "--moe-backend deep_gemm_mega_moe" in shell_command
    assert "--attention_config.use_fp4_indexer_cache True" in shell_command
