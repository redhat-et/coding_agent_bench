import shlex
import shutil
import subprocess
import asyncio
import json


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

    def __init__(self, job_name: str):
        self._job_name = job_name
        self._pod_name = f"coding-agent-bench--{self._job_name}"[:58]

    def _resume_job_spec(self, shell_command: str) -> dict:
        """Build a pod spec for a resume job with a raw shell command."""
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": self._pod_name, "labels": {"app": "harbor"}},
            "spec": {
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "serviceAccountName": "harbor-orchestrator",
                        "volumes": [{"name": "jobs", "type": "emptyDir"}],
                        "containers": [
                            {
                                "name": "harbor",
                                "image": "ghcr.io/redhat-et/coding_agent_bench:latest",
                                "imagePullPolicy": "Always",
                                "command": ["sh", "-c"],
                                "args": [shell_command],
                                "env": [
                                    {"name": "HOME", "value": "/tmp"},
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

    def _job_spec(self, command: list[str], before_script: list[str] = None) -> dict:
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": self._pod_name, "labels": {"app": "harbor"}},
            "spec": {
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "serviceAccountName": "harbor-orchestrator",
                        "volumes": [{"name": "jobs", "type": "emptyDir"}],
                        "containers": [
                            {
                                "name": "harbor",
                                "image": "ghcr.io/redhat-et/coding_agent_bench:latest",
                                "imagePullPolicy": "Always",
                                "command": ["sh", "-c"],
                                "args": [
                                    ("" if before_script is None else (shlex.join(before_script) + " && "))
                                    + "uv run --no-sync --no-cache "
                                    + shlex.join(command) + ";"
                                    + " mc alias set minio http://harbor-minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD"
                                    + " && mc mb --ignore-existing minio/results"
                                    + " && mc cp --recursive /app/jobs/ minio/results/"
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
        except asyncio.TimeoutError:
            process.terminate()
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=5
                )
            except asyncio.TimeoutError:
                process.kill()
                stdout_bytes, stderr_bytes = await process.communicate()
            raise RuntimeError(
                f"oc command timed out after {timeout_sec} seconds: "
                f"{' '.join(full_command)}"
            )

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

    async def _signal_job_pod(self) -> None:
        """Send SIGTERM to the harbor process inside the job pod so it
        can run its own cleanup (stopping task pods via
        OpenshiftEnvironment.stop)."""
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
            ["exec", pod_name, "--", "kill", "-TERM", "1"],
            check=False,
        )

        for _ in range(30):
            result_stdout, _ = await self._run_oc_command(
                [
                    "get", "pod", pod_name,
                    "-o", "jsonpath={.status.phase}",
                ],
                check=False,
            )
            phase = (result_stdout or "").strip()
            if phase in ("Succeeded", "Failed", ""):
                break
            await asyncio.sleep(2)

    async def _delete_harbor_pods(self):
        """Delete all pods spawned by harbor that are associated with this job."""
        await self._run_oc_command(
            ["delete", "pods", f"--selector=harbor-parent={self._pod_name}", "--ignore-not-found"],
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

    async def run_async(self, command: list[str], before_script: list[str] = None):
        job_spec = self._job_spec(command, before_script)
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

    def run(self, command: list[str], before_script: list[str] = None):
        return asyncio.run(self.run_async(command, before_script))

    async def _cleanup_async(self):
        await self._signal_job_pod()
        await self._delete_job()

    def cleanup(self):
        asyncio.run(self._cleanup_async())
