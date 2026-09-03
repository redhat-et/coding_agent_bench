import asyncio
import json

from coding_agent_bench.job import OpenshiftJob


def test_legacy_cleanup_only_deletes_pods_owned_by_job(monkeypatch):
    job = OpenshiftJob("job-1", clean_legacy_pods=True)
    pods = {
        "items": [
            {
                "metadata": {"name": "current-match"},
                "spec": {
                    "containers": [
                        {"env": [{"name": "HARBOR_PARENT", "value": job._pod_name}]}
                    ]
                },
            },
            {
                "metadata": {
                    "name": "legacy-match",
                    "labels": {"harbor-parent": job._pod_name},
                },
                "spec": {"containers": [{"env": []}]},
            },
            {
                "metadata": {"name": "other-job"},
                "spec": {"containers": [{"env": []}]},
            },
        ]
    }
    commands = []

    async def run_oc(command, **_kwargs):
        commands.append(command)
        if command[0] == "get":
            return json.dumps(pods), None
        return None, None

    monkeypatch.setattr(job, "_run_oc_command", run_oc)

    asyncio.run(job._delete_harbor_pods())

    assert commands[1] == [
        "delete",
        "pods",
        "current-match",
        "legacy-match",
        "--ignore-not-found",
    ]
