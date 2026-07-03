import json
from pathlib import Path


TEMPLATE = """model = {model_name}
model_provider = "vllm"
web_search = "disabled"

[model_providers.vllm]
name = "vllm"
base_url = {base_url}
wire_api = "responses"
requires_openai_auth = false

[features]
js_repl = false
multi_agent = true
guardian_approval = true
prevent_idle_sleep = true
image_generation = false
"""


def _toml_string(value: str) -> str:
    return json.dumps(value)


def codex_create_toml(model_name: str, server_url: str, outpath: Path):
    base_url = f"{server_url.rstrip('/')}/v1"
    toml = TEMPLATE.format(
        model_name=_toml_string(model_name),
        base_url=_toml_string(base_url),
    )

    with open(outpath, "w") as f:
        f.write(toml)
