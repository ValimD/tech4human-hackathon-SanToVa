import json

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
