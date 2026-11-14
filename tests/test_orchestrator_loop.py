import pytest
from langchain_core.messages import AIMessage

from n1_agents.incident_agent import IncidentResult
from n1_agents.orchestrator_loop import (
    OrchestratorDecision,
    parse_orchestrator_decision,
    run_orchestrator_loop,
)


def test_orchestrator_decision_supports_incident_handoff() -> None:
    decision = parse_orchestrator_decision(
        '{"evento_id":"PED-029","remetente":"ana@t4h.exemplo",'
        '"destino":"incidente","criticidade":"P0",'
        '"categoria":"incidente_produto","produto":"Portal do Cliente",'
        '"motivo":"Produto fora do ar para todos."}'
    )

    assert isinstance(decision, OrchestratorDecision)
    assert decision.destino == "incidente"


def test_orchestrator_decision_supports_idle_state() -> None:
    decision = parse_orchestrator_decision(
        '{"status":"idle","evento_id":null,"destino":null,'
        '"motivo":"Nenhum evento disponível."}'
    )

    assert decision.status == "idle"
    assert decision.evento_id is None


def test_invalid_orchestrator_destination_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_orchestrator_decision(
            '{"evento_id":"PED-001","destino":"desconhecido",'
            '"motivo":"Destino inválido."}'
        )


def test_loop_dispatches_incident_and_stops_when_idle(monkeypatch) -> None:
    client = BatchClient(
        [
            {"evento": None},
            event(29),
            {"evento": None},
            {"evento": None, "encerrado": True},
        ]
    )

    dispatched = []
    emitted = []

    def fake_dispatch(decision, *, model, client):
        dispatched.append(decision.evento_id)
        return IncidentResult(
            evento_id=decision.evento_id,
            acao="aberto",
            incidente_id="INC-001",
            criticidade="P0",
            motivo="Incidente processado.",
        )

    monkeypatch.setattr(
        "n1_agents.orchestrator_loop.dispatch_decision",
        fake_dispatch,
    )
    results = run_orchestrator_loop(
        "Leia os eventos",
        client=client,
        model=BatchModel(),
        max_events=5,
        on_result=emitted.append,
    )

    assert dispatched == ["PED-29"]
    assert len(results) == 2
    assert [result.evento_id for result in emitted] == ["PED-29", "PED-29"]


class BatchClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def list_tools(self):
        return []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return next(self.responses)


def event(number):
    return {
        "evento": {
            "id": f"PED-{number}",
            "de": "ana@t4h.exemplo",
            "assunto": "Falha",
            "corpo": "Portal fora do ar",
        }
    }


class BatchModel:
    def __init__(self):
        self.batches = []

    def invoke(self, messages):
        import json

        payload = json.loads(messages[-1].content)
        self.batches.append(payload["eventos"])
        return AIMessage(
            content=json.dumps(
                {
                    "decisoes": [
                        {
                            "evento_id": item["id"],
                            "remetente": item["de"],
                            "destino": "incidente",
                            "criticidade": "P0",
                            "produto": "Portal do Cliente",
                            "motivo": "Produto fora do ar.",
                        }
                        for item in payload["eventos"]
                    ]
                }
            )
        )


def test_loop_batches_five_and_drains_partial_batch(monkeypatch):
    client = BatchClient(
        [
            {"evento": None},
            *[event(i) for i in range(7)],
            {"evento": None, "encerrado": True},
        ]
    )
    model = BatchModel()
    dispatched = []
    summaries = []

    def dispatch(decision, **kwargs):
        dispatched.append(decision.evento_id)
        return IncidentResult(
            evento_id=decision.evento_id,
            acao="aberto",
            incidente_id="INC-1",
            criticidade="P0",
            motivo="OK",
        )

    monkeypatch.setattr("n1_agents.orchestrator_loop.dispatch_decision", dispatch)
    results = run_orchestrator_loop(
        "Leia os eventos", client=client, model=model, on_summary=summaries.append
    )
    assert [len(batch) for batch in model.batches] == [5, 2]
    assert dispatched == [f"PED-{i}" for i in range(7)]
    assert len(results) == 14
    assert "encerrado" in summaries[-1].lower()
    assert any("agente-incidente" in summary for summary in summaries)
    assert all(args["agente"] == "orquestrador" for _, args in client.calls)
    assert client.calls[0][1]["esperar_segundos"] > 0
    assert client.calls[2][1]["esperar_segundos"] == 0


