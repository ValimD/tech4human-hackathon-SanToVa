"""Processamento inicial de eventos recebidos pelo servidor MCP."""

import json
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage


class MCPToolClient(Protocol):
    """Contrato mínimo do cliente MCP usado pelo processador."""

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Executa uma ferramenta MCP."""


class ChatModel(Protocol):
    """Contrato mínimo do modelo usado pelo processador."""

    def invoke(self, messages: list[Any]) -> Any:
        """Gera uma resposta para as mensagens."""


def _decode_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content", [])
    if not content:
        return result
    text = content[0].get("text") if isinstance(content[0], dict) else None
    if not isinstance(text, str):
        raise ValueError("Resposta MCP sem conteúdo textual")
    decoded = json.loads(text)
    if not isinstance(decoded, dict):
        raise ValueError("Resposta MCP não contém um objeto JSON")
    return decoded


def process_next_event(
    mcp: MCPToolClient,
    model: ChatModel,
    *,
    agent_name: str,
) -> dict[str, str] | None:
    """Pega um evento, gera uma resposta e registra o atendimento."""

    result = _decode_tool_result(
        mcp.call_tool(
            "proximo_evento",
            {"agente": agent_name, "esperar_segundos": 0},
        )
    )
    event = result.get("evento")
    if not isinstance(event, dict):
        return None

    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("Evento MCP sem id válido")

    prompt = (
        f"Remetente: {event.get('de', 'desconhecido')}\n"
        f"Assunto: {event.get('assunto', '')}\n"
        f"Mensagem: {event.get('corpo', '')}"
    )
    model_result = model.invoke(
        [
            SystemMessage(
                content=(
                    "Você é o agente orquestrador de suporte N1. "
                    "Responda com clareza e não invente informações."
                )
            ),
            HumanMessage(content=prompt),
        ]
    )
    response = getattr(model_result, "content", None)
    if not isinstance(response, str) or not response.strip():
        raise ValueError("O modelo retornou uma resposta vazia ou inválida")

    mcp.call_tool(
        "responder_evento",
        {
            "agente": agent_name,
            "evento_id": event_id,
            "mensagem": response,
            "aguardar_resposta": False,
        },
    )
    return {"event_id": event_id, "response": response}
