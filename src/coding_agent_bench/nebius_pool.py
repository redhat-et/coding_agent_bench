"""Queue-facing Nebius ownership and single-instance lifecycle coordination.

The queue supplies its store and backend explicitly. Scheduling, job status
transitions and HTTP handling stay in api.py; provider and regional operations
stay in nebius_utils.py. This module owns no queue or additional durable state.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
import os
import time

from dotenv import load_dotenv

from coding_agent_bench.nebius_utils import (
    NebiusInstanceManager, RESOURCE_CONFIG_REGISTRY, RegionalNebiusOrchestrator,
    NebiusCommandTimeout, NebiusModelStartTimeout, NebiusPoolBusy,
    NEBIUS_MODEL_START_TIMEOUT_SECONDS, ProvisioningRecord,
    ReconcileOutcome, reconcile_placement, ensure_other_vms_stopped,
)
from coding_agent_bench.resume import is_resume_command

load_dotenv()
logger = logging.getLogger(__name__)
PREEMPT_STABLE_SECONDS = int(os.environ.get("PREEMPT_STABLE_SECONDS", "90"))
PREEMPT_RESTART_ATTEMPTS = int(os.environ.get("PREEMPT_RESTART_ATTEMPTS", "10"))
PREEMPT_STABILIZE_ERROR_SECONDS = int(os.environ.get("PREEMPT_STABILIZE_ERROR_SECONDS", "120"))
# States no start call can bring back (including records left by idle deletion).
NEBIUS_UNRECOVERABLE_STATES = {"DELETED", "ERROR", "CRASHED"}


def parse_nebius_url(server_url: str) -> str | None:
    """Return the resource config name for a managed Nebius placeholder."""
    prefix = "nebius-"
    if server_url.lower().startswith(prefix):
        return server_url[len(prefix):].lower()
    return None


def _monotonic() -> float:
    """Monotonic clock seam for recovery stabilization."""
    return asyncio.get_running_loop().time()


@dataclass
class NebiusInstanceState:
    instance_name: str
    gpu_config: str
    current_model: str | None = None
    provisioning_model: str | None = None  # set while a model is being started/swapped
    job_running: bool = False
    last_job_completed_at: float | None = None
    region: str = ""
    project_id: str = ""


class NebiusOrchestrator:
    """Track a single project's instance, model readiness and idle cleanup.

    Regional routing composes these project-scoped backends. Durable ownership
    and reconciliation are coordinated by NebiusPool below.
    """

    def __init__(self, manager: NebiusInstanceManager, subnet_id: str,
                 instance_name_prefix: str, idle_timeout: int):
        """Initialize the in-memory Nebius instance lifecycle tracker."""
        self._manager = manager
        self._subnet_id = subnet_id
        self._prefix = instance_name_prefix
        self._idle_timeout = idle_timeout
        self._instances: dict[str, NebiusInstanceState] = {}
        self._lock = asyncio.Lock()
        self._pool_guard_active = None

    def _pick_instance_name(self) -> str:
        """Return the name for the next instance. Currently single-instance."""
        return f"{self._prefix}-0"

    def configured_location(self, gpu_config):
        """Expose the single-region placement to the persistence boundary."""
        return {"project_id": self._manager.project_id, "subnet_id": self._subnet_id,
                "instance_name": self._pick_instance_name(), "region": "", "project_name": "",
                "gpu_config": gpu_config}

    def configure_provisioning(self, observer, active, previous_location=None):
        """Configure explicit provider journaling and idle-cleanup exclusion."""
        self._manager.set_mutation_observer(observer)
        self._pool_guard_active = active

    def is_legacy_placement(self, location):
        """The original single-project pool has one deterministic legacy name."""
        return (location["project_id"], location["instance_name"]) == (self._manager.project_id, self._pick_instance_name())

    async def check_other_placements(self, placements):
        """Confirm other owners' VMs are stopped before a managed allocation."""
        await ensure_other_vms_stopped(self._manager, placements, self.configured_location(""))

    def _validate_placement(self, location):
        """Reject configuration changes that would redirect a saved operation."""
        if (self._manager.project_id, self._pick_instance_name()) != (location["project_id"], location["instance_name"]):
            raise ValueError("saved placement differs from current single-region configuration; restore it or reconcile the saved VM manually")

    async def inspect_placement(self, location):
        """Read only the recorded target; never silently redirect to a new project."""
        self._validate_placement(location)
        return await self._manager.get_instance(location["instance_name"])

    async def delete_placement(self, location):
        """Delete the recorded target under the normal lifecycle lock."""
        self._validate_placement(location)
        await self.delete_recovered_instance()

    def forget_placement(self, location: dict) -> None:
        """Discard a manually confirmed absent VM from the local cache."""
        if location.get("project_id") == self._manager.project_id:
            self._instances.pop(location["instance_name"], None)

    def _observe_vm(self):
        """Notify the durable guard when a VM is known to exist."""
        observer = getattr(self._manager, "observe_vm", None)
        if observer:
            observer()

    async def acquire_instance(self, model_name: str, gpu_config: str) -> tuple[str, str]:
        """
        Provision an instance with the requested model and return (instance_name, server_url).

        Creates the VM if it doesn't exist, starts it if stopped, and swaps
        the model if a different one is loaded. Skips steps that are already
        satisfied to minimize latency.
        """
        async with self._lock:
            # Reuse an existing instance with matching gpu_config, or create a new one.
            # Delete idle instances with the wrong gpu_config to free the slot.
            instance_name = None
            to_delete: list[str] = []
            for name, state in self._instances.items():
                if state.job_running:
                    continue
                if state.gpu_config == gpu_config:
                    instance_name = name
                    break
                else:
                    to_delete.append(name)

            for name in to_delete:
                logger.info(f"Deleting nebius instance {name} (gpu_config mismatch, had {self._instances[name].gpu_config}, need {gpu_config})")
                # An earlier delete may have completed despite a CLI timeout.
                if await self._manager.instance_exists(name):
                    await self._manager.delete_instance(name)
                del self._instances[name]

            if instance_name is None:
                instance_name = self._pick_instance_name()

            # Create the instance if we haven't tracked it yet
            if instance_name not in self._instances:
                if await self._manager.instance_exists(instance_name):
                    self._observe_vm()
                    # A timed-out create may have succeeded remotely. Reconcile
                    # the deterministic VM before issuing another create/delete.
                    details = await self._manager.get_instance(instance_name)
                    resources = details.get("spec", {}).get("resources", {})
                    requested = RESOURCE_CONFIG_REGISTRY[gpu_config]
                    matching = (resources.get("platform"), resources.get("preset")) == (requested.platform, requested.preset)
                    usable = details.get("status", {}).get("state") not in NEBIUS_UNRECOVERABLE_STATES
                    if not matching or not usable:
                        logger.info(f"Replacing incompatible nebius instance {instance_name}")
                        await self._manager.delete_instance(instance_name)
                        await self._manager.create_instance(instance_name, self._subnet_id, gpu_config)
                else:
                    logger.info(f"Creating nebius instance {instance_name} with {gpu_config}")
                    await self._manager.create_instance(instance_name, self._subnet_id, gpu_config)
                self._instances[instance_name] = NebiusInstanceState(instance_name=instance_name, gpu_config=gpu_config, last_job_completed_at=time.time())

            # Start the instance (noop if already running)
            self._observe_vm()
            logger.info(f"Ensuring nebius instance {instance_name} is running")
            try:
                await self._manager.start_instance(instance_name)
            except Exception as e:
                if "not found" in str(e).lower() or "NotFound" in str(e):
                    logger.warning(f"Instance {instance_name} no longer exists, recreating")
                    del self._instances[instance_name]
                    await self._manager.create_instance(instance_name, self._subnet_id, gpu_config)
                    self._instances[instance_name] = NebiusInstanceState(instance_name=instance_name, gpu_config=gpu_config, last_job_completed_at=time.time())
                    await self._manager.start_instance(instance_name)
                else:
                    raise

            state = self._instances[instance_name]

            # Swap model if needed
            if state.current_model != model_name:
                state.provisioning_model = model_name
                try:
                    async with asyncio.timeout(NEBIUS_MODEL_START_TIMEOUT_SECONDS):
                        try:
                            logger.info(f"Stopping any running model on {instance_name}")
                            await self._manager.stop_model(instance_name)
                        except Exception:
                            logger.debug(f"stop_model failed on {instance_name} (may be expected)", exc_info=True)
                        logger.info(f"Starting model {model_name} on {instance_name}")
                        await self._manager.start_model(instance_name, model_name)
                    state.current_model = model_name
                except TimeoutError as error:
                    state.current_model = None
                    raise NebiusModelStartTimeout(
                        f"Model startup/readiness exceeded {NEBIUS_MODEL_START_TIMEOUT_SECONDS:g}s on {instance_name}"
                    ) from error
                except Exception:
                    state.current_model = None
                    raise
                finally:
                    state.provisioning_model = None

            # Fetch the public IP and build the server URL
            ip = await self._manager.get_instance_ip_address(instance_name)
            if ip and "/" in ip:
                ip = ip.split("/")[0]
            if not ip:
                raise RuntimeError(f"Instance {instance_name} has no public IP address")
            server_url = f"http://{ip}:8000"
            return instance_name, server_url

    async def mark_job_started(self, instance_name: str):
        """Mark a tracked Nebius instance as busy."""
        if instance_name not in self._instances:
            logger.warning(f"mark_job_started: instance {instance_name} already evicted")
            return
        self._instances[instance_name].job_running = True

    async def mark_job_completed(self, instance_name: str):
        """Mark a tracked Nebius instance idle after a job completes."""
        state = self._instances.get(instance_name)
        if state is None:
            logger.warning(f"mark_job_completed: instance {instance_name} already evicted")
            return
        state.job_running = False
        state.last_job_completed_at = time.time()

    async def adopt_running_instance(self, model_name: str, gpu_config: str) -> str:
        """Restore tracking for the deterministic instance used by a running job."""
        async with self._lock:
            instance_name = self._pick_instance_name()
            if not await self._manager.instance_exists(instance_name):
                raise RuntimeError(f"Nebius instance {instance_name} is missing for recovered job")
            self._observe_vm()
            self._instances[instance_name] = NebiusInstanceState(
                instance_name=instance_name,
                gpu_config=gpu_config,
                current_model=model_name,
                job_running=True,
            )
            return instance_name

    async def delete_recovered_instance(self) -> None:
        """Delete the deterministic VM left behind by an interrupted terminal transition."""
        async with self._lock:
            instance_name = self._pick_instance_name()
            if await self._manager.instance_exists(instance_name):
                logger.info(f"Deleting recovered nebius instance {instance_name}")
                await self._manager.delete_instance(instance_name)
            self._instances.pop(instance_name, None)

    async def mark_job_paused(self, instance_name: str):
        """Release a preempted instance: it is free again and its model died with it."""
        state = self._instances.get(instance_name)
        if state is None:
            return
        state.job_running = False
        state.current_model = None
        state.provisioning_model = None
        state.last_job_completed_at = time.time()

    async def adopt_paused_instance(self, model_name: str, gpu_config: str) -> str | None:
        """Track the deterministic instance left by a paused job.

        Returns the instance name when it exists in a startable state and
        belongs to the paused job's gpu_config without another job on it.
        Returns None when the instance is gone or sits in an unrecoverable
        state (e.g. DELETED after idle cleanup deleted the preempted VM):
        the caller then re-queues and the worker's acquire path deletes and
        recreates it. Raises when the Nebius API is unreachable so the
        caller keeps the job paused and retries on a later pass.
        """
        async with self._lock:
            instance_name = self._pick_instance_name()
            state = self._instances.get(instance_name)
            if state is not None and (state.job_running or state.gpu_config != gpu_config):
                return None
            try:
                remote = await self.get_instance_state(instance_name)
            except Exception as e:
                if "NotFound" in str(e):
                    logger.info(
                        f"Paused job's instance {instance_name} no longer exists; "
                        "worker will recreate it"
                    )
                    self._instances.pop(instance_name, None)
                    return None
                raise
            if remote in NEBIUS_UNRECOVERABLE_STATES:
                logger.warning(
                    f"Not adopting {instance_name} for paused recovery: state {remote} "
                    "cannot be started; worker will delete and recreate it"
                )
                self._instances.pop(instance_name, None)
                return None
            self._observe_vm()
            if state is None:
                self._instances[instance_name] = NebiusInstanceState(
                    instance_name=instance_name,
                    gpu_config=gpu_config,
                    current_model=None,
                    job_running=False,
                    last_job_completed_at=time.time(),
                )
            return instance_name

    async def recover_stopped_instance(self, instance_name: str) -> None:
        """Start a preempted instance and prove it survives the stabilization window.

        Raises RuntimeError after PREEMPT_RESTART_ATTEMPTS failed restarts so
        the caller keeps the job paused and retries on a later pass.
        """
        for attempt in range(1, PREEMPT_RESTART_ATTEMPTS + 1):
            try:
                await self._manager.start_instance(instance_name)
            except asyncio.CancelledError:
                raise
            except NebiusCommandTimeout:
                # Do not issue another start while its previous outcome is
                # unknown. The durable pool owner will reconcile this target.
                raise
            except Exception as e:
                logger.warning(
                    f"Preemption recovery: start of {instance_name} attempt "
                    f"{attempt}/{PREEMPT_RESTART_ATTEMPTS} failed: {e}"
                )
                await asyncio.sleep(30)
                continue
            # start_instance just ensures RUNNING (it may have issued the
            # start, found it already RUNNING, or waited out STARTING/
            # CREATING). Which of those happened is not the point: only the
            # stabilization window proves a preemptible machine will stay up,
            # so always run it.
            stable_since: float | None = None
            error_since: float | None = None
            while True:
                await asyncio.sleep(10)
                try:
                    details = await self._manager.get_instance(instance_name)
                    state = details.get("status", {}).get("state")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception(f"Preemption recovery: state check failed for {instance_name}")
                    if "NotFound" in str(e):
                        raise RuntimeError(
                            f"Instance {instance_name} disappeared while stabilizing"
                        ) from e
                    if error_since is None:
                        error_since = _monotonic()
                    if _monotonic() - error_since >= PREEMPT_STABILIZE_ERROR_SECONDS:
                        raise RuntimeError(
                            f"Instance {instance_name} state checks failed for "
                            f"{PREEMPT_STABILIZE_ERROR_SECONDS}s while stabilizing"
                        ) from e
                    stable_since = None
                    continue
                error_since = None
                if state == "RUNNING":
                    if stable_since is None:
                        stable_since = _monotonic()
                    if _monotonic() - stable_since >= PREEMPT_STABLE_SECONDS:
                        logger.info(f"Preemption recovery: {instance_name} stable RUNNING for {PREEMPT_STABLE_SECONDS}s")
                        return
                elif state in ("STOPPED", "STOPPING"):
                    logger.warning(
                        f"Preemption recovery: {instance_name} preempted again while stabilizing "
                        f"(attempt {attempt}/{PREEMPT_RESTART_ATTEMPTS})"
                    )
                    break
                else:
                    raise RuntimeError(f"Instance {instance_name} entered {state} while stabilizing")
            await asyncio.sleep(30)
        raise RuntimeError(
            f"Instance {instance_name} was preempted {PREEMPT_RESTART_ATTEMPTS} times during recovery"
        )

    def has_busy_instance(self) -> bool:
        """True when any tracked Nebius instance currently hosts a job."""
        return any(state.job_running for state in self._instances.values())

    async def get_instance_state(self, instance_name: str) -> str | None:
        """Return the lifecycle state (RUNNING/STOPPED/...) of an instance.

        Raises when the Nebius API call fails (an outage signal); returns
        None when the payload lacks a usable state (a shape anomaly, which
        is neither evidence of preemption nor of an outage).
        """
        details = await self._manager.get_instance(instance_name)
        return details.get("status", {}).get("state")

    async def idle_cleanup_loop(self):
        """Periodically delete idle instances and evict stale entries."""
        while True:
            await asyncio.sleep(60)
            try:
                await self.cleanup_idle_instances()
            except Exception:
                logger.exception("Nebius idle cleanup failed")

    async def cleanup_idle_instances(self):
        """Perform one project-scoped cleanup pass, also usable by regional routing."""
        async with self._lock:
            if self._pool_guard_active and self._pool_guard_active():
                return
            now = time.time()
            to_delete = [
                name for name, state in self._instances.items()
                if not state.job_running and state.last_job_completed_at is not None
                and now - state.last_job_completed_at > self._idle_timeout
            ]
            for name in to_delete:
                logger.info(f"Deleting idle nebius instance {name}")
                await self._manager.delete_instance(name)
                del self._instances[name]
            to_evict = []
            for name, state in self._instances.items():
                if not state.job_running and not await self._manager.instance_exists(name):
                    to_evict.append(name)
            for name in to_evict:
                logger.warning(f"Evicting stale nebius instance {name} (no longer exists)")
                del self._instances[name]

    def get_instance_states(self) -> list[NebiusInstanceState]:
        """Return current state of all managed instances (in-memory, no CLI calls)."""
        return list(self._instances.values())


