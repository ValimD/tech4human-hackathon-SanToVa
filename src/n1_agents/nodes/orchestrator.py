"""Agente orquestrador inicial."""

from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import ORCHESTRATOR_SYSTEM_PROMPT
from ..state import AgentState


class ChatModel(Protocol):
    """Contrato mínimo necessário para um modelo conversacional."""

    def invoke(self, messages: list[Any]) -> Any:
        """Gera uma resposta para as mensagens recebidas."""


def make_orchestrator_node(
    model: ChatModel,
    *,
    system_prompt: str = ORCHESTRATOR_SYSTEM_PROMPT,
    max_iterations: int = 2,
    final_model: ChatModel | None = None,
):
    """Cria um nó que responde ou solicita ferramentas ao modelo."""

    def orchestrator_node(state: AgentState) -> AgentState:
        user_input = state.get("user_input", "").strip()
        if not user_input:
            raise ValueError("user_input não pode ser vazio")

        iteration = state.get("iterations", 0) + 1
        messages = list(state.get("messages", []))
        if not messages:
            messages.append(HumanMessage(content=user_input))
        active_model = (
            final_model
            if final_model is not None and iteration >= max_iterations
            else model
        )
        result = active_model.invoke(
            [SystemMessage(content=system_prompt), *messages]
        )
        updates: AgentState = {"messages": [result], "iterations": iteration}
        if getattr(result, "tool_calls", None):
            if iteration >= max_iterations:
                updates.update(
                    {
                        "response": (
                            "Execução interrompida após atingir o limite "
                            "de iterações do agente."
                        ),
                        "status": "stopped",
                    }
                )
                return updates
            updates["status"] = "tool_calling"
            return updates

        response = getattr(result, "content", None)
        if isinstance(response, list):
            response = "".join(
                item.get("text", "")
                for item in response
                if isinstance(item, dict)
            )
        if not isinstance(response, str) or not response.strip():
            raise ValueError("O modelo retornou uma resposta vazia ou inválida")

        updates.update({"response": response, "status": "answered"})
        if not state.get("messages"):
            updates["messages"] = [HumanMessage(content=user_input), result]
        return updates

    return orchestrator_node
