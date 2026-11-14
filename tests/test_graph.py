from langchain_core.messages import AIMessage

from n1_agents.graph import build_graph
from n1_agents.nodes.orchestrator import make_orchestrator_node


class FakeChatModel:
    def invoke(self, messages):
        return AIMessage(content=f"Resposta para: {messages[-1].content}")


def test_orchestrator_responds_to_a_user_prompt() -> None:
    graph = build_graph(model=FakeChatModel())

    result = graph.invoke(
        {
            "messages": [],
            "user_input": "Explique o que é suporte N1",
        }
    )

    assert result["response"] == "Resposta para: Explique o que é suporte N1"
    assert result["status"] == "answered"


def test_orchestrator_rejects_an_empty_prompt() -> None:
    graph = build_graph(model=FakeChatModel())

    try:
        graph.invoke({"messages": [], "user_input": " "})
    except ValueError as error:
        assert str(error) == "user_input não pode ser vazio"
    else:
        raise AssertionError("O orquestrador deveria rejeitar um prompt vazio")


def test_orchestrator_rejects_an_empty_model_response() -> None:
    class EmptyModel:
        def invoke(self, messages):
            return AIMessage(content="")

    node = make_orchestrator_node(EmptyModel())

    try:
        node({"messages": [], "user_input": "Olá"})
    except ValueError as error:
        assert str(error) == "O modelo retornou uma resposta vazia ou inválida"
    else:
        raise AssertionError("O orquestrador deveria rejeitar uma resposta vazia")
