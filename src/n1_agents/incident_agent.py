"""Agente executor responsável por abrir e atualizar incidentes."""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from .graph import build_graph
from .mcp_tools import (
    INCIDENT_TOOL_NAMES,
    MCPToolProvider,
    create_mcp_tools,
)
from .prompts import INCIDENT_SYSTEM_PROMPT


class IncidentHandoff(BaseModel):
    """Contrato enviado pelo orquestrador ao agente de incidentes."""

    evento_id: str
    remetente: str
    destino: Literal["incidente"]
    criticidade: Literal["P0", "P1", "P2"]
    categoria: Literal["incidente_produto", "followup"]
    produto: Literal["Portal do Cliente", "App Agenda", "Painel de Vendas"]
    motivo: str = Field(min_length=1, max_length=2000)
    sinais: dict = Field(default_factory=dict)
    relacionados: list[str] = Field(default_factory=list)
    ligar_a: str | None = None


class IncidentResult(BaseModel):
    """Contrato devolvido ao orquestrador após a execução."""

    evento_id: str
    acao: Literal["aberto", "duplicado", "reclassificado", "falhou"]
    incidente_id: str | None = None
    criticidade: Literal["P0", "P1", "P2"]
    motivo: str = Field(min_length=1, max_length=2000)


def parse_incident_result(content: str) -> IncidentResult:
    """Valida a resposta JSON produzida pelo agente executor."""

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError("Agente de incidentes não retornou JSON válido") from error
    return IncidentResult.model_validate(payload)


def build_incident_graph(model=None, tools=None, *, max_iterations: int = 8):
    """Monta o grafo do executor com o prompt e tools de incidentes."""

    return build_graph(
        model=model,
        tools=tools,
        system_prompt=INCIDENT_SYSTEM_PROMPT,
        max_iterations=max_iterations,
    )


def run_incident_agent(
    handoff: IncidentHandoff,
    *,
    model,
    client: MCPToolProvider,
) -> IncidentResult:
    """Executa um handoff estruturado sem expor tools ao orquestrador."""

    tools = create_mcp_tools(
        client,
        agent_name="agente-incidente",
        allowed_names=INCIDENT_TOOL_NAMES,
    )
    required_tools = {"consultar", "registrar", "atualizar", "enviar_mensagem"}
    available_tools = {tool.name for tool in tools}
    missing_tools = required_tools - available_tools
    if missing_tools:
        raise RuntimeError(
            "MCP não publicou tools obrigatórias de incidente: "
            + ", ".join(sorted(missing_tools))
        )

    graph = build_incident_graph(model=model, tools=tools, max_iterations=8)
    result = graph.invoke(
        {
            "messages": [],
            "user_input": handoff.model_dump_json(),
        }
    )
    if not any(
        getattr(message, "type", None) == "tool"
        for message in result.get("messages", [])
    ):
        raise RuntimeError(
            "Agente de incidentes encerrou sem executar uma tool MCP"
        )
    if result.get("status") == "stopped":
        return IncidentResult(
            evento_id=handoff.evento_id,
            acao="falhou",
            criticidade=handoff.criticidade,
            motivo=result["response"],
        )
    return parse_incident_result(result["response"])
