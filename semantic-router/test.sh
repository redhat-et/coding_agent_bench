#!/usr/bin/env bash
# Smoke-test a standalone router deployment through a local port-forward.
#
#   ./semantic-router/test.sh <namespace> ["prompt"]
#
# Sends a hard coding prompt (expect gpt-luna), an easy one (expect qwen), and
# probes the Service from a separate pod. Requires semantic-router-secret/OPENAI_API_KEY.
# The hard prompt gets a 10000-token budget: GPT Luna is a reasoning model and
# spends thousands of tokens thinking before it writes any text.
set -euo pipefail

NS="${1:?usage: $0 <namespace> [prompt]}"
PROMPT="${2:-Design and implement a thread-safe LRU cache with TTL expiry and write a proof of its amortized O(1) complexity}"
PORT=18899

oc rollout status deployment/semantic-router -n "$NS" --timeout=60m

oc port-forward svc/semantic-router "$PORT":8899 -n "$NS" >/tmp/sr-port-forward.log 2>&1 &
PF=$!
trap 'kill "$PF" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "== /v1/models =="
curl -s "http://127.0.0.1:$PORT/v1/models" | head -c 400; echo

echo "== hard coding prompt (expect hard-route -> gpt-luna) =="
code=$(curl -s -o /tmp/sr-chat.json -w '%{http_code}' \
  -X POST "http://127.0.0.1:$PORT/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"vllm-sr/auto\",\"max_tokens\":10000,\"messages\":[{\"role\":\"user\",\"content\":\"$PROMPT\"}]}")
echo "HTTP $code"
head -c 400 /tmp/sr-chat.json; echo

echo "== easy coding prompt (expect default-route -> qwen) =="
code=$(curl -s -o /tmp/sr-chat2.json -w '%{http_code}' \
  -X POST "http://127.0.0.1:$PORT/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"vllm-sr/auto","max_tokens":2000,"messages":[{"role":"user","content":"Write a python function that returns the sum of two numbers."}]}')
echo "HTTP $code"
head -c 400 /tmp/sr-chat2.json; echo

echo "== in-cluster reachability (separate pod -> http://semantic-router:8899) =="
oc run sr-probe -n "$NS" --rm -i --restart=Never --quiet \
  --image=registry.access.redhat.com/ubi9/ubi-minimal -- \
  curl -s -m 20 -w '\nHTTP %{http_code}\n' http://semantic-router:8899/v1/models || echo "probe failed"

echo "== router decisions =="
oc logs deployment/semantic-router -n "$NS" --tail=200 \
  | grep -o '"decision":"[^"]*"\|"selected_model":"[^"]*"' | tail -8 || true
