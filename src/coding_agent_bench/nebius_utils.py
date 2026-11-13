from abc import ABC
from copy import copy
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
import asyncio
import hashlib
import logging
import json
import os
import re
import shlex
import tempfile

from coding_agent_bench.models import (
    get_model_config,
    Qwen_Qwen3_8_27B,
    Qwen_Qwen3_8_27B_FP8,
    RedHatAI_Qwen3_6_27B_FP8,
    RedHatAI_Qwen3_8_27B_INT4,
    RedHatAI_DeepSeek_V4_Flash,
    RedHatAI_DeepSeek_V4_Flash_NVFP4_FP8,
    RedHatAI_GLM_5_2_FP8,
    RedHatAI_gpt_oss_120b,
    RedHatAI_Inkling_Small,
    RedHatAI_Laguna_S_2_1,
    RedHatAI_NVIDIA_Nemotron_3_Super_120B_A12B_NVFP4,
    Poolside_Laguna_S_2_1_NVFP4,
)


logger = logging.getLogger(__name__)
NEBIUS_CLI_TIMEOUT_SECONDS = float(os.environ.get("NEBIUS_CLI_TIMEOUT_SECONDS", "300"))
if not 0 < NEBIUS_CLI_TIMEOUT_SECONDS < float("inf"):
    raise ValueError("NEBIUS_CLI_TIMEOUT_SECONDS must be positive")
NEBIUS_MODEL_START_TIMEOUT_SECONDS = float(os.environ.get("NEBIUS_MODEL_START_TIMEOUT_SECONDS", "1800"))
if not 0 < NEBIUS_MODEL_START_TIMEOUT_SECONDS < float("inf"):
    raise ValueError("NEBIUS_MODEL_START_TIMEOUT_SECONDS must be positive")


class PoolPhase(str, Enum):
    """Persisted phases; values retain compatibility with existing guard rows."""

    PREPARING = "preparing"
    REQUEST_PENDING = "inflight"
    UNKNOWN = "uncertain"
    CONFIRMED = "settled"
    REJECTED = "rejected"
    IDLE = "released"


@dataclass(frozen=True)
class ProvisioningRecord:
    """Interpret one durable pool record, independently of job/queue status.

    ``vm_known`` records whether an existing or successfully allocated VM may
    require cleanup. It is stored in the legacy ``mutation_seen`` column.
    Backend caches only locate clients; this record controls dispatch blocking.
    """

    phase: PoolPhase
    operation: str = ""
    vm_known: bool = False

    @classmethod
    def from_row(cls, row):
        return cls(PoolPhase(row["state"]), row["operation"], bool(row["mutation_seen"]))

    @property
    def untouched(self):
        return self.phase == PoolPhase.PREPARING and not self.operation and not self.vm_known

    @property
    def needs_cleanup(self):
        return self.phase in (PoolPhase.REQUEST_PENDING, PoolPhase.UNKNOWN) or self.vm_known

    @property
    def absence_is_conclusive(self):
        return self.operation in ("delete", "observe") and (
            self.vm_known or self.phase == PoolPhase.CONFIRMED
        )

    def transition(self, phase, operation=""):
        """Apply a provider observation without scattering transition SQL."""
        phase = PoolPhase(phase)
        if operation and operation not in ("create", "start", "stop", "delete", "observe"):
            raise ValueError(f"Unsupported Nebius pool operation: {operation}")
        known = self.vm_known
        if phase in (PoolPhase.CONFIRMED, PoolPhase.PREPARING) and operation in ("create", "start", "observe"):
            known = True
        elif phase == PoolPhase.CONFIRMED and operation == "delete":
            known = False
        return replace(self, phase=phase, operation=operation or self.operation, vm_known=known)


class ReconcileOutcome(str, Enum):
    """Cloud reconciliation results; the caller alone changes queue/store state."""

    VM_READY = "vm_ready"
    ABSENT = "absent"


async def reconcile_placement(backend, location, record: ProvisioningRecord, *, cleanup, can_cleanup, record_event):
    """Probe exactly the saved target; never discover/create during reconciliation."""
    try:
        details = await backend.inspect_placement(location)
    except Exception as error:
        if "NotFound" not in str(error):
            raise
        if record.absence_is_conclusive:
            return ReconcileOutcome.ABSENT
        raise RuntimeError("VM not visible yet; a lost create/start response is not proof of absence") from error
    state = details.get("status", {}).get("state")
    if state == "DELETED" and record.operation == "delete":
        return ReconcileOutcome.ABSENT
    if state not in ("RUNNING", "STOPPED", "ERROR", "CRASHED"):
        raise RuntimeError(f"VM is still transitioning ({state})")
    if not cleanup:
        record_event(PoolPhase.PREPARING, "observe")
        return ReconcileOutcome.VM_READY
    if not can_cleanup(location, backend.is_legacy_placement(location)):
        raise RuntimeError("recorded VM is claimed by another recoverable job; operator reconciliation is required")
    record_event(PoolPhase.CONFIRMED, "observe")
    record_event(PoolPhase.REQUEST_PENDING, "delete")
    await backend.delete_placement(location)
    try:
        details = await backend.inspect_placement(location)
    except Exception as error:
        if "NotFound" in str(error):
            return ReconcileOutcome.ABSENT
        raise
    if details.get("status", {}).get("state") != "DELETED":
        raise RuntimeError("VM deletion is not yet confirmed")
    return ReconcileOutcome.ABSENT


class NebiusCommandError(RuntimeError):
    """Nebius rejected a CLI operation; retain output without logging command secrets."""

    def __init__(self, args: list[str], returncode: int, stdout: str, stderr: str):
        self.args_list = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Nebius CLI failed ({returncode}): {stderr or stdout or 'no error details'}")


class NebiusCapacityError(NebiusCommandError):
    """A create/start request failed because physical capacity is unavailable."""


