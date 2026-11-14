import json

import httpx

from n1_agents.mcp_client import MCPClient


def _sse(payload: dict) -> httpx.Response:
    body = f"event: message\ndata: {json.dumps(payload)}\n\n"
    return httpx.Response(
        200,
        headers={
            "content-type": "text/event-stream",
            "mcp-session-id": "test-session",
        },
        content=body,
    )


def test_client_initializes_session_and_lists_tools() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body["method"] == "initialize":
            return _sse(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"capabilities": {"tools": {}}},
                }
            )
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return _sse(
            {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"tools": [{"name": "proximo_evento"}]},
            }
        )

    with MCPClient(
        "http://localhost:8765/mcp",
        transport=httpx.MockTransport(handler),
    ) as client:
        tools = client.list_tools()

    assert tools == [{"name": "proximo_evento"}]
    assert calls[0]["method"] == "initialize"
    assert calls[1]["method"] == "notifications/initialized"
    assert calls[2]["method"] == "tools/list"


def test_client_retries_a_503_up_to_three_attempts() -> None:
    initialize_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        nonlocal initialize_attempts
        if body["method"] == "initialize":
            initialize_attempts += 1
        if body["method"] == "initialize" and initialize_attempts < 3:
            return httpx.Response(503, content="temporarily unavailable")
        if body["method"] == "initialize":
            return _sse(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"capabilities": {"tools": {}}},
                }
            )
        return httpx.Response(202)

    with MCPClient(
        "http://localhost:8765/mcp",
        retry_delay_seconds=0,
        transport=httpx.MockTransport(handler),
    ):
        pass

    assert initialize_attempts == 3
