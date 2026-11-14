"""Construção do grafo de suporte."""

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .model import create_chat_model
from .nodes.orchestrator import make_orchestrator_node
from .prompts import ORCHESTRATOR_SYSTEM_PROMPT
from .state import AgentState


def _next_step(state: AgentState, max_iterations: int) -> str:
    last_message = state.get("messages", [])[-1]
    if (
        getattr(last_message, "tool_calls", None)
        and state.get("iterations", 0) < max_iterations
    ):
        return "tools"
    return END


def build_graph(model=None, tools=None, system_prompt=None, max_iterations=2):
    """Monta o grafo com resposta direta e execução opcional de tools."""

    if max_iterations < 1:
        raise ValueError("max_iterations deve ser maior ou igual a 1")
    workflow = StateGraph(AgentState)
    final_model = None
    if tools:
        base_model = model if model is not None else create_chat_model()
        if not hasattr(base_model, "bind_tools"):
            raise TypeError("O modelo precisa suportar bind_tools para usar tools")
        resolved_model = base_model.bind_tools(tools)
        try:
            final_model = base_model.bind_tools(tools, tool_choice="none")
        except TypeError:
            final_model = None
        workflow.add_node("tools", ToolNode(tools))
    else:
        resolved_model = model if model is not None else create_chat_model()

    orchestrator = make_orchestrator_node(
        resolved_model,
        system_prompt=system_prompt or ORCHESTRATOR_SYSTEM_PROMPT,
        max_iterations=max_iterations,
        final_model=final_model,
    )
    workflow.add_node("orchestrator", orchestrator)
    workflow.add_edge(START, "orchestrator")
    if tools:
        workflow.add_conditional_edges(
            "orchestrator",
            lambda state: _next_step(state, max_iterations),
            {"tools": "tools", END: END},
        )
        workflow.add_edge("tools", "orchestrator")
    else:
        workflow.add_edge("orchestrator", END)
    return workflow.compile()