def test_loop_processes_event_before_honoring_mcp_shutdown(monkeypatch):
    client = BatchClient(
        [
            {
                "evento": event(1)["evento"],
                "encerrado": True,
            },
            {"evento": None, "encerrado": True},
        ]
    )
    dispatched = []
    summaries = []

    monkeypatch.setattr(
        "n1_agents.orchestrator_loop.dispatch_decision",
        lambda decision, **kwargs: dispatched.append(decision.evento_id),
    )

    results = run_orchestrator_loop(
        "Leia os eventos",
        client=client,
        model=BatchModel(),
        on_summary=summaries.append,
    )

    assert dispatched == ["PED-1"]
    assert [result.evento_id for result in results] == ["PED-1"]
    assert any("encerrado" in summary.lower() for summary in summaries)
    assert len(client.calls) == 2


def test_missing_decision_rejected_before_dispatch():
    class MissingModel:
        def invoke(self, messages):
            return AIMessage(content='{"decisoes": []}')

    client = BatchClient([event(1), {"evento": None, "encerrado": True}])
    with pytest.raises(ValueError, match="exatamente uma decisão"):
        run_orchestrator_loop("Leia", client=client, model=MissingModel())


def test_empty_queue_never_calls_model():
    client = BatchClient([{"evento": None}, {"evento": None, "encerrado": True}])
    model = BatchModel()
    assert run_orchestrator_loop("Leia", client=client, model=model) == []
    assert model.batches == []


def test_mcp_error_is_not_treated_as_idle():
    client = BatchClient([{"status": "erro", "codigo": 500}])
    with pytest.raises(RuntimeError, match="MCP"):
        run_orchestrator_loop("Leia", client=client, model=BatchModel())


def test_executor_failure_does_not_drop_remaining_events(monkeypatch):
    client = BatchClient([event(1), event(2), {"evento": None, "encerrado": True}])
    dispatched = []

    def dispatch(decision, **kwargs):
        dispatched.append(decision.evento_id)
        if len(dispatched) == 1:
            raise RuntimeError("falha com conteúdo privado")
        return IncidentResult(
            evento_id=decision.evento_id, acao="aberto", criticidade="P0", motivo="OK"
        )

    monkeypatch.setattr("n1_agents.orchestrator_loop.dispatch_decision", dispatch)
    results = run_orchestrator_loop("Leia", client=client, model=BatchModel())
    assert dispatched == ["PED-1", "PED-2"]
    assert results[1].acao == "falhou"
    assert "privado" not in results[1].motivo


@pytest.mark.parametrize("change", ["duplicate", "sender", "idle", "destination"])
def test_batch_rejects_incompatible_decisions(change):
    import json

    from n1_agents.orchestrator_loop import parse_batch_decisions

    decisions = [
        dict(
            evento_id=f"PED-{i}",
            remetente="ana@t4h.exemplo",
            destino="chamado",
            motivo="Triagem",
        )
        for i in range(2)
    ]
    if change == "duplicate":
        decisions[1]["evento_id"] = "PED-0"
    elif change == "sender":
        decisions[0]["remetente"] = "outro@t4h.exemplo"
    elif change == "idle":
        decisions[0]["status"] = "idle"
    else:
        decisions[0]["destino"] = None
    with pytest.raises(ValueError):
        parse_batch_decisions(
            json.dumps({"decisoes": decisions}), [event(i)["evento"] for i in range(2)]
        )


def test_max_events_bounds_empty_polling():
    client = BatchClient([{"evento": None}] * 2)
    assert (
        run_orchestrator_loop("Leia", client=client, model=BatchModel(), max_events=2)
        == []
    )
    assert len(client.calls) == 2