@dataclass(frozen=True)
class NebiusJobOwnership:
    """Read-only interpretation of a durable job's VM claim, not another journal.

    A cancelling legacy row without a location or recovery metadata may own the
    old VM, so it blocks conflicting work. Cancellation alone does not authorize
    deletion: a fresh intake cancelled during discovery has the same shape.
    """

    location: dict | None = None
    legacy: bool = False
    cleanup_legacy: bool = False

    @classmethod
    def from_job(cls, row: dict):
        """Interpret the store's placement, vacancy and legacy recovery signals."""
        if parse_nebius_url(row["server_url"]) is None:
            return cls()
        saved = row.get("nebius_location")
        if saved:
            return cls(location=json.loads(saved) if isinstance(saved, str) else saved)
        if row.get("nebius_vacant"):
            return cls()
        recovery = bool(row.get("pause_checkpointed")) or is_resume_command(json.loads(row["command"]))
        cleanup = recovery or row["status"] in ("running", "completing", "failing", "pausing", "paused")
        return cls(legacy=cleanup or row["status"] == "cancelling", cleanup_legacy=cleanup)

    @property
    def claimed(self) -> bool:
        """Whether this job must be considered before using the shared pool."""
        return self.location is not None or self.legacy

    def matches(self, location: dict, legacy: bool) -> bool:
        """Match a saved target exactly or a conservative legacy reservation."""
        if self.location is not None:
            return (self.location["project_id"], self.location["instance_name"]) == (location["project_id"], location["instance_name"])
        return self.legacy and legacy


