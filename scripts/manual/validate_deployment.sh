#!/bin/sh

if [ $# -lt 2 ]; then
  echo "Usage: $0 <server-url> <model-name> [concurrency]"
  echo "Example: $0 http://qwen36-27b-coding-agent-leaderboard.apps.example.com qwen3.6-27b 8"
  exit 1
fi

SERVER_URL="$1"
MODEL_NAME="$2"
CONCURRENCY="${3:-8}"
PASS=0
FAIL=0

echo "=== Validating deployment: $MODEL_NAME ==="
echo "Server: $SERVER_URL"
echo ""

# Check 1: Max model length
echo "--- Check 1: Max model length ---"
MAX_LEN=$(curl -s "$SERVER_URL/v1/models" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for m in data['data']:
    if m['id']=='$MODEL_NAME':
        print(m['max_model_len'])
" 2>/dev/null)

if [ -n "$MAX_LEN" ] && [ "$MAX_LEN" -gt 0 ] 2>/dev/null; then
  echo "max_model_len: $MAX_LEN"
  echo "PASS"
  PASS=$((PASS+1))
else
  echo "Could not retrieve max_model_len"
  echo "FAIL"
  FAIL=$((FAIL+1))
fi
echo ""

# Check 2: Concurrency
echo "--- Check 2: ${CONCURRENCY}x concurrency ---"
RESULTS_DIR=$(mktemp -d)
for i in $(seq 1 "$CONCURRENCY"); do
  curl -s --max-time 120 -o /dev/null -w "%{http_code}" \
    "$SERVER_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL_NAME\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello\"}],\"max_tokens\":10}" \
    > "$RESULTS_DIR/$i" &
done
wait

OK=0
for i in $(seq 1 "$CONCURRENCY"); do
  CODE=$(cat "$RESULTS_DIR/$i")
  if [ "$CODE" = "200" ]; then
    OK=$((OK+1))
  fi
done
rm -rf "$RESULTS_DIR"

echo "$OK/$CONCURRENCY requests returned 200"
if [ "$OK" -eq "$CONCURRENCY" ]; then
  echo "PASS"
  PASS=$((PASS+1))
else
  echo "FAIL"
  FAIL=$((FAIL+1))
fi
echo ""

# Check 3: Tool calling
echo "--- Check 3: Tool calling ---"
echo "Sending tool calling request (this may take a minute)..."
TOOL_RESPONSE_FILE=$(mktemp)
curl -s --max-time 120 "$SERVER_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL_NAME\",
    \"messages\": [{\"role\": \"user\", \"content\": \"What is the weather in Boston?\"}],
    \"max_tokens\": 512,
    \"tools\": [{
      \"type\": \"function\",
      \"function\": {
        \"name\": \"get_weather\",
        \"description\": \"Get the current weather for a location\",
        \"parameters\": {
          \"type\": \"object\",
          \"properties\": {
            \"location\": {\"type\": \"string\", \"description\": \"City name\"}
          },
          \"required\": [\"location\"]
        }
      }
    }],
    \"tool_choice\": \"auto\"
  }" > "$TOOL_RESPONSE_FILE"

if [ ! -s "$TOOL_RESPONSE_FILE" ]; then
  echo "No response from server (timeout or connection error)"
  echo "FAIL"
  FAIL=$((FAIL+1))
else
  echo "Raw response:"
  python3 -c "import json; print(json.dumps(json.load(open('$TOOL_RESPONSE_FILE')),indent=2))" 2>/dev/null || cat "$TOOL_RESPONSE_FILE"
  echo ""

  HAS_TOOL_CALL=$(python3 -c "
import json
data=json.load(open('$TOOL_RESPONSE_FILE'))
choices=data.get('choices',[])
if choices and choices[0].get('message',{}).get('tool_calls'):
    print('yes')
else:
    print('no')
" 2>/dev/null || echo "error")

  if [ "$HAS_TOOL_CALL" = "yes" ]; then
    echo "PASS"
    PASS=$((PASS+1))
  else
    echo "FAIL"
    FAIL=$((FAIL+1))
  fi
fi
rm -f "$TOOL_RESPONSE_FILE"
echo ""

# Summary
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
