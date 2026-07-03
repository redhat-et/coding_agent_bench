from pathlib import Path

TEMPLATE = """model = "{model_name}"
model_provider = "vllm"
web_search = "disabled"

[model_providers.vllm]
name = "vllm"
base_url = "{server_url}/v1"
wire_api = "responses"
requires_openai_auth = false

[features]
js_repl = false
multi_agent = true
guardian_approval = true
prevent_idle_sleep = true
image_generation = false
"""

def codex_create_toml(model_name: str, server_url: str, outpath: Path):
    toml = TEMPLATE.format(model_name=model_name, server_url=server_url.rstrip("/"))
    with open(outpath, "w") as f:
        f.write(toml)