@pytest.mark.parametrize("priority", ["P0", "P1", "P2"])
def test_dispatch_sends_all_incident_priorities(priority, monkeypatch):
    from n1_agents.orchestrator_loop import dispatch_decision

    received = []
    monkeypatch.setattr(
        "n1_agents.orchestrator_loop.run_incident_agent",
        lambda handoff, **kwargs: received.append(handoff),
    )
    decision = OrchestratorDecision(
        evento_id="PED-1",
        remetente="ana@t4h.exemplo",
        destino="incidente",
        criticidade=priority,
        produto="Portal do Cliente",
        motivo="Falha",
    )
    dispatch_decision(decision, model=object(), client=BatchClient([]))
    assert received[0].criticidade == priority
    assert received[0].evento_id == "PED-1"


@pytest.mark.parametrize("destination", ["chamado", "ferias", "seguranca"])
def test_unimplemented_destinations_do_not_execute(destination):
    from n1_agents.orchestrator_loop import dispatch_decision

    decision = OrchestratorDecision(destino=destination, motivo="Revisão humana")
    assert dispatch_decision(decision, model=None, client=BatchClient([])) is None


def test_loop_dispatches_partial_batch_before_reporting_collection_error(monkeypatch):
    client = BatchClient([event(1), {"status": "erro", "codigo": 504}])
    dispatched = []
    monkeypatch.setattr(
        "n1_agents.orchestrator_loop.dispatch_decision",
        lambda decision, **kwargs: dispatched.append(decision.evento_id),
    )
    with pytest.raises(RuntimeError, match="504"):
        run_orchestrator_loop("Leia", client=client, model=BatchModel())
    assert dispatched == ["PED-1"]


@pytest.mark.parametrize(
    "signals, expected",
    [
        ("falha parcial com contorno", {"resumo": "falha parcial com contorno"}),
        (None, {}),
        (
            {"escopo": "todos", "tem_contorno": False},
            {"escopo": "todos", "tem_contorno": False},
        ),
    ],
)
def test_decision_normalizes_optional_model_fields(signals, expected):
    decision = OrchestratorDecision.model_validate(
        {
            "motivo": "Triagem",
            "sinais": signals,
            "relacionados": None,
        }
    )
    assert decision.sinais == expected
    assert decision.relacionados == []


def test_decision_normalizes_empty_criticidade_for_non_incident_routes():
    decision = OrchestratorDecision.model_validate(
        {
            "destino": "chamado",
            "criticidade": "",
            "motivo": "Dúvida de catálogo.",
        }
    )

    assert decision.criticidade is None


@pytest.mark.parametrize(
    "field, value",
    [
        ("sinais", ["falha"]),
        ("sinais", 42),
        ("relacionados", "PED-1"),
        ("relacionados", [42]),
        ("destino", "inventado"),
        ("criticidade", "P9"),
    ],
)
def test_decision_still_rejects_invalid_types_and_routing(field, value):
    with pytest.raises(ValueError):
        OrchestratorDecision.model_validate({"motivo": "Triagem", field: value})


def test_loop_normalizes_model_output_before_incident_handoff(monkeypatch):
    import json

    class NonCanonicalModel:
        def invoke(self, messages):
            return AIMessage(
                content=json.dumps(
                    {
                        "decisoes": [
                            {
                                "evento_id": "PED-1",
                                "remetente": "ana@t4h.exemplo",
                                "destino": "incidente",
                                "criticidade": "P2",
                                "produto": "Portal do Cliente",
                                "motivo": "Falha parcial",
                                "sinais": "contorno disponível",
                                "relacionados": None,
                            }
                        ]
                    }
                )
            )

    handoffs = []
    monkeypatch.setattr(
        "n1_agents.orchestrator_loop.run_incident_agent",
        lambda handoff, **kwargs: handoffs.append(handoff),
    )
    client = BatchClient([event(1), {"evento": None, "encerrado": True}])
    results = run_orchestrator_loop("Leia", client=client, model=NonCanonicalModel())
    assert len(results) == 1
    assert handoffs[0].sinais == {"resumo": "contorno disponível"}
    assert handoffs[0].relacionados == []
