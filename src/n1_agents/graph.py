"""Construção do grafo de suporte."""

from langgraph.graph import END, START, StateGraph

from .nodes.triage import triage_node
from .state import AgentState


def build_graph():
    """Monta e compila o grafo; dependências externas entram nos nós."""

    workflow = StateGraph(AgentState)
    workflow.add_node("triage", triage_node)
    workflow.add_edge(START, "triage")
    workflow.add_edge("triage", END)
    return workflow.compile()
