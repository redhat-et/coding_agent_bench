from __future__ import annotations

import concurrent.futures
import json
import math
import re
import shlex
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from huggingface_hub import HfApi, hf_hub_download

BYTES_PER_DTYPE = {
    "F64": 8,
    "F32": 4,
    "F16": 2,
    "BF16": 2,
    "F8_E4M3": 1,
    "F8_E5M2": 1,
    "I64": 8,
    "I32": 4,
    "I16": 2,
    "I8": 1,
    "U64": 8,
    "U32": 4,
    "U16": 2,
    "U8": 1,
    "BOOL": 1,
}

@dataclass
class GpuPool:
    """A cluster GPU pool with its hardware specs and nodeSelector label."""

    name: str
    label: str
    gpus: int
    gpu_model: str
    vram_per_gpu: int

    @property
    def total_vram(self) -> int:
        return self.gpus * self.vram_per_gpu


def _default_gpu_pools() -> dict[str, GpuPool]:
    return {
        "small": GpuPool(
            name="small",
            label="gpu-pool-size=small",
            gpus=1,
            gpu_model="L40S",
            vram_per_gpu=48,
        ),
        "large": GpuPool(
            name="large",
            label="gpu-pool-size=large",
            gpus=4,
            gpu_model="L4",
            vram_per_gpu=23,
        ),
        "xlarge": GpuPool(
            name="xlarge",
            label="gpu-pool-size=xlarge",
            gpus=4,
            gpu_model="L40S",
            vram_per_gpu=48,
        ),
    }


def load_gpu_pools(pools_file: Path | None) -> dict[str, GpuPool]:
    """Load GPU pool definitions from a YAML file, or return built-in defaults."""
    if pools_file is None:
        return _default_gpu_pools()
    with open(pools_file) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "pools" not in data:
        raise ValueError(f"GPU pools file must contain a 'pools' mapping: {pools_file}")
    if not data["pools"]:
        raise ValueError(f"GPU pools file has an empty 'pools' section: {pools_file}")
    pools = {}
    required_keys = {"label", "gpus", "gpu_model", "vram_per_gpu"}
    for name, cfg in data["pools"].items():
        missing = required_keys - set(cfg.keys())
        if missing:
            raise ValueError(f"GPU pool '{name}' missing required keys: {', '.join(sorted(missing))}")
        pools[name] = GpuPool(
            name=name,
            label=cfg["label"],
            gpus=cfg["gpus"],
            gpu_model=cfg["gpu_model"],
            vram_per_gpu=cfg["vram_per_gpu"],
        )
    return pools


@dataclass
class ModelMetadata:
    """HuggingFace model metadata: parameter counts, config, and weight size."""

    model_id: str
    parameter_count: dict[str, int]
    config: dict
    weight_size_gb: float
    total_params: int

    def _text_config(self) -> dict:
        return self.config.get("text_config", self.config)

    @property
    def max_position_embeddings(self) -> int | None:
        return self._text_config().get("max_position_embeddings")

    @property
    def num_hidden_layers(self) -> int | None:
        cfg = self._text_config()
        n = cfg.get("num_hidden_layers")
        if n is None and "layers_block_type" in cfg:
            n = len(cfg["layers_block_type"])
        return n

    @property
    def num_key_value_heads(self) -> int | None:
        return self._text_config().get("num_key_value_heads")

    @property
    def head_dim(self) -> int | None:
        cfg = self._text_config()
        hd = cfg.get("head_dim")
        if hd is None:
            hidden = cfg.get("hidden_size")
            n_heads = cfg.get("num_attention_heads")
            if hidden and n_heads:
                hd = hidden // n_heads
        return hd

    @property
    def sliding_window(self) -> int | None:
        return self._text_config().get("sliding_window")

    @property
    def layer_types(self) -> list[str] | None:
        """Per-layer attention type list (e.g. Gemma's mix of sliding/full)."""
        return self._text_config().get("layer_types")

    @property
    def global_head_dim(self) -> int | None:
        return self._text_config().get("global_head_dim")

    @property
    def num_global_key_value_heads(self) -> int | None:
        return self._text_config().get("num_global_key_value_heads")


