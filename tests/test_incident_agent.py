import pytest
from langchain_core.messages import AIMessage

from n1_agents.incident_agent import (
    IncidentHandoff,
    IncidentResult,
    parse_incident_result,
    run_incident_agent,
)
from n1_agents.mcp_tools import INCIDENT_TOOL_NAMES, create_mcp_tools


def test_incident_handoff_accepts_only_incident_priorities() -> None:
    handoff = IncidentHandoff(
        evento_id="PED-029",
        remetente="ana@t4h.exemplo",
        destino="incidente",
        criticidade="P1",
        categoria="incidente_produto",
        produto="Portal do Cliente",
        motivo="Falha para muitos clientes.",
    )

    assert handoff.criticidade == "P1"


def test_incident_handoff_rejects_p3() -> None:
    with pytest.raises(ValueError):
        IncidentHandoff(
            evento_id="PED-017",
            remetente="ana@t4h.exemplo",
            destino="incidente",
            criticidade="P3",
            categoria="incidente_produto",
            produto="Portal do Cliente",
            motivo="Prioridade inválida.",
        )


def test_incident_result_is_parsed_as_structured_contract() -> None:
    result = parse_incident_result(
        '{"evento_id":"PED-029","acao":"aberto",'
        '"incidente_id":"INC-001","criticidade":"P0",'
        '"motivo":"Produto fora do ar para todos."}'
    )

    assert isinstance(result, IncidentResult)
    assert result.incidente_id == "INC-001"


class FakeMCP:
    def list_tools(self):
        return [
            {
                "name": name,
                "description": name,
                "inputSchema": {"type": "object", "properties": {}},
            }
            for name in INCIDENT_TOOL_NAMES | {"listar_eventos"}
        ]

    def call_tool(self, name, arguments):
        return {"content": [{"type": "text", "text": '{"status":"ok"}'}]}


def test_incident_agent_receives_only_executor_tools() -> None:
    tools = create_mcp_tools(
        FakeMCP(),
        agent_name="agente-incidente",
        allowed_names=INCIDENT_TOOL_NAMES,
    )

    assert {tool.name for tool in tools} == INCIDENT_TOOL_NAMES


class ActionMCP(FakeMCP):
    def __init__(self) -> None:
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {
            "content": [
                {
                    "type": "text",
                    "text": '{"status":"ok","incidentes":[]}',
                }
            ]
        }


class ActionModel:
    def __init__(self) -> None:
        self.calls = 0

    def bind_tools(self, tools):
        assert {tool.name for tool in tools} == INCIDENT_TOOL_NAMES
        return self

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "consultar",
                        "args": {},
                        "id": "call-consultar",
                    }
                ],
            )
        return AIMessage(
            content=(
                '{"evento_id":"PED-029","acao":"aberto",'
                '"incidente_id":"INC-001","criticidade":"P0",'
                '"motivo":"Incidente registrado e Produto avisado."}'
            )
        )


def test_incident_agent_executes_an_mcp_tool_before_returning() -> None:
    client = ActionMCP()
    handoff = IncidentHandoff(
        evento_id="PED-029",
        remetente="ana@t4h.exemplo",
        destino="incidente",
        criticidade="P0",
        categoria="incidente_produto",
        produto="Portal do Cliente",
        motivo="Produto fora do ar para todos.",
    )

    result = run_incident_agent(
        handoff,
        model=ActionModel(),
        client=client,
    )

    assert result.incidente_id == "INC-001"
    assert client.calls[0][0] == "consultar"
    assert client.calls[0][1]["agente"] == "agente-incidente"
