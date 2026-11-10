"""Regional discovery and lifecycle routing never allocate against the wrong project."""

import asyncio
from collections import defaultdict, deque
import json
from unittest.mock import AsyncMock

import pytest

from coding_agent_bench import api
from coding_agent_bench.nebius_utils import (
    NebiusCapacityError, NebiusCommandError, NebiusCommandTimeout,
    NebiusInstanceManager, RESOURCE_CONFIG_REGISTRY, RegionalNebiusOrchestrator,
)


def capacity():
    return NebiusCapacityError(["compute", "instance", "create"], 1, "", "Not enough resources")


def quota():
    return NebiusCommandError(["compute", "instance", "create"], 1, "", "Quota exceeded")


def location(project, region):
    return {"project_id": project, "project_name": f"default-{region}", "region": region,
            "subnet_id": f"subnet-{project}", "gpu_config": "h200"}


class RegionalManager(NebiusInstanceManager):
    def __init__(self):
        self._parent_id = "primary"
        self._tenant_id = "tenant"
        self.locations = [location("primary", "us-central1"), location("secondary", "eu-west1")]
        self.cloud = {}
        self.events = []
        self.failures = defaultdict(deque)

    async def discover_locations(self, gpu_config, project_prefix, regions):
        return [dict(item) for item in self.locations if not regions or item["region"] in regions]

    async def instance_exists(self, name):
        self.events.append(("exists", self._parent_id))
        return (self._parent_id, name) in self.cloud

    async def get_instance(self, name):
        self.events.append(("get", self._parent_id))
        return self.cloud[self._parent_id, name]

    async def create_instance(self, name, subnet, gpu_config):
        self.events.append(("create", self._parent_id))
        assert subnet == f"subnet-{self._parent_id}"
        failure = self.failures[self._parent_id].popleft() if self.failures[self._parent_id] else None
        if failure and not isinstance(failure, NebiusCommandTimeout):
            raise failure
        resource = RESOURCE_CONFIG_REGISTRY[gpu_config]
        self.cloud[self._parent_id, name] = {
            "spec": {"resources": {"platform": resource.platform, "preset": resource.preset}},
            "status": {"state": "STOPPED"},
        }
        if failure:
            raise failure

    async def start_instance(self, name):
        self.events.append(("start", self._parent_id))
        self.cloud[self._parent_id, name]["status"]["state"] = "RUNNING"

    async def delete_instance(self, name):
        self.events.append(("delete", self._parent_id))
        self.cloud.pop((self._parent_id, name), None)

    async def stop_model(self, name):
        pass

    async def start_model(self, name, model):
        self.events.append(("model", self._parent_id))

    async def get_instance_ip_address(self, name):
        return "203.0.113.1"


def regional(manager, **kwargs):
    return RegionalNebiusOrchestrator(manager, "subnet-primary", "queue", 600,
                                      api.NebiusOrchestrator, **kwargs)


def test_falls_back_on_capacity_and_records_placement_before_creating_vm():
    manager = RegionalManager()
    manager.failures["primary"].append(capacity())
    orchestrator = regional(manager)
    placements = []

    def save(selected):
        placements.append(selected)
        manager.events.append(("record", selected["project_id"]))
        return True

    orchestrator.bind_job(None, save)
    name, url = asyncio.run(orchestrator.acquire_instance("model", "h200"))
    assert url == "http://203.0.113.1:8000"
    assert [(event, project) for event, project in manager.events if event == "create"] == [
        ("create", "primary"), ("create", "secondary"),
    ]
    for project in ("primary", "secondary"):
        assert manager.events.index(("record", project)) < manager.events.index(("create", project))
    assert placements[-1]["region"] == "eu-west1"
    assert placements[-1]["instance_name"] == name
    assert len(manager.cloud) == 1
    state = orchestrator.get_instance_states()[0]
    assert state.region == "eu-west1"
    assert state.project_id == "secondary"


