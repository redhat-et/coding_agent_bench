# Standalone vLLM Semantic Router

Self-contained deployment of the [vLLM Semantic Router](https://github.com/vllm-project/semantic-router)
in **standalone** mode (no Envoy). It serves an OpenAI-compatible API on port
8899 and routes each request to one of two backends based on `config.yaml`:

- `gpt-luna`: OpenAI (frontier tier), via `https://api.openai.com/v1`.
- `qwen`: a self-hosted Qwen served by vLLM, outside the namespace (for example
  on Nebius).

Clients use the model name `vllm-sr/auto` and the router picks the backend.

## Routing

This router is for coding tasks. Routing is by difficulty only, judged by the
decision model:

| Decision | Matches | Backend |
|---|---|---|
| `hard-route` | Difficulty `hard` | `gpt-luna` |
| `default-route` | Everything else (easy, medium) | `qwen` |

The decisions are in `recipes` in `config.yaml`. To send medium tasks to Luna as
well, add a `complexity` condition with `label: medium` to `hard-route` and
change its `operator` to `OR`.

## Configure

Edit the `TODO` values in `config.yaml`:

- `qwen`: `provider_model_id` (the vLLM `--served-model-name`), `endpoint`
  (`host:port`, no scheme) and `protocol` (`http` or `https`).
- `gpt-luna`: `provider_model_id` (the exact OpenAI model id).

The Qwen backend has no auth configured. If the server requires an API key, add
an `auth` block like the one on `gpt-luna` and a matching env var in
`deployment.yaml`.

## Deploy

```bash
NS=<namespace>

# OpenAI key, read by the router as OPENAI_API_KEY
oc create secret generic semantic-router-secret -n "$NS" \
  --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY"

oc apply -k semantic-router/ -n "$NS"
oc rollout status deployment/semantic-router -n "$NS" --timeout=60m
./semantic-router/test.sh "$NS"
```

The first start downloads the decision model (`vllm-sr/vela3-fast`) onto the
`semantic-router-models` PVC. That is the slow part; later starts are quick.

The ConfigMap keeps a stable name (the router patches it at runtime), so after
editing `config.yaml` run:

```bash
oc apply -k semantic-router/ -n "$NS"
oc rollout restart deployment/semantic-router -n "$NS"
```

## Test

`test.sh` runs against the deployed router:

1. A hard coding prompt, expected to log `hard-route` and select `gpt-luna`.
2. An easy coding prompt, expected to log `default-route` and select `qwen`.
3. A reachability probe from a separate pod to `http://semantic-router:8899`,
   the URL other pods in the namespace use.

Check decisions manually with:

```bash
oc logs deployment/semantic-router -n "$NS" --tail=100 | grep routing_decision
```

## Notes

- `config.yaml` must validate against the router's v0.5 schema, available in the
  upstream repo at `src/semantic-router/pkg/configschema/router-config-v0.5.schema.json`.
- `openai-compatible` has **no default auth header**. Keep `auth.header:
  Authorization` and `auth.prefix: Bearer` on the OpenAI backend, or the key is
  never sent.
- The Route is optional and unauthenticated (`listeners[].api_keys` is empty).
  Anyone with its hostname can spend the OpenAI key and the Qwen capacity. Delete
  `route.yaml` from `kustomization.yaml` unless you need external access.
- The Deployment's 12Gi memory limit is upstream's default. Run one router per
  small node.
- The namespace must allow egress to `api.openai.com` and to the Qwen host.
