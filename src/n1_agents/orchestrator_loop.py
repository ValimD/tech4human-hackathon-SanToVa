"""Loop externo que despacha decisões do orquestrador aos executores."""

import json
import re
from collections.abc import Callable
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from .event_processor import EventBatchReadError, receive_event_batch
from .graph import build_graph
from .incident_agent import IncidentHandoff, IncidentResult, run_incident_agent
from .mcp_tools import ORCHESTRATOR_TOOL_NAMES, MCPToolProvider, create_mcp_tools
from .model import create_chat_model
from .prompts import ORCHESTRATOR_BATCH_PROMPT


class OrchestratorDecision(BaseModel):
    """Contrato de decisão produzido pelo orquestrador."""

    status: Literal["routed", "idle"] = "routed"
    encerrado: bool = False
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

    @model_validator(mode="before")
    @classmethod
    def normalize_category_in_destination(cls, value: Any) -> Any:
        """Corrige categoria de resposta usada indevidamente como destino."""
        if not isinstance(value, dict) or value.get("destino") != "resposta_pendente":
            return value
        normalized = dict(value)
        normalized["destino"] = "chamado"
        normalized.setdefault("categoria", "resposta_pendente")
        return normalized

    @field_validator("sinais", mode="before")
    @classmethod
    def normalize_signals(cls, value: Any) -> Any:
        """Preserva sinais textuais sem inferir impacto ou campos ausentes."""
        if value is None:
            return {}
        if isinstance(value, str):
            return {"resumo": value}
        return value

    @field_validator("relacionados", mode="before")
    @classmethod
    def normalize_related_events(cls, value: Any) -> Any:
        """Null representa ausência de relações, não um identificador."""
        return [] if value is None else value

    @field_validator("criticidade", mode="before")
    @classmethod
    def normalize_empty_criticality(cls, value: Any) -> Any:
        """Rotas sem prioridade podem chegar com string vazia do modelo."""
        return None if value == "" else value


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


def parse_batch_decisions(
    content: str, events: list[dict[str, Any]]
) -> list[OrchestratorDecision]:
    """Exige cobertura completa do lote antes de qualquer despacho."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    payload = json.loads(cleaned)
    if not isinstance(payload, dict) or not isinstance(payload.get("decisoes"), list):
        raise ValueError("Orquestrador deve retornar uma lista de decisoes")
    decisions = [
        OrchestratorDecision.model_validate(item) for item in payload["decisoes"]
    ]
    expected = {event["id"]: event["de"] for event in events}
    if len(decisions) != len(events) or {d.evento_id for d in decisions} != set(
        expected
    ):
        raise ValueError("Lote deve conter exatamente uma decisão por evento")
    for decision in decisions:
        if (
            decision.status != "routed"
            or decision.encerrado
            or decision.destino is None
            or decision.remetente != expected[decision.evento_id]
        ):
            raise ValueError("Decisão incompatível com evento recebido")
    return sorted(
        decisions,
        key=lambda d: (
            0 if d.destino == "seguranca" else 1,
            d.criticidade or "P4",
        ),
    )


def _classify_batch(
    graph,
    *,
    prompt: str,
    events: list[dict[str, Any]],
    on_summary: Callable[[str], None] | None,
) -> list[OrchestratorDecision]:
    """Classifica um lote e corrige uma resposta incompleta uma vez."""
    request = {
        "solicitacao": prompt,
        "eventos": events,
    }
    for attempt in range(2):
        state = graph.invoke(
            {
                "messages": [],
                "user_input": json.dumps(
                    request,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )
        try:
            return parse_batch_decisions(state["response"], events)
        except ValueError:
            if attempt == 1:
                raise
            request["correcao"] = (
                "A resposta anterior não cobriu exatamente todos os eventos. "
                "Retorne uma decisão para cada evento, sem omitir nenhum id."
            )
            if on_summary:
                on_summary("Contrato incompleto; solicitando correção do mesmo lote.")
    raise AssertionError("Tentativas de classificação esgotadas")


def run_orchestrator_loop(
    prompt: str,
    *,
    client: MCPToolProvider,
    model=None,
    max_events: int | None = None,
    on_result: Callable[[OrchestratorDecision | IncidentResult], None] | None = None,
    on_summary: Callable[[str], None] | None = None,
) -> list[OrchestratorDecision | IncidentResult]:
    """Coleta lotes de até cinco até encerrado; max_events limita ciclos de coleta."""
    if max_events is not None and max_events < 1:
        raise ValueError("max_events deve ser maior ou igual a 1")
    resolved_model = model or create_chat_model()
    tools = create_mcp_tools(
        client,
        agent_name="orquestrador",
        allowed_names=ORCHESTRATOR_TOOL_NAMES - {"proximo_evento", "listar_eventos"},
    )
    graph = build_graph(
        model=resolved_model,
        tools=tools,
        system_prompt=ORCHESTRATOR_BATCH_PROMPT,
        max_iterations=2,
    )
    results: list[OrchestratorDecision | IncidentResult] = []
    cycles = 0
    total = 0
    waiting = False
    while max_events is None or cycles < max_events:
        cycles += 1
        collection_error: EventBatchReadError | None = None
        try:
            events, closed = receive_event_batch(client)
        except EventBatchReadError as error:
            if not error.events:
                raise
            collection_error = error
            events, closed = error.events, False
            if on_summary:
                on_summary("Falha na coleta; processando eventos já recebidos.")
        if events:
            waiting = False
            total += len(events)
            if on_summary:
                on_summary(f"Lote: {len(events)} eventos; total recebido: {total}.")
            decisions = _classify_batch(
                graph,
                prompt=prompt,
                events=events,
                on_summary=on_summary,
            )
            for decision in decisions:
                results.append(decision)
                if on_result:
                    on_result(decision)
                if (
                    on_summary
                    and decision.destino == "incidente"
                    and decision.evento_id
                ):
                    on_summary(
                        f"Despachando {decision.evento_id} para "
                        "agente-incidente."
                    )
                try:
                    incident_result = dispatch_decision(
                        decision,
                        model=resolved_model,
                        client=client,
                    )
                except (RuntimeError, ValueError, httpx.HTTPError):
                    if decision.destino != "incidente" or decision.criticidade not in {
                        "P0",
                        "P1",
                        "P2",
                    }:
                        raise
                    incident_result = IncidentResult(
                        evento_id=decision.evento_id,
                        acao="falhou",
                        criticidade=decision.criticidade,
                        motivo="Falha no executor; revisão humana prioritária. "
                        "Consultar ações no MCP antes de repetir.",
                    )
                    if on_summary and decision.evento_id:
                        on_summary(
                            f"Executor agente-incidente falhou para "
                            f"{decision.evento_id}; revisão humana necessária."
                        )
                if incident_result:
                    results.append(incident_result)
                    if on_result:
                        on_result(incident_result)
        elif not closed and not waiting:
            waiting = True
            if on_summary:
                on_summary("Fila vazia; aguardando eventos no MCP.")
        if collection_error is not None and collection_error.code != 504:
            raise collection_error
        if collection_error is not None and on_summary:
            on_summary(
                "MCP retornou 504 em proximo_evento; "
                "continuando a escuta sem repetir a leitura automaticamente."
            )
        if closed:
            if on_summary:
                on_summary(f"MCP encerrado; {total} eventos recebidos.")
            break
    else:
        if on_summary:
            on_summary(f"Limite de ciclos atingido; {total} eventos recebidos.")
    return results
