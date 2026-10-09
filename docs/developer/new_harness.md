# Add a New Harness

This will walk you through the two step process of adding a new harness to the project: first validating the harness and then registering it.

## Validate a New Harness

For harnesses to be added to `coding_agent_bench`, it must satisfy 3 requirements:

1. It must be supported by Harbor
2. It must support self-hosted models
3. Any required configuration must be managed through volume mounts and environment variables only - no interactive setup allowed

### Checking Harbor Support

You can see the supported harnesses under `--agents` in `harbor run --help`.

If you do not see the harness listed, look into [open PRs](https://github.com/harbor-framework/harbor/pulls) on the Harbor project.

If none exist, consider creating an issue and contributing it!

### Checking Self-Hosted Model Support

You can verify if a harness supports self-hosted models by checking for a few things.
In priority order:

1. **vLLM Support** - Search the docs for mentions of "vLLM" specifically
2. **LiteLLM Support** - Search the docs for "LiteLLM" -> This can be configured with the [`hosted_vllm/` provider](https://docs.litellm.ai/docs/providers/vllm) to connect the harness to the self-hosted model
3. **OpenAI-Compatible API Support** - Search the docs for "OpenAI compatible" -> Follow their configuration, which typically involves setting a base URL and API key
4. **OpenAI Support** - Search the docs for "OpenAI" (most will have this) -> You can typically override the base URL for OpenAI API calls using the `OPENAI_BASE_URL` environment variable
5. **Anthropic Support** - Search the docs for "Anthropic" or "Claude" -> You can typically override the base URL for OpenAI API calls using the `ANTHROPIC_BASE_URL` environment variable

### Verifying Configuration

You can test that your environment variables and volume mounts are sufficient for task execution using the `harbor task start-env` command.

For this to work, you need a task directory, which means you need to download a dataset, e.g. `swe-bench/swe-bench-verified`.

```sh
mkdir datasets
harbor dataset download swe-bench/swe-bench-verified -o ./datasets
```

Then you can test your configuration by creating a task container and starting a terminal in it:

```sh
harbor task start-env \
    --path ./datasets/astropy__astropy-7166 \
    --agent <your-agent> \
    --env docker \
    --mounts <your-mounts> \
    --ak <agent-kwargs>
```

Then you can export any needed envvars and run your harness command to test your configuration.

## Register the Harness in `coding_agent_bench`

Once you have verified your configuration, you can register the harness in `coding_agent_bench` to be used in benchmark runs.

1. Add a new subclass of `AgentConfig` to `src/coding_agent_bench/agents/configs.py`. For example:

    ```python
    class MyAgentConfig(AgentConfig):
        """Configuration for MyAgent."""

        name = "my-agent"
        version = "1.0.0"

        def configure(self, **kwargs) -> AgentConfigResult:
            ...your configuration code...
    ```

2. Register the new class in `AGENT_CONFIGS` in `src/coding_agent_bench/agents/__init__.py`
3. Add any needed tests for your new class to `tests/`
