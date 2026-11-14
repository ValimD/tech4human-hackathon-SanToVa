"""Comandos de diagnóstico e leitura da caixa de entrada MCP."""

import json
from typing import Any

from .config import get_settings
from .event_processor import _decode_tool_result
from .mcp_client import MCPClient


def list_all_events(
    client: MCPClient,
    *,
    agent_name: str,
    page_size: int = 200,
) -> list[dict[str, Any]]:
    """Lista todos os eventos, respeitando a paginação do servidor MCP."""

    events: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = _decode_tool_result(
            client.call_tool(
                "listar_eventos",
                {
                    "agente": agent_name,
                    "limite": page_size,
                    "offset": offset,
                },
            )
        )
        page = result.get("eventos", [])
        if not isinstance(page, list):
            raise ValueError("MCP retornou uma lista de eventos inválida")
        events.extend(event for event in page if isinstance(event, dict))
        if not result.get("tem_mais", False):
            return events
        if not page:
            raise RuntimeError(
                "MCP indicou mais eventos, mas retornou uma página vazia"
            )
        offset += len(page)


def main() -> None:
    """Testa a sessão MCP e imprime todos os eventos encontrados."""

    settings = get_settings()
    with MCPClient(
        settings.mcp_endpoint,
        timeout=settings.mcp_timeout_seconds,
    ) as client:
        tools = client.list_tools()
        events = list_all_events(client, agent_name=settings.agent_name)

    print(f"MCP conectado: {settings.mcp_endpoint}")
    print(f"Ferramentas disponíveis: {len(tools)}")
    print(f"Eventos encontrados: {len(events)}")
    print(json.dumps(events, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
