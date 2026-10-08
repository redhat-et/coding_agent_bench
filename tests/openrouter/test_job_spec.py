from coding_agent_bench.job import OpenshiftJob


def _env_by_name(spec):
    container = spec["spec"]["template"]["spec"]["containers"][0]
    return {e["name"]: e for e in container.get("env", [])}


def test_job_spec_injects_openrouter_secret_only_when_openrouter():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(job._job_spec(["echo", "hi"], openrouter=True))
    assert "OPENROUTER_API_KEY" in env
    ref = env["OPENROUTER_API_KEY"]["valueFrom"]["secretKeyRef"]
    assert ref["name"] == "job-queue-secret"
    assert ref["key"] == "OPENROUTER_API_KEY"
    assert ref["optional"] is True


def test_job_spec_omits_openrouter_secret_for_non_openrouter():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(job._job_spec(["echo", "hi"]))  # openrouter defaults to False
    assert "OPENROUTER_API_KEY" not in env


def test_resume_job_spec_never_injects_openrouter_secret():
    # Resuming an OpenRouter job is rejected at the API (400), so resume pods
    # never need the key.
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(job._resume_job_spec("echo hi"))
    assert "OPENROUTER_API_KEY" not in env


def test_storage_endpoint_is_passed_to_both_job_types(monkeypatch):
    monkeypatch.setenv("STORAGE_ENDPOINT_URL", "https://storage.example.test:9443")
    job = OpenshiftJob(job_name="test")

    regular_env = _env_by_name(job._job_spec(["echo", "hi"]))
    resume_env = _env_by_name(job._resume_job_spec("echo hi"))

    assert regular_env["STORAGE_ENDPOINT_URL"]["value"] == "https://storage.example.test:9443"
    assert resume_env["STORAGE_ENDPOINT_URL"]["value"] == "https://storage.example.test:9443"
