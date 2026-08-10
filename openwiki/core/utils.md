---
type: utility
title: Utilities
description: Shared utility functions — command string formatting and other helpers used across the codebase.
tags: [utilities, helpers]
resource: src/coding_agent_bench/utils.py
---

# Utilities

Shared utility functions used across the coding-agent-bench codebase.

## Command Formatting

```python
def cmd_to_string(cmd: list[str]) -> str
```

Formats a command list as a shell-safe string using `shlex.join()`.

Used by the CLI to display the Harbor command before execution:

```python
# In cli.py
typer.echo(f"Job command:\n{cmd_to_string(harbor_command)}\n")
```

## Evidence

- Source: `src/coding_agent_bench/utils.py`