def fetch_model_metadata(model_id: str) -> ModelMetadata:
    """Fetch model config and safetensors metadata from HuggingFace."""
    api = HfApi()

    config_path = hf_hub_download(model_id, "config.json")
    with open(config_path) as f:
        config = json.load(f)

    safetensors_meta = api.get_safetensors_metadata(model_id)
    param_count = dict(safetensors_meta.parameter_count)

    total_params = sum(param_count.values())
    weight_bytes = sum(
        count * BYTES_PER_DTYPE.get(dtype, 1) for dtype, count in param_count.items()
    )
    weight_size_gb = weight_bytes / (1024**3)

    return ModelMetadata(
        model_id=model_id,
        parameter_count=param_count,
        config=config,
        weight_size_gb=weight_size_gb,
        total_params=total_params,
    )


@dataclass
class VramEstimate:
    """VRAM estimation: weight size, overhead, KV cache, and total."""

    weight_gb: float
    overhead_gb: float
    kv_cache_gb: float
    min_vram_gb: float


def _estimate_kv_cache_bytes(metadata: ModelMetadata, max_model_len: int | None) -> float | None:
    """Estimate KV cache bytes for one full-context request.

    Assumes FP8 KV cache (1 byte per element), which is the default
    dtype used in generated manifests.  Accounts for sliding window
    attention: layers with a sliding window only store KV entries for
    the window size, not the full context.  Models with heterogeneous
    layer types (e.g. Gemma's mix of sliding_attention + full_attention
    with different head dims) are handled per-layer-group.
    """
    n_layers = metadata.num_hidden_layers
    n_kv_heads = metadata.num_key_value_heads
    head_dim = metadata.head_dim
    if any(v is None for v in [n_layers, n_kv_heads, head_dim, max_model_len]):
        return None

    layer_types = metadata.layer_types
    sliding_window = metadata.sliding_window
    if sliding_window is not None and sliding_window <= 0:
        sliding_window = None

    kv_dtype_bytes = 1  # FP8

    if layer_types and sliding_window is not None:
        global_head_dim = metadata.global_head_dim or head_dim
        global_kv_heads = metadata.num_global_key_value_heads or n_kv_heads

        total_bytes = 0
        for lt in layer_types:
            if lt == "full_attention":
                total_bytes += 2 * global_kv_heads * global_head_dim * kv_dtype_bytes * max_model_len
            else:
                tokens = min(sliding_window, max_model_len)
                total_bytes += 2 * n_kv_heads * head_dim * kv_dtype_bytes * tokens
        return float(total_bytes)

    if sliding_window is not None:
        tokens = min(sliding_window, max_model_len)
    else:
        tokens = max_model_len

    return float(2 * n_kv_heads * head_dim * n_layers * kv_dtype_bytes * tokens)


def estimate_vram(metadata: ModelMetadata, max_model_len: int | None) -> VramEstimate:
    """Estimate VRAM for pool selection: weights + 15% overhead + KV cache.

    KV cache is estimated per-layer, accounting for sliding window
    attention where applicable.  The 15% overhead covers CUDA context,
    activations, and CUDA graphs.
    """
    weight_gb = metadata.weight_size_gb
    overhead_gb = weight_gb * 0.15

    kv_bytes = _estimate_kv_cache_bytes(metadata, max_model_len)
    kv_cache_gb = (kv_bytes / (1024**3)) if kv_bytes is not None else 0.0

    min_vram_gb = weight_gb + overhead_gb + kv_cache_gb

    return VramEstimate(
        weight_gb=weight_gb,
        overhead_gb=overhead_gb,
        kv_cache_gb=kv_cache_gb,
        min_vram_gb=min_vram_gb,
    )


