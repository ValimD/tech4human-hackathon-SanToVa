from n1_agents.mcp_tools import create_mcp_tools


class FakeMCP:
    def __init__(self) -> None:
        self.calls = []

    def list_tools(self):
        return [
            {
                "name": "listar_eventos",
                "description": "Lista eventos",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agente": {"type": "string"},
                        "limite": {"type": "integer"},
                    },
                    "required": ["agente"],
                },
            },
            {
                "name": "registrar",
                "description": "Não deve ser exposta ao orquestrador",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text": '{"status":"ok"}'}]}


def test_mcp_tool_injects_agent_name() -> None:
    client = FakeMCP()
    tool = create_mcp_tools(client, agent_name="orchestrator")[0]

    result = tool.invoke({"limite": 10})

    assert result == {"status": "ok"}
    assert client.calls == [
        ("listar_eventos", {"agente": "orchestrator", "limite": 10})
    ]


def test_mcp_tool_overrides_handoff_event_id() -> None:
    client = FakeMCP()
    client.list_tools = lambda: [
        {
            "name": "registrar",
            "description": "Registra incidente",
            "inputSchema": {
                "type": "object",
                "properties": {"evento_id": {"type": "string"}},
            },
        }
    ]
    tool = create_mcp_tools(
        client,
        agent_name="agente-incidente",
        allowed_names=frozenset({"registrar"}),
        fixed_arguments={"evento_id": "PED-005"},
    )[0]

    tool.invoke({"evento_id": "PED-029"})

    assert client.calls == [
        ("registrar", {"agente": "agente-incidente", "evento_id": "PED-005"})
    ]
