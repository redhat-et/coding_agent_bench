import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


OPENCODE_BINARY = os.environ.get("OPENCODE_BINARY")


def _sse_chunk(model, delta, finish_reason=None):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": model,
        "choices": [
            {"index": 0, "delta": delta, "finish_reason": finish_reason}
        ],
    }


def _sse(*chunks):
    return (
        "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
        + "data: [DONE]\n\n"
    )


class _MockModelHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests: list[dict]

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        self.requests.append({"headers": dict(self.headers), **body})
        has_tools = bool(body.get("tools"))
        has_tool_result = any(
            message.get("role") == "tool" for message in body.get("messages", [])
        )

        if not has_tools:
            payload = self._stream(
                body["model"],
                {"role": "assistant", "content": "session title"},
            )
        elif body["model"] == "primary" and not has_tool_result:
            arguments = json.dumps(
                {
                    "description": "Request review",
                    "prompt": "Review this controlled delegation test.",
                    "subagent_type": "reviewer",
                }
            )
            payload = self._stream(
                "primary",
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_reviewer",
                            "type": "function",
                            "function": {
                                "name": "task",
                                "arguments": arguments,
                            },
                        }
                    ],
                },
                "tool_calls",
            )
        elif body["model"] == "reviewer":
            payload = self._stream(
                "reviewer",
                {
                    "role": "assistant",
                    "content": "REVIEWER_MODEL_USED:reviewer;FINDING:delegation works",
                },
            )
        else:
            payload = self._stream(
                "primary",
                {"role": "assistant", "content": "PRIMARY_CONSUMED_REVIEW:delegation works"},
            )

        data = payload.encode()
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()
        self.close_connection = True

    def _stream(self, model, delta, finish_reason=None):
        return _sse(
            _sse_chunk(model, delta, finish_reason),
            _sse_chunk(model, {}, "stop" if finish_reason is None else finish_reason),
        )

    def log_message(self, *_args):
        pass


@pytest.mark.skipif(
    OPENCODE_BINARY is None,
    reason="Set OPENCODE_BINARY to the pinned OpenCode 1.18.1 executable",
)
def test_opencode_1_18_1_routes_and_delegates(tmp_path):
    version = subprocess.run(
        [OPENCODE_BINARY, "--version"],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.strip()
    assert version == "1.18.1"

    handler_requests: list[dict] = []
    _MockModelHandler.requests = handler_requests
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockModelHandler)
    endpoint = f"http://127.0.0.1:{server.server_port}/v1"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        home = tmp_path / "home"
        config_dir = home / ".config" / "opencode"
        config_dir.mkdir(parents=True)
        config = {
            "$schema": "https://opencode.ai/config.json",
            "model": "mock/primary",
            "provider": {
                "mock": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Mock",
                    "options": {"baseURL": endpoint, "apiKey": "mock-key"},
                    "models": {
                        "primary": {"name": "Primary"},
                        "reviewer": {"name": "Reviewer"},
                    },
                }
            },
            "agent": {
                "reviewer": {
                    "description": "Review code",
                    "mode": "subagent",
                    "model": "mock/reviewer",
                    "permission": {"edit": "deny", "bash": "deny"},
                    "prompt": "Review the request and report findings.",
                }
            },
        }
        (config_dir / "opencode.json").write_text(json.dumps(config))

        result = subprocess.run(
            [
                OPENCODE_BINARY,
                "run",
                "--format=json",
                "--model=mock/primary",
                "Use the reviewer subagent.",
            ],
            cwd=tmp_path,
            env={
                "HOME": str(home),
                "PATH": "/usr/bin:/bin",
                "NO_COLOR": "1",
            },
            capture_output=True,
            text=True,
            timeout=45,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.returncode == 0, result.stderr
    assert [request["model"] for request in handler_requests] == [
        "primary",
        "primary",
        "reviewer",
        "primary",
    ]
    assert all(
        request["headers"].get("Authorization") == "Bearer mock-key"
        for request in handler_requests
    )
    reviewer_request = handler_requests[2]
    assert reviewer_request["messages"][0]["content"].startswith(
        "Review the request and report findings."
    )
    assert "exact model ID is mock/reviewer" in reviewer_request["messages"][0]["content"]
    assert '"tool":"task"' in result.stdout
    assert '"modelID":"reviewer"' in result.stdout
    assert "PRIMARY_CONSUMED_REVIEW:delegation works" in result.stdout


@pytest.mark.skipif(
    OPENCODE_BINARY is None,
    reason="Set OPENCODE_BINARY to the pinned OpenCode 1.18.1 executable",
)
def test_opencode_1_18_1_reports_unavailable_reviewer_model_without_fallback(tmp_path):
    version = subprocess.run(
        [OPENCODE_BINARY, "--version"],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.strip()
    assert version == "1.18.1"

    handler_requests: list[dict] = []
    _MockModelHandler.requests = handler_requests
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockModelHandler)
    endpoint = f"http://127.0.0.1:{server.server_port}/v1"
    threading.Thread(target=server.serve_forever, daemon=True).start()

    home = tmp_path / "home"
    config_dir = home / ".config" / "opencode"
    config_dir.mkdir(parents=True)
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": "mock/primary",
        "provider": {
            "mock": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Mock",
                "options": {
                    "baseURL": endpoint,
                    "apiKey": "mock-key",
                },
                "models": {"primary": {"name": "Primary"}},
            }
        },
        "agent": {
            "reviewer": {
                "description": "Review code",
                "mode": "subagent",
                "model": "mock/reviewer",
                "permission": {"edit": "deny", "bash": "deny"},
                "prompt": "Review the request and report findings.",
            }
        },
    }
    (config_dir / "opencode.json").write_text(json.dumps(config))

    try:
        result = subprocess.run(
            [
                OPENCODE_BINARY,
                "run",
                "--format=json",
                "--model=mock/primary",
                "Use the reviewer subagent.",
            ],
            cwd=tmp_path,
            env={"HOME": str(home), "PATH": "/usr/bin:/bin", "NO_COLOR": "1"},
            capture_output=True,
            text=True,
            timeout=45,
        )
    finally:
        server.shutdown()
        server.server_close()

    output = result.stderr + result.stdout
    assert "Model not found: mock/reviewer." in output
    assert '"status":"error"' in output
    assert not any(request["model"] == "reviewer" for request in handler_requests)