def select_gpu_pool(
    vram_needed: float,
    pools: dict[str, GpuPool],
    override: str | None = None,
) -> GpuPool:
    """Select the smallest GPU pool that fits the model, or use an override."""
    if override:
        if override not in pools:
            available = ", ".join(pools.keys())
            raise ValueError(f"Unknown GPU pool '{override}'. Available: {available}")
        pool = pools[override]
        usable = pool.total_vram * 0.9
        if vram_needed > usable:
            print(
                f"Warning: model needs ~{vram_needed:.1f} GB but {pool.name} pool "
                f"has {pool.total_vram} GB ({usable:.0f} GB usable). May not fit."
            )
        return pool

    sorted_pools = sorted(pools.values(), key=lambda p: p.total_vram)
    for pool in sorted_pools:
        usable = pool.total_vram * 0.9
        if usable >= vram_needed:
            return pool

    largest = sorted_pools[-1]
    largest_usable = largest.total_vram * 0.9
    if largest_usable >= vram_needed * 0.85:
        print(
            f"Warning: model needs ~{vram_needed:.1f} GB but {largest.name} pool "
            f"has {largest.total_vram} GB ({largest_usable:.0f} GB usable) — tight fit, "
            f"vLLM may reduce context length."
        )
        return largest
    raise ValueError(
        f"Model needs ~{vram_needed:.1f} GB VRAM but the largest available pool "
        f"({largest.name}) provides {largest.total_vram} GB. "
        f"This model cannot be deployed on the current cluster."
    )


def determine_max_model_len(
    metadata: ModelMetadata,
    override: int | None = None,
) -> int | None:
    """Return the max context length from model config, or an override."""
    if override is not None:
        if override <= 0:
            raise ValueError("--max-model-len must be a positive integer")
        return override
    max_model_len = metadata.max_position_embeddings
    if max_model_len is not None and max_model_len <= 0:
        raise ValueError(f"Invalid max_position_embeddings in model config: {max_model_len}")
    return max_model_len


def _normalize_model_name(model_id: str, *, keep_dots: bool = False) -> str:
    name = model_id.split("/")[-1].lower()
    for suffix in ["-fp8-dynamic", "-fp8-block", "-fp8", "-nvfp4", "-it"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    if not keep_dots:
        name = name.replace(".", "")
    name = name.replace("_", "-")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    if keep_dots:
        allowed.add(".")
    name = "".join(c for c in name if c in allowed)
    name = name.strip("-.")
    while "--" in name:
        name = name.replace("--", "-")
    return name


def derive_app_name(model_id: str, override: str | None = None) -> str:
    """Derive a K8s-safe resource name from a HuggingFace model ID."""
    if override:
        return override
    return _normalize_model_name(model_id, keep_dots=False)[:63]


def derive_served_model_name(model_id: str, override: str | None = None) -> str:
    """Derive the vLLM --served-model-name from a HuggingFace model ID."""
    if override:
        return override
    return _normalize_model_name(model_id, keep_dots=True)


def determine_pvc_size(weight_gb: float) -> str:
    """Calculate PVC size in Gi, rounded up to next 50 Gi (min 100 Gi)."""
    needed = weight_gb * 1.5
    size_gi = max(100, math.ceil(needed / 50) * 50)
    return f"{size_gi}Gi"


@dataclass
class ManifestConfig:
    """All parameters needed to generate a vLLM deployment manifest."""

    model_id: str
    app_name: str
    served_model_name: str
    namespace: str
    gpu_pool: GpuPool
    tensor_parallel_size: int
    max_model_len: int | None
    pvc_size: str
    vllm_image: str
    route_timeout: str
    vllm_serve_args: list[str] = field(default_factory=list)
    anyuid: bool = False
    before_script: str | None = None
    gpu_memory_utilization: float = 0.9
    cpu_request: str = "2"
    cpu_limit: str = "4"
    memory_request: str = "20G"
    memory_limit: str = "30G"
    shm_size: str = "16Gi"


class _LiteralStr(str):
    pass


class _ManifestDumper(yaml.Dumper):
    pass


def _literal_str_representer(dumper: yaml.Dumper, data: _LiteralStr) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


_ManifestDumper.add_representer(_LiteralStr, _literal_str_representer)


def _build_vllm_command(cfg: ManifestConfig) -> str:
    parts = [f"vllm serve {shlex.quote(cfg.model_id)}"]
    parts.append(f"--served-model-name {shlex.quote(cfg.served_model_name)}")
    parts.append("--async-scheduling")
    parts.append("--dtype auto")
    parts.append(f"--max-model-len {cfg.max_model_len if cfg.max_model_len is not None else 'auto'}")
    parts.append("--trust-remote-code")
    parts.append(f"--tensor-parallel-size {cfg.tensor_parallel_size}")
    parts.append(f"--gpu-memory-utilization {cfg.gpu_memory_utilization}")
    parts.append("--enable-chunked-prefill")
    parts.append("--enable-prefix-caching")
    parts.append("--kv-cache-dtype fp8")
    parts.append("--enable-auto-tool-choice")
    for arg in cfg.vllm_serve_args:
        parts.append(arg)
    vllm_cmd = " \\\n  ".join(parts)
    if cfg.before_script:
        return f"set -eu\n{cfg.before_script}\n{vllm_cmd}\n"
    return vllm_cmd + "\n"


def _build_service_account(cfg: ManifestConfig) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "labels": {"app": cfg.app_name, "component": "vllm"},
            "name": cfg.app_name,
            "namespace": cfg.namespace,
        },
    }


