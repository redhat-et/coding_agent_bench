#!/usr/bin/env python3
"""debug helper -- NOT part of the adapter/harness, just for reading
agent trajectory logs (jobs/*/*/agent/<agent>.txt) without staring at giant
single-line JSON blobs.

Different agents log different JSONL shapes; dispatch is by filename, which
is stable across scenarios/agents:
    claude-code.txt -> Claude Code's --output-format stream-json
                       (system/assistant/user/result)
    opencode.txt    -> opencode's own event stream (step_start/reasoning/
                       tool_use/step_finish)
    pi.txt          -> pi's own event stream (turn_end bundles thinking/
                       toolCall/toolResults/usage together)

Usage:
    python3 parse_agent_log.py <scenario-dir | log-file> [--show-reasoning] [--limit N]

    <scenario-dir>   a scenario dir (jobs/<job>/<scenario>); the log is picked
                     out of its agent/ subdir -- handy since the basename is
                     all you'd otherwise have to remember.
    --show-reasoning also print reasoning/thinking blocks (chain-of-thought);
                     hidden by default. Everything else (tool calls, output,
                     assistant text, per-turn stats) always shows.
    --limit N        truncate each tool's output to N chars (default 1000,
                     0 disables truncation).

Examples:
    python3 parse_agent_log.py jobs/it_bench_aa_claude_sonnet_5/scenario-1__Srz3oQF
    python3 parse_agent_log.py <scenario> --show-reasoning --limit 0 | less -R
"""

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
_RESET = "\033[0m"
_BOLD, _DIM = "\033[1m", "\033[2m"
_CYAN, _MAGENTA, _GREEN, _YELLOW, _BLUE, _RED, _GRAY = (
    "\033[36m", "\033[35m", "\033[32m", "\033[33m", "\033[34m", "\033[31m", "\033[90m",
)

# agent log basenames, in the order we prefer when handed a scenario dir
AGENT_LOGS = ("claude-code.txt", "opencode.txt", "pi.txt")

# ANSI CSI/OSC/other escape sequences that log content could smuggle into our terminal.
_ANSI_RE = re.compile(r"\x1B(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1B]*(?:\x07|\x1B\\)|[@-Z\\-_])")
# remaining C0 control chars and DEL, excluding the newlines/tabs we want to keep.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def sanitize(text) -> str:
    """Strip terminal control sequences from log-derived text before it's printed."""
    text = text if isinstance(text, str) else str(text)
    return _CONTROL_RE.sub("", _ANSI_RE.sub("", text))


def style(text: str, *codes: str) -> str:
    text = sanitize(text)
    return f"{''.join(codes)}{text}{_RESET}" if _COLOR else text


