import shlex
import shutil
import subprocess
import asyncio
import logging
import os

import json

from coding_agent_bench.preemption import PAUSE_REQUEST_PATH


DEFAULT_CODING_AGENT_BENCH_IMAGE = "ghcr.io/redhat-et/coding_agent_bench:latest"


def _job_image() -> str:
    """Allow isolated deployments to run the queue's matching image."""
    return os.environ.get("CODING_AGENT_BENCH_IMAGE", DEFAULT_CODING_AGENT_BENCH_IMAGE)


logger = logging.getLogger(__name__)


def _build_logged_shell_step(command: list[str], job_dir: str) -> str:
    """Stream command output to the pod and console.log, retaining both exit codes.

    The caller must use Bash and upload results before exiting with harbor_rc.
    Append mode preserves console output from earlier resume attempts.
    """
    return (
        f"mkdir -p {shlex.quote(job_dir)} || exit $?; "
        f"{shlex.join(command)} 2>&1 | tee -a {shlex.quote(job_dir + '/console.log')}; "
        'harbor_status=("${PIPESTATUS[@]}"); harbor_rc=${harbor_status[0]}; '
        'if [ "$harbor_rc" -eq 0 ]; then harbor_rc=${harbor_status[1]}; fi;'
    )


class OpenshiftJob:
    @classmethod
    def preflight(cls) -> None:
        if not shutil.which("oc"):
            raise SystemExit(
                "oc CLI is not installed or not on PATH. "
                "Please install the OpenShift CLI and try again."
            )
        try:
            subprocess.run(
                ["oc", "whoami"],
                capture_output=True,
                timeout=10,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            raise SystemExit(
                "Not logged in to an OpenShift cluster. "
                "Please run 'oc login' and try again."
            )

    def __init__(self, job_name: str, clean_legacy_pods: bool = False):
        self._job_name = job_name
        self._pod_name = f"coding-agent-bench--{self._job_name}"[:58]
        self._clean_legacy_pods = clean_legacy_pods

    def _resume_job_spec(self, shell_command: str) -> dict:
        """Build a pod spec for a resume job with a raw shell command."""
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": self._pod_name, "labels": {"app": "harbor"}},
            "spec": {
                "backoffLimit": 0,
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "serviceAccountName": "harbor-orchestrator",
                        "volumes": [{"name": "jobs", "type": "emptyDir"}],
                        "containers": [
                            {
                                "name": "harbor",
                                "image": _job_image(),
                                "imagePullPolicy": "Always",
                                "command": ["bash", "-c"],
                                "args": [shell_command],
                                "env": [
                                    {"name": "HOME", "value": "/tmp"},
                                    {"name": "HARBOR_PARENT", "value": self._pod_name},
                                    {"name": "CAB_PAUSE_REQUEST_PATH", "value": PAUSE_REQUEST_PATH},
                                ],
                                "volumeMounts": [{"name": "jobs", "mountPath": "/app/jobs"}],
                                "envFrom": [
                                    {"secretRef": {"name": "harbor-minio"}}
                                ],
                            }
                        ],
                    }
                }
            },
        }

    def _job_spec(
        self,
        command: list[str],
        before_script: list[str] = None,
        openrouter: bool = False,
    ) -> dict:
        """Build a benchmark pod that logs output and uploads results before exit."""
        # Queue pod names use the job UUID; artifacts use Harbor's --job-name.
        artifact_name = self._job_name
        for index, arg in enumerate(command):
            if arg == "--job-name" and index + 1 < len(command):
                artifact_name = command[index + 1]
            elif arg.startswith("--job-name="):
                artifact_name = arg.split("=", 1)[1]
        logged_command = _build_logged_shell_step(
            ["uv", "run", "--no-sync", "--no-cache", *command],
            f"/app/jobs/{artifact_name}",
        )
        # Only openrouter jobs need the OpenRouter key, so scope the secret to
        # them rather than exposing it to every job pod.
        env: list[dict] = [
            {"name": "HARBOR_PARENT", "value": self._pod_name},
            {"name": "CAB_PAUSE_REQUEST_PATH", "value": PAUSE_REQUEST_PATH},
        ]
        if openrouter:
            env.append(
                {
                    "name": "OPENROUTER_API_KEY",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "openrouter-api-key",
                            "key": "OPENROUTER_API_KEY",
                            "optional": True,
                        }
                    },
                }
            )
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": self._pod_name, "labels": {"app": "harbor"}},
            "spec": {
                "backoffLimit": 0,
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "serviceAccountName": "harbor-orchestrator",
                        "volumes": [{"name": "jobs", "type": "emptyDir"}],
                        "containers": [
                            {
                                "name": "harbor",
                                "image": _job_image(),
                                "imagePullPolicy": "Always",
                                "command": ["bash", "-c"],
                                "args": [
                                    # Preserve partial results without hiding Harbor's failure.
                                    ("" if before_script is None else (shlex.join(before_script) + " || exit $?; "))
                                    + logged_command
                                    + " export AWS_ACCESS_KEY_ID=\"$MINIO_ROOT_USER\""
                                    + " AWS_SECRET_ACCESS_KEY=\"$MINIO_ROOT_PASSWORD\""
                                    + " AWS_DEFAULT_REGION=us-east-1"
                                    + " AWS_EC2_METADATA_DISABLED=true"
                                    + " && (uv run --no-sync --no-cache aws --endpoint-url http://harbor-minio:9000"
                                    + " s3api head-bucket --bucket results >/dev/null 2>&1"
                                    + " || uv run --no-sync --no-cache aws --endpoint-url http://harbor-minio:9000"
                                    + " s3 mb s3://results"
                                    # A concurrent job may have created the bucket first.
                                    + " || uv run --no-sync --no-cache aws --endpoint-url http://harbor-minio:9000"
                                    + " s3api head-bucket --bucket results)"
                                    + " && uv run --no-sync --no-cache aws --endpoint-url http://harbor-minio:9000"
                                    + " s3 cp --recursive /app/jobs/ s3://results/"
                                    + " || exit $?; exit \"$harbor_rc\""
                                ],
                                "env": env,
                                "volumeMounts": [{"name": "jobs", "mountPath": "/app/jobs"}],
                                "envFrom": [
                                    {"secretRef": {"name": "harbor-minio"}}
                                ],
                            }
                        ],
                    }
                }
            },
        }

    async def _run_oc_command(
        self,
        command: list[str],
        check: bool = True,
        timeout_sec: int | None = None,
        stdin_data: bytes | None = None,
    ) -> tuple[str, str]:
        full_command = ["oc"] + command

        process = await asyncio.create_subprocess_exec(
            *full_command,
            stdin=asyncio.subprocess.PIPE if stdin_data else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            if timeout_sec:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(input=stdin_data), timeout=timeout_sec
                )
            else:
                stdout_bytes, stderr_bytes = await process.communicate(input=stdin_data)
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            process.terminate()
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=5
                )
            except asyncio.TimeoutError:
                process.kill()
                stdout_bytes, stderr_bytes = await process.communicate()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise RuntimeError(f"oc command timed out after {timeout_sec} seconds: {' '.join(full_command)}")

        stdout = stdout_bytes.decode(errors="replace") if stdout_bytes else None
        stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else None
        return_code = process.returncode or 0

        if check and return_code != 0:
            raise RuntimeError(
                f"oc command failed: {' '.join(full_command)}. "
                f"Return code: {return_code}. "
                f"Stdout: {stdout}. "
                f"Stderr: {stderr}."
            )

        return stdout, stderr

    async def _get_job(self) -> dict | None:
        """Return the OpenShift Job resource, or None when it does not exist."""
        try:
            stdout, _ = await self._run_oc_command(
                ["get", f"job/{self._pod_name}", "-o", "json"],
                timeout_sec=30,
            )
        except RuntimeError as exc:
            if "notfound" in str(exc).lower() or "not found" in str(exc).lower():
                return None
            raise
        if not stdout:
            raise RuntimeError(f"oc returned no data for job/{self._pod_name}")
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"oc returned invalid JSON for job/{self._pod_name}") from exc

    async def request_pause(self, reason: str, wait_seconds: int = 600) -> bool:
        """Cancel trials cooperatively and wait for successful result upload.

        Unlike user cancellation, a preemption must not kill the Harbor process
        or parent pod: the plugin records pending trials and the shell uploads
        them. False means the caller must retain the parent and retry later.
        """
        stdout, _ = await self._run_oc_command(
            ["get", "pod", f"--selector=job-name={self._pod_name}", "-o", "json"],
            timeout_sec=30,
        )
        pods = json.loads(stdout or "{}").get("items", [])
        pod = next((p for p in pods if p.get("status", {}).get("phase") == "Running"), None)
        if pod is None:
            return False
        environment = [
            e for c in pod.get("spec", {}).get("containers", []) for e in c.get("env", [])
        ]
        if not any(e.get("name") == "CAB_PAUSE_REQUEST_PATH" for e in environment):
            raise RuntimeError("Parent pod predates cooperative pause support; retaining it for manual recovery")
        script = (
            "import json, pathlib, datetime; "
            f"path = pathlib.Path({PAUSE_REQUEST_PATH!r}); "
            f"request = {{'reason': {reason!r}, "
            "'requested_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}; "
            "temporary = path.with_suffix('.tmp'); "
            "temporary.write_text(json.dumps(request)); temporary.replace(path)"
        )
        await self._run_oc_command(
            ["exec", pod["metadata"]["name"], "-c", "harbor", "--", "python3", "-c", script],
            timeout_sec=30,
        )
        deadline = asyncio.get_running_loop().time() + wait_seconds
        while True:
            job = await self._get_job()
            conditions = {
                c.get("type") for c in (job or {}).get("status", {}).get("conditions", [])
                if c.get("status") == "True"
            }
            if "Complete" in conditions:
                return True  # The shell reports success only after the S3 upload.
            if "Failed" in conditions or job is None:
                return False
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(2)

    async def _signal_job_pod(self, wait_seconds: int = 60) -> bool | None:
        """Send SIGTERM to the harbor process inside the job pod so it
        can run its own cleanup (stopping task pods via
        OpenshiftEnvironment.stop).

        Waits up to wait_seconds for the pod to exit; the pod's script
        uploads results to MinIO after harbor returns, so pausing passes a
        budget large enough to cover that upload before the job is deleted.
        Returns True if the pod reached a terminal phase within the budget,
        False if it was still running when the wait expired (the checkpoint
        upload may then be incomplete), or None if no job pod existed.
        """
        stdout, _ = await self._run_oc_command(
            [
                "get", "pod",
                f"--selector=job-name={self._pod_name}",
                "-o", "jsonpath={.items[0].metadata.name}",
            ],
            check=False,
        )
        pod_name = (stdout or "").strip()
        if not pod_name:
            return

        await self._run_oc_command(
            [
                "exec", pod_name, "--", "sh", "-c",
                "for f in /proc/[0-9]*/cmdline; do "
                "pid=${f#/proc/}; pid=${pid%/cmdline}; "
                "[ \"$pid\" = 1 ] && continue; "
                "[ \"$pid\" = \"$$\" ] && continue; "
                "cmd=$(tr '\\0' ' ' < \"$f\" 2>/dev/null) || continue; "
                "case \"$cmd\" in *'harbor run'*|*'harbor jobs resume'*) "
                "kill -TERM \"$pid\" 2>/dev/null || true;; esac; done",
            ],
            check=False,
        )

        for _ in range(max(1, wait_seconds // 2)):
            result_stdout, _ = await self._run_oc_command(
                [
                    "get", "pod", pod_name,
                    "-o", "jsonpath={.status.phase}",
                ],
                check=False,
            )
            phase = (result_stdout or "").strip()
            if phase in ("Succeeded", "Failed", ""):
                return True
            await asyncio.sleep(2)

        logger.warning(
            f"Job pod {pod_name} still {phase or 'running'} after {wait_seconds}s wait"
        )
        return False

    async def _delete_harbor_pods(self):
        """Delete task pods whose environment identifies this parent Job."""
        stdout, _ = await self._run_oc_command(
            ["get", "pods", "--selector=app=harbor,harbor-session", "-o", "json"],
            timeout_sec=60,
        )
        pods = json.loads(stdout or "{}").get("items", [])
        pod_names = []
        for pod in pods:
            env = [
                item
                for container in pod.get("spec", {}).get("containers", [])
                for item in container.get("env", [])
            ]
            has_parent = any(item.get("name") == "HARBOR_PARENT" for item in env)
            matches_parent = any(
                item.get("name") == "HARBOR_PARENT"
                and item.get("value") == self._pod_name
                for item in env
            )
            labels = pod.get("metadata", {}).get("labels", {})
            matches_legacy_parent = (
                self._clean_legacy_pods
                and not has_parent
                and labels.get("harbor-parent") == self._pod_name
            )
            if matches_parent or matches_legacy_parent:
                pod_names.append(pod["metadata"]["name"])
        if not pod_names:
            return
        await self._run_oc_command(
            ["delete", "pods", *pod_names, "--ignore-not-found"],
            timeout_sec=60,
        )

    async def _delete_job(self):
        """Delete the job and assoicated pods."""
        delete_error = None
        try:
            await self._run_oc_command(
                ["delete", f"job/{self._pod_name}", "--cascade=foreground", "--ignore-not-found"],
                timeout_sec=60,
            )
        except Exception as exc:
            delete_error = exc
        finally:
            await self._delete_harbor_pods()

        if delete_error:
            raise delete_error

    async def _wait_for_job_pod_ready(self, timeout_sec: int = 300) -> None:
        """Wait for the job pod to be ready."""
        for elapsed in range(timeout_sec):
            stdout, _ = await self._run_oc_command(
                [
                    "get",
                    "pod",
                    f"--selector=job-name={self._pod_name}",
                    "-o",
                    "json",
                ],
                check=False,
            )
            if not stdout:
                if elapsed % 10 == 0:
                    print(
                        f"No pods found for job {self._pod_name} ({elapsed}s elapsed)"
                    )
                await asyncio.sleep(1)
                continue

            pods = json.loads(stdout).get("items", [])
            if not pods:
                await asyncio.sleep(1)
                continue

            pod = pods[0]
            phase = pod.get("status", {}).get("phase", "")

            if phase == "Running":
                container_statuses = pod.get("status", {}).get(
                    "containerStatuses", []
                )
                if container_statuses and all(
                    cs.get("ready") for cs in container_statuses
                ):
                    return

            elif phase == "Succeeded":
                return

            elif phase in ("Failed", "Unknown", "Error"):
                reason = pod.get("status", {}).get("reason", "")
                message = pod.get("status", {}).get("message", "")
                raise RuntimeError(
                    f"Job pod for {self._pod_name} entered terminal phase "
                    f"'{phase}': reason={reason}, message={message}"
                )

            elif phase == "Pending":
                for cs in pod.get("status", {}).get("containerStatuses", []):
                    waiting = cs.get("state", {}).get("waiting", {})
                    waiting_reason = waiting.get("reason", "")
                    if waiting_reason in ("ImagePullBackOff", "ErrImagePull"):
                        raise RuntimeError(
                            f"Failed to pull image for job {self._pod_name}: "
                            f"{waiting.get('message', waiting_reason)}"
                        )

            if elapsed % 10 == 0:
                print(
                    f"Job pod status: {phase} ({elapsed}s elapsed)"
                )

            await asyncio.sleep(1)

        raise RuntimeError(
            f"Job pod for {self._pod_name} not ready after {timeout_sec} seconds"
        )

    async def run_async(
        self,
        command: list[str],
        before_script: list[str] = None,
        openrouter: bool = False,
    ):
        job_spec = self._job_spec(command, before_script, openrouter=openrouter)
        job_json = json.dumps(job_spec)

        try:
            await self._run_oc_command(
                ["apply", "-f", "-"],
                stdin_data=job_json.encode(),
            )

            await self._wait_for_job_pod_ready()
        except (asyncio.CancelledError, KeyboardInterrupt):
            await self._signal_job_pod()
            await self._delete_job()
            raise
        except BaseException:
            await self._delete_job()
            raise

    def run(
        self,
        command: list[str],
        before_script: list[str] = None,
        openrouter: bool = False,
    ):
        return asyncio.run(
            self.run_async(command, before_script, openrouter=openrouter)
        )

    async def _cleanup_async(self):
        await self._signal_job_pod()
        await self._delete_job()

    def cleanup(self):
        asyncio.run(self._cleanup_async())