def _build_role_binding(cfg: ManifestConfig) -> dict:
    return {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {
            "labels": {"app": cfg.app_name, "component": "vllm"},
            "name": f"{cfg.app_name}-anyuid",
            "namespace": cfg.namespace,
        },
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "ClusterRole",
            "name": "system:openshift:scc:anyuid",
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": cfg.app_name,
                "namespace": cfg.namespace,
            }
        ],
    }


def _build_pvc(cfg: ManifestConfig) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "labels": {"app": cfg.app_name, "component": "vllm"},
            "name": cfg.app_name,
            "namespace": cfg.namespace,
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": cfg.pvc_size}},
            "volumeMode": "Filesystem",
        },
    }


def _build_deployment(cfg: ManifestConfig) -> dict:
    label_key, label_val = cfg.gpu_pool.label.split("=", 1)
    vllm_cmd = _LiteralStr(_build_vllm_command(cfg))

    container = {
        "args": [vllm_cmd],
        "command": ["/bin/sh", "-c"],
        "image": cfg.vllm_image,
        "imagePullPolicy": "Always",
        "envFrom": [{"secretRef": {"name": "hf-token-secret"}}],
        "name": cfg.app_name,
        "securityContext": {"allowPrivilegeEscalation": False},
        "ports": [{"containerPort": 8000}],
        "startupProbe": {
            "httpGet": {"path": "/health", "port": 8000},
            "initialDelaySeconds": 1800,
            "periodSeconds": 30,
            "failureThreshold": 10,
        },
        "readinessProbe": {
            "httpGet": {"path": "/health", "port": 8000},
            "periodSeconds": 10,
        },
        "livenessProbe": {
            "httpGet": {"path": "/health", "port": 8000},
            "periodSeconds": 30,
        },
        "resources": {
            "limits": {
                "cpu": cfg.cpu_limit,
                "memory": cfg.memory_limit,
                "nvidia.com/gpu": str(cfg.gpu_pool.gpus),
            },
            "requests": {
                "cpu": cfg.cpu_request,
                "memory": cfg.memory_request,
                "nvidia.com/gpu": str(cfg.gpu_pool.gpus),
            },
        },
        "volumeMounts": [
            {"mountPath": "/.cache", "name": "cache-volume"},
            {"mountPath": "/.config", "name": "config-volume"},
            {"mountPath": "/.triton", "name": "triton-volume"},
            {"mountPath": "/.local", "name": "local-volume"},
            {"mountPath": "/dev/shm", "name": "shm"},
        ],
    }

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "labels": {"app": cfg.app_name, "component": "vllm"},
            "name": cfg.app_name,
            "namespace": cfg.namespace,
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": {"app": cfg.app_name, "component": "vllm"},
            },
            "template": {
                "metadata": {
                    "labels": {"app": cfg.app_name, "component": "vllm"},
                },
                "spec": {
                    "serviceAccountName": cfg.app_name,
                    "nodeSelector": {label_key: label_val},
                    "securityContext": {
                        "runAsUser": 2000,
                        "runAsGroup": 0,
                        "fsGroup": 0,
                    },
                    "containers": [container],
                    "volumes": [
                        {
                            "name": "cache-volume",
                            "persistentVolumeClaim": {"claimName": cfg.app_name},
                        },
                        {
                            "emptyDir": {"medium": "Memory", "sizeLimit": "2Gi"},
                            "name": "config-volume",
                        },
                        {
                            "emptyDir": {"medium": "Memory", "sizeLimit": "2Gi"},
                            "name": "local-volume",
                        },
                        {
                            "emptyDir": {"medium": "Memory", "sizeLimit": "2Gi"},
                            "name": "triton-volume",
                        },
                        {
                            "emptyDir": {"medium": "Memory", "sizeLimit": cfg.shm_size},
                            "name": "shm",
                        },
                    ],
                },
            },
        },
    }


