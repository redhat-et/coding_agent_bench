from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

BREV_LOCAL_PORT = 9000
BREV_REMOTE_PORT = 8000
BREV_INSTANCE_NAME = "coding-agent-bench"
BREV_INSTANCE_TYPE = "dmz.h100x2.pcie"


@dataclass
class ModelConfig:
    container_name: str
    docker_command: str


MODEL_CONFIGS: dict[str, ModelConfig] = {
    "RedHatAI/Qwen3.6-27B-FP8": ModelConfig(
        container_name="qwen3.6-27b",
        docker_command="""docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/Qwen3.6-27B-FP8 \
    --dtype auto \
    --max-model-len 131072 \
    --trust-remote-code \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --kv-cache-dtype fp8 \
    --enable-auto-tool-choice \
    --reasoning-parser qwen3 \
    --tool-call-parser qwen3_coder \
    --default-chat-template-kwargs '{"enable_thinking": true}'
"""
    ),
    "RedHatAI/gemma-4-31B-it-FP8-block": ModelConfig(
        container_name="gemma-4-31b-it",
        docker_command="""docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/gemma-4-31B-it-FP8-block \
    --dtype auto \
    --max-model-len 131072 \
    --trust-remote-code \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --kv-cache-dtype fp8 \
    --enable-auto-tool-choice \
    --reasoning-parser gemma4 \
    --tool-call-parser gemma4 \
    --default-chat-template-kwargs '{"enable_thinking": true}'
"""
    ),
    "RedHatAI/gpt-oss-120b": ModelConfig(
        container_name="gpt-oss-120b",
        docker_command="""docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/gpt-oss-120b \
    --dtype auto \
    --kv-cache-dtype fp8 \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --enable-auto-tool-choice \
    --tool-call-parser openai
""",
    ),
    "RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4": ModelConfig(
        container_name="nemotron-3-super-120b",
        docker_command="""docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 \
    --dtype auto \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --enable-auto-tool-choice \
    --reasoning-parser nemotron_v3 \
    --tool-call-parser qwen3_coder
"""
    ),
    "RedHatAI/Mistral-Small-4-119B-2603-NVFP4": ModelConfig(
        container_name="mistral-small-4-119b",
        docker_command="""docker run --runtime nvidia --gpus all \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=$HF_TOKEN" \
    -p 8000:8000 \
    --ipc=host \
    vllm/vllm-openai:v0.24.0 \
    --model RedHatAI/Mistral-Small-4-119B-2603-NVFP4 \
    --dtype auto \
    --max-model-len 131072 \
    --trust-remote-code \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.9 \
    --async-scheduling \
    --enable-chunked-prefill \
    --enable-prefix-caching \
    --kv-cache-dtype auto \
    --enable-auto-tool-choice \
    --reasoning-parser mistral \
    --tool-call-parser mistral \
    --default-chat-template-kwargs '{"reasoning_effort": "high"}' \
    --limit-mm-per-prompt '{"image": 0}'
"""
    )
}


