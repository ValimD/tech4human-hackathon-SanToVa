"""Nó inicial de triagem do suporte N1."""

from ..state import AgentState

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "access": ("acesso", "login", "senha", "conta", "autenticação"),
    "performance": ("lento", "lentidão", "demora", "travando", "indisponível"),
}


def classify_intent(user_input: str) -> str:
    """Classifica uma solicitação com regras simples e substituíveis por um LLM."""

    normalized_input = user_input.casefold()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(keyword in normalized_input for keyword in keywords):
            return intent
    return "general"


def triage_node(state: AgentState) -> AgentState:
    """Enriquece o estado com a triagem inicial e uma resposta segura."""

    user_input = state.get("user_input", "").strip()
    if not user_input:
        raise ValueError("user_input não pode ser vazio")

    intent = classify_intent(user_input)
    return {
        "intent": intent,
        "queue": "n1",
        "response": "Sua solicitação foi recebida e encaminhada para o suporte N1.",
        "status": "triaged",
    }