def fmt_ts(ts):
    """Timestamps are epoch-ms for opencode/pi, ISO-8601 for claude-code."""
    if not ts:
        return "?"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts / 1000, tz=UTC)
        else:
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is None:  # logs are UTC but sometimes omit the offset
                dt = dt.replace(tzinfo=UTC)
        return dt.strftime("%H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return str(ts)


def print_reasoning(ts, text, show):
    if not show or not text:
        return
    print(f"[{ts}] {style('reasoning', _DIM, _MAGENTA)}:")
    print(style(text, _DIM))


def print_text(ts, text):
    print(f"[{ts}] {style('text', _GREEN)}:")
    print(sanitize(text))


def print_tool_call(ts, tool, cmd, prompt="$"):
    print(f"[{ts}] {style(f'tool_use ({tool})', _CYAN)}:")
    print(f"  {style(prompt, _YELLOW)} {sanitize(cmd)}")


def print_tool_output(text, limit, tool=None):
    if not text:
        return
    truncated = bool(limit) and len(text) > limit
    label = f"output ({tool}):" if tool else "output:"
    print(style(f"  {label}", _DIM))
    for out_line in (text[:limit] if truncated else text).splitlines():
        print(style(f"    {out_line}", _DIM))
    if truncated:
        print(style(f"    ...[truncated, {len(text)} chars total]", _DIM, _YELLOW))


def print_tool_error(err, limit=0):
    text = str(err)
    truncated = bool(limit) and len(text) > limit
    print(style(f"  ERROR: {text[:limit] if truncated else text}", _RED, _BOLD))
    if truncated:
        print(style(f"    ...[truncated, {len(text)} chars total]", _DIM, _YELLOW))


def print_step_finish(ts, reason, tokens, cost):
    reason_color = _RED if reason in ("unknown", "error") else _BLUE
    print(style(f"[{ts}] step finish: reason={reason} tokens={tokens} cost={cost}", _DIM, reason_color))


def iter_events(path):
    with open(path, "r", errors="replace") as f:
        for lineno, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                yield lineno, json.loads(line)
            except json.JSONDecodeError as e:
                print(style(f"--- line {lineno}: could not parse ({e}) ---", _RED))
                print(sanitize(line[:300]))


# ---------------------------------------------------------------------------
# claude-code.txt: Claude Code's stream-json. One event per line:
#   system(init)  session header; assistant/user carry a full API `message`;
#   each assistant event holds a single content block (thinking/text/tool_use)
#   but shares its `message.id` + usage with the blocks of the same turn, and
#   the following user event holds the matching tool_result(s); `result` is the
#   run summary. Non-JSON lines (CLI warnings on stderr) can precede the stream.
# ---------------------------------------------------------------------------
_INPUT_KEYS = (
    "command", "file_path", "path", "file", "pattern", "glob", "url", "query",
    "prompt", "description", "skill", "subagent_type",
)
_TOKEN_KEYS = (
    "input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
)


def summarize_tool_input(inp):
    """Show the one field that identifies the call, plus short scalar extras."""
    if not isinstance(inp, dict):
        return str(inp)
    primary = next(
        ((k, inp[k]) for k in _INPUT_KEYS if isinstance(inp.get(k), str) and inp[k].strip()),
        None,
    )
    if primary is None:
        return json.dumps(inp)[:400]
    rest = {
        k: v
        for k, v in inp.items()
        if k != primary[0]
        and (isinstance(v, (bool, int, float)) or (isinstance(v, str) and len(v) <= 80))
    }
    return primary[1] if not rest else f"{primary[1]}  {json.dumps(rest)}"


def tool_result_text(part, tool_use_result):
    content = part.get("content")
    if isinstance(content, str):
        text = content
    else:
        text = "\n".join(
            c.get("text", "") for c in (content or []) if isinstance(c, dict)
        )
    if not text and isinstance(tool_use_result, dict):
        text = "\n".join(
            str(tool_use_result[k]) for k in ("stdout", "stderr") if tool_use_result.get(k)
        )
        if not text:
            text = json.dumps(tool_use_result)[:400]
    if isinstance(tool_use_result, dict) and tool_use_result.get("persistedOutputPath"):
        text += f"\n[full output persisted to {tool_use_result['persistedOutputPath']}]"
    return text


def parse_claude(path, show_reasoning, limit):
    tool_names = {}  # tool_use_id -> name, so tool_results can be labelled
    turn = None  # {id, ts, usage, stop} of the assistant turn being streamed
    last_ts, last_text = "?", None  # `result` carries no timestamp of its own

    def flush_turn():
        nonlocal turn
        if turn is None:
            return
        usage = turn["usage"]
        tokens = {k: usage[k] for k in _TOKEN_KEYS if usage.get(k)}
        print_step_finish(turn["ts"], turn["stop"] or "turn_end", tokens, 0)
        turn = None

    with open(path, "r", errors="replace") as f:
        for lineno, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line:
                continue
            if not line.startswith("{"):
                print(style(f"--- line {lineno}: non-JSON (harness stderr?) ---", _DIM, _YELLOW))
                print(style(line[:300], _DIM))
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as e:
                print(style(f"--- line {lineno}: could not parse ({e}) ---", _RED))
                print(sanitize(line[:300]))
                continue

            etype = event.get("type", "?")
            message = event.get("message")
            if not isinstance(message, dict):
                message = {}
            stamp = event.get("timestamp") or message.get("timestamp")
            if stamp:
                last_ts = fmt_ts(stamp)
            ts = style(last_ts, _GRAY)
            content = message.get("content")

            if etype == "system":
                subtype = event.get("subtype", "?")
                if subtype == "init":
                    print(style(
                        f"\n=== claude-code {event.get('claude_code_version', '')} "
                        f"model={event.get('model', '?')} cwd={event.get('cwd', '?')} ===",
                        _BOLD, _CYAN,
                    ))
                elif subtype != "thinking_tokens":  # pure streaming counters
                    print(f"[{ts}] {style(f'system ({subtype})', _MAGENTA)}")
                continue

            if etype == "assistant":
                mid = message.get("id")
                if turn is None or turn["id"] != mid:
                    flush_turn()
                    print(style(f"\n=== [{ts}] assistant ===", _BOLD, _CYAN))
                    turn = {"id": mid, "ts": ts, "usage": {}, "stop": message.get("stop_reason")}
                if isinstance(message.get("usage"), dict):
                    turn["usage"] = message["usage"]
                if message.get("stop_reason"):
                    turn["stop"] = message["stop_reason"]
                if isinstance(content, str):
                    print_text(ts, content)
                    continue
                for part in content or []:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type")
                    if ptype == "thinking":
                        thinking = part.get("thinking", "")
                        if show_reasoning and not thinking:
                            print(style("  (thinking block has no text in this log)", _DIM))
                            continue
                        print_reasoning(ts, thinking, show_reasoning)
                    elif ptype == "text":
                        last_text = part.get("text", "")
                        print_text(ts, last_text)
                    elif ptype == "tool_use":
                        name = part.get("name", "?")
                        tool_names[part.get("id")] = name
                        print_tool_call(
                            ts,
                            name,
                            summarize_tool_input(part.get("input")),
                            "$" if name in ("Bash", "bash") else "->",
                        )

                continue

            if etype == "user":
                flush_turn()
                tool_use_result = event.get("tool_use_result")
                if isinstance(content, str):
                    print_text(ts, content)
                    continue
                for part in content or []:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type")
                    if ptype == "text":
                        print_text(ts, part.get("text", ""))
                    elif ptype == "tool_result":
                        tool = tool_names.get(part.get("tool_use_id"), "?")
                        print(f"[{ts}] {style(f'tool_result ({tool})', _CYAN)}:")
                        if part.get("is_error"):
                            print_tool_error(
                                tool_result_text(part, tool_use_result) or "(no error message)", limit
                            )
                            continue
                        print_tool_output(tool_result_text(part, tool_use_result), limit)
                continue

            if etype == "result":
                flush_turn()
                print(style("\n=== run result ===", _BOLD, _CYAN))
                usage = event.get("usage") or {}
                tokens = {k: usage[k] for k in _TOKEN_KEYS if usage.get(k)}
                reason = event.get("terminal_reason") or event.get("subtype") or "?"
                print_step_finish(ts, reason, tokens, event.get("total_cost_usd", 0))
                print(style(
                    f"[{ts}] {event.get('num_turns', '?')} turns, "
                    f"{event.get('duration_ms', 0) / 1000:.1f}s, "
                    f"stop_reason={event.get('stop_reason', '?')}"
                    + (f", api_error={event['api_error_status']}" if event.get("api_error_status") else ""),
                    _DIM, _GRAY,
                ))
                if event.get("is_error"):
                    print_tool_error("run ended with is_error", limit)
                if event.get("result") and event["result"] != last_text:
                    print_text(ts, event["result"])
                continue

            print(f"[{ts}] {style(etype, _MAGENTA)}: {json.dumps(content or event)[:300]}")

    flush_turn()


# ---------------------------------------------------------------------------
# opencode.txt: one flat event per line (step_start/reasoning/text/tool_use/
# step_finish), timestamps are top-level epoch-ms.
# ---------------------------------------------------------------------------
def parse_opencode(path, show_reasoning, limit):
    for lineno, event in iter_events(path):
        etype = event.get("type", "?")
        ts = style(fmt_ts(event.get("timestamp")), _GRAY)
        part = event.get("part", {}) or {}

        if etype == "step_start":
            print(style(f"\n=== [{ts}] step start ===", _BOLD, _CYAN))

        elif etype == "reasoning":
            print_reasoning(ts, part.get("text", ""), show_reasoning)

        elif etype == "text":
            print_text(ts, part.get("text", ""))

        elif etype == "tool_use":
            tool = part.get("tool", "?")
            state = part.get("state", {}) or {}
            if state.get("status") == "error":
                print(f"[{ts}] {style(f'tool_use ({tool})', _CYAN)}:")
                print_tool_error(state.get("error", "(no error message)"), limit)
                continue
            inp = state.get("input")
            cmd = inp.get("command") if isinstance(inp, dict) else inp
            print_tool_call(ts, tool, cmd)
            print_tool_output(str(state.get("output", "") or ""), limit)

        elif etype == "step_finish":
            print_step_finish(ts, part.get("reason", "?"), part.get("tokens", {}), part.get("cost", 0))

        else:
            print(f"[{ts}] {style(etype, _MAGENTA)}: {json.dumps(part)[:300]}")


# ---------------------------------------------------------------------------
# pi.txt: richer per-line events (session/agent_start/turn_start/turn_end/
# agent_end); `turn_end` already bundles the assistant message (thinking/
# text/toolCall parts + usage/cost) together with the resulting toolResults,
# so that's the one event type worth rendering in full -- the parallel
# message_start/message_end/tool_execution_* stream is the same data,
# just re-emitted incrementally for live UIs.
# ---------------------------------------------------------------------------
def parse_pi(path, show_reasoning, limit):
    for lineno, event in iter_events(path):
        etype = event.get("type", "?")

        if etype == "turn_start":
            print(style("\n=== turn start ===", _BOLD, _CYAN))
            continue
        if etype in ("session", "agent_start", "agent_end"):
            continue  # markers / full-history dump, nothing new to show

        if etype != "turn_end":
            continue

        message = event.get("message", {}) or {}
        ts = style(fmt_ts(message.get("timestamp")), _GRAY)

        tool_calls = {}  # id -> (name, args) so we can pair with toolResults below
        for part in message.get("content", []) or []:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "thinking":
                print_reasoning(ts, part.get("thinking", ""), show_reasoning)
            elif ptype == "text":
                print_text(ts, part.get("text", ""))
            elif ptype == "toolCall":
                name = part.get("name", "?")
                args = part.get("arguments", {})
                cmd = args.get("command") if isinstance(args, dict) else args
                tool_calls[part.get("id")] = name
                print_tool_call(ts, name, cmd)

        for tr in event.get("toolResults", []) or []:
            if not isinstance(tr, dict):
                continue
            tool = tr.get("toolName") or tool_calls.get(tr.get("toolCallId"), "?")
            text = "\n".join(
                c.get("text", "") for c in (tr.get("content") or []) if isinstance(c, dict)
            )
            print_tool_output(text, limit, tool)

        usage = message.get("usage", {}) or {}
        cost = (usage.get("cost") or {}).get("total", 0)
        tokens = {k: usage.get(k) for k in ("input", "output", "cacheRead", "cacheWrite", "totalTokens") if k in usage}
        print_step_finish(ts, message.get("stopReason", "?"), tokens, cost)


PARSERS = {
    "claude-code.txt": parse_claude,
    "opencode.txt": parse_opencode,
    "pi.txt": parse_pi,
}


def resolve_log(arg):
    """A scenario dir is enough: the log lives in its agent/ subdir."""
    if os.path.isfile(arg):
        return arg
    if not os.path.isdir(arg):
        sys.exit(sanitize(f"error: no such file or directory: {arg}"))
    agent_dir = arg if os.path.basename(os.path.normpath(arg)) == "agent" else os.path.join(arg, "agent")
    if not os.path.isdir(agent_dir):
        scenarios = sorted(
            d for d in os.listdir(arg) if os.path.isdir(os.path.join(arg, d, "agent"))
        )
        hint = (
            f"\nthis looks like a job dir -- point at one scenario instead, e.g. "
            f"{os.path.join(arg, scenarios[0])}"
            if scenarios
            else ""
        )
        sys.exit(sanitize(f"error: no agent/ dir under {arg}{hint}"))
    for name in AGENT_LOGS:
        candidate = os.path.join(agent_dir, name)
        if os.path.isfile(candidate):
            return candidate
    candidates = sorted(f for f in os.listdir(agent_dir) if f.endswith(".txt"))
    if len(candidates) == 1:
        return os.path.join(agent_dir, candidates[0])
    if not candidates:
        sys.exit(sanitize(f"error: no agent log (*.txt) under {agent_dir}"))
    sys.exit(sanitize(f"error: several logs under {agent_dir}: {candidates} -- pass one explicitly"))


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        epilog="logs: " + ", ".join(PARSERS),
    )
    parser.add_argument(
        "path", help="scenario dir (reads its agent/<agent>.txt) or an explicit agent log file"
    )
    parser.add_argument(
        "--show-reasoning",
        action="store_true",
        help="also print reasoning/thinking blocks (chain-of-thought); hidden by default",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="truncate each tool output to N chars (default: %(default)s, 0 = no limit)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    path = resolve_log(args.path)
    name = os.path.basename(path)
    parser = PARSERS.get(name)
    if parser is None:
        print(style(f"unknown agent log filename {name!r} -- defaulting to opencode's format", _YELLOW))
        parser = parse_opencode
    parser(path, args.show_reasoning, args.limit)


if __name__ == "__main__":
    main()
