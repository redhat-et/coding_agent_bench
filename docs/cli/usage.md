# CLI Usage

## Prerequisites

- Install dependencies with uv
    
    ```bash
    uv sync
    ```

- [Set up a vLLM server](#deploy-models-with-vllm), or other Anthropic- and OpenAI-compatible server
- Select a benchmark from among the options in [Harbor Hub](https://hub.harborframework.com/)

## Run a Benchmark

The following is the minimal configuration needed to run a job with the CLI:

```sh
uv run coding-agent-bench run \
    --agent <agent> \
    --dataset <benchmark-name> \
    --model-name <model-name> \
    --server-url <server-url>
```

For example, to run `swe-bench/swe-bench-verified` in Claude Code against a self-hosted model:

```sh
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset scale-ai/swe-bench-pro \
    --model-name my-model \
    --server-url http://my.server.url
```

If you want to see a preview of Harbor command that would be run for a given set of arguments without actually running the job, add the `--dry-run` flag.

> [!note]
> Additional configuration options are available, use `uv run coding-agent-bench run --help` to see them.

## Use Agent Skills

Pass one or more skill directories or Git sources with the repeatable `--skill`
option (`--skills` is an alias). Harbor installs the resolved skills into the
agent used by the benchmark.

To test a skill from your local filesystem:

```sh
uv run coding-agent-bench run \
    --agent opencode \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://my.server.url \
    --skill ./my-skills
```

Git sources make skills easy to share and reproduce. Repeat the option to test
multiple skill collections, for example Superpowers together with Caveman:

```sh
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://my.server.url \
    --skill obra/superpowers \
    --skill juliusbrussee/caveman
```

Harbor accepts `org/name` and `org/name@ref` shorthand and HTTP(S) Git URLs.
Repository shorthand loads skills from the repository's `skills/` directory.
Use a full URL such as
`https://github.com/org/repo/tree/<ref>/<subdir>` to select another directory.
Pin a tag or named branch with `@ref` (or in the full URL) when comparing
benchmark runs. Harbor resolves the reference to a commit and records that
commit in the job lock file for reproducibility.

## Run with Openshift

### Prerequisites

Login to your cluster and select a project:

```bash
oc login --token=<token> --server=<server>
oc project <project>
```

Create ServiceAccounts and RoleBindings to run tasks and orchestrate:

```bash
oc apply -f deploy/harbor-task-sa.yml
oc apply -f deploy/harbor-orchestrator-sa.yml
```

Create a MinIO deployment to store your job results:

```bash
oc apply -f deploy/harbor-minio.yml
```

### Run Tasks in Openshift (Orchestrate Locally)

Using the CLI, start a job and set `--environment openshift`, e.g.:

```bash
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset scale-ai/swe-bench-pro \
    --model-name my-model \
    --server-url http://my.server.url \
    --environment openshift
```

Skills used by a remote OpenShift Job must be public Git sources. Local paths
are rejected because they are not available inside the orchestrator pod. The
pod also needs outbound network access to the Git host.

```bash
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://my.server.url \
    --skill obra/superpowers@<ref> \
    --environment openshift
```


### Run Tasks and Orchestrate in Openshift

Using the CLI, start a job with the `--remote` flag enabled and set `--environment openshift`, e.g.:

```bash
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset scale-ai/swe-bench-pro \
    --model-name my-model \
    --server-url http://my.server.url \
    --remote \
    --environment openshift
```

Skills used by a remote OpenShift Job must be public Git sources. Local paths
are rejected because they are not available inside the orchestrator pod. The
pod also needs outbound network access to the Git host.

```bash
uv run coding-agent-bench run \
    --agent claude-code \
    --dataset swe-bench/swe-bench-verified \
    --model-name my-model \
    --server-url http://my.server.url \
    --skill obra/superpowers@<ref> \
    --remote \
    --environment openshift
```