class BrevInstance:
    def __init__(
        self,
        instance_name: str = BREV_INSTANCE_NAME,
        instance_type: str = BREV_INSTANCE_TYPE,
        local_port: int = BREV_LOCAL_PORT,
        remote_port: int = BREV_REMOTE_PORT,
    ):
        self._instance_name = instance_name
        self._instance_type = instance_type
        self._local_port = local_port
        self._remote_port = remote_port
        self._port_forward_process: asyncio.subprocess.Process | None = None
        self._running = False
        self._logged_in = False
        self._current_model: str | None = None

    @property
    def is_alive(self) -> bool:
        return self._running

    @property
    def server_url(self) -> str:
        return "http://brev-model-service"

    async def _run_brev(
        self,
        args: list[str],
        check: bool = True,
        timeout_sec: int = 300,
    ) -> tuple[str, str]:
        cmd = ["brev", *args]
        logger.info("Running: %s", " ".join(cmd))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout_sec
            )
        except asyncio.TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.communicate(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
            raise RuntimeError(
                f"brev command timed out after {timeout_sec}s: {' '.join(cmd)}"
            )

        stdout = stdout_bytes.decode(errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else ""
        rc = process.returncode or 0

        if check and rc != 0:
            raise RuntimeError(
                f"brev command failed (rc={rc}): {' '.join(cmd)}\n"
                f"stdout: {stdout}\nstderr: {stderr}"
            )

        logger.info("brev stdout: %s", stdout.strip())
        if stderr.strip():
            logger.info("brev stderr: %s", stderr.strip())

        return stdout, stderr

    async def _login(self) -> None:
        if self._logged_in:
            return
        token = os.environ.get("BREV_TOKEN")
        if not token:
            raise RuntimeError("BREV_TOKEN environment variable is not set")
        await self._run_brev(["login", "--token", token])
        self._logged_in = True

    async def ensure_running(self) -> None:
        if self._running:
            return

        await self._login()

        logger.info("Creating Brev instance %s", self._instance_name)
        await self._run_brev(
            ["create", self._instance_name, "--type", self._instance_type],
            timeout_sec=600,
        )
        self._running = True

        logger.info("Starting port-forward %d:%d", self._local_port, self._remote_port)
        self._port_forward_process = await asyncio.create_subprocess_exec(
            "brev", "port-forward", self._instance_name,
            "--port", f"{self._local_port}:{self._remote_port}",
            "--host", "0.0.0.0",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Give port-forward a moment to bind
        await asyncio.sleep(3)

        if self._port_forward_process.returncode is not None:
            stdout = await self._port_forward_process.stdout.read()
            stderr = await self._port_forward_process.stderr.read()
            raise RuntimeError(
                f"brev port-forward exited immediately "
                f"(rc={self._port_forward_process.returncode})\n"
                f"stdout: {stdout.decode(errors='replace')}\n"
                f"stderr: {stderr.decode(errors='replace')}"
            )

    async def _wait_for_health(
        self,
        timeout_sec: int = 1800,
        poll_interval: int = 15,
    ) -> None:
        health_url = f"http://localhost:{self._local_port}/health"
        logger.info("Waiting for model health at %s", health_url)

        for elapsed in range(0, timeout_sec, poll_interval):
            try:
                req = urllib.request.Request(health_url, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info("Model healthy after %ds", elapsed)
                        return
            except Exception:
                pass

            if elapsed % 60 == 0:
                logger.info("Model not ready yet (%ds elapsed)", elapsed)
            await asyncio.sleep(poll_interval)

        raise RuntimeError(
            f"Model health check timed out after {timeout_sec}s"
        )

    async def start_model(self, model_name: str) -> None:
        config = MODEL_CONFIGS.get(model_name)
        if config is None:
            raise ValueError(
                f"No Brev model config for '{model_name}'. "
                f"Available: {', '.join(MODEL_CONFIGS.keys()) or '(none)'}"
            )

        logger.info("Starting model container %s", config.container_name)
        await self._run_brev(
            ["exec", self._instance_name, "--host", config.docker_command],
            timeout_sec=60,
        )
        self._current_model = model_name

        await self._wait_for_health()

    async def stop_model(self, model_name: str) -> None:
        config = MODEL_CONFIGS.get(model_name)
        if config is None:
            return

        logger.info("Stopping model container %s", config.container_name)
        await self._run_brev(
            [
                "exec", self._instance_name, "--host",
                f"docker container rm -f {config.container_name}",
            ],
            check=False,
            timeout_sec=60,
        )
        self._current_model = None

    async def destroy(self) -> None:
        logger.info("Destroying Brev instance %s", self._instance_name)

        if self._port_forward_process is not None:
            self._port_forward_process.terminate()
            try:
                await asyncio.wait_for(
                    self._port_forward_process.communicate(), timeout=10
                )
            except asyncio.TimeoutError:
                self._port_forward_process.kill()
                await self._port_forward_process.communicate()
            self._port_forward_process = None

        # Retry deletion — Brev VMs are expensive, we must not leave them running
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                await self._run_brev(
                    ["delete", self._instance_name],
                    check=True,
                    timeout_sec=120,
                )
                self._running = False
                self._current_model = None
                return
            except Exception as e:
                last_err = e
                logger.warning(
                    "brev delete attempt %d/3 failed: %s", attempt + 1, e
                )
                if attempt < 2:
                    await asyncio.sleep(5)

        logger.error(
            "All brev delete attempts failed for %s: %s",
            self._instance_name, last_err,
        )
        raise last_err  # type: ignore[misc]

    def destroy_sync(self) -> None:
        """Synchronous best-effort destroy for use in signal handlers and atexit.
        Blocks the calling thread. Does not raise."""
        logger.info("Sync-destroying Brev instance %s", self._instance_name)

        if self._port_forward_process is not None:
            try:
                self._port_forward_process.kill()
            except Exception:
                pass

        for attempt in range(3):
            try:
                subprocess.run(
                    ["brev", "delete", self._instance_name],
                    capture_output=True,
                    timeout=120,
                    check=True,
                )
                logger.info("Sync brev delete succeeded")
                self._running = False
                return
            except Exception as e:
                logger.warning(
                    "Sync brev delete attempt %d/3 failed: %s", attempt + 1, e
                )

        logger.error(
            "All sync brev delete attempts failed for %s", self._instance_name
        )
        self._running = False

    @classmethod
    def cleanup_orphaned(cls, instance_name: str = BREV_INSTANCE_NAME) -> None:
        """Delete a Brev instance by name if it exists. Call at startup to
        clean up after a previous crash. Synchronous and best-effort."""
        token = os.environ.get("BREV_TOKEN")
        if not token:
            return

        try:
            subprocess.run(
                ["brev", "login", "--token", token],
                capture_output=True,
                timeout=30,
                check=True,
            )
        except Exception as e:
            logger.warning("brev login failed during orphan cleanup: %s", e)
            return

        try:
            subprocess.run(
                ["brev", "delete", instance_name],
                capture_output=True,
                timeout=120,
                check=False,
            )
            logger.info(
                "Orphan cleanup: attempted delete of instance '%s'",
                instance_name,
            )
        except Exception as e:
            logger.warning("Orphan cleanup failed for '%s': %s", instance_name, e)
