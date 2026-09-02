from coding_agent_bench.job import JobOptions, OpenshiftJob
from coding_agent_bench.providers import ModelProvider


def _env_by_name(spec):
    container = spec["spec"]["template"]["spec"]["containers"][0]
    return {e["name"]: e for e in container.get("env", [])}


def test_job_spec_injects_openrouter_secret_only_when_openrouter():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(
        job._job_spec(
            ["echo", "hi"],
            options=JobOptions(model_provider=ModelProvider.OPENROUTER),
        )
    )
    assert "OPENROUTER_API_KEY" in env
    ref = env["OPENROUTER_API_KEY"]["valueFrom"]["secretKeyRef"]
    assert ref["name"] == "openrouter-api-key"
    assert ref["key"] == "OPENROUTER_API_KEY"
    assert ref["optional"] is True


def test_job_spec_omits_openrouter_secret_for_non_openrouter():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(job._job_spec(["echo", "hi"]))  # openrouter defaults to False
    assert "OPENROUTER_API_KEY" not in env


def test_job_spec_injects_openai_secret_only_when_enabled():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(
        job._job_spec(
            ["echo", "hi"],
            options=JobOptions(model_provider=ModelProvider.OPENAI),
        )
    )
    ref = env["OPENAI_API_KEY"]["valueFrom"]["secretKeyRef"]
    assert ref == {
        "name": "openai-api-key",
        "key": "OPENAI_API_KEY",
        "optional": True,
    }
    assert "OPENROUTER_API_KEY" not in env


def test_resume_job_spec_injects_configured_provider_secret():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(
        job._resume_job_spec(
            "echo hi",
            options=JobOptions(model_provider=ModelProvider.OPENROUTER),
        )
    )
    assert set(env) == {"HOME", "OPENROUTER_API_KEY"}
