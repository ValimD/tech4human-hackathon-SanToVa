import json

import pytest
from langchain_core.messages import AIMessage

from n1_agents.event_processor import process_next_event


class FakeMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        if name == "proximo_evento":
            payload = {
                "status": "ok",
                "evento": {
                    "id": "PED-001",
                    "de": "ana@t4h.exemplo",
                    "assunto": "Acesso bloqueado",
                    "corpo": "Não consigo entrar no sistema.",
                },
            }
        else:
            payload = {"status": "ok"}
        return {"content": [{"type": "text", "text": json.dumps(payload)}]}


class FakeModel:
    def invoke(self, messages):
        return AIMessage(content="Vou verificar sua solicitação.")


def test_process_next_event_responds_to_the_received_email() -> None:
    mcp = FakeMCP()

    result = process_next_event(mcp, FakeModel(), agent_name="orchestrator")

    assert result == {
        "event_id": "PED-001",
        "response": "Vou verificar sua solicitação.",
    }
    assert mcp.calls[0] == (
        "proximo_evento",
        {"agente": "orchestrator", "esperar_segundos": 0},
    )
    assert mcp.calls[1] == (
        "responder_evento",
        {
            "agente": "orchestrator",
            "evento_id": "PED-001",
            "mensagem": "Vou verificar sua solicitação.",
            "aguardar_resposta": False,
        },
    )


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"evento": {}, "encerrado": False},
        {"evento": None, "encerrado": "true"},
    ],
)
def test_batch_rejects_invalid_mcp_response(response):
    from n1_agents.event_processor import receive_event_batch

    class Client:
        def call_tool(self, name, arguments):
            return response

    with pytest.raises(ValueError):
        receive_event_batch(Client())


class SequenceMCP:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def call_tool(self, name, arguments):
        self.calls += 1
        return {"content": [{"type": "text", "text": json.dumps(next(self.responses))}]}


def test_batch_retries_structured_503(monkeypatch):
    from n1_agents.event_processor import receive_event_batch

    monkeypatch.setattr("time.sleep", lambda _: None)
    client = SequenceMCP(
        [
            {"status": "erro", "codigo": 503},
            {"status": "ok", "evento": {"id": "PED-1", "de": "a@t4h.exemplo"}},
            {"evento": None},
        ]
    )
    events, closed = receive_event_batch(client)
    assert [event["id"] for event in events] == ["PED-1"]
    assert closed is False
    assert client.calls == 3


def test_batch_reports_code_and_preserves_collected_events():
    from n1_agents.event_processor import receive_event_batch

    client = SequenceMCP(
        [
            {"evento": {"id": "PED-1", "de": "a@t4h.exemplo"}},
            {"status": "erro", "codigo": 504, "mensagem": "conteúdo privado"},
        ]
    )
    with pytest.raises(RuntimeError, match="504") as caught:
        receive_event_batch(client)
    assert [event["id"] for event in caught.value.events] == ["PED-1"]
    assert "privado" not in str(caught.value)
    assert client.calls == 2


def test_batch_stops_after_three_structured_503_attempts(monkeypatch):
    from n1_agents.event_processor import receive_event_batch

    monkeypatch.setattr("time.sleep", lambda _: None)
    client = SequenceMCP([{"status": "erro", "codigo": 503}] * 3)
    with pytest.raises(RuntimeError, match="503"):
        receive_event_batch(client)
    assert client.calls == 3


def test_batch_recognizes_scenario_ended_code():
    from n1_agents.event_processor import receive_event_batch

    client = SequenceMCP([{"status": "erro", "codigo": 410}])
    assert receive_event_batch(client) == ([], True)
