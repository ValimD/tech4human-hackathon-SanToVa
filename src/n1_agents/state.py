"""Contratos de estado compartilhados pelos nós do grafo."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Estado mínimo e extensível de uma solicitação de suporte."""

    messages: Annotated[list[Any], add_messages]
    user_input: str
    intent: str
    queue: str
    response: str
    status: str
    iterations: int
