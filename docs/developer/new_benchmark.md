# Add a New Benchmark

This will walk you through how to add a new benchmark to the project.

This has the widest range of potential effort needed to complete; sometimes running a new benchmark requires zero code changes

## Prerequisites

1. Identify the benchmark you want to run and check if it is available on [Harbor Hub](https://hub.harborframework.com/datasets). This will determine the path you follow:
    - If the benchmark is available on Harbor Hub, follow [Option 1: The Benchmark is Available on Harbor Hub](#option-1-the-benchmark-is-available-on-harbor-hub)
    - Otherwise, follow [Option 2: Create a Harbor Dataset](#option-2-create-a-harbor-dataset)

## Option 1: The Benchmark is Available on Harbor Hub

If the benchmark is available on Harbor Hub and requires no additional dependencies, then there is no additional work required!

Additional dependencies include (but are not limited to):
- LLM-as-judge Configurations: Each one is different, and thus requires special handling in the code to inject environment variables and other arguments to handle.
- Internet/Network Restrictions: If the benchmark needs network control lists or other network restrictions, the code will need to handle adding the URL of the model server to the agent's network allowlist.
- Enhanced Resource Requirements: The queue service sets default resources for each task pod. If the benchmark requires more CPUs or memory than is provided by the task definitions (the `task.toml`) or more than the cluster can handle, then the code will need to handle overriding the resources.

If the benchmark requires any of the above dependencies or other dependencies not available through the code already, please make a PR to support the required options.

Do not hardcode the benchmark name and use that as a condition for adding dependencies; instead offer the options needed to run your benchmark in the CLI, Job Queue, and UI so that others can reuse those components.

## Option 2: Create a Harbor Dataset

This option can be labor-intensive, so consider it only if there are no other options.

1. Migrate your benchmark to the [Harbor dataset format](https://docs.harborframework.com/tasks/overview)
2. Test your benchmark locally with one of our [validated Harbor commands](../validated_harbor_commands.md)
3. [Publish the dataset to Harbor Hub](https://docs.harborframework.com/datasets/create-a-dataset#publish-a-dataset)