class NebiusCommandTimeout(TimeoutError):
    """The bounded CLI attempt expired; its remote outcome may be unknown."""


class NebiusCommandNotStarted(RuntimeError):
    """Local process creation failed before any provider request could be sent."""


class NebiusModelStartTimeout(TimeoutError):
    """Model readiness expired on a known VM, which must be cleaned up."""


class NebiusPoolBusy(RuntimeError):
    """A different durable owner has a VM that is not confirmed stopped."""


async def ensure_other_vms_stopped(manager, placements, legacy):
    """Allow retained stopped caches, but never allocate beside another running VM."""
    checked = set()
    for placement in placements:
        location = placement or legacy
        key = location["project_id"], location["instance_name"]
        if key in checked:
            continue
        checked.add(key)
        try:
            details = await manager.for_project(location["project_id"]).get_instance(location["instance_name"])
        except Exception as error:
            if "NotFound" in str(error):
                continue
            raise NebiusPoolBusy("Could not confirm another job's VM is stopped") from error
        state = details.get("status", {}).get("state")
        if state not in ("STOPPED", "DELETED"):
            raise NebiusPoolBusy(f"Another recoverable job's VM is {state}; waiting before allocating")


async def _close_process(process, *, graceful=False):
    """Bound local process shutdown so a readiness deadline cannot hang in cleanup."""
    if process.returncode is None:
        try:
            process.terminate() if graceful else process.kill()
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(process.communicate(), timeout=5)
    except asyncio.TimeoutError:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        logger.warning("Timed out draining a terminated Nebius/SSH subprocess")


def _is_capacity_error(args: list[str], output: str) -> bool:
    """Retry explicit allocation shortages, not generic quota/auth/config errors.

    Nebius documents 'Not enough resources' for VM creation/restart shortages.
    RESOURCE_EXHAUSTED alone is not sufficient evidence: it also covers quotas.
    """
    offset = 2 if args[:2] == ["compute", "v1"] else 1
    if not args or args[0] != "compute" or args[offset:offset + 2] not in (["instance", "create"], ["instance", "start"]):
        return False
    text = re.sub(r"[_-]+", " ", output.lower())
    if any(marker in text for marker in (
        "quota", "permission denied", "permissiondenied", "unauthenticated", "invalid argument", "invalidargument",
        "unauthorized", "not authorized", "billing", "balance",
        "limit exceeded", "limits exceeded",
    )):
        return False
    return any(marker in text for marker in (
        "not enough resources", "not enough capacity", "insufficient capacity",
        "insufficient resources", "no available capacity",
    ))

# Note: Resources with the '-a' subscript are specific to the me-west1 region.

class ResourceConfig(ABC):
    
    name: str
    """Resource name for lookup and pickers."""
    platform: str
    """Platform ID."""
    preset: str
    """Hardware preset."""
    tensor_parallel_size: int
    """Tensor parallel size on this hardware (= num GPUs)."""
    is_preemptible: bool
    """Boolean to indicate if preemptible instances are available for this resource."""
    additional_args: list[str] = []
    """Additional CLI arguments for instance creation."""
    model_extra_args: dict[str, list[str]] = {}
    """Additional vLLM server engine arguments for specific models on this hardware."""
    model_concurrency: dict[str, int] = {}
    """Mapping of model name to maximum concurrency of the model on this hardware."""
    
class B200(ResourceConfig):
    
    name = "b200"
    platform = "gpu-b200-sxm"
    preset = "1gpu-20vcpu-224gb"
    tensor_parallel_size = 1
    is_preemptible = True
    model_concurrency = {
        Qwen_Qwen3_8_27B.name: 12,
        Qwen_Qwen3_8_27B_FP8.name: 15,
        RedHatAI_Qwen3_6_27B_FP8.name: 29,
        RedHatAI_Qwen3_8_27B_INT4.name: 16,
        RedHatAI_gpt_oss_120b.name: 40,
        RedHatAI_NVIDIA_Nemotron_3_Super_120B_A12B_NVFP4.name: 14,
        Poolside_Laguna_S_2_1_NVFP4.name: 2,
    }
    
class B200A(B200):
    
    name = "b200a"
    platform = "gpu-b200-sxm-a"
    
class B200x8(ResourceConfig):
    
    name = "b200x8"
    platform = "gpu-b200-sxm"
    preset = "8gpu-160vcpu-1792gb"
    tensor_parallel_size = 8
    is_preemptible = True
    model_extra_args = {
        RedHatAI_DeepSeek_V4_Flash.name: ["--moe-backend", "deep_gemm_mega_moe", "--attention_config.use_fp4_indexer_cache", "True"],
        RedHatAI_DeepSeek_V4_Flash_NVFP4_FP8.name: ["--attention_config.use_fp4_indexer_cache", "True"],
    }
    model_concurrency = {
        RedHatAI_GLM_5_2_FP8.name: 5,
        RedHatAI_DeepSeek_V4_Flash.name: 14,
        RedHatAI_DeepSeek_V4_Flash_NVFP4_FP8.name: 13,
    }
    
class B200x8A(B200x8):
    
    name = "b200x8a"
    platform = "gpu-b200-sxm-a"

class H200(ResourceConfig):

    name = "h200"
    platform = "gpu-h200-sxm"
    preset = "1gpu-16vcpu-200gb"
    tensor_parallel_size = 1
    is_preemptible = True
    
class H200x8(ResourceConfig):

    name = "h200x8"
    platform = "gpu-h200-sxm"
    preset = "8gpu-128vcpu-1600gb"
    tensor_parallel_size = 8
    is_preemptible = True
    model_concurrency = {
        RedHatAI_GLM_5_2_FP8.name: 2,
        RedHatAI_DeepSeek_V4_Flash.name: 9,
        RedHatAI_DeepSeek_V4_Flash_NVFP4_FP8.name: 9,
        RedHatAI_Inkling_Small.name: 13,
        RedHatAI_Laguna_S_2_1.name: 30,
    }

