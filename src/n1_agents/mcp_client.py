"""Cliente mínimo para o transporte MCP Streamable HTTP."""

import json
import time
from typing import Any

import httpx


class MCPClient:
    """Mantém uma sessão MCP e executa ferramentas do servidor remoto."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout: float = 15.0,
        max_attempts: int = 3,
        retry_delay_seconds: float = 0.5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts deve ser maior ou igual a 1")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds não pode ser negativo")
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self._endpoint = endpoint
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._session_id: str | None = None
        self._request_id = 0
        self._initialize()

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(1, self._max_attempts + 1):
            response = self._http.post(
                self._endpoint,
                headers=self._headers(),
                json=payload,
            )
            if response.status_code < 400:
                break
            if response.status_code != 503 or attempt == self._max_attempts:
                raise RuntimeError(
                    f"MCP respondeu HTTP {response.status_code}: {response.text}"
                )
            time.sleep(self._retry_delay_seconds)

        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id

        if not response.content:
            return {}
        if response.headers.get("content-type", "").startswith(
            "text/event-stream"
        ):
            for line in response.text.splitlines():
                if line.startswith("data: "):
                    return json.loads(line[6:])
            raise RuntimeError("MCP retornou um stream sem mensagem JSON")
        return response.json()

    def _initialize(self) -> None:
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "n1-support-agents",
                        "version": "0.1.0",
                    },
                },
            }
        )
        if "error" in result:
            raise RuntimeError(f"Falha ao inicializar MCP: {result['error']}")
        self._post(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )

    def list_tools(self) -> list[dict[str, Any]]:
        """Retorna as ferramentas publicadas pelo servidor MCP."""

        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "tools/list",
                "params": {},
            }
        )
        if "error" in result:
            raise RuntimeError(f"Falha ao listar ferramentas MCP: {result['error']}")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Executa uma ferramenta MCP e retorna seu resultado estruturado."""

        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in result:
            raise RuntimeError(f"Falha ao executar ferramenta MCP: {result['error']}")
        return result.get("result", {})