def test_all_regions_short_on_capacity_produce_one_durable_retry_round(tmp_path, monkeypatch):
    manager = RegionalManager()
    manager.failures["primary"].append(capacity())
    manager.failures["secondary"].append(capacity())
    orchestrator = regional(manager)
    store = api.JobStore(tmp_path / "queue.db")
    command = ["coding-agent-bench", "run"]
    store.insert("job", "job", "opencode", "org/bench", "model", "nebius-h200", command)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_nebius", orchestrator)
    monkeypatch.setattr(api, "_run_job", AsyncMock())
    queued = api.QueuedJob("job", command, "nebius-h200", "model")
    asyncio.run(api._process_queued_job(queued))
    row = store.get("job")
    assert row["status"] == "queued"
    assert row["nebius_retry_attempts"] == 1
    assert row["nebius_retry_at"] > 0
    assert "us-central1" in row["error"] and "eu-west1" in row["error"]
    saved = json.loads(row["nebius_location"])
    assert saved["project_id"] == "secondary"
    assert api.JobResponse(**row).nebius_location == saved
    assert manager.cloud == {}
    api._run_job.assert_not_awaited()

    # Another round is eligible after the persisted deadline, not per region.
    with store._connect() as conn:
        conn.execute("UPDATE jobs SET nebius_retry_at = 0 WHERE job_id = 'job'")
    asyncio.run(api._process_queued_job(queued))
    api._run_job.assert_awaited_once()
    assert store.get("job")["nebius_retry_at"] == 0
    assert len(manager.cloud) == 1


@pytest.mark.parametrize("all_quota", [False, True])
def test_quota_is_not_treated_as_capacity_but_another_region_can_succeed(all_quota):
    manager = RegionalManager()
    manager.failures["primary"].append(quota())
    if all_quota:
        manager.failures["secondary"].append(quota())
    orchestrator = regional(manager)
    if all_quota:
        with pytest.raises(RuntimeError, match="quota exceeded") as error:
            asyncio.run(orchestrator.acquire_instance("model", "h200"))
        assert not isinstance(error.value, NebiusCapacityError)
    else:
        name, _ = asyncio.run(orchestrator.acquire_instance("model", "h200"))
        assert ("secondary", name) in manager.cloud


def test_uncertain_create_stops_round_and_restart_reconciles_same_location():
    manager = RegionalManager()
    manager.failures["primary"].append(NebiusCommandTimeout("response lost"))
    first = regional(manager)
    saved = []
    first.bind_job(None, lambda selected: saved.append(selected))
    with pytest.raises(NebiusCommandTimeout):
        asyncio.run(first.acquire_instance("model", "h200"))
    assert saved[-1]["project_id"] == "primary"
    assert ("create", "secondary") not in manager.events
    second = regional(manager)
    second.bind_job(saved[-1], lambda _: True)
    name, _ = asyncio.run(second.acquire_instance("model", "h200"))
    assert manager.events.count(("create", "primary")) == 1
    assert ("create", "secondary") not in manager.events
    assert len(manager.cloud) == 1
    assert ("primary", name) in manager.cloud


def test_restart_routes_monitoring_pause_and_cleanup_to_saved_region(monkeypatch):
    manager = RegionalManager()
    manager.failures["primary"].append(capacity())
    saved = []
    first = regional(manager)
    first.bind_job(None, lambda selected: saved.append(selected))
    name, _ = asyncio.run(first.acquire_instance("model", "h200"))
    second = regional(manager)
    second.bind_job(saved[-1], lambda _: True)
    manager.events.clear()
    assert asyncio.run(second.adopt_running_instance("model", "h200")) == name
    assert asyncio.run(second.get_instance_state(name)) == "RUNNING"
    assert second.has_busy_instance()
    asyncio.run(second.mark_job_paused(name))
    assert not second.has_busy_instance()
    child = second._route(name)
    recovery = AsyncMock()
    monkeypatch.setattr(child, "recover_stopped_instance", recovery)
    asyncio.run(second.recover_stopped_instance(name))
    recovery.assert_awaited_once_with(name)
    asyncio.run(second.delete_recovered_instance())
    assert manager.cloud == {}
    assert all(project == "secondary" for _, project in manager.events)


