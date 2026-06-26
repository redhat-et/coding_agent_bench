#!/bin/sh
if [ $# -lt 2 ]; then
  echo "Usage: $0 <server-url> <model-name> [n-tasks]"
  echo "Example: $0 http://qwen36-27b-coding-agent-leaderboard.apps.example.com qwen3.6-27b 4"
  exit 1
fi

SERVER_URL="$1"
MODEL_NAME="$2"
N_TASKS="${3:-4}"

uv run harbor run -a claude-code -d scale-ai/swe-bench-pro \
    -i '*ansible*' \
    --ae ANTHROPIC_BASE_URL="$SERVER_URL" \
    --ae ANTHROPIC_API_KEY='sk-no-key-required' \
    --ae ANTHROPIC_MODEL="$MODEL_NAME" \
    --ae ANTHROPIC_DEFAULT_OPUS_MODEL="$MODEL_NAME" \
    --ae ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL_NAME" \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL="$MODEL_NAME" \
    --n-tasks "$N_TASKS"