def _build_service(cfg: ManifestConfig) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "labels": {"app": cfg.app_name, "component": "vllm"},
            "name": cfg.app_name,
            "namespace": cfg.namespace,
        },
        "spec": {
            "ports": [
                {
                    "name": "http",
                    "port": 80,
                    "protocol": "TCP",
                    "targetPort": 8000,
                }
            ],
            "selector": {"app": cfg.app_name, "component": "vllm"},
            "sessionAffinity": "None",
            "type": "ClusterIP",
        },
    }


def _build_route(cfg: ManifestConfig) -> dict:
    return {
        "apiVersion": "route.openshift.io/v1",
        "kind": "Route",
        "metadata": {
            "annotations": {
                "haproxy.router.openshift.io/timeout": cfg.route_timeout,
            },
            "labels": {"app": cfg.app_name, "component": "vllm"},
            "name": cfg.app_name,
            "namespace": cfg.namespace,
        },
        "spec": {
            "port": {"targetPort": 8000},
            "tls": {
                "termination": "edge",
                "insecureEdgeTerminationPolicy": "Redirect",
            },
            "to": {
                "kind": "Service",
                "name": cfg.app_name,
                "weight": 100,
            },
            "wildcardPolicy": "None",
        },
    }


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"' if data.isdigit() else None)


_ManifestDumper.add_representer(str, _str_representer)


def generate_manifest_yaml(cfg: ManifestConfig) -> str:
    """Assemble all K8s resources into a multi-document YAML string."""
    docs = [
        _build_service_account(cfg),
    ]
    if cfg.anyuid:
        docs.append(_build_role_binding(cfg))
    docs.extend([
        _build_pvc(cfg),
        _build_deployment(cfg),
        _build_service(cfg),
        _build_route(cfg),
    ])
    output = yaml.dump_all(docs, Dumper=_ManifestDumper, default_flow_style=False, sort_keys=False)
    if not output.startswith("---"):
        output = "---\n" + output
    return output


def format_params(total: int) -> str:
    if total >= 1_000_000_000:
        return f"{total / 1_000_000_000:.1f}B"
    if total >= 1_000_000:
        return f"{total / 1_000_000:.1f}M"
    return f"{total:,}"