class NebiusPool:
    """Coordinate the existing store and backend without owning worker state.

    Instances are lightweight views over explicit dependencies. Provider hooks
    retain the same store/backend; startup cleanup queries worker activity through
    the supplied callback so a retry cannot sweep a newly active job's VM.
    """

    def __init__(self, store, backend, *, cleanup_attempts: int,
                 cleanup_retry_seconds: float, worker_active: Callable[[], bool]):
        self.store = store
        self.backend = backend
        self.cleanup_attempts = cleanup_attempts
        self.cleanup_retry_seconds = cleanup_retry_seconds
        self.worker_active = worker_active

    def _other_owners(self, job_id: str | None):
        """Yield live ownership claims, excluding the worker's current job."""
        for owner in [*self.store.list_recoverable(), *self.store.list_paused()]:
            if owner["job_id"] != job_id:
                ownership = NebiusJobOwnership.from_job(owner)
                if ownership.claimed:
                    yield ownership

    def claimed_elsewhere(self, job_id: str | None, location: dict, legacy: bool) -> bool:
        """Protect the same durable owners used by allocation and recovery checks."""
        return any(owner.matches(location, legacy) for owner in self._other_owners(job_id))

    def configure(self, job_id: str | None) -> None:
        """Tie provider mutation tracking and idle cleanup to the durable pool."""
        callback = (lambda state, operation: self.store.update_nebius_guard(job_id, state, operation)) if job_id else None
        if isinstance(self.backend, (NebiusOrchestrator, RegionalNebiusOrchestrator)):
            self.backend.configure_provisioning(callback, lambda: self.store.nebius_guard() is not None,
                                               self.store.last_nebius_location())

    def begin(self, job_id: str, gpu_config: str) -> bool:
        """Own the pool before an initial allocation or preemption-recovery start."""
        if not self.store.claim_nebius_guard(job_id):
            return False
        self.configure(job_id)
        if isinstance(self.backend, (NebiusOrchestrator, RegionalNebiusOrchestrator)):
            location = self.backend.configured_location(gpu_config)
            if location:
                self.store.record_nebius_location(job_id, location)
        return True

    async def check_owners(self, job_id: str) -> None:
        """Allow another owner's stopped cache, never an additional running VM."""
        if not isinstance(self.backend, (NebiusOrchestrator, RegionalNebiusOrchestrator)):
            return
        current = NebiusJobOwnership.from_job(self.store.get(job_id))
        if isinstance(self.backend, NebiusOrchestrator) and current.location is not None and not current.matches(
            self.backend.configured_location(""), True,
        ):
            raise NebiusPoolBusy("Saved placement differs from current single-region configuration; reconcile the saved VM before allocating")
        owners = list(self._other_owners(job_id))
        placements = [owner.location for owner in owners]
        if isinstance(self.backend, NebiusOrchestrator):
            previous = self.store.last_nebius_location()
            if previous and not self.backend.is_legacy_placement(previous):
                # A configuration change must not hide the prior pool's running VM.
                placements.append(previous)
        await self.backend.check_other_placements(placements)
        if isinstance(self.backend, NebiusOrchestrator) and any(
            owner.matches(self.backend.configured_location(""), True) for owner in owners
        ):
            # Regional routing can select a different target beside a stopped cache;
            # single-region mode must not reuse/delete another owner's fixed VM.
            raise NebiusPoolBusy("Single-region Nebius placement is reserved by another recoverable job")

    async def retire_idle_for_recovery(self, row: dict) -> bool:
        """Retire a different idle VM before restarting this job's retained VM.

        Recovery precedes acquire_instance, so its normal idle replacement logic is
        too late. Journal the cleanup target in the guard while preserving the paused
        job's own placement; uncertainty must survive a restart and block dispatch.
        """
        previous = self.store.last_nebius_location()
        if not previous:
            return True
        legacy = self.backend.is_legacy_placement(previous)
        if NebiusJobOwnership.from_job(row).matches(previous, legacy):
            return True
        if self.claimed_elsewhere(row["job_id"], previous, legacy):
            return True  # The shared owner check already confirmed this cache stopped.
        if not self.store.claim_nebius_guard(row["job_id"]):
            return False
        if not self.store.record_nebius_idle_cleanup(row["job_id"], previous):
            return False
        return await self.reconcile(row, cleanup=True)

    async def reconcile(self, row: dict, *, cleanup: bool = False) -> bool:
        """Resolve the recorded target without interpreting a lost create as absent."""
        guard = self.store.nebius_guard()
        if not guard or guard["job_id"] != row["job_id"]:
            return guard is None
        record = ProvisioningRecord.from_row(guard)
        if record.untouched:
            # The durable pre-request hook was never reached (e.g. cancelled during
            # discovery). No mutating provider request can be outstanding.
            self.store.release_nebius_guard(row["job_id"])
            self.configure(None)
            return True
        self.configure(row["job_id"])
        saved = guard.get("location") or row.get("nebius_location")
        reason = "provider outcome is still unknown"
        try:
            if not saved:
                raise RuntimeError("no recorded placement; operator reconciliation is required")
            location = json.loads(saved) if isinstance(saved, str) else saved
            outcome = await reconcile_placement(
                self.backend, location, record, cleanup=cleanup,
                can_cleanup=lambda selected, legacy: not self.claimed_elsewhere(row["job_id"], selected, legacy),
                record_event=lambda phase, operation: self.store.update_nebius_guard(row["job_id"], phase, operation),
            )
            if outcome == ReconcileOutcome.ABSENT:
                self.store.release_nebius_guard(row["job_id"])
                self.configure(None)
            return True
        except Exception as error:
            reason = str(error)
            logger.warning("Nebius provisioning reconciliation pending for %s: %s", row["job_id"], reason)
        previous = (row.get("error") or "").split(" | Nebius reconciliation pending:")[0]
        message = f"Nebius reconciliation pending: {reason}"
        if cleanup and previous:
            message = previous + " | " + message
        self.store.wait_nebius_guard(row["job_id"], message)
        return False

    def bind(self, row: dict) -> None:
        """Restore ownership context; a fresh queued intake does not own the legacy VM."""
        if not isinstance(self.backend, RegionalNebiusOrchestrator):
            return
        job_id = row["job_id"]
        ownership = NebiusJobOwnership.from_job(row)
        self.backend.bind_job(
            ownership.location,
            lambda selected: self.store.record_nebius_location(job_id, selected),
            job_id=job_id, legacy_recovery=ownership.cleanup_legacy,
            can_use=lambda selected, legacy: not self.claimed_elsewhere(job_id, selected, legacy),
        )

    async def cleanup(self, job_id: str) -> None:
        """Retry scoped deletion, preserving unresolved guards and other owners."""
        assert self.backend is not None
        for attempt in range(1, self.cleanup_attempts + 1):
            guard = self.store.nebius_guard()
            if guard:
                # An unconfirmed provider request is never retired by a blind
                # name-based sweep, even if its job was cancelled meanwhile.
                if job_id == guard["job_id"]:
                    row = self.store.get(job_id)
                    if row:
                        await self.reconcile(row, cleanup=True)
                return
            if job_id == "startup" and self.worker_active():
                # A delayed startup retry must not follow a newly bound region.
                return
            row = self.store.get(job_id)
            ownership = NebiusJobOwnership.from_job(row) if row else NebiusJobOwnership()
            if job_id != "startup" and not ownership.claimed:
                return
            try:
                if job_id == "startup" and any(self._other_owners(None)):
                    return
                if isinstance(self.backend, RegionalNebiusOrchestrator):
                    if job_id == "startup":
                        # Re-check durable jobs during discovery and on every retry.
                        await self.backend.cleanup_startup_instances(
                            can_use=lambda selected, legacy: not self.claimed_elsewhere(None, selected, legacy),
                        )
                    else:
                        row = self.store.get(job_id)
                        if not row or parse_nebius_url(row["server_url"]) is None:
                            return
                        self.bind(row)
                        await self.backend.delete_recovered_instance()
                elif isinstance(self.backend, NebiusOrchestrator):
                    if job_id != "startup" and ownership.location is None and not ownership.cleanup_legacy:
                        return
                    location = ownership.location or self.backend.configured_location("")
                    if self.claimed_elsewhere(job_id, location, True):
                        return
                    await self.backend.delete_placement(location)
                else:
                    await self.backend.delete_recovered_instance()
                return
            except Exception:
                logger.exception(
                    f"Unable to delete recovered Nebius instance for {job_id} "
                    f"(attempt {attempt}/{self.cleanup_attempts})"
                )
                if attempt < self.cleanup_attempts:
                    await asyncio.sleep(self.cleanup_retry_seconds)
        logger.error(f"Nebius cleanup exhausted for {job_id}; advancing recovery")
