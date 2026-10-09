# Developer Documentation

## Prerequisites

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Getting Started

Clone and install the project:

```sh
git clone https://github.com/redhat-et/coding_agent_bench.git
cd coding_agent_bench

uv venv
uv sync
```

Copy `.env.example` to `.env`:

```sh
cp .env.example .env
```

Follow the specific set up instructions for any components you are testing:
- [CLI](../cli.md)
- [Queue Service](../queue-service/local.md)
- [Nebius](../queue-service/nebius.md)
- [Intake Poller](../queue-service/intake_poller.md)
