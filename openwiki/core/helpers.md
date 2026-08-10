---
type: component
title: Helpers
description: Utility functions for agent-specific configuration file generation, including Codex config.toml creation.
tags: [helpers, utilities, codex]
resource: src/coding_agent_bench/helpers
---

# Helpers

Utility modules for generating agent-specific configuration files and other helper functions.

## Codex Config Generator

```
src/coding_agent_bench/helpers/codex.py
```

### `codex_create_toml(model_name, server_url, outpath)`

Generates a `config.toml` file for the Codex agent that points it at a vLLM model server.

**Template:**

```toml
model = "<model_name>"
model_provider = "vllm"
web_search = "disabled"

[model_providers.vllm]
name = "vllm"
base_url = "<server_url>/v1"
wire_api = "responses"
requires_openai_auth = false

[features]
js_repl = false
multi_agent = true
guardian_approval = true
prevent_idle_sleep = true
image_generation = false
```

The template uses JSON string escaping for the model name and base URL to ensure valid TOML syntax.

## Evidence

- Source: `src/coding_agent_bench/helpers/codex.py`
- Used by: `CodexAgentConfig.configure()` in `agents/configs.py`
