#!/bin/sh
SERVER_URL="${1:-http://your-model-route.apps.example.com}"
CONCURRENCY="${2:-8}"

echo "Testing $CONCURRENCY concurrent requests against $SERVER_URL"
echo ""

for i in $(seq 1 "$CONCURRENCY"); do
  curl -s -o /dev/null -w "Request $i: %{http_code} (%{time_total}s)\n" \
    "$SERVER_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen3.6-27b","messages":[{"role":"user","content":"Say hello"}],"max_tokens":10}' &
done
wait

echo ""
echo "Done."
