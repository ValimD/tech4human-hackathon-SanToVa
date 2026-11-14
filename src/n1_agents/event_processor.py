"""Processamento inicial de eventos recebidos pelo servidor MCP."""

import json
import time
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


class EventBatchReadError(RuntimeError):
    """Falha de coleta com os eventos já consumidos disponíveis ao chamador."""

    def __init__(self, code: int | None, events: list[dict[str, Any]]) -> None:
        self.events = list(events)
        self.code = code
        label = str(code) if code is not None else "não informado"
        super().__init__(
            f"MCP falhou ao buscar eventos: proximo_evento, código {label}; "
            "confira o painel/log do servidor antes de repetir."
        )


def _receive_event(mcp: MCPToolClient, *, wait_seconds: int) -> dict[str, Any]:
    """Repete somente 503 explícito no resultado da ferramenta, até três vezes."""
    for attempt in range(3):
        raw = mcp.call_tool(
            "proximo_evento",
            {"agente": "orquestrador", "esperar_segundos": wait_seconds},
        )
        result = _decode_tool_result(raw)
        if not raw.get("isError") and result.get("status") != "erro":
            return result
        value = result.get("codigo")
        # Não inclua texto livre do servidor: ele pode conter dados pessoais.
        code = value if type(value) is int else None
        if code == 410:
            return {"evento": None, "encerrado": True}
        if code != 503 or attempt == 2:
            raise EventBatchReadError(code, [])
        time.sleep(0.5)
    raise AssertionError("Tentativas de coleta esgotadas")


def receive_event_batch(
    mcp: MCPToolClient, *, limit: int = 5
) -> tuple[list[dict[str, Any]], bool]:
    """Consome até cinco eventos; espera somente quando o lote está vazio.

    Cada chamada marca um evento como lido no MCP. Erros são explícitos;
    a função não repete uma leitura que possa ter consumido um evento.
    """
    if not 1 <= limit <= 5:
        raise ValueError("limit deve estar entre 1 e 5")
    events: list[dict[str, Any]] = []
    for _ in range(limit):
        try:
            result = _receive_event(mcp, wait_seconds=10 if not events else 0)
        except EventBatchReadError as error:
            raise EventBatchReadError(error.code, events) from None
        closed = result.get("encerrado", False)
        if not isinstance(closed, bool) or "evento" not in result:
            raise ValueError("Resposta MCP de eventos inválida")
        event = result["evento"]
        if event is not None:
            if not isinstance(event, dict) or any(
                not isinstance(event.get(key), str) or not event[key].strip()
                for key in ("id", "de")
            ):
                raise ValueError("Evento MCP sem id ou remetente válido")
            if event["id"] in {item["id"] for item in events}:
                raise ValueError("Evento MCP repetido no lote")
            events.append(event)
        if event is None:
            return events, closed
        # A resposta que entrega um evento ainda precisa ser drenada. Alguns
        # servidores anunciam o encerramento junto do último evento; somente
        # uma resposta sem evento é terminal para o loop externo.
    return events, False
