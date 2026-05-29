import asyncio
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import EnvironmentPaths, TrialPaths


def _sanitize_k8s_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    if not name or not name[0].isalnum():
        name = "hb-" + name
    return name[:58]


class OpenshiftEnvironment(BaseEnvironment):
    _image_build_locks: dict[str, asyncio.Lock] = {}

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

    def __init__(
        self,
        environment_dir: Path,
        environment_name: str,
        session_id: str,
        trial_paths: TrialPaths,
        task_env_config: EnvironmentConfig,
        namespace: str | None = None,
        **kwargs,
    ):
        super().__init__(
            environment_dir=environment_dir,
            environment_name=environment_name,
            session_id=session_id,
            trial_paths=trial_paths,
            task_env_config=task_env_config,
            **kwargs,
        )

        self._namespace = namespace
        self._pod_name = _sanitize_k8s_name(f"hb-{session_id}")
        self._build_name = _sanitize_k8s_name(f"hb-build-{environment_name}")
        self._image_name: str | None = None
        self._log_streamer: asyncio.subprocess.Process | None = None
        self._log_file_handle = None
        self._env_paths = EnvironmentPaths()

    @staticmethod
    def type() -> str:
        return "openshift"

    @property
    def is_mounted(self) -> bool:
        return False

    @property
    def supports_gpus(self) -> bool:
        return False

    @property
    def can_disable_internet(self) -> bool:
        return False

    @property
    def _dockerfile_path(self) -> Path:
        return self.environment_dir / "Dockerfile"

    def _validate_definition(self):
        if not self._dockerfile_path.exists() and not self.task_env_config.docker_image:
            raise FileNotFoundError(
                f"No Dockerfile found at {self._dockerfile_path} and no "
                "docker_image configured. At least one must be provided."
            )

    def _ns_args(self) -> list[str]:
        if self._namespace:
            return ["-n", self._namespace]
        return []

    async def _run_oc_command(
        self,
        command: list[str],
        check: bool = True,
        timeout_sec: int | None = None,
        stdin_data: bytes | None = None,
    ) -> ExecResult:
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

        result = ExecResult(
            stdout=stdout,
            stderr=stderr,
            return_code=process.returncode or 0,
        )

        if check and result.return_code != 0:
            raise RuntimeError(
                f"oc command failed: {' '.join(full_command)}. "
                f"Return code: {result.return_code}. "
                f"Stdout: {result.stdout}. "
                f"Stderr: {result.stderr}."
            )

        return result

    async def _build_image(self) -> str:
        lock = self._image_build_locks.setdefault(self.environment_name, asyncio.Lock())
        async with lock:
            existing = await self._run_oc_command(
                ["get", "bc", self._build_name, *self._ns_args(), "-o", "name"],
                check=False,
            )
            if existing.return_code != 0:
                await self._run_oc_command(
                    [
                        "new-build",
                        "--binary",
                        f"--name={self._build_name}",
                        "--strategy=docker",
                        *self._ns_args(),
                    ],
                    timeout_sec=int(self.task_env_config.build_timeout_sec),
                )

            await self._run_oc_command(
                [
                    "start-build",
                    self._build_name,
                    f"--from-dir={self.environment_dir.resolve().absolute()}",
                    "--follow",
                    "--wait",
                    *self._ns_args(),
                ],
                timeout_sec=int(self.task_env_config.build_timeout_sec),
            )

        is_result = await self._run_oc_command(
            [
                "get",
                "is",
                self._build_name,
                *self._ns_args(),
                "-o",
                "jsonpath={.status.dockerImageRepository}",
            ]
        )
        return (is_result.stdout or "").strip()

    def _pod_spec(self, image: str) -> dict:
        env_list = []
        merged_env = {**self._persistent_env}
        if self.task_env_config.env:
            merged_env.update(self.task_env_config.env)
        for k, v in merged_env.items():
            env_list.append({"name": k, "value": v})

        resources = {
            "requests": {
                "cpu": str(self.task_env_config.cpus),
                "memory": f"{self.task_env_config.memory_mb}Mi",
            },
            "limits": {
                "cpu": str(self.task_env_config.cpus),
                "memory": f"{self.task_env_config.memory_mb}Mi",
            },
        }

        pod = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self._pod_name,
                "labels": {
                    "app": "harbor",
                    "harbor-session": self._pod_name,
                },
            },
            "spec": {
                "restartPolicy": "Never",
                # Use a dedicated service account with the anyuid SCC so
                # the container can run as root.  CRI-O mounts / read-only
                # for non-root UIDs, and the harbor test harness writes
                # files to / (via cd .. from /tests).
                # Apply the SA + RoleBinding with:
                #   oc apply -f deploy/harbor-rbac.yml -n <ns>
                "serviceAccountName": "harbor-agent",
                "securityContext": {"runAsUser": 0},
                "containers": [
                    {
                        "name": "main",
                        "image": image,
                        "command": ["tail", "-f", "/dev/null"],
                        "env": env_list,
                        "resources": resources,
                    }
                ],
            },
        }
        return pod

    async def _start_log_streaming(self) -> None:
        log_path = self.trial_paths.agent_dir / "pod-stdout.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file_handle = open(log_path, "w")
        cmd = ["oc", "logs", "-f", self._pod_name, "-c", "main", *self._ns_args()]
        self._log_streamer = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=self._log_file_handle,
            stderr=self._log_file_handle,
            stdin=asyncio.subprocess.DEVNULL,
        )
        self.logger.debug(f"Started log streaming to {log_path}")

    async def _stop_log_streaming(self) -> None:
        if self._log_streamer is not None:
            try:
                self._log_streamer.terminate()
                await asyncio.wait_for(self._log_streamer.wait(), timeout=5)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self._log_streamer.kill()
                except ProcessLookupError:
                    pass
            self._log_streamer = None
        if self._log_file_handle is not None:
            self._log_file_handle.close()
            self._log_file_handle = None

    async def start(self, force_build: bool) -> None:
        use_prebuilt = not force_build and self.task_env_config.docker_image

        if use_prebuilt:
            self._image_name = self.task_env_config.docker_image
        else:
            self._image_name = await self._build_image()

        # Clean up any stale pod from a previous run with the same session ID.
        await self._run_oc_command(
            ["delete", "pod", self._pod_name, *self._ns_args(), "--ignore-not-found"],
            check=False,
        )

        pod_spec = self._pod_spec(self._image_name)
        pod_json = json.dumps(pod_spec)

        await self._run_oc_command(
            ["apply", "-f", "-", *self._ns_args()],
            stdin_data=pod_json.encode(),
        )

        await self._run_oc_command(
            [
                "wait",
                f"pod/{self._pod_name}",
                "--for=condition=Ready",
                "--timeout=300s",
                *self._ns_args(),
            ],
            timeout_sec=310,
        )

        await self.exec(
            f"mkdir -p {self._env_paths.agent_dir} {self._env_paths.verifier_dir} "
            f"{self._env_paths.artifacts_dir} && "
            f"chmod 777 {self._env_paths.agent_dir} {self._env_paths.verifier_dir}"
        )

        await self._start_log_streaming()

    async def stop(self, delete: bool):
        await self._stop_log_streaming()
        try:
            await self._run_oc_command(
                [
                    "delete",
                    "pod",
                    self._pod_name,
                    *self._ns_args(),
                    "--grace-period=10",
                ],
                check=False,
            )
        except Exception as e:
            self.logger.warning(f"Failed to delete pod {self._pod_name}: {e}")

        if delete:
            for resource in [
                f"bc/{self._build_name}",
                f"is/{self._build_name}",
            ]:
                try:
                    await self._run_oc_command(
                        [
                            "delete",
                            resource,
                            *self._ns_args(),
                            "--ignore-not-found",
                        ],
                        check=False,
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to delete {resource}: {e}")

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
        user: str | int | None = None,
    ) -> ExecResult:
        user = self._resolve_user(user)
        env = self._merge_env(env)

        shell_parts = []
        if env:
            for key, value in env.items():
                shell_parts.append(f"export {key}={shlex.quote(value)}")

        effective_cwd = cwd or self.task_env_config.workdir
        if effective_cwd:
            shell_parts.append(f"cd {shlex.quote(effective_cwd)}")

        shell_parts.append(command)
        shell_command = " && ".join(shell_parts)

        exec_command = ["exec", self._pod_name, "-c", "main", *self._ns_args(), "--"]

        if user is not None:
            exec_command.extend([
                "runuser", "-s", "/bin/bash", str(user), "-c", shell_command,
            ])
        else:
            exec_command.extend(["bash", "-c", shell_command])

        return await self._run_oc_command(
            exec_command, check=False, timeout_sec=timeout_sec
        )

    async def upload_file(self, source_path: Path | str, target_path: str):
        await self._run_oc_command(
            [
                "cp",
                str(source_path),
                f"{self._pod_name}:{target_path}",
                "-c",
                "main",
                *self._ns_args(),
            ]
        )

    async def upload_dir(self, source_dir: Path | str, target_dir: str):
        # Use trailing "/." to copy the *contents* of source_dir into
        # target_dir, matching podman cp behavior.  Without this,
        # "oc cp /path/to/tests pod:/tests" creates /tests/tests/ instead
        # of placing the files directly under /tests/.
        source = f"{Path(source_dir).resolve()}/."
        await self._run_oc_command(
            [
                "cp",
                source,
                f"{self._pod_name}:{target_dir}",
                "-c",
                "main",
                *self._ns_args(),
            ]
        )

    async def download_file(self, source_path: str, target_path: Path | str):
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        await self._run_oc_command(
            [
                "cp",
                f"{self._pod_name}:{source_path}",
                str(target_path),
                "-c",
                "main",
                *self._ns_args(),
            ]
        )

    async def download_dir(self, source_dir: str, target_dir: Path | str):
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        # Trailing "/." copies contents, matching podman cp behavior.
        await self._run_oc_command(
            [
                "cp",
                f"{self._pod_name}:{source_dir}/.",
                str(target_dir),
                "-c",
                "main",
                *self._ns_args(),
            ]
        )

    async def attach(self) -> None:
        cmd = ["oc", "rsh", *self._ns_args(), "-c", "main", self._pod_name]
        os.execvp("oc", cmd)