def test_discovery_refreshes_each_round_and_rejects_no_eligible_regions():
    manager = RegionalManager()
    manager.locations = []
    orchestrator = regional(manager)
    with pytest.raises(RuntimeError, match="No eligible"):
        asyncio.run(orchestrator.acquire_instance("model", "h200"))
    manager.locations = [location("secondary", "eu-west1")]
    assert asyncio.run(orchestrator.acquire_instance("model", "h200"))[0]


def test_cancelled_row_prevents_regional_allocation():
    manager = RegionalManager()
    orchestrator = regional(manager)
    orchestrator.bind_job(None, lambda _: False)
    with pytest.raises(RuntimeError, match="recoverable state"):
        asyncio.run(orchestrator.acquire_instance("model", "h200"))
    assert not manager.cloud
    assert not any(event == "create" for event, _ in manager.events)


def test_active_regional_job_is_not_replaced_by_another_allocation():
    manager = RegionalManager()
    orchestrator = regional(manager)
    name, _ = asyncio.run(orchestrator.acquire_instance("model", "h200"))
    asyncio.run(orchestrator.mark_job_started(name))
    manager.events.clear()
    with pytest.raises(RuntimeError, match="Another job"):
        asyncio.run(orchestrator.acquire_instance("other-model", "h200"))
    assert manager.events == []
    assert len(manager.cloud) == 1


def test_delayed_startup_cleanup_cannot_delete_new_job_region(monkeypatch):
    cleanup = AsyncMock()
    monkeypatch.setattr(api, "_nebius", type("Pool", (), {"delete_recovered_instance": cleanup})())
    monkeypatch.setattr(api, "_active_job", ("new-job", None))
    asyncio.run(api._delete_recovered_nebius("startup"))
    cleanup.assert_not_awaited()


def test_queue_restart_reconstructs_pending_region_before_retry(tmp_path, monkeypatch):
    manager = RegionalManager()
    manager.failures["primary"].append(capacity())
    manager.failures["secondary"].append(NebiusCommandTimeout("response lost"))
    store = api.JobStore(tmp_path / "queue.db")
    command = ["coding-agent-bench", "run"]
    store.insert("job", "job", "opencode", "org/bench", "model", "nebius-h200", command)
    monkeypatch.setattr(api, "job_store", store)
    monkeypatch.setattr(api, "_nebius", regional(manager))
    monkeypatch.setattr(api, "_job_queue", [])
    monkeypatch.setattr(api, "_job_event", asyncio.Event())
    monkeypatch.setattr(api, "_run_job", AsyncMock())
    asyncio.run(api._process_queued_job(api.QueuedJob("job", command, "nebius-h200", "model")))
    assert json.loads(store.get("job")["nebius_location"])["region"] == "eu-west1"

    monkeypatch.setattr(api, "_nebius", regional(manager))
    monkeypatch.setattr(api.OpenshiftJob, "_get_job", AsyncMock(return_value=None))
    with store._connect() as conn:
        conn.execute("UPDATE jobs SET nebius_retry_at = 0 WHERE job_id = 'job'")
    asyncio.run(api._restore_jobs())
    asyncio.run(api._process_queued_job(api._job_queue[0]))
    api._run_job.assert_awaited_once()
    assert manager.events.count(("create", "secondary")) == 1
    assert manager.events.count(("create", "primary")) == 1
    assert len(manager.cloud) == 1


def test_regional_platform_alias_survives_adoption_without_vm_recreation():
    manager = RegionalManager()
    manager.locations = [{**location("secondary", "me-west1"), "gpu_config": "b200x8a"}]
    first = regional(manager)
    saved = []
    first.bind_job(None, lambda item: saved.append(item))
    name, _ = asyncio.run(first.acquire_instance("model", "b200x8"))
    second = regional(manager)
    second.bind_job(saved[-1], lambda _: True)
    asyncio.run(second.adopt_running_instance("model", "b200x8"))
    assert second.get_instance_states()[0].gpu_config == "b200x8a"
    asyncio.run(second.mark_job_completed(name))
    second.bind_job(None, lambda _: True)
    assert asyncio.run(second.acquire_instance("model", "b200x8"))[0] == name
    assert manager.events.count(("create", "secondary")) == 1


