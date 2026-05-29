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

    def __init__(self):
        self._pod_name = "coding-agent-bench"

    def _job_spec(self, command: list[str]) -> dict:
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": self._pod_name, "labels": {"app": "harbor"}},
            "spec": {
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "serviceAccountName": "harbor-orchestrator",
                        "containers": [
                            {
                                "name": "harbor",
                                "image": "ghcr.io/redhat-et/coding_agent_bench:latest",
                                "command": ["uv", "run", "--no-sync", "--no-cache", *command],
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

    async def _delete_job(self):
        await self._run_oc_command(
            ["delete", f"job/{self._pod_name}", "--ignore-not-found"],
            check=False,
        )

    async def run_async(self, command: list[str]):
        job_spec = self._job_spec(command)
        job_json = json.dumps(job_spec)

        try:
            await self._run_oc_command(
                ["apply", "-f", "-"],
                stdin_data=job_json.encode(),
            )

            await self._run_oc_command(
                [
                    "wait",
                    f"pod",
                    f"--selector=job-name={self._pod_name}",
                    "--for=condition=Ready",
                    "--timeout=300s",
                ],
                timeout_sec=310,
            )
        except BaseException:
            await self._delete_job()
            raise

    def run(self, command: list[str]):
        return asyncio.run(self.run_async(command))
