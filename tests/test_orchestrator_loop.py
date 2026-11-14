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
    class FakeClient:
        def list_tools(self):
            return []

    class FakeModel:
        def __init__(self):
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                content = (
                    '{"evento_id":"PED-029","remetente":"ana@t4h.exemplo",'
                    '"destino":"incidente","criticidade":"P0",'
                    '"categoria":"incidente_produto",'
                    '"produto":"Portal do Cliente",'
                    '"motivo":"Produto fora do ar."}'
                )
            else:
                content = (
                    '{"status":"idle","evento_id":null,"destino":null,'
                    '"motivo":"Nenhum evento disponível."}'
                )
            return AIMessage(content=content)

    dispatched = []

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
        client=FakeClient(),
        model=FakeModel(),
        max_events=5,
    )

    assert dispatched == ["PED-029"]
    assert len(results) == 2