RESOURCE_CONFIGS: list[ResourceConfig] = [
    B200,
    B200A,
    B200x8,
    B200x8A,
    H200,
    H200x8,
]

RESOURCE_CONFIG_REGISTRY: dict[str, ResourceConfig] = {c.name: c for c in RESOURCE_CONFIGS}
RESOURCE_CONFIG_HARDWARE_REGISTRY: dict[tuple[str, str], ResourceConfig] = {(c.platform, c.preset): c for c in RESOURCE_CONFIGS}

def get_model_max_concurrency(gpu_config: str, model_name: str) -> int:
    """Get the maximum concurrency for a model on an instance."""
    # Fetch the model config
    model_config = get_model_config(model_name)

    # Fetch the GPU config
    resource_config = RESOURCE_CONFIG_REGISTRY.get(gpu_config)
    if resource_config is None:
        raise ValueError(f"Unknown GPU config: {gpu_config}")

    # Get the max concurrency for the model on the resource
    concurrency = resource_config.model_concurrency.get(model_config.name)

    if concurrency is None:
        raise ValueError("No concurrency found for this model on this resource")

    return concurrency

class NebiusInstanceManager:
    """Manage Nebius compute instances via the nebius CLI."""

    _mutation_callback = None

    @property
    def project_id(self):
        return self._parent_id

    def set_mutation_observer(self, observer):
        """Install a synchronous durable observer before making VM mutations."""
        self._mutation_callback = observer

    def observe_vm(self):
        """Record a confirmed VM without coupling callers to observer internals."""
        if self._mutation_callback:
            self._mutation_callback(PoolPhase.CONFIRMED, "observe")

    async def mutate_instance(self, operation: str, args: list[str]):
        """Explicitly journal create/start/stop/delete before invoking the CLI.

        Transport failures and cancellation retain the pending operation.
        Definitive provider rejection and completed requests settle it.
        """
        if operation not in ("create", "start", "stop", "delete"):
            raise ValueError(f"Unsupported instance mutation: {operation}")
        notify = self._mutation_callback
        if notify:
            notify(PoolPhase.REQUEST_PENDING, operation)
        try:
            result = await self.exec(args)
        except NebiusCommandError as error:
            text = (error.stdout + "\n" + error.stderr).lower()
            if not isinstance(error, NebiusCapacityError) and any(marker in text for marker in (
                "deadlineexceeded", "deadline exceeded", "context deadline", "unavailable",
                "connection reset", "transport is closing", "timed out", "unexpected eof",
            )):
                raise NebiusCommandTimeout("Nebius mutating request returned a transport/deadline error; remote outcome needs reconciliation") from error
            if notify:
                notify(PoolPhase.REJECTED, operation)
            raise
        except NebiusCommandNotStarted:
            # The local executable could not be started; no RPC was sent.
            if notify:
                notify(PoolPhase.REJECTED, operation)
            raise
        if notify:
            notify(PoolPhase.CONFIRMED, operation)
        return result

    def __init__(self, credentials_path: str | Path | None, user: str, ssh_public_key_path: str | Path, ssh_private_key_path: str | Path, parent_id: str, tenant_id: str, service_account_id: str, credentials: str | None = None):
        if credentials_path is None and credentials is None:
            raise ValueError("Either credentials_path or credentials must be provided")
        self._credentials_path = credentials_path
        self._credentials = credentials
        self._ssh_public_key_path = ssh_public_key_path
        self._ssh_private_key_path = ssh_private_key_path
        self._user = user
        self._parent_id = parent_id
        self._tenant_id = tenant_id
        self._service_account_id = service_account_id

        self._ssh_key = Path(self._ssh_public_key_path).expanduser().resolve().read_text()

    async def init(self):
        """Create the default CLI profile. Call once after construction."""
        temp_creds = False
        if self._credentials_path:
            creds_path = Path(self._credentials_path).expanduser().resolve()
        else:
            f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            f.write(self._credentials)  # type: ignore[arg-type]  # validated non-None in __init__
            f.close()
            creds_path = Path(f.name)
            temp_creds = True
        try:
            profile_name = "default-service-account"
            self.profile = await self.create_profile(
                profile_name,
                credentials_path=creds_path,
            )
            await self.activate_profile(
                profile_name
            )
        finally:
            if temp_creds:
                creds_path.unlink(missing_ok=True)

    async def exec(self, args: list[str]) -> str:
        """Execute a nebius CLI command."""
        command = ["nebius"] + args
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as error:
            raise NebiusCommandNotStarted("Unable to launch the local Nebius CLI") from error
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=NEBIUS_CLI_TIMEOUT_SECONDS,
            )
        except (asyncio.CancelledError, asyncio.TimeoutError) as error:
            await _close_process(process)
            if isinstance(error, asyncio.TimeoutError):
                raise NebiusCommandTimeout(
                    f"Nebius CLI timed out after {NEBIUS_CLI_TIMEOUT_SECONDS:g}s; remote outcome needs reconciliation"
                ) from error
            raise
        stdout = stdout_bytes.decode() if stdout_bytes else ""
        stderr = stderr_bytes.decode() if stderr_bytes else ""

        if process.returncode != 0:
            text = (stdout + "\n" + stderr).lower()
            capacity = _is_capacity_error(args, text)
            error_class = NebiusCapacityError if capacity else NebiusCommandError
            raise error_class(args, process.returncode, stdout, stderr)
        return stdout

    def for_project(self, project_id: str):
        """Share credentials/SSH settings without changing the active CLI profile."""
        manager = copy(self)
        manager._parent_id = project_id
        return manager

    async def list_resources(self, command: list[str]) -> list[dict]:
        """Read all CLI pages; do not silently truncate discovery to its first page."""
        items = []
        token = ""
        seen = set()
        while True:
            args = [*command, "--format", "json"]
            if token:
                args += ["--page-token", token]
            document = json.loads(await self.exec(args))
            page = document.get("items", [])
            if not isinstance(page, list):
                raise ValueError("Nebius list response has no usable items list")
            items.extend(page)
            token = document.get("next_page_token") or document.get("nextPageToken") or ""
            if not token:
                return items
            if token in seen:
                raise ValueError("Nebius returned a repeated pagination token")
            seen.add(token)

    async def discover_locations(self, gpu_config: str | None, project_prefix: str, regions: set[str]) -> list[dict]:
        """Find approved projects/subnets supporting the requested GPU and pricing.

        Quota and live capacity are checked authoritatively by allocation, not
        inferred from absent quota counters or platform-list availability.
        """
        requested = RESOURCE_CONFIG_REGISTRY[gpu_config] if gpu_config else None
        equivalents = [requested, *(resource for resource in RESOURCE_CONFIGS if requested and resource is not requested
                        and resource.platform.removesuffix("-a") == requested.platform.removesuffix("-a")
                        and resource.preset == requested.preset
                        and resource.tensor_parallel_size == requested.tensor_parallel_size
                        and resource.is_preemptible == requested.is_preemptible)]
        projects = await self.list_resources(["iam", "v2", "project", "list", "--parent-id", self._tenant_id])
        locations = []
        for project in projects:
            metadata = project.get("metadata", {})
            region = (project.get("spec") or {}).get("region") or (project.get("status") or {}).get("region")
            if not metadata.get("name", "").startswith(project_prefix) or not region or (regions and region not in regions):
                continue
            project_id = metadata["id"]
            try:
                platforms = await self.list_resources(["compute", "platform", "list", "--parent-id", project_id]) if requested else []
                effective = next((resource for resource in equivalents if resource for platform in platforms
                                  if platform.get("metadata", {}).get("name") == resource.platform
                                  and any(preset.get("name") == resource.preset
                                          for preset in platform.get("spec", {}).get("presets", []))
                                  and (not resource.is_preemptible or platform.get("status", {}).get("allowed_for_preemptibles") is True)), None)
                if requested and effective is None:
                    continue
                subnets = await self.list_resources(["vpc", "subnet", "list", "--parent-id", project_id])
                defaults = [subnet for subnet in subnets if subnet.get("metadata", {}).get("name", "").startswith("default-")]
                if len(defaults) != 1:
                    logger.warning("Skipping project %s: expected one default subnet, found %s", metadata["name"], len(defaults))
                    continue
                locations.append({"project_id": project_id, "project_name": metadata["name"],
                                  "region": region, "subnet_id": defaults[0]["metadata"]["id"],
                                  "gpu_config": effective.name if effective else ""})
            except NebiusCommandError as error:
                # Project-specific permissions do not make another project
                # unusable, but none of these failures count as capacity waits.
                logger.warning("Skipping regional discovery for %s: %s", metadata["name"], error)
        return sorted(locations, key=lambda item: (item["project_id"] != self._parent_id, item["region"], item["project_name"]))

    async def create_profile(self, name: str, credentials_path: Path):
        """Create a profile or refresh credentials for an existing one."""
        create_args = [
            "profile", "create",
            "--endpoint", "api.nebius.cloud",
            "--parent-id", self._parent_id,
            "--tenant-id", self._tenant_id,
            "--service-account-file", str(credentials_path),
            "--profile", name,
        ]
        try:
            # Creating the first profile initializes ~/.nebius/config.yaml.
            # Do this before any profile-list command: on a fresh pod that
            # config file does not exist yet.
            return await self.exec(create_args)
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                raise

        logger.info("Nebius profile already exists; updating its credentials")
        update_args = [
            "profile", "update", name,
            "--endpoint", "api.nebius.cloud",
            "--parent-id", self._parent_id,
            "--tenant-id", self._tenant_id,
            "--service-account-file", str(credentials_path),
        ]
        return await self.exec(update_args)

    async def activate_profile(self, name: str):
        """Activate a profile."""
        try:
            args = ["profile", "activate", name]
            await self.exec(args)
        except Exception as e:
            logger.error(f"Failed to activate profile {name}")
            raise e

    async def create_instance(self, instance_name: str, subnet_id: str, gpu_config: str = "h200"):
        """Create a new compute instance."""
        cloud_init_user_data = (
            "users:\n"
            f"  - name: {self._user}\n"
            "    sudo: ALL=(ALL) NOPASSWD:ALL\n"
            "    shell: /bin/bash\n"
            "    ssh_authorized_keys:\n"
            f"      - {self._ssh_key}\n"
        )
        network_interfaces = [{"subnetId": subnet_id, "name": "eth0", "ipAddress": {}, "publicIpAddress": {}}]

        # Get GPU config
        resource_config = RESOURCE_CONFIG_REGISTRY.get(gpu_config)
        if resource_config is None:
            raise ValueError(f"GPU config '{gpu_config}' is not recognized. Please choose from: {RESOURCE_CONFIG_REGISTRY.keys()}")

        # Build the create command
        args = [
            "compute", "v1", "instance", "create",
            "--parent-id", self._parent_id,
            "--name", instance_name,
            "--service-account-id", self._service_account_id,
            "--resources-platform", resource_config.platform,
            "--resources-preset", resource_config.preset,
            "--network-interfaces", json.dumps(network_interfaces),
            "--boot-disk-attach-mode", "read_write",
            "--boot-disk-managed-disk-name", f"{instance_name}-boot-disk",
            "--boot-disk-managed-disk-size-bytes", "1374389534720",
            "--boot-disk-managed-disk-block-size-bytes", "4096",
            "--boot-disk-managed-disk-type", "network_ssd",
            "--boot-disk-managed-disk-source-image-family-image-family", "ubuntu24.04-cuda13.0",
            "--boot-disk-device-id", "boot-disk",
            "--cloud-init-user-data", cloud_init_user_data,
            "--reservation-policy-policy", "forbid",
        ]
        args += resource_config.additional_args

        # Prefer preemptible instances, if the resource supports it
        if resource_config.is_preemptible:
            args += [
                "--preemptible-on-preemption", "stop",
                "--recovery-policy", "fail",
                "--follows-spot-price=true",
            ]

        await self.mutate_instance("create", args)

    async def get_instance(self, instance_name: str):
        """Get details about a running instance."""
        args = [
            "compute", "instance", "get-by-name",
            "--name", instance_name,
            "--parent-id", self._parent_id,
            "--format", "json",
        ]
        stdout = await self.exec(args)
        return json.loads(stdout)

    async def get_instance_ip_address(self, instance_name: str):
        """Get the IP address of a running instance."""
        try:
            instance_details = await self.get_instance(instance_name)
        except Exception as e:
            if "NotFound" in str(e):
                raise ValueError("Instance not found")
            else:
                raise e

        return instance_details.get("status", {}).get("network_interfaces", [{}])[0].get("public_ip_address", {}).get("address")

    async def instance_exists(self, instance_name: str) -> bool:
        try:
            await self.get_instance(instance_name)
            return True
        except Exception as e:
            if "NotFound" in str(e):
                return False
            raise

    async def _wait_for_instance_state(self, instance_name: str, target: str, timeout: int = 300, interval: int = 10):
        """Poll until instance reaches target state. Raises on ERROR or timeout."""
        terminal_ok = {target}
        terminal_fail = {"ERROR", "CRASHED", "DELETED"}
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            details = await self.get_instance(instance_name)
            state = details.get("status", {}).get("state")
            if state in terminal_ok:
                return
            if state in terminal_fail:
                raise RuntimeError(f"Instance {instance_name} reached {state} while waiting for {target}")
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(f"Instance {instance_name} still in {state} after {timeout}s (wanted {target})")
            logger.info(f"Instance {instance_name} in {state}, waiting for {target}...")
            await asyncio.sleep(interval)

    async def start_instance(self, instance_name: str):
        """Start a stopped instance and wait until it is RUNNING."""
        try:
            instance_details = await self.get_instance(instance_name)
        except Exception as e:
            if "NotFound" in str(e):
                raise ValueError("Instance not found")
            else:
                raise e

        state = instance_details.get("status", {}).get("state")
        instance_id = instance_details.get("metadata", {}).get("id")

        if state is None:
            raise ValueError("Instance state is not available")

        if state == "RUNNING":
            logger.info(f"Instance {instance_name} ({instance_id}) is already running")
            return

        if state in ["STOPPED", "STOPPING", "STARTING", "CREATING"]:
            if state in ["STOPPED", "STOPPING"]:
                logger.info(f"Starting instance {instance_name} ({instance_id})")
                args = [
                    "compute", "instance", "start",
                    "--id", instance_id,
                ]
                await self.mutate_instance("start", args)
                await self._wait_for_instance_state(instance_name, "RUNNING")
                logger.info(f"Instance {instance_name} ({instance_id}) is now running")
                return
            logger.info(f"Instance {instance_name} ({instance_id}) is {state}, waiting for RUNNING")
            await self._wait_for_instance_state(instance_name, "RUNNING")
            logger.info(f"Instance {instance_name} ({instance_id}) is now running")
            return

        raise RuntimeError(f"Instance {instance_name} ({instance_id}) is in unexpected state: {state}")

    async def stop_instance(self, instance_name: str):
        """Stop a running instance and wait until it is STOPPED."""
        try:
            instance_details = await self.get_instance(instance_name)
        except Exception as e:
            if "NotFound" in str(e):
                raise ValueError("Instance not found")
            else:
                raise e

        state = instance_details.get("status", {}).get("state")
        instance_id = instance_details.get("metadata", {}).get("id")

        if state is None:
            raise ValueError("Instance state is not available")

        if state == "STOPPED":
            logger.info(f"Instance {instance_name} ({instance_id}) is already stopped")
            return

        if state in ["RUNNING", "STARTING", "STOPPING"]:
            if state in ["RUNNING", "STARTING"]:
                logger.info(f"Stopping instance {instance_name} ({instance_id})")
                args = [
                    "compute", "instance", "stop",
                    "--id", instance_id,
                ]
                await self.mutate_instance("stop", args)
            else:
                logger.info(f"Instance {instance_name} ({instance_id}) is STOPPING, waiting for STOPPED")
            await self._wait_for_instance_state(instance_name, "STOPPED")
            logger.info(f"Instance {instance_name} ({instance_id}) is now stopped")
            return

        raise RuntimeError(f"Instance {instance_name} ({instance_id}) is in unexpected state: {state}")

    async def delete_instance(self, instance_name: str):
        try:
            instance_details = await self.get_instance(instance_name)
        except Exception as e:
            if "NotFound" in str(e):
                raise ValueError("Instance not found")
            else:
                raise e

        state = instance_details.get("status", {}).get("state")
        instance_id = instance_details.get("metadata", {}).get("id")

        if state == "RUNNING":
            await self.stop_instance(instance_name)

        logger.info(f"Deleting instance {instance_name} ({instance_id})")
        args = [
            "compute", "instance", "delete",
            "--id", instance_id,
        ]
        await self.mutate_instance("delete", args)

        logger.info(f"Deleted instance {instance_name} ({instance_id})")

    async def instance_exec(self, instance_name: str, command: list[str], exit_after: str | None = None, retries: int = 5, retry_delay: int = 10):
        """Connect to an instance over SSH and execute a command.

        Retries on SSH connection failures (e.g. VM just started and sshd
        isn't ready yet). CancelledError is always re-raised immediately
        so shutdown isn't blocked.
        """
        # Sanitize then log the command
        log_safe = shlex.join(command)
        if "HF_TOKEN" in log_safe:
            log_safe = re.sub(r"HF_TOKEN=\S+", "HF_TOKEN=<redacted>", log_safe)
        logger.info(f"Executing command on {instance_name}: {log_safe}")

        last_error: Exception = ValueError(f"instance_exec called with retries=0 for {instance_name}")
        for attempt in range(1, retries + 1):
            try:
                public_ip_address = await self.get_instance_ip_address(instance_name=instance_name)

                if public_ip_address is None:
                    raise ValueError("Public IP address not found")

                if "/" in public_ip_address:
                    public_ip_address = public_ip_address.split("/")[0]

                ssh_command = [
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-o", "ConnectTimeout=10",
                    "-i", str(self._ssh_private_key_path),
                    f"{self._user}@{public_ip_address}",
                    shlex.join(command),
                ]

                if exit_after is None:
                    return await self._ssh_run(ssh_command)
                else:
                    return await self._ssh_stream(ssh_command, exit_after)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = e
                if attempt < retries:
                    logger.warning(f"SSH attempt {attempt}/{retries} failed, retrying in {retry_delay}s: {e}")
                    await asyncio.sleep(retry_delay)

        raise last_error

    async def _ssh_run(self, ssh_command: list[str]) -> str:
        """Run an SSH command and return stdout."""
        process = await asyncio.create_subprocess_exec(
            *ssh_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await process.communicate()
        except asyncio.CancelledError:
            await _close_process(process)
            raise
        stdout = stdout_bytes.decode() if stdout_bytes else ""
        stderr = stderr_bytes.decode() if stderr_bytes else ""
        if process.returncode != 0:
            raise Exception(f"SSH command failed:\nstdout: {stdout}\nstderr: {stderr}")
        return stdout

    async def _ssh_stream(self, ssh_command: list[str], exit_after: str) -> str:
        """Run an SSH command and stream stdout until exit_after marker is found."""
        logger.info(f"Following command until '{exit_after}' is found:")
        process = await asyncio.create_subprocess_exec(
            *ssh_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output_lines: list[str] = []
        try:
            assert process.stdout is not None
            async for raw_line in process.stdout:
                line = raw_line.decode()
                output_lines.append(line)
                logger.info(line.rstrip())
                if exit_after in line:
                    await _close_process(process, graceful=True)
                    return "".join(output_lines)
            await process.wait()
            if process.returncode != 0:
                raise Exception(f"SSH command failed before '{exit_after}' was found:\noutput: {''.join(output_lines)}")
            raise Exception(f"Command finished without outputting '{exit_after}':\noutput: {''.join(output_lines)}")
        except asyncio.CancelledError:
            await _close_process(process)
            raise
        except Exception:
            await _close_process(process)
            raise

    async def start_model(self, instance_name: str, model_name: str):
        """Start a model on a Nebius instance."""
        # Fetch the model config
        model_config = get_model_config(model_name)

        # Get the instance
        try:
            instance_details = await self.get_instance(instance_name)
        except Exception as e:
            if "NotFound" in str(e):
                raise ValueError("Instance not found")
            else:
                raise e

        # Lookup the resource config of the instance
        spec_resources = instance_details.get("spec", {}).get("resources", {})
        preset = spec_resources.get("preset")
        platform = spec_resources.get("platform", "")
        resource_config = RESOURCE_CONFIG_HARDWARE_REGISTRY.get((platform, preset))
        if resource_config is None:
            raise ValueError(f"Instance does not match any configured resource spec - {platform} - {preset}")

        # Add extra arguments from the resource
        resource_extra_args = ["--tensor-parallel-size", str(resource_config.tensor_parallel_size)]
        resource_extra_args += resource_config.model_extra_args.get(model_config.name, [])

        # Build the vLLM command — HF_TOKEN is exported on the remote shell
        # so it never appears in command args, logs, or `docker inspect`.
        docker_cmd = [
            "sudo", "docker", "run",
            "--name", "vllm",
            "--runtime", "nvidia",
            "--gpus", "all",
            "-v", "/home/.cache/huggingface:/root/.cache/huggingface",
            "--env", "HF_TOKEN",
            "-p", "8000:8000",
            "--ipc=host",
        ]
        docker_cmd += [model_config.image]
        docker_cmd += model_config.args + model_config.default_args
        docker_cmd += resource_extra_args

        hf_token = os.environ.get("HF_TOKEN", "")
        shell_command = f"export HF_TOKEN={shlex.quote(hf_token)} && {shlex.join(docker_cmd)}"
        command = ["bash", "-c", shell_command]

        # More retries than default — instance may have just booted and sshd isn't ready yet
        await self.instance_exec(instance_name=instance_name, command=command, exit_after="Available routes", retries=18, retry_delay=10)

    async def stop_model(self, instance_name: str):
        """Stop a running vLLM server on the given instance."""
        await self.instance_exec(instance_name, ["sudo", "docker", "stop", "vllm"])
        await self.instance_exec(instance_name, ["sudo", "docker", "rm", "vllm"])


class RegionalNebiusOrchestrator:
    """Discover allocation targets while keeping all lifecycle calls project-scoped.

    The queue worker binds one durable placement callback at a time. Placement
    is recorded *before* provisioning, so a lost CLI response or queue restart
    cannot cause the next attempt to forget where it may already own a VM.
    """

    def forget_placement(self, location: dict) -> None:
        """Forget only the resolved target; no provider calls are made."""
        key = self._key(location)
        child = self._children.pop(key, None)
        self._locations.pop(key, None)
        if child:
            child.forget_placement(location)
        if self._bound and self._key(self._bound) == key:
            self._bound = None
        if self._pool_location and self._key(self._pool_location) == key:
            self._pool_location = None

    def __init__(self, manager, subnet_id, instance_name_prefix, idle_timeout,
                 orchestrator_factory, project_prefix="default-", regions=None):
        self._manager = manager
        self._prefix = instance_name_prefix
        self._idle_timeout = idle_timeout
        self._factory = orchestrator_factory
        self._project_prefix = project_prefix
        self._regions = set(regions or [])
        self._children = {}
        self._locations = {}
        self._bound = None
        self._save = None
        self._job_id = None
        self._legacy_recovery = False
        self._can_use = None
        self._mutation_callback = None
        self._guard_active = None
        self._pool_location = None
        self._lock = asyncio.Lock()
        self.cleanup_active = False
        self._legacy = {"project_id": manager._parent_id, "subnet_id": subnet_id,
                        "project_name": "", "region": "", "gpu_config": "",
                        "instance_name": f"{instance_name_prefix}-0"}
        self._child(self._legacy)

    def bind_job(self, location, save, *, job_id=None, legacy_recovery=False, can_use=None):
        """Restore the current job's placement without consulting mutable discovery."""
        same_job = job_id is not None and job_id == self._job_id
        self._legacy_recovery = legacy_recovery or (same_job and self._legacy_recovery)
        self._job_id = job_id
        self._can_use = can_use
        self._save = save
        self._bound = dict(location) if location else None
        if self._bound:
            self._child(self._bound)

    def _key(self, location):
        return location["project_id"], location["instance_name"]

    def _named(self, location):
        location = dict(location)
        project_hash = hashlib.sha256(location["project_id"].encode()).hexdigest()[:8]
        location["instance_name"] = f"{self._prefix[:30]}-{location['region']}-{project_hash}-0"
        return location

    def _child(self, location):
        key = self._key(location)
        if key in self._locations and self._locations[key]["subnet_id"] != location["subnet_id"]:
            raise ValueError("Saved Nebius placement conflicts with discovered subnet")
        if key not in self._children:
            if not location["instance_name"].endswith("-0"):
                raise ValueError("Invalid persisted Nebius instance name")
            manager = self._manager.for_project(location["project_id"])
            manager.set_mutation_observer(self._mutation_callback)
            self._children[key] = self._factory(
                manager, location["subnet_id"], location["instance_name"][:-2], self._idle_timeout,
            )
            self._locations[key] = dict(location)
            self._children[key].configure_provisioning(self._mutation_callback, self._guard_active)
        return self._children[key]

    def configure_provisioning(self, callback, active, previous_location=None):
        """Attach durable mutation notifications to every project-scoped client."""
        self.restore_pool_location(previous_location)
        self._mutation_callback = callback
        self._guard_active = active
        self._manager.set_mutation_observer(callback)
        for child in self._children.values():
            child.configure_provisioning(callback, active)

    def configured_location(self, gpu_config):
        """Regional placement is recorded when a target is selected, not earlier."""
        return None

    async def check_other_placements(self, placements):
        await ensure_other_vms_stopped(self._manager, placements, self._legacy)

    def is_legacy_placement(self, location):
        return self._key(location) == self._key(self._legacy)

    async def inspect_placement(self, location):
        """Inspect the saved project/name without requiring new discovery."""
        return await self._child(location).inspect_placement(location)

    async def delete_placement(self, location):
        """Delete only the supplied saved target, not the mutable current binding."""
        async with self._lock:
            await self._child(location).delete_placement(location)

    def provisioning_child(self, location):
        """Route reconciliation directly to the persisted target, without discovery."""
        return self._child(location)

    def restore_pool_location(self, location):
        """Remember a settled idle VM without assigning it to a pending job."""
        self._pool_location = dict(location) if location else None
        if self._pool_location:
            self._child(self._pool_location)

    def _remember(self, location):
        if not self._can_touch(location):
            raise RuntimeError("Nebius placement is claimed by another recoverable job")
        if self._save:
            if self._save(dict(location)) is False:
                raise RuntimeError("Job left its recoverable state before regional provisioning")
        # A failed claim must not leave a cancelled job bound to an unowned VM.
        self._bound = dict(location)
        self._locations[self._key(location)] = dict(location)

    def _can_touch(self, location):
        """Check live ownership before claiming or deleting a shared-pool VM."""
        return self._can_use is None or self._can_use(location, self._key(location) == self._key(self._legacy))

    def _route(self, instance_name):
        matches = [child for key, child in self._children.items() if key[1] == instance_name]
        if len(matches) != 1:
            raise ValueError(f"No unambiguous saved region for Nebius instance {instance_name}")
        return matches[0]

    def _annotate(self, child, location):
        for state in child.get_instance_states():
            state.region = location["region"]
            state.project_id = location["project_id"]

    async def acquire_instance(self, model_name, gpu_config):
        """Try each eligible region once; only all-capacity failures defer the job."""
        async with self._lock:
            if self.has_busy_instance():
                raise RuntimeError("Another job still owns a regional Nebius instance")
            locations = [self._named(item) for item in await self._manager.discover_locations(
                gpu_config, self._project_prefix, self._regions,
            )]
            locations = [item for item in locations if self._can_touch(item)]
            if not locations:
                raise RuntimeError("No eligible Nebius projects/subnets support the requested GPU and pricing policy; check discovery permissions and region configuration")

            # Include the old single-region VM name for rolling upgrades. Never
            # reuse it for a different project than its configured original one.
            primary = next((item for item in locations if item["project_id"] == self._legacy["project_id"]), None)
            if primary and self._can_touch(self._legacy) and await self._child(self._legacy)._manager.instance_exists(self._legacy["instance_name"]):
                locations.insert(0, {**primary, "instance_name": self._legacy["instance_name"],
                                     "subnet_id": self._legacy["subnet_id"]})

            # Look for owned VMs left by earlier runs before creating another.
            existing = []
            for location in locations:
                if await self._child(location)._manager.instance_exists(location["instance_name"]):
                    existing.append(location)
            # A previous job may have used a region that does not support this
            # job's different hardware. Reconcile its idle VM before allocating
            # elsewhere, including after a queue restart.
            known = [self._pool_location] if self._pool_location else []
            known += [self._locations[key] for key, child in self._children.items() if child.get_instance_states()]
            candidate_keys = {self._key(item) for item in locations}
            existing_keys = {self._key(item) for item in existing}
            for previous in known:
                key = self._key(previous)
                if key not in candidate_keys and key not in existing_keys and self._can_touch(previous):
                    if await self._child(previous)._manager.instance_exists(previous["instance_name"]):
                        existing.append(previous)
                        existing_keys.add(key)
            bound_key = self._key(self._bound) if self._bound else None
            if bound_key and all(self._key(item) != bound_key for item in locations):
                # An uncertain outcome in a now-ineligible location must first
                # be reconciled, not forgotten while allocating somewhere else.
                if not self._can_touch(self._bound):
                    raise RuntimeError("Saved Nebius placement is claimed by another recoverable job")
                child = self._child(self._bound)
                if await child._manager.instance_exists(self._bound["instance_name"]):
                    await child.delete_recovered_instance()
            existing_keys = {self._key(item) for item in existing}
            locations.sort(key=lambda item: (self._key(item) != bound_key, self._key(item) not in existing_keys))
            capacity_regions = []
            quota_regions = []
            for location in locations:
                child = self._child(location)
                for other in list(existing):
                    if self._key(other) != self._key(location):
                        other_child = self._child(other)
                        if other_child.has_busy_instance():
                            raise RuntimeError("Another job still owns a regional Nebius instance")
                        self._remember(other)
                        await other_child.delete_recovered_instance()
                        existing.remove(other)
                self._remember(location)
                if self._key(location) in existing_keys:
                    child._manager.observe_vm()
                logger.info("Trying Nebius region %s, project %s, resource %s", location["region"], location["project_name"], location["gpu_config"])
                try:
                    answer = await child.acquire_instance(model_name, location["gpu_config"])
                except NebiusCommandError as error:
                    if isinstance(error, NebiusCapacityError):
                        capacity_regions.append(location["region"])
                    elif "quota" in (error.stderr + error.stdout).lower():
                        quota_regions.append(location["region"])
                    else:
                        raise
                    # Only move to another region after confirming the failed
                    # target has no live VM. Timeouts bubble out for reconciliation.
                    if not self._can_touch(location):
                        raise RuntimeError("Nebius placement was claimed during provisioning") from error
                    await child.delete_recovered_instance()
                    existing = [item for item in existing if self._key(item) != self._key(location)]
                    continue
                self._annotate(child, location)
                return answer
            if capacity_regions:
                error = NebiusCapacityError(["compute", "instance", "create"], 1, "",
                                             "Not enough resources in regions: " + ", ".join(capacity_regions))
                error.regions = capacity_regions
                raise error
            raise RuntimeError("No regional allocation available: quota exceeded in " + ", ".join(quota_regions))

    async def adopt_running_instance(self, model_name, gpu_config):
        location = dict(self._bound or self._legacy)
        location["gpu_config"] = location.get("gpu_config") or gpu_config
        if not self._can_touch(location):
            raise RuntimeError("Nebius placement is claimed by another recoverable job")
        child = self._child(location)
        name = await child.adopt_running_instance(model_name, location["gpu_config"])
        self._remember(location)
        self._annotate(child, location)
        return name

    async def adopt_paused_instance(self, model_name, gpu_config):
        location = dict(self._bound or self._legacy)
        location["gpu_config"] = location.get("gpu_config") or gpu_config
        if not self._can_touch(location):
            raise RuntimeError("Nebius placement is claimed by another recoverable job")
        child = self._child(location)
        name = await child.adopt_paused_instance(model_name, location["gpu_config"])
        self._remember(location)
        self._annotate(child, location)
        return name

    async def delete_recovered_instance(self):
        """Clean only this job's recorded or verified legacy placement, never sweep."""
        async with self._lock:
            location = self._bound or (self._legacy if self._legacy_recovery else None)
            if location is None:
                logger.info("Skipping cleanup: this job has not selected or owned a Nebius VM")
                return
            if not self._can_touch(location):
                logger.info("Skipping cleanup: Nebius VM is claimed by another recoverable job")
                return
            await self._child(location).delete_recovered_instance()

    async def startup_cleanup_locations(self):
        """Discover approved targets without deletion or mutable job binding."""
        return [self._legacy, *(self._named(item) for item in await self._manager.discover_locations(
            None, self._project_prefix, self._regions,
        ))]

    def idle_cleanup_locations(self):
        """Return expired project-scoped caches for guarded pool maintenance."""
        return [self._locations[key] for key, child in self._children.items() if child.idle_cleanup_locations()]

    async def mark_job_started(self, instance_name):
        await self._route(instance_name).mark_job_started(instance_name)

    async def mark_job_completed(self, instance_name):
        await self._route(instance_name).mark_job_completed(instance_name)

    async def mark_job_paused(self, instance_name):
        await self._route(instance_name).mark_job_paused(instance_name)

    async def recover_stopped_instance(self, instance_name):
        child = self._route(instance_name)
        async with child._lock:
            await child.recover_stopped_instance(instance_name)

    async def get_instance_state(self, instance_name):
        return await self._route(instance_name).get_instance_state(instance_name)

    def has_busy_instance(self):
        return any(child.has_busy_instance() for child in self._children.values())

    def get_instance_states(self):
        return [state for child in self._children.values() for state in child.get_instance_states()]
