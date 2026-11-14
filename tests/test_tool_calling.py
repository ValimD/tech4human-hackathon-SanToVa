from langchain_core.messages import AIMessage

from n1_agents.graph import build_graph


class FakeToolModel:
    def __init__(self) -> None:
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "fake_lookup",
                        "args": {"query": "eventos"},
                        "id": "call-1",
                    }
                ],
            )
        return AIMessage(content="Encontrei os eventos solicitados.")


def test_graph_executes_requested_tool_before_final_response() -> None:
    model = FakeToolModel()

    def fake_lookup(query: str) -> str:
        """Busca dados de teste."""

        return f"Resultado para {query}"

    graph = build_graph(model=model, tools=[fake_lookup])

    result = graph.invoke(
        {
            "messages": [],
            "user_input": "Liste os eventos",
        }
    )

    assert result["response"] == "Encontrei os eventos solicitados."
    assert result["status"] == "answered"


def test_graph_stops_when_model_keeps_requesting_tools() -> None:
    class LoopingModel(FakeToolModel):
        def invoke(self, messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "fake_lookup",
                        "args": {"query": "eventos"},
                        "id": f"call-{self.calls}",
                    }
                ],
            )

    def fake_lookup(query: str) -> str:
        """Busca dados de teste."""

        return f"Resultado para {query}"

    graph = build_graph(
        model=LoopingModel(),
        tools=[fake_lookup],
        max_iterations=2,
    )

    result = graph.invoke(
        {
            "messages": [],
            "user_input": "Liste os eventos",
        }
    )

    assert result["status"] == "stopped"
    assert "limite" in result["response"].lower()


def test_last_iteration_forces_a_final_response_without_tools() -> None:
    class FinalResponseModel(FakeToolModel):
        def bind_tools(self, tools, **kwargs):
            tool_choice = kwargs.get("tool_choice")
            parent = self

            class BoundModel:
                def invoke(self, messages):
                    if tool_choice == "none":
                        return AIMessage(content="Resposta final após a consulta.")
                    parent.calls += 1
                    return AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "fake_lookup",
                                "args": {"query": "eventos"},
                                "id": "call-1",
                            }
                        ],
                    )

            return BoundModel()

    def fake_lookup(query: str) -> str:
        """Busca dados de teste."""

        return f"Resultado para {query}"

    graph = build_graph(
        model=FinalResponseModel(),
        tools=[fake_lookup],
        max_iterations=2,
    )

    result = graph.invoke({"messages": [], "user_input": "Leia os eventos"})

    assert result["status"] == "answered"
    assert result["response"] == "Resposta final após a consulta."
