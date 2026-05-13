import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path

from harbor.environments.base import BaseEnvironment, ExecResult
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import EnvironmentPaths, TrialPaths


def _sanitize_container_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9_.-]", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    if not name or not name[0].isalnum():
        name = "hb-" + name
    return name[:63]


def _sanitize_image_name(name: str) -> str:
    name = name.lower()
    if not re.match(r"^[a-z0-9]", name):
        name = "0" + name
    name = re.sub(r"[^a-z0-9._-]", "-", name)
    return name


class PodmanEnvironment(BaseEnvironment):
    _image_build_locks: dict[str, asyncio.Lock] = {}

    @classmethod
    def preflight(cls) -> None:
        if not shutil.which("podman"):
            raise SystemExit(
                "podman is not installed or not on PATH. "
                "Please install Podman and try again."
            )
        try:
            subprocess.run(
                ["podman", "info"],
                capture_output=True,
                timeout=15,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            raise SystemExit(
                "Podman is not operational. "
                "Please ensure the Podman machine is running and try again."
            )

    def __init__(
        self,
        environment_dir: Path,
        environment_name: str,
        session_id: str,
        trial_paths: TrialPaths,
        task_env_config: EnvironmentConfig,
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

        self._container_name = _sanitize_container_name(f"hb-{session_id}")
        self._image_name = _sanitize_image_name(f"hb__{environment_name}")
        self._built_image: str | None = None
        self._env_paths = EnvironmentPaths()

    @staticmethod
    def type() -> str:
        return "podman"

    @property
    def supports_gpus(self) -> bool:
        return False

    @property
    def can_disable_internet(self) -> bool:
        return False

    @property
    def is_mounted(self) -> bool:
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

    async def _run_podman(
        self,
        args: list[str],
        check: bool = True,
        timeout_sec: int | None = None,
        stdin_data: bytes | None = None,
    ) -> ExecResult:
        cmd = ["podman"] + args

        process = await asyncio.create_subprocess_exec(
            *cmd,
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
                f"podman command timed out after {timeout_sec}s: {' '.join(cmd)}"
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
                f"podman command failed: {' '.join(cmd)}. "
                f"Return code: {result.return_code}. "
                f"Stdout: {result.stdout}. "
                f"Stderr: {result.stderr}."
            )

        return result

    async def _build_image(self) -> str:
        lock = self._image_build_locks.setdefault(self.environment_name, asyncio.Lock())
        async with lock:
            await self._run_podman(
                [
                    "build",
                    "-t",
                    self._image_name,
                    str(self.environment_dir.resolve().absolute()),
                ],
                timeout_sec=int(self.task_env_config.build_timeout_sec),
            )
        return self._image_name

    async def start(self, force_build: bool) -> None:
        use_prebuilt = not force_build and self.task_env_config.docker_image

        if use_prebuilt:
            self._built_image = self.task_env_config.docker_image
        else:
            self._built_image = await self._build_image()

        await self._run_podman(
            ["rm", "-f", self._container_name],
            check=False,
        )

        run_args = [
            "run",
            "-d",
            "--name",
            self._container_name,
            "--cpus",
            str(self.task_env_config.cpus),
            "--memory",
            f"{self.task_env_config.memory_mb}m",
        ]

        merged_env = {**self._persistent_env}
        if self.task_env_config.env:
            merged_env.update(self.task_env_config.env)
        for key, value in merged_env.items():
            run_args.extend(["--env", f"{key}={value}"])

        run_args.extend([self._built_image, "tail", "-f", "/dev/null"])

        await self._run_podman(run_args)

        await self._run_podman(
            ["wait", "--condition=running", self._container_name],
            timeout_sec=60,
        )

        await self.exec(
            f"mkdir -p {self._env_paths.agent_dir} {self._env_paths.verifier_dir} "
            f"{self._env_paths.artifacts_dir} && "
            f"chmod 777 {self._env_paths.agent_dir} {self._env_paths.verifier_dir}"
        )

    async def stop(self, delete: bool):
        try:
            await self._run_podman(
                ["rm", "-f", self._container_name],
                check=False,
            )
        except Exception as e:
            self.logger.warning(
                f"Failed to remove container {self._container_name}: {e}"
            )

        if delete and self._built_image:
            try:
                await self._run_podman(
                    ["rmi", "-f", self._built_image],
                    check=False,
                )
            except Exception as e:
                self.logger.warning(f"Failed to remove image {self._built_image}: {e}")

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

        exec_args = ["exec"]

        effective_cwd = cwd or self.task_env_config.workdir
        if effective_cwd:
            exec_args.extend(["-w", effective_cwd])

        if env:
            for key, value in env.items():
                exec_args.extend(["-e", f"{key}={value}"])

        if user is not None:
            exec_args.extend(["--user", str(user)])

        exec_args.append(self._container_name)
        exec_args.extend(["bash", "-c", command])

        return await self._run_podman(exec_args, check=False, timeout_sec=timeout_sec)

    async def upload_file(self, source_path: Path | str, target_path: str):
        await self._run_podman(
            ["cp", str(source_path), f"{self._container_name}:{target_path}"]
        )

    async def upload_dir(self, source_dir: Path | str, target_dir: str):
        await self._run_podman(
            ["cp", f"{source_dir}/.", f"{self._container_name}:{target_dir}"]
        )

    async def download_file(self, source_path: str, target_path: Path | str):
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        await self._run_podman(
            ["cp", f"{self._container_name}:{source_path}", str(target_path)]
        )

    async def download_dir(self, source_dir: str, target_dir: Path | str):
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        await self._run_podman(
            ["cp", f"{self._container_name}:{source_dir}/.", str(target_dir)]
        )

    async def attach(self) -> None:
        cmd = ["podman", "exec", "-it", self._container_name, "bash"]
        os.execvp("podman", cmd)