def _generate_manifest(
    model_id: str,
    reasoning_parser: str | None = None,
    tool_call_parser: str | None = None,
    chat_template_kwargs: str | None = None,
    extra_vllm_args: list[str] | None = None,
    gpu_pool_override: str | None = None,
    gpu_pools_file: Path | None = None,
    max_model_len_override: int | None = None,
    namespace: str = "coding-agent-leaderboard",
    vllm_image: str = "vllm/vllm-openai:v0.23.0",
    route_timeout: str = "600s",
    app_name_override: str | None = None,
    served_model_name_override: str | None = None,
    anyuid: bool = False,
    before_script: str | None = None,
) -> str:
    """Fetch model metadata, estimate resources, and build the YAML manifest."""
    print(f"Fetching metadata for {model_id}...")
    metadata = fetch_model_metadata(model_id)

    pools = load_gpu_pools(gpu_pools_file)
    max_model_len = determine_max_model_len(metadata, max_model_len_override)
    vram = estimate_vram(metadata, max_model_len)

    param_breakdown = ", ".join(
        f"{dtype}: {format_params(count)}"
        for dtype, count in sorted(metadata.parameter_count.items())
    )
    print()
    print(f"  Model:            {metadata.model_id}")
    print(f"  Parameters:       {format_params(metadata.total_params)} ({param_breakdown})")
    print(f"  Weight size:      {vram.weight_gb:.1f} GB")
    if vram.kv_cache_gb > 0:
        print(f"  KV cache:         {vram.kv_cache_gb:.1f} GB (1 request × {max_model_len} tokens)")
    print(f"  Min VRAM needed:  {vram.min_vram_gb:.1f} GB (weights + overhead + KV cache)")

    pool = select_gpu_pool(vram.min_vram_gb, pools, gpu_pool_override)
    tensor_parallel = pool.gpus
    pvc_size = determine_pvc_size(metadata.weight_size_gb)
    app_name = derive_app_name(model_id, app_name_override)
    served_name = derive_served_model_name(model_id, served_model_name_override)

    print(f"  GPU pool:         {pool.name} ({pool.gpus}x {pool.gpu_model}, {pool.total_vram} GB)")
    print(f"  Tensor parallel:  {tensor_parallel}")
    print(f"  Max model length: {max_model_len if max_model_len is not None else 'auto'}")
    print(f"  PVC storage:      {pvc_size}")
    print()

    vllm_args: list[str] = []
    if reasoning_parser:
        vllm_args.append(f"--reasoning-parser {reasoning_parser}")
    if tool_call_parser:
        vllm_args.append(f"--tool-call-parser {tool_call_parser}")
    if chat_template_kwargs:
        vllm_args.append(f"--default-chat-template-kwargs '{chat_template_kwargs}'")
    if extra_vllm_args:
        vllm_args.extend(extra_vllm_args)

    cfg = ManifestConfig(
        model_id=model_id,
        app_name=app_name,
        served_model_name=served_name,
        namespace=namespace,
        gpu_pool=pool,
        tensor_parallel_size=tensor_parallel,
        max_model_len=max_model_len,
        pvc_size=pvc_size,
        vllm_image=vllm_image,
        route_timeout=route_timeout,
        vllm_serve_args=vllm_args,
        anyuid=anyuid,
        before_script=before_script,
    )

    return generate_manifest_yaml(cfg)


def generate(
    model_id: str,
    reasoning_parser: str | None = None,
    tool_call_parser: str | None = None,
    chat_template_kwargs: str | None = None,
    extra_vllm_args: list[str] | None = None,
    gpu_pool_override: str | None = None,
    gpu_pools_file: Path | None = None,
    max_model_len_override: int | None = None,
    namespace: str = "coding-agent-leaderboard",
    vllm_image: str = "vllm/vllm-openai:v0.23.0",
    route_timeout: str = "600s",
    app_name_override: str | None = None,
    served_model_name_override: str | None = None,
    output: Path | None = None,
    dry_run: bool = False,
    anyuid: bool = False,
    before_script: str | None = None,
) -> str | None:
    """Generate a manifest and print/write it. CLI entry point for generate-manifest."""
    manifest_yaml = _generate_manifest(
        model_id=model_id,
        reasoning_parser=reasoning_parser,
        tool_call_parser=tool_call_parser,
        chat_template_kwargs=chat_template_kwargs,
        extra_vllm_args=extra_vllm_args,
        gpu_pool_override=gpu_pool_override,
        gpu_pools_file=gpu_pools_file,
        max_model_len_override=max_model_len_override,
        namespace=namespace,
        vllm_image=vllm_image,
        route_timeout=route_timeout,
        app_name_override=app_name_override,
        served_model_name_override=served_model_name_override,
        anyuid=anyuid,
        before_script=before_script,
    )

    if dry_run:
        return None

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(manifest_yaml)
        print(f"Manifest written to {output}")
    else:
        print(manifest_yaml)

    return manifest_yaml


