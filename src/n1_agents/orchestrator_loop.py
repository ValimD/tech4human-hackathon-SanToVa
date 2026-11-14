"""Loop externo que despacha decisões do orquestrador aos executores."""

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from .graph import build_graph
from .incident_agent import IncidentHandoff, IncidentResult, run_incident_agent
from .mcp_tools import MCPToolProvider, create_mcp_tools
from .model import create_chat_model


class OrchestratorDecision(BaseModel):
    """Contrato de decisão produzido pelo orquestrador."""

    status: Literal["routed", "idle"] = "routed"
    evento_id: str | None = None
    remetente: str | None = None
    destino: Literal["seguranca", "incidente", "ferias", "chamado"] | None = None
    criticidade: Literal["P0", "P1", "P2", "P3", "P4"] | None = None
    categoria: str | None = None
    produto: str | None = None
    motivo: str = Field(min_length=1, max_length=2000)
    sinais: dict[str, Any] = Field(default_factory=dict)
    relacionados: list[str] = Field(default_factory=list)
    ligar_a: str | None = None


def parse_orchestrator_decision(content: str) -> OrchestratorDecision:
    """Valida o JSON retornado pelo orquestrador."""

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError("Orquestrador não retornou JSON válido") from error
    return OrchestratorDecision.model_validate(payload)


def dispatch_decision(
    decision: OrchestratorDecision,
    *,
    model,
    client: MCPToolProvider,
) -> IncidentResult | None:
    """Despacha somente decisões de incidente para o executor implementado."""

    if decision.status == "idle" or decision.destino != "incidente":
        return None
    if not decision.evento_id or not decision.remetente:
        raise ValueError("Handoff de incidente sem evento_id ou remetente")
    if decision.criticidade not in {"P0", "P1", "P2"}:
        raise ValueError("Incidente precisa ter criticidade P0, P1 ou P2")
    if decision.produto not in {
        "Portal do Cliente",
        "App Agenda",
        "Painel de Vendas",
    }:
        raise ValueError("Incidente precisa ter um produto conhecido")

    handoff = IncidentHandoff(
        evento_id=decision.evento_id,
        remetente=decision.remetente,
        destino="incidente",
        criticidade=decision.criticidade,
        categoria=(
            decision.categoria
            if decision.categoria in {"incidente_produto", "followup"}
            else "incidente_produto"
        ),
        produto=decision.produto,
        motivo=decision.motivo,
        sinais=decision.sinais,
        relacionados=decision.relacionados,
        ligar_a=decision.ligar_a,
    )
    return run_incident_agent(handoff, model=model, client=client)


def run_orchestrator_loop(
    prompt: str,
    *,
    client: MCPToolProvider,
    model=None,
    max_events: int = 20,
) -> list[OrchestratorDecision | IncidentResult]:
    """Processa eventos até ficar ocioso ou atingir o limite configurado."""

    if max_events < 1:
        raise ValueError("max_events deve ser maior ou igual a 1")
    resolved_model = model or create_chat_model()
    tools = create_mcp_tools(client, agent_name="orquestrador")
    graph = build_graph(model=resolved_model, tools=tools, max_iterations=2)
    results: list[OrchestratorDecision | IncidentResult] = []
    current_prompt = prompt

    for _ in range(max_events):
        state = graph.invoke({"messages": [], "user_input": current_prompt})
        decision = parse_orchestrator_decision(state["response"])
        if decision.status == "idle":
            break
        results.append(decision)
        incident_result = dispatch_decision(
            decision,
            model=resolved_model,
            client=client,
        )
        if incident_result:
            results.append(incident_result)
        current_prompt = (
            "Processe o próximo evento disponível. Se não houver evento, "
            "retorne status idle."
        )
    return results
