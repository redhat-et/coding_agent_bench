from coding_agent_bench.job import OpenshiftJob


def _env_by_name(spec):
    container = spec["spec"]["template"]["spec"]["containers"][0]
    return {e["name"]: e for e in container.get("env", [])}


def test_job_spec_injects_generic_model_secret():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(job._job_spec(["echo", "hi"], model_api_key_secret="cab-model-key-test"))
    assert "CAB_MODEL_API_KEY" in env
    ref = env["CAB_MODEL_API_KEY"]["valueFrom"]["secretKeyRef"]
    assert ref["name"] == "cab-model-key-test"
    assert ref["key"] == "key"


def test_job_spec_omits_model_secret_without_key():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(job._job_spec(["echo", "hi"]))  # openrouter defaults to False
    assert "CAB_MODEL_API_KEY" not in env


def test_resume_job_spec_injects_model_secret_when_requested():
    job = OpenshiftJob(job_name="test")
    env = _env_by_name(job._resume_job_spec("echo hi", "cab-model-key-test"))
    assert env["CAB_MODEL_API_KEY"]["valueFrom"]["secretKeyRef"]["key"] == "key"


def test_storage_endpoint_is_passed_to_both_job_types(monkeypatch):
    monkeypatch.setenv("STORAGE_ENDPOINT_URL", "https://storage.example.test:9443")
    job = OpenshiftJob(job_name="test")

    regular_env = _env_by_name(job._job_spec(["echo", "hi"]))
    resume_env = _env_by_name(job._resume_job_spec("echo hi"))

    assert regular_env["STORAGE_ENDPOINT_URL"]["value"] == "https://storage.example.test:9443"
    assert resume_env["STORAGE_ENDPOINT_URL"]["value"] == "https://storage.example.test:9443"
