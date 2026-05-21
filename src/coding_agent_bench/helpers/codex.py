from pathlib import Path

TEMPLATE = """profile = "custom-vllm"
web_search = "disabled"

[model_providers.vllm]
name = "vllm"
base_url = "{server_url}/v1"
wire_api = "responses"
requires_openai_auth = false

[profiles.custom-vllm]
model_provider = "vllm"
model = "{model_name}"

[features]
js_repl = false
multi_agent = true
guardian_approval = true
prevent_idle_sleep = true
image_generation = false
"""


def codex_create_toml(model_name: str, server_url: str, outpath: Path):
    toml = TEMPLATE.format(model_name=model_name, server_url=server_url)
    with open(outpath, "w") as f:
        f.write(toml)