def test_cli_discovery_reads_all_pages_and_rejects_repeated_tokens(monkeypatch):
    manager = object.__new__(NebiusInstanceManager)
    execute = AsyncMock(side_effect=[
        json.dumps({"items": [{"name": "one"}], "next_page_token": "second"}),
        json.dumps({"items": [{"name": "two"}]}),
    ])
    monkeypatch.setattr(manager, "exec", execute)
    assert asyncio.run(manager.list_resources(["iam", "v2", "project", "list"])) == [{"name": "one"}, {"name": "two"}]
    assert execute.call_args_list[1].args[0][-2:] == ["--page-token", "second"]
    execute.side_effect = [json.dumps({"items": [], "next_page_token": "repeat"})] * 2
    with pytest.raises(ValueError, match="repeated"):
        asyncio.run(manager.list_resources(["iam", "v2", "project", "list"]))


def test_discovery_filters_projects_subnets_gpu_and_regional_platform_alias(monkeypatch):
    manager = object.__new__(NebiusInstanceManager)
    manager._tenant_id = "tenant"
    manager._parent_id = "primary"
    calls = []
    projects = [
        {"metadata": {"name": "stage-project-us-central1", "id": "stage"}, "spec": {"region": "us-central1"}},
        {"metadata": {"name": "default-project-me-west1", "id": "primary"}, "spec": {"region": "me-west1"}},
        {"metadata": {"name": "default-other", "id": "excluded"}, "spec": {"region": "eu-west1"}},
    ]

    async def listing(command):
        calls.append(command)
        if command[:4] == ["iam", "v2", "project", "list"]:
            return projects
        assert command[-1] == "primary"
        if command[:3] == ["compute", "platform", "list"]:
            return [{"metadata": {"name": "gpu-b200-sxm-a"},
                     "spec": {"presets": [{"name": "8gpu-160vcpu-1792gb"}]},
                     "status": {"allowed_for_preemptibles": True}}]
        return [{"metadata": {"name": "default-subnet", "id": "subnet"}}]

    monkeypatch.setattr(manager, "list_resources", listing)
    found = asyncio.run(manager.discover_locations("b200x8", "default-", {"me-west1"}))
    assert len(found) == 1
    assert found[0]["gpu_config"] == "b200x8a"
    assert found[0]["project_id"] == "primary"
    assert all("stage" not in command and "excluded" not in command for command in calls)
    assert all("create" not in command and "delete" not in command for command in calls)
    assert asyncio.run(manager.discover_locations("h200", "default-", {"me-west1"})) == []


def test_project_clone_does_not_change_original_profile_or_parent():
    manager = object.__new__(NebiusInstanceManager)
    manager._parent_id = "primary"
    manager.profile = "service-account"
    clone = manager.for_project("secondary")
    assert clone._parent_id == "secondary"
    assert manager._parent_id == "primary"
    assert clone.profile == manager.profile


@pytest.mark.parametrize("preemptible, subnet_count", [(False, 1), (True, 2)])
def test_discovery_does_not_guess_subnet_or_change_pricing_policy(monkeypatch, preemptible, subnet_count):
    manager = object.__new__(NebiusInstanceManager)
    manager._tenant_id = "tenant"
    manager._parent_id = "primary"

    async def listing(command):
        if command[:4] == ["iam", "v2", "project", "list"]:
            return [{"metadata": {"id": "primary", "name": "default-project"}, "spec": {"region": "us-central1"}}]
        if command[:3] == ["compute", "platform", "list"]:
            return [{"metadata": {"name": "gpu-h200-sxm"},
                     "spec": {"presets": [{"name": "1gpu-16vcpu-200gb"}]},
                     "status": {"allowed_for_preemptibles": preemptible}}]
        return [{"metadata": {"name": f"default-{index}", "id": str(index)}} for index in range(subnet_count)]

    monkeypatch.setattr(manager, "list_resources", listing)
    assert asyncio.run(manager.discover_locations("h200", "default-", set())) == []
