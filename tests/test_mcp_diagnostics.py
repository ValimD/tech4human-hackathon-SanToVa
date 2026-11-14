import json

from n1_agents.mcp_diagnostics import list_all_events


class FakeMCP:
    def __init__(self) -> None:
        self.offsets: list[int] = []

    def call_tool(self, name: str, arguments: dict) -> dict:
        assert name == "listar_eventos"
        self.offsets.append(arguments["offset"])
        events = (
            [{"id": "PED-001"}, {"id": "PED-002"}]
            if arguments["offset"] == 0
            else [{"id": "PED-003"}]
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "status": "ok",
                            "total": 3,
                            "eventos": events,
                            "tem_mais": arguments["offset"] == 0,
                        }
                    ),
                }
            ]
        }


def test_list_all_events_handles_mcp_pagination() -> None:
    client = FakeMCP()

    events = list_all_events(client, agent_name="orchestrator", page_size=2)

    assert [event["id"] for event in events] == [
        "PED-001",
        "PED-002",
        "PED-003",
    ]
    assert client.offsets == [0, 2]
