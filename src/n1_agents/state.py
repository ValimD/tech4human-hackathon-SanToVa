"""Contratos de estado compartilhados pelos nós do grafo."""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Estado mínimo e extensível de uma solicitação de suporte."""

    messages: list[Any]
    user_input: str
    intent: str
    queue: str
    response: str
    status: str