def _run_oc(args: list[str], namespace: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["oc"] + args
    if namespace:
        cmd.extend(["-n", namespace])
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def get_route_url(app_name: str, namespace: str) -> str:
    """Get the HTTPS route URL for a deployed app from OpenShift."""
    result = _run_oc(
        ["get", "route", app_name, "-o", "jsonpath={.spec.host}"],
        namespace=namespace,
    )
    host = result.stdout.strip()
    if not host:
        raise ValueError(f"Could not get route URL for {app_name}")
    return f"https://{host}"


def apply_manifest(manifest_yaml: str, namespace: str) -> None:
    """Apply a YAML manifest to OpenShift via oc apply -f stdin."""
    cmd = ["oc", "apply", "-f", "-", "-n", namespace]
    subprocess.run(cmd, input=manifest_yaml, text=True, check=True)


def wait_for_health(
    url: str,
    timeout_seconds: int = 1800,
    poll_interval: int = 30,
    initial_delay: int = 1200,
) -> bool:
    """Poll /health until 200 or timeout, with an initial delay for model loading."""
    health_url = f"{url}/health"
    if initial_delay > 0:
        print(f"  Waiting {initial_delay // 60}m before first health check (model downloading)...")
        time.sleep(initial_delay)
    start = time.time()
    while time.time() - start < timeout_seconds:
        elapsed = int(time.time() - start)
        last_error = ""
        try:
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    print(f"  [{elapsed // 60}m{elapsed % 60:02d}s] Health check passed!")
                    return True
        except Exception as e:
            last_error = f" ({type(e).__name__})"
        print(f"  [{elapsed // 60}m{elapsed % 60:02d}s] Not ready yet{last_error}")
        time.sleep(poll_interval)
    return False


def get_vllm_concurrency(app_name: str, namespace: str) -> tuple[int, float] | None:
    """Extract max concurrency from vLLM pod logs after startup."""
    try:
        result = _run_oc(["logs", f"deployment/{app_name}"], namespace)
    except subprocess.CalledProcessError:
        return None
    match = re.search(
        r"Maximum concurrency for ([\d,]+) tokens per request: ([\d.]+)x",
        result.stdout,
    )
    if not match:
        return None
    max_len = int(match.group(1).replace(",", ""))
    concurrency = float(match.group(2))
    return max_len, concurrency


def validate_deployment(url: str, model_name: str, concurrency: int = 8) -> bool:
    """Run validation checks: model responding, concurrency, and tool calling."""
    passed = 0
    failed = 0

    print("--- Check 1: Model responding ---")
    try:
        req = urllib.request.Request(f"{url}/v1/models")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        max_len = None
        for m in data.get("data", []):
            if m["id"] == model_name:
                max_len = m.get("max_model_len")
        if max_len:
            print(f"  max_model_len: {max_len}")
            print("  PASS")
            passed += 1
        else:
            print(f"  Model '{model_name}' not found in response")
            print("  FAIL")
            failed += 1
    except Exception as e:
        print(f"  Error: {e}")
        print("  FAIL")
        failed += 1

    print(f"--- Check 2: {concurrency}x concurrency ---")
    payload = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": "Say hello"}],
        "max_tokens": 10,
    }).encode()

    def _send_request() -> int:
        try:
            req = urllib.request.Request(
                f"{url}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.status
        except Exception:
            return 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_send_request) for _ in range(concurrency)]
        results = [f.result() for f in futures]

    ok = sum(1 for r in results if r == 200)
    print(f"  {ok}/{concurrency} requests returned 200")
    if ok == concurrency:
        print("  PASS")
        passed += 1
    else:
        print("  FAIL")
        failed += 1

    print("--- Check 3: Tool calling ---")
    tool_payload = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": "What is the weather in Boston?"}],
        "max_tokens": 512,
        "tools": [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                    },
                    "required": ["location"],
                },
            },
        }],
        "tool_choice": "auto",
    }).encode()

    try:
        req = urllib.request.Request(
            f"{url}/v1/chat/completions",
            data=tool_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        choices = data.get("choices", [])
        has_tool_call = (
            choices
            and choices[0].get("message", {}).get("tool_calls")
        )
        if has_tool_call:
            print("  PASS")
            passed += 1
        else:
            print("  No tool call in response")
            print("  FAIL")
            failed += 1
    except Exception as e:
        print(f"  Error: {e}")
        print("  FAIL")
        failed += 1

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    return failed == 0


def scale_down(app_name: str, namespace: str) -> None:
    """Scale deployment to 0 replicas, freeing GPUs but keeping cached weights."""
    _run_oc(
        ["scale", f"deployment/{app_name}", "--replicas=0"],
        namespace=namespace,
    )
    print(f"Scaled down {app_name} (replicas=0). Resources and cached weights preserved.")


def teardown(app_name: str, namespace: str) -> None:
    """Delete all K8s resources for a model (SA, RoleBinding, PVC, Deployment, Service, Route)."""
    _run_oc(
        ["delete", "route,svc,deployment,pvc,rolebinding,sa",
         "-l", f"app={app_name}",
         "--ignore-not-found"],
        namespace=namespace,
    )
    print(f"Deleted all resources for {app_name}.")


def deploy(
    model_id: str,
    reasoning_parser: str | None = None,
    tool_call_parser: str | None = None,
    chat_template_kwargs: str | None = None,
    extra_vllm_args: list[str] | None = None,
    gpu_pool_override: str | None = None,
    gpu_pools_file: Path | None = None,
    max_model_len_override: int | None = None,
    namespace: str = "coding-agent-leaderboard",
    vllm_image: str = "vllm/vllm-openai:v0.23.0",
    route_timeout: str = "600s",
    app_name_override: str | None = None,
    served_model_name_override: str | None = None,
    do_scale_down: bool = False,
    do_teardown: bool = False,
    skip_validation: bool = False,
    concurrency: int = 8,
    health_timeout: int = 1800,
    initial_delay: int = 1200,
    anyuid: bool = False,
    before_script: str | None = None,
) -> None:
    """Deploy a model: generate manifest, apply, wait for health, and validate."""
    app_name = derive_app_name(model_id, app_name_override)
    served_name = derive_served_model_name(model_id, served_model_name_override)

    if do_scale_down:
        scale_down(app_name, namespace)
        return

    if do_teardown:
        teardown(app_name, namespace)
        return

    manifest_yaml = _generate_manifest(
        model_id=model_id,
        reasoning_parser=reasoning_parser,
        tool_call_parser=tool_call_parser,
        chat_template_kwargs=chat_template_kwargs,
        extra_vllm_args=extra_vllm_args,
        gpu_pool_override=gpu_pool_override,
        gpu_pools_file=gpu_pools_file,
        max_model_len_override=max_model_len_override,
        namespace=namespace,
        vllm_image=vllm_image,
        route_timeout=route_timeout,
        app_name_override=app_name_override,
        served_model_name_override=served_model_name_override,
        anyuid=anyuid,
        before_script=before_script,
    )

    print("Applying manifest...")
    apply_manifest(manifest_yaml, namespace)
    print("Manifest applied.")

    url = get_route_url(app_name, namespace)
    print(f"Route URL: {url}")

    if skip_validation:
        print("Skipping validation (--skip-validation).")
        return

    print(f"\nWaiting for health check (timeout: {health_timeout // 60}m)...")
    healthy = wait_for_health(url, timeout_seconds=health_timeout, initial_delay=initial_delay)
    if not healthy:
        raise ValueError(
            f"Health check timed out after {health_timeout // 60}m. "
            f"The model may still be downloading weights. Check pod logs with: "
            f"oc logs -f deployment/{app_name} -n {namespace}"
        )

    concurrency_info = get_vllm_concurrency(app_name, namespace)
    if concurrency_info:
        max_len, max_concurrency = concurrency_info
        print(f"  vLLM max concurrency: {max_concurrency}x at {max_len:,} tokens")

    print(f"\n=== Validating {served_name} ===")
    success = validate_deployment(url, served_name, concurrency=concurrency)
    if not success:
        raise ValueError("Validation failed. Check the output above for details.")
